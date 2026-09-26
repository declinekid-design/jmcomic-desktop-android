from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .constants import (
    APP_VERSION,
    UPDATE_DOWNLOAD_DIR,
    UPDATE_HELPER_PATH,
)


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    url: str
    sha256: str
    size: int
    notes: str
    source: str


def version_key(version: str) -> tuple[tuple[int, int | str], ...]:
    parts: list[tuple[int, int | str]] = []
    for part in re.split(r"[._-]", str(version).strip().lstrip("vV")):
        if part.isdigit():
            parts.append((1, int(part)))
        elif part:
            parts.append((0, part.lower()))
    return tuple(parts)


def is_newer(candidate: str, current: str = APP_VERSION) -> bool:
    return version_key(candidate) > version_key(current)


def _source_path(source: str) -> Path | None:
    if source.lower().startswith("file://"):
        return Path(urllib.parse.unquote(urllib.request.url2pathname(source[7:])))
    if "://" not in source:
        return Path(source).expanduser()
    return None


def _opener(proxies: dict[str, str] | None):
    if proxies is None:
        return urllib.request.build_opener()
    return urllib.request.build_opener(urllib.request.ProxyHandler(proxies))


def _open_source(source: str, proxies: dict[str, str] | None):
    local_path = _source_path(source)
    if local_path is not None:
        return local_path.open("rb")
    request = urllib.request.Request(
        source,
        headers={
            "User-Agent": f"JMComicDesktop/{APP_VERSION}",
            "Accept": "application/json, application/octet-stream, */*",
        },
    )
    return _opener(proxies).open(request, timeout=30)


def parse_manifest(payload: bytes | str, source: str = "") -> UpdateInfo:
    try:
        data: Any = json.loads(
            payload.decode("utf-8") if isinstance(payload, bytes) else payload
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise UpdateError("更新清单不是有效的 UTF-8 JSON。") from exc
    if not isinstance(data, dict):
        raise UpdateError("更新清单根节点必须是对象。")

    version = str(data.get("version") or "").strip()
    url = str(data.get("url") or "").strip()
    sha256 = str(data.get("sha256") or "").strip().lower()
    if not version:
        raise UpdateError("更新清单缺少 version。")
    if not url:
        raise UpdateError("更新清单缺少 url。")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise UpdateError("更新清单的 sha256 无效。")

    if source and not urllib.parse.urlparse(url).scheme:
        local_path = _source_path(source)
        if local_path is not None:
            url = str((local_path.parent / url).resolve())
        else:
            url = urllib.parse.urljoin(source, url)

    try:
        size = max(int(data.get("size") or 0), 0)
    except (TypeError, ValueError):
        size = 0
    return UpdateInfo(
        version=version,
        url=url,
        sha256=sha256,
        size=size,
        notes=str(data.get("notes") or "").strip(),
        source=source,
    )


def load_manifest(
    source: str,
    proxies: dict[str, str] | None = None,
) -> UpdateInfo:
    source = source.strip()
    if not source:
        raise UpdateError("尚未配置更新清单地址。")
    try:
        with _open_source(source, proxies) as response:
            payload = response.read(4 * 1024 * 1024 + 1)
    except OSError as exc:
        raise UpdateError(f"无法读取更新清单：{exc}") from exc
    if len(payload) > 4 * 1024 * 1024:
        raise UpdateError("更新清单超过 4 MB，已拒绝。")
    return parse_manifest(payload, source)


def _copy_stream(
    response,
    target,
    total: int,
    progress: Callable[[int, int], None] | None,
) -> str:
    hasher = hashlib.sha256()
    downloaded = 0
    while True:
        chunk = response.read(128 * 1024)
        if not chunk:
            break
        target.write(chunk)
        hasher.update(chunk)
        downloaded += len(chunk)
        if progress is not None:
            progress(downloaded, total)
    return hasher.hexdigest()


def download_update(
    info: UpdateInfo,
    proxies: dict[str, str] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> Path:
    UPDATE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    destination = UPDATE_DOWNLOAD_DIR / f"JMComicDesktop-{info.version}-win64.zip"
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        with _open_source(info.url, proxies) as response:
            try:
                total = int(response.headers.get("Content-Length") or info.size)
            except (AttributeError, TypeError, ValueError):
                total = info.size
            if info.size:
                total = info.size
            with partial.open("wb") as handle:
                actual_hash = _copy_stream(response, handle, total, progress)
        if actual_hash.lower() != info.sha256:
            raise UpdateError("更新包 SHA-256 校验失败。")
        if info.size and partial.stat().st_size != info.size:
            raise UpdateError("更新包大小与清单不一致。")
        os.replace(partial, destination)
        return destination
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def launch_updater(
    package_path: Path,
    sha256: str,
    restart: bool = True,
) -> None:
    if not UPDATE_HELPER_PATH.exists():
        raise UpdateError("缺少更新器 JMComicDesktopUpdater.exe。")
    if not package_path.exists():
        raise UpdateError("更新包不存在。")
    command = [
        str(UPDATE_HELPER_PATH),
        "--apply",
        "--package",
        str(package_path),
        "--target",
        str(UPDATE_HELPER_PATH.parent.parent),
        "--pid",
        str(os.getpid()),
        "--sha256",
        sha256,
    ]
    if restart:
        command.append("--restart")
    creation_flags = 0
    if os.name == "nt":
        creation_flags = (
            subprocess.CREATE_DETACHED
            | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    try:
        subprocess.Popen(
            command,
            cwd=str(UPDATE_HELPER_PATH.parent),
            close_fds=True,
            creationflags=creation_flags,
        )
    except OSError as exc:
        raise UpdateError(f"无法启动更新器：{exc}") from exc
