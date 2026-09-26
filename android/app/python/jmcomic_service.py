from __future__ import annotations

import base64
import hashlib
import json
import os
import queue
import re
import secrets
import shutil
import threading
import traceback
import urllib.parse
import urllib.request
import zipfile
from functools import partial
from pathlib import Path
from typing import Any

from android_webp import install_webp_support


_EVENTS: queue.Queue[dict[str, Any]] = queue.Queue()
_CONFIG: dict[str, Any] = {}
_SESSION: dict[str, str] = {}
_SESSION_USERNAME = ""
_CANCEL_EVENT = threading.Event()
_DOWNLOAD_LOCK = threading.Lock()
_JM_IMPORT_ERROR: BaseException | None = None

try:
    import yaml
    import jmcomic
    from jmcomic import JmDownloader, JmModuleConfig
    from jmcomic.jm_task_context import jm_task_context
    from jmcomic.jm_toolkit import JmImageTool, JmcomicText
except BaseException as exc:
    _JM_IMPORT_ERROR = exc
    yaml = None
    jmcomic = None
    JmDownloader = None
    JmModuleConfig = None
    jm_task_context = None
    JmImageTool = None
    JmcomicText = None


SEPARATOR = "─" * 44


def _emit(kind: str, **payload: Any) -> None:
    event = {"kind": kind}
    event.update(payload)
    _EVENTS.put(event)


def _ok(data: Any = None, **extra: Any) -> str:
    result = {"ok": True, "data": data}
    result.update(extra)
    return json.dumps(result, ensure_ascii=False, default=str)


def _error(message: str, code: str = "error") -> str:
    return json.dumps(
        {"ok": False, "code": code, "error": message},
        ensure_ascii=False,
    )


def _require_jmcomic() -> None:
    if _JM_IMPORT_ERROR is not None or jmcomic is None:
        detail = (
            str(_JM_IMPORT_ERROR)
            or _JM_IMPORT_ERROR.__class__.__name__
            if _JM_IMPORT_ERROR
            else "unknown import error"
        )
        raise RuntimeError(f"jmcomic 导入失败：{detail}")


def _safe_text(value: Any, default: str = "未知") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _join_values(values: Any) -> str:
    if values is None:
        return "未知"
    if isinstance(values, str):
        return _safe_text(values)
    items = [str(value).strip() for value in values if str(value).strip()]
    return ", ".join(items) if items else "未知"


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


def _setting(name: str, default: Any = None) -> Any:
    value = _CONFIG.get(name, default)
    return default if value is None else value


def _paths(config: dict[str, Any]) -> None:
    data_dir = Path(str(config.get("data_dir") or "")).expanduser()
    download_dir = Path(str(config.get("download_dir") or "")).expanduser()
    if not str(data_dir):
        raise ValueError("Android 数据目录为空。")
    if not str(download_dir):
        raise ValueError("Android 下载目录为空。")
    data_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    (data_dir / "updates").mkdir(parents=True, exist_ok=True)
    config["data_dir"] = str(data_dir)
    config["download_dir"] = str(download_dir)
    config["settings_path"] = str(data_dir / "settings.json")
    config["session_path"] = str(data_dir / "session.bin")
    config["session_key_path"] = str(data_dir / "session.key")
    config["update_dir"] = str(data_dir / "updates")


def initialize(config_json: str) -> str:
    try:
        config = json.loads(config_json or "{}")
        if not isinstance(config, dict):
            raise ValueError("配置必须是 JSON 对象。")
        _paths(config)
        _CONFIG.clear()
        _CONFIG.update(config)
        _load_session()
        _require_jmcomic()
        if JmImageTool is not None:
            install_webp_support(JmImageTool)
        if JmModuleConfig is not None:
            JmModuleConfig.AFIELD_ADVICE["jm_id"] = (
                lambda album: f"JM{album.album_id}"
            )
        return _ok(
            {
                "data_dir": _CONFIG["data_dir"],
                "download_dir": _CONFIG["download_dir"],
                "session_active": bool(_SESSION),
                "session_username": _SESSION_USERNAME,
                "core_version": str(getattr(jmcomic, "__version__", "unknown")),
            }
        )
    except BaseException as exc:
        return _error(_message(exc), "initialize")


