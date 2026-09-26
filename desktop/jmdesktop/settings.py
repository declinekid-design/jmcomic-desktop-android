from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from .constants import (
    APP_DIR,
    DEFAULT_UPDATE_MANIFEST_URL,
    SETTINGS_PATH,
    UPDATE_BACKUP_DIR,
    UPDATE_DOWNLOAD_DIR,
    UPDATE_STAGING_DIR,
    default_download_dir,
)


def ensure_app_dirs() -> None:
    for path in (
        APP_DIR,
        APP_DIR / "logs",
        UPDATE_DOWNLOAD_DIR,
        UPDATE_STAGING_DIR,
        UPDATE_BACKUP_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def default_settings() -> dict[str, Any]:
    return {
        "folder": str(default_download_dir()),
        "client": "api",
        "image_threads": 10,
        "chapter_threads": min(os.cpu_count() or 4, 8),
        "proxy_mode": "system",
        "proxy": "",
        "image_suffix": None,
        "naming": "id",
        "pack_zip": True,
        "delete_after_zip": True,
        "theme": "system",
        "open_folder": False,
        "geometry": "",
        "update_manifest_url": DEFAULT_UPDATE_MANIFEST_URL,
        "auto_check_update": True,
    }


def load_settings() -> dict[str, Any]:
    defaults = default_settings()
    ensure_app_dirs()
    try:
        saved = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return defaults

    if isinstance(saved, dict):
        defaults.update(saved)
    return defaults


def save_settings(settings: dict[str, Any]) -> None:
    try:
        ensure_app_dirs()
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=APP_DIR,
            prefix="settings-",
            suffix=".tmp",
            delete=False,
        ) as handle:
            json.dump(settings, handle, ensure_ascii=False, indent=2)
            temp_path = handle.name
        os.replace(temp_path, SETTINGS_PATH)
    except OSError:
        pass


def write_startup_error(message: str) -> None:
    try:
        ensure_app_dirs()
        (APP_DIR / "startup-error.log").write_text(message, encoding="utf-8")
    except OSError:
        pass
