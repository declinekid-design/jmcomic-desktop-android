from __future__ import annotations

import argparse
import ctypes
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath


HELPER_NAME = "JMComicDesktopUpdater.exe"
MAIN_EXE_NAME = "JMComicDesktop.exe"
PROTECTED_NAMES = {"data", "downloads", "updater"}
PROTECTED_NAMES_LOWER = {name.lower() for name in PROTECTED_NAMES}
PRESERVED_NAMES = {"预览图", "更新文件"}


class UpdateError(RuntimeError):
    pass


def _log(target: Path, message: str) -> None:
    try:
        log_dir = target / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "updater.log").open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(
                f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n"
            )
    except OSError:
        pass


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _validate_entry(name: str, mode: int = 0) -> None:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    parts = path.parts
    if not parts:
        return
    if path.is_absolute() or ".." in parts:
        raise UpdateError(f"更新包包含非法路径：{name}")
    if parts[0].lower() in {"data", "downloads", "updater"}:
        raise UpdateError(f"更新包不得覆盖用户目录：{name}")
    if len(parts[0]) >= 2 and parts[0][1] == ":":
        raise UpdateError(f"更新包包含绝对路径：{name}")
    if stat.S_ISLNK(mode):
        raise UpdateError(f"更新包包含符号链接：{name}")


def _is_kept(name: str) -> bool:
    return (
        name.lower() in PROTECTED_NAMES_LOWER
        or name in PRESERVED_NAMES
    )


def validate_package(package: Path, expected_sha256: str) -> None:
    if not package.is_file():
        raise UpdateError(f"更新包不存在：{package}")
    if expected_sha256 and _sha256(package) != expected_sha256.lower():
        raise UpdateError("更新包 SHA-256 校验失败。")
    try:
        with zipfile.ZipFile(package) as archive:
            for info in archive.infolist():
                _validate_entry(
                    info.filename,
                    (info.external_attr >> 16) & 0xFFFF,
                )
            if not archive.namelist():
                raise UpdateError("更新包为空。")
    except (OSError, zipfile.BadZipFile) as exc:
        raise UpdateError(f"更新包不是有效的 ZIP：{exc}") from exc


def extract_package(package: Path, staging: Path) -> None:
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    with zipfile.ZipFile(package) as archive:
        for info in archive.infolist():
            _validate_entry(
                info.filename,
                (info.external_attr >> 16) & 0xFFFF,
            )
        archive.extractall(staging)


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


def _replace_program(target: Path, staging: Path) -> Path:
    backup_root = (
        target
        / "data"
        / "updates"
        / "backups"
        / f"backup-{time.strftime('%Y%m%d-%H%M%S')}"
    )
    backup_root.mkdir(parents=True, exist_ok=False)
    moved: list[str] = []

    try:
        for item in list(target.iterdir()):
            if _is_kept(item.name):
                continue
            shutil.move(str(item), str(backup_root / item.name))
            moved.append(item.name)

        for item in list(staging.iterdir()):
            if item.name.lower() in PROTECTED_NAMES_LOWER:
                raise UpdateError(f"更新包不得覆盖用户目录：{item.name}")
            if item.name in PRESERVED_NAMES:
                continue
            shutil.move(str(item), str(target / item.name))
    except BaseException:
        for item in list(target.iterdir()):
            if _is_kept(item.name):
                continue
            _remove_path(item)
        for name in moved:
            old = backup_root / name
            if old.exists():
                shutil.move(str(old), str(target / name))
        raise

    try:
        shutil.rmtree(backup_root)
    except OSError:
        pass
    return backup_root


def apply_update(
    package: Path,
    target: Path,
    expected_sha256: str,
    restart: bool,
) -> None:
    target = target.resolve()
    package = package.resolve()
    if not (target / MAIN_EXE_NAME).exists():
        raise UpdateError(f"目标目录缺少 {MAIN_EXE_NAME}。")

    _log(target, f"start package={package} target={target}")
    validate_package(package, expected_sha256)
    staging = (
        target
        / "data"
        / "updates"
        / "staging"
        / f"apply-{os.getpid()}"
    )
    extract_package(package, staging)
    _replace_program(target, staging)
    shutil.rmtree(staging, ignore_errors=True)
    _log(target, "update applied")

    if restart:
        subprocess.Popen(
            [str(target / MAIN_EXE_NAME)],
            cwd=str(target),
            close_fds=True,
        )