def _message(exc: BaseException) -> str:
    text = str(exc).strip()
    return text or exc.__class__.__name__


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _prune_empty_directories(root: Path) -> bool:
    if not root.exists() or not root.is_dir():
        return False
    removed = False
    for path in sorted(
        root.rglob("*"),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        if not path.is_dir():
            continue
        try:
            path.rmdir()
            removed = True
        except OSError:
            pass
    try:
        root.rmdir()
        removed = True
    except OSError:
        pass
    return removed


def _load_or_create_key() -> bytes:
    path = Path(str(_CONFIG.get("session_key_path") or ""))
    try:
        key = path.read_bytes()
        if len(key) == 32:
            return key
    except OSError:
        pass
    key = secrets.token_bytes(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(key)
    os.replace(temporary, path)
    return key


def _encrypt_session(payload: bytes) -> bytes:
    try:
        from Crypto.Cipher import AES

        cipher = AES.new(
            _load_or_create_key(),
            AES.MODE_GCM,
            nonce=secrets.token_bytes(12),
        )
        ciphertext, tag = cipher.encrypt_and_digest(payload)
        return b"JMA1" + cipher.nonce + tag + ciphertext
    except BaseException:
        return b"JMB1" + base64.b64encode(payload)


def _decrypt_session(payload: bytes) -> bytes:
    if payload.startswith(b"JMA1"):
        from Crypto.Cipher import AES

        body = payload[4:]
        if len(body) < 28:
            raise ValueError("会话文件损坏。")
        nonce, tag, ciphertext = body[:12], body[12:28], body[28:]
        cipher = AES.new(_load_or_create_key(), AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)
    if payload.startswith(b"JMB1"):
        return base64.b64decode(payload[4:])
    raise ValueError("未知会话格式。")


def _load_session() -> None:
    global _SESSION, _SESSION_USERNAME
    _SESSION = {}
    _SESSION_USERNAME = ""
    path = Path(str(_CONFIG.get("session_path") or ""))
    try:
        raw = path.read_bytes()
        payload = json.loads(_decrypt_session(raw).decode("utf-8"))
        cookies = payload.get("cookies")
        if isinstance(cookies, dict):
            _SESSION = {
                str(key): str(value)
                for key, value in cookies.items()
                if str(key)
            }
            _SESSION_USERNAME = str(payload.get("username") or "")
    except (OSError, ValueError, TypeError, KeyError):
        _SESSION = {}
        _SESSION_USERNAME = ""


def _save_session(persist: bool) -> None:
    path = Path(str(_CONFIG.get("session_path") or ""))
    if not persist:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        return
    payload = json.dumps(
        {
            "version": 1,
            "username": _SESSION_USERNAME,
            "cookies": _SESSION,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(_encrypt_session(payload))
    os.replace(temporary, path)


def _parse_input(raw_text: str) -> tuple[str, str]:
    text = str(raw_text or "").strip()
    if not text:
        raise ValueError("请输入作品车号、章节车号或禁漫链接。")
    _require_jmcomic()
    if len(text) >= 2 and text[0].lower() == "p":
        return "photo", JmcomicText.parse_to_jm_id(text[1:].strip())
    lower = text.lower()
    if "/photo/" in lower or "/photos/" in lower:
        return "photo", JmcomicText.parse_to_jm_id(text)
    return "album", JmcomicText.parse_to_jm_id(text)


def _proxy_config() -> Any:
    mode = str(_CONFIG.get("proxy_mode") or "system")
    if mode == "none":
        return None
    if mode == "manual":
        address = str(_CONFIG.get("proxy") or "").strip()
        if not address:
            raise ValueError("已选择手动代理，但代理地址为空。")
        if "://" not in address:
            address = "http://" + address
        return {"http": address, "https": address}
    # Android network/VPN settings are applied below the Python socket layer.
    return None


def _build_option(config: dict[str, Any], pack_zip: bool, use_session: bool = True):
    _require_jmcomic()
    naming = str(config.get("naming") or "id")
    if naming not in ("id", "title"):
        naming = "id"
    folder = Path(str(config.get("folder") or "")).expanduser()
    if not str(folder):
        raise ValueError("请选择下载目录。")
    folder.mkdir(parents=True, exist_ok=True)

    dir_rule = (
        "Bd / Ajm_id / Pindextitle"
        if naming == "id"
        else "Bd / Atitle / Pindextitle"
    )
    image_suffix = config.get("image_suffix")
    if image_suffix in ("", "None", "null"):
        image_suffix = ".png"
    if image_suffix == ".webp":
        image_suffix = ".png"
    if image_suffix not in (None, ".jpg", ".png", ".webp"):
        image_suffix = None

    option_dict: dict[str, Any] = {
        "log": False,
        "dir_rule": {
            "base_dir": str(folder),
            "rule": dir_rule,
        },
        "download": {
            "cache": True,
            "image": {
                "decode": True,
                "suffix": image_suffix,
            },
            "threading": {
                "image": max(1, min(int(config.get("image_threads") or 10), 50)),
                "photo": max(1, min(int(config.get("chapter_threads") or 4), 64)),
            },
        },
        "client": {
            "impl": str(config.get("client") or "api"),
            "retry_times": 5,
            "postman": {
                "meta_data": {
                    "timeout": 30,
                    "proxies": _proxy_config(),
                }
            },
        },
    }
    if pack_zip:
        option_dict["plugins"] = {
            "after_album": [
                {
                    "plugin": "zip",
                    "kwargs": {
                        "zip_dir": str(folder),
                        "filename_rule": (
                            "JM{Aid}" if naming == "id" else "{Atitle}"
                        ),
                        "suffix": "zip",
                        "level": "album",
                        "delete_original_file": bool(
                            config.get("delete_after_zip", True)
                        ),
                    },
                }
            ]
        }

    option_text = yaml.safe_dump(
        option_dict,
        allow_unicode=True,
        sort_keys=False,
    )
    option = jmcomic.create_option_by_str(option_text)
    if use_session and _SESSION:
        option.update_cookies(_SESSION)
    return option


def _album_payload(album: Any, query_text: str, focus_photo_id: str = "") -> dict[str, Any]:
    episodes = []
    for item in album.episode_list:
        photo_id, photo_index, photo_name = item
        episodes.append(
            {
                "id": str(photo_id),
                "index": int(photo_index),
                "name": str(photo_name),
                "label": f"第{int(photo_index)}话  {photo_name}  (ID: {photo_id})",
            }
        )
    duplicate = {str(item["id"]) for item in episodes}
    if focus_photo_id and focus_photo_id not in duplicate:
        episodes.append(
            {
                "id": focus_photo_id,
                "index": 1,
                "name": "重点章节",
                "label": f"章节  (ID: {focus_photo_id})",
            }
        )
    return {
        "album_id": str(album.album_id),
        "name": str(album.name or ""),
        "link": JmcomicText.format_album_url(album.album_id),
        "authors": _json_safe(album.authors),
        "pub_date": _safe_text(album.pub_date),
        "update_date": _safe_text(album.update_date),
        "page_count": int(album.page_count or 0),
        "views": _safe_text(album.views),
        "likes": _safe_text(album.likes),
        "comment_count": _safe_text(album.comment_count, "0"),
        "tags": _json_safe(album.tags),
        "actors": _json_safe(album.actors),
        "works": _json_safe(album.works),
        "description": str(album.description or ""),
        "episodes": episodes,
        "focus_photo_id": focus_photo_id,
        "query_text": query_text,
        "detail_text": _format_detail_text(
            album,
            query_text,
            episodes,
        ),
    }


def _format_detail_text(
    album: Any,
    query_text: str,
    episodes: list[dict[str, Any]],
) -> str:
    lines = [
        f"🔍 正在查询 禁漫车号 - [{query_text}] 的详情...",
        SEPARATOR,
        f"📖 标题:  {album.name}",
        f"🆔 ID:    JM{album.album_id}",
        f"🔗 链接:  {JmcomicText.format_album_url(album.album_id)}",
        f"✍️ 作者:  {_join_values(album.authors)}",
        SEPARATOR,
        f"📅 发布日期:  {album.pub_date or '未知'}",
        f"📅 更新日期:  {album.update_date or '未知'}",
        f"📄 总页数:    {album.page_count}",
        f"👀 观看:      {album.views or '未知'}",
        f"❤️ 点赞:     {album.likes or '未知'}",
        f"💬 评论:      {album.comment_count}",
        SEPARATOR,
        f"🏷️ 标签:  {_join_values(album.tags)}",
        f"🎭 人物:  {_join_values(album.actors)}",
        f"📚 作品:  {_join_values(album.works)}",
    ]
    if album.description:
        lines.append(f"📝 简介:  {album.description}")
    lines.extend([SEPARATOR, f"📑 章节 ({len(episodes)}):"])
    for item in episodes:
        lines.append(f"    {item['label']}")
    lines.extend([SEPARATOR, "查询完成，请选择章节范围。"])
    return "\n".join(lines)


def query_album(query_text: str, config_json: str) -> str:
    try:
        config = json.loads(config_json or "{}")
        _CONFIG.update(config)
        _require_jmcomic()
        query_type, jm_id = _parse_input(query_text)
        _emit("log", message=f"🔍 正在查询 禁漫车号 - [{query_text}] 的详情...")
        option = _build_option(_CONFIG, pack_zip=False)
        client = option.build_jm_client()
        focus_photo_id = ""
        if query_type == "photo":
            photo = client.get_photo_detail(jm_id)
            focus_photo_id = str(photo.photo_id)
            album = photo.from_album or client.get_album_detail(photo.album_id)
        else:
            album = client.get_album_detail(jm_id)
        payload = _album_payload(album, query_text, focus_photo_id)
        _emit(
            "detail",
            album_id=payload["album_id"],
            title=payload["name"],
            episode_count=len(payload["episodes"]),
        )
        return _ok(payload)
    except BaseException as exc:
        _emit("log", message=f"查询失败：{_message(exc)}")
        return _error(_message(exc), "query")


_BaseDownloader = JmDownloader or object


class AndroidDownloader(_BaseDownloader):
    def __init__(self, option, photo_range: tuple[int, int]):
        super().__init__(option)
        self.photo_range = photo_range
        self.completed_images = 0
        self.total_images = 0
        self.export_filepaths: list[str] = []
        self._progress_lock = threading.Lock()

    def do_filter(self, detail):
        if detail.is_album():
            start, end = self.photo_range
            return detail[start:end]
        return detail

    def before_album(self, album) -> None:
        super().before_album(album)
        start, end = self.photo_range
        selected_count = max(min(end, len(album)) - start, 0)
        self.total_images = 0
        self.completed_images = 0
        _emit(
            "album",
            title=str(album.name or ""),
            author=_join_values(album.authors),
            selected_count=selected_count,
            total_images=self.total_images,
            total_chapters=len(album),
        )

    def before_photo(self, photo) -> None:
        super().before_photo(photo)
        with self._progress_lock:
            self.total_images += max(len(photo), 0)
        _emit(
            "chapter",
            chapter_name=str(photo.name or ""),
            chapter_index=int(photo.index),
            chapter_count=(
                len(photo.from_album)
                if photo.from_album is not None
                else 1
            ),
            image_count=len(photo),
        )

    def after_image(self, image, img_save_path) -> None:
        if _CANCEL_EVENT.is_set():
            raise RuntimeError("用户已取消下载。")
        super().after_image(image, img_save_path)
        with self._progress_lock:
            self.completed_images += 1
            completed = self.completed_images
            total = self.total_images
        _emit("progress", completed=completed, total=total)

    def record_export_filepath(self, detail, filepath: str) -> None:
        super().record_export_filepath(detail, filepath)
        self.export_filepaths.append(str(filepath))
        _emit("export", path=str(filepath))


def start_download(config_json: str) -> str:
    try:
        config = json.loads(config_json or "{}")
        _CONFIG.update(config)
        _require_jmcomic()
        if not _DOWNLOAD_LOCK.acquire(blocking=False):
            return _error("已有下载任务正在运行。", "busy")
        try:
            album_id = str(config.get("album_id") or "").strip()
            if not album_id:
                raise ValueError("缺少作品 ID。")
            start = max(int(config.get("start_index") or 0), 0)
            end = max(int(config.get("end_index") or (start + 1)), start + 1)
            selected_count = max(int(config.get("selected_count") or 0), 0)
            if selected_count <= 0:
                selected_count = end - start
            pack_zip = bool(config.get("pack_zip", True)) and selected_count > 1
            _CANCEL_EVENT.clear()
            _emit(
                "log",
                message=(
                    f"开始任务：JM{album_id}，章节 {start + 1} 到 {end}，"
                    f"共 {selected_count} 话"
                ),
            )
            if pack_zip:
                _emit("log", message="下载完成后按当前命名方式打包为 ZIP。")
            option = _build_option(_CONFIG, pack_zip=pack_zip)
            downloader_factory = partial(
                AndroidDownloader,
                photo_range=(start, end),
            )
            with jm_task_context(download_type="album", jm_id=album_id):
                result = jmcomic.download_album(
                    album_id,
                    option,
                    downloader_factory,
                )
            downloader = result.downloader
            if (
                pack_zip
                and bool(_CONFIG.get("delete_after_zip", True))
                and downloader.export_filepaths
            ):
                album_root = Path(
                    option.dir_rule.decide_album_root_dir(result.detail)
                )
                try:
                    if _prune_empty_directories(album_root):
                        _emit("cleaned", path=str(album_root))
                except BaseException:
                    pass
            payload = {
                "album_id": album_id,
                "zip_paths": downloader.export_filepaths,
                "folder": str(config.get("folder") or ""),
                "images": int(downloader.completed_images),
                "pack_zip": pack_zip,
            }
            _record_history(payload, result.detail)
            _emit("done", success=True, data=payload)
            return _ok(payload)
        finally:
            _DOWNLOAD_LOCK.release()
    except BaseException as exc:
        _emit("error", message=_message(exc))
        _emit("done", success=False, error=_message(exc))
        return _error(_message(exc), "download")


def _record_history(payload: dict[str, Any], detail: Any) -> None:
    path = Path(str(_CONFIG.get("data_dir") or "")) / "download-history.json"
    history = _read_json(path, [])
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "album_id": payload.get("album_id"),
            "title": str(getattr(detail, "name", "") or ""),
            "folder": payload.get("folder"),
            "zip_paths": payload.get("zip_paths") or [],
            "images": payload.get("images") or 0,
            "created_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }
    )
    _write_json(path, history[-200:])


def cancel_download() -> str:
    _CANCEL_EVENT.set()
    return _ok({"cancelled": True})


def login(username: str, password: str, persist: bool, config_json: str) -> str:
    try:
        global _SESSION_USERNAME
        config = json.loads(config_json or "{}")
        _CONFIG.update(config)
        _require_jmcomic()
        username = str(username or "").strip()
        if not username:
            raise ValueError("请输入账号。")
        if not password:
            raise ValueError("请输入密码。")
        option = _build_option(_CONFIG, pack_zip=False, use_session=False)
        client = option.build_jm_client()
        client.login(username, password)
        cookies = {
            str(key): str(value)
            for key, value in dict(client["cookies"]).items()
        }
        if not cookies:
            raise RuntimeError("登录成功，但服务器没有返回会话。")
        _SESSION.clear()
        _SESSION.update(cookies)
        _SESSION_USERNAME = username
        _save_session(bool(persist))
        _emit("login", active=True, username=username, cookie_count=len(cookies))
        return _ok(
            {
                "active": True,
                "username": username,
                "cookie_count": len(cookies),
                "persisted": bool(persist),
            }
        )
    except BaseException as exc:
        _emit("login", active=False)
        return _error(_message(exc), "login")


def logout() -> str:
    global _SESSION_USERNAME
    _SESSION.clear()
    _SESSION_USERNAME = ""
    try:
        path = Path(str(_CONFIG.get("session_path") or ""))
        path.unlink(missing_ok=True)
        key_path = Path(str(_CONFIG.get("session_key_path") or ""))
        key_path.unlink(missing_ok=True)
    except OSError:
        pass
    _emit("login", active=False)
    return _ok({"active": False})


def get_state() -> str:
    return _ok(
        {
            "session_active": bool(_SESSION),
            "session_username": _SESSION_USERNAME,
            "download_running": _DOWNLOAD_LOCK.locked(),
            "core_version": str(
                getattr(jmcomic, "__version__", "unknown")
            ),
        }
    )


def poll_events() -> str:
    events: list[dict[str, Any]] = []
    while len(events) < 300:
        try:
            events.append(_EVENTS.get_nowait())
        except queue.Empty:
            break
    return json.dumps(events, ensure_ascii=False, default=str)


def _version_key(value: str) -> tuple[tuple[int, int | str], ...]:
    parts: list[tuple[int, int | str]] = []
    for part in re.split(r"[._-]", str(value).strip().lstrip("vV")):
        if part.isdigit():
            parts.append((1, int(part)))
        elif part:
            parts.append((0, part.lower()))
    return tuple(parts)


def _copy_update(
    source: Any,
    target: Path,
    expected_hash: str,
    expected_size: int,
) -> str:
    hasher = hashlib.sha256()
    downloaded = 0
    with target.open("wb") as handle:
        while True:
            chunk = source.read(128 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            hasher.update(chunk)
            downloaded += len(chunk)
    actual_hash = hasher.hexdigest().lower()
    if expected_hash and actual_hash != expected_hash:
        raise ValueError("更新包 SHA-256 校验失败。")
    if expected_size and downloaded != expected_size:
        raise ValueError("更新包大小与清单不一致。")
    return actual_hash


def check_update(config_json: str) -> str:
    try:
        config = json.loads(config_json or "{}")
        _CONFIG.update(config)
        source_url = str(config.get("update_manifest_url") or "").strip()
        if not source_url:
            return _ok(
                {
                    "update_available": False,
                    "message": "尚未配置更新清单地址。",
                }
            )
        proxy = _proxy_config()
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler(proxy) if proxy else urllib.request.ProxyHandler({})
        )
        _emit("update", message="正在检查更新...")
        request = urllib.request.Request(
            source_url,
            headers={
                "User-Agent": "JMComicAndroid/1.0.1",
                "Accept": "application/json, application/octet-stream, */*",
            },
        )
        with opener.open(request, timeout=30) as response:
            manifest_bytes = response.read(4 * 1024 * 1024 + 1)
        if len(manifest_bytes) > 4 * 1024 * 1024:
            raise ValueError("更新清单超过 4 MB。")
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("更新清单根节点必须是对象。")
        version = str(manifest.get("version") or "").strip()
        url = str(manifest.get("url") or "").strip()
        expected_hash = str(manifest.get("sha256") or "").strip().lower()
        if not version or not url:
            raise ValueError("更新清单缺少 version 或 url。")
        if not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
            raise ValueError("更新清单的 sha256 无效。")
        expected_size = max(int(manifest.get("size") or 0), 0)
        current = str(config.get("current_version") or "1.0.1")
        if _version_key(version) <= _version_key(current):
            _emit("update", message=f"当前已是最新版本 v{current}。")
            return _ok(
                {
                    "update_available": False,
                    "message": f"当前已是最新版本 v{current}。",
                    "version": version,
                }
            )
        update_dir = Path(str(_CONFIG.get("update_dir") or ""))
        update_dir.mkdir(parents=True, exist_ok=True)
        target = update_dir / f"JMComic-Android-{version}.apk"
        partial = target.with_suffix(".apk.part")
        if not urllib.parse.urlparse(url).scheme:
            url = urllib.parse.urljoin(source_url, url)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "JMComicAndroid/1.0.1"},
        )
        _emit("update", message=f"正在下载 v{version} 更新包...")
        try:
            with opener.open(request, timeout=60) as response:
                actual_hash = _copy_update(
                    response,
                    partial,
                    expected_hash,
                    expected_size,
                )
            os.replace(partial, target)
        except BaseException:
            partial.unlink(missing_ok=True)
            raise
        _emit("update", message=f"更新包 v{version} 已校验完成。")
        return _ok(
            {
                "update_available": True,
                "version": version,
                "path": str(target),
                "sha256": actual_hash,
                "notes": str(manifest.get("notes") or ""),
            }
        )
    except BaseException as exc:
        _emit("update", message=f"检查更新失败：{_message(exc)}")
        return _error(_message(exc), "update")


def import_self_test() -> str:
    return _ok(
        {
            "jmcomic_imported": _JM_IMPORT_ERROR is None,
            "jmcomic_error": _message(_JM_IMPORT_ERROR)
            if _JM_IMPORT_ERROR
            else "",
            "version": str(getattr(jmcomic, "__version__", "unknown")),
        }
    )