def _wait_for_process(process_id: int, timeout: int = 180) -> None:
    if process_id <= 0 or os.name != "nt":
        return
    synchronize = 0x00100000
    wait_object_0 = 0x00000000
    wait_timeout = 0x00000102
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(synchronize, False, process_id)
    if not handle:
        return
    try:
        result = kernel32.WaitForSingleObject(handle, timeout * 1000)
        if result == wait_timeout:
            raise UpdateError("等待主程序退出超时。")
        if result != wait_object_0:
            raise UpdateError("等待主程序退出失败。")
    finally:
        kernel32.CloseHandle(handle)


def _run_self_test() -> int:
    try:
        with tempfile.TemporaryDirectory(prefix="jm-updater-test-") as temp:
            root = Path(temp)
            target = root / "target"
            target.mkdir()
            (target / MAIN_EXE_NAME).write_text("old-main", encoding="utf-8")
            (target / "_internal").mkdir()
            (target / "_internal" / "old.txt").write_text(
                "old",
                encoding="utf-8",
            )
            (target / "data").mkdir()
            (target / "data" / "settings.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (target / "downloads").mkdir()
            (target / "downloads" / "keep.txt").write_text(
                "keep",
                encoding="utf-8",
            )
            (target / "预览图").mkdir()
            (target / "预览图" / "keep.png").write_text(
                "keep",
                encoding="utf-8",
            )
            (target / "更新文件").mkdir()
            (target / "更新文件" / "keep.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (target / "使用说明.txt").write_text(
                "old-doc",
                encoding="utf-8",
            )

            package = root / "update.zip"
            with zipfile.ZipFile(
                package,
                "w",
                compression=zipfile.ZIP_DEFLATED,
            ) as archive:
                archive.writestr(MAIN_EXE_NAME, "new-main")
                archive.writestr("_internal/new.txt", "new")
                archive.writestr("使用说明.txt", "new-doc")

            apply_update(
                package,
                target,
                _sha256(package),
                restart=False,
            )
            checks = {
                "main": (target / MAIN_EXE_NAME).read_text(
                    encoding="utf-8"
                )
                == "new-main",
                "internal": (target / "_internal" / "new.txt").read_text(
                    encoding="utf-8"
                )
                == "new",
                "data_preserved": (target / "data" / "settings.json").exists(),
                "downloads_preserved": (
                    target / "downloads" / "keep.txt"
                ).exists(),
                "preview_preserved": (
                    target / "预览图" / "keep.png"
                ).exists(),
                "update_files_preserved": (
                    target / "更新文件" / "keep.json"
                ).exists(),
                "documentation_updated": (
                    target / "使用说明.txt"
                ).read_text(encoding="utf-8")
                == "new-doc",
            }

            unsafe = root / "unsafe.zip"
            with zipfile.ZipFile(unsafe, "w") as archive:
                archive.writestr("../escape.txt", "bad")
            try:
                validate_package(unsafe, _sha256(unsafe))
            except UpdateError:
                checks["path_traversal_rejected"] = True
            else:
                checks["path_traversal_rejected"] = False

            return 0 if all(checks.values()) else 1
    except BaseException:
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--package")
    parser.add_argument("--target")
    parser.add_argument("--sha256", default="")
    parser.add_argument("--pid", type=int, default=0)
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return _run_self_test()
    if not args.apply or not args.package or not args.target:
        return 2

    target = Path(args.target)
    try:
        _wait_for_process(args.pid)
        apply_update(
            Path(args.package),
            target,
            args.sha256,
            args.restart,
        )
        return 0
    except BaseException as exc:
        _log(target, f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
