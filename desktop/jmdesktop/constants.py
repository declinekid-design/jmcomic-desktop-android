from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "JMComic Desktop"
APP_VERSION = "1.5.0"
BROWSE_URL = "https://comic18j-hbd.space/"


def _runtime_dir() -> Path:
    override = os.getenv("JMCOMIC_DESKTOP_RUNTIME_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


RUNTIME_DIR = _runtime_dir()
APP_DIR = Path(
    os.getenv("JMCOMIC_DESKTOP_HOME", str(RUNTIME_DIR / "data"))
).expanduser().resolve()
SETTINGS_PATH = APP_DIR / "settings.json"
SESSION_PATH = APP_DIR / "session.bin"
LOG_DIR = APP_DIR / "logs"
UPDATE_DIR = APP_DIR / "updates"
UPDATE_DOWNLOAD_DIR = UPDATE_DIR / "downloads"
UPDATE_STAGING_DIR = UPDATE_DIR / "staging"
UPDATE_BACKUP_DIR = UPDATE_DIR / "backups"
UPDATE_HELPER_NAME = "JMComicDesktopUpdater.exe"
UPDATE_HELPER_DIR = RUNTIME_DIR / "updater"
UPDATE_HELPER_PATH = UPDATE_HELPER_DIR / UPDATE_HELPER_NAME
DEFAULT_DOWNLOAD_DIR = RUNTIME_DIR / "downloads"
DEFAULT_UPDATE_MANIFEST_URL = os.getenv(
    "JMCOMIC_DESKTOP_UPDATE_URL", ""
).strip()

CLIENT_LABELS = {
    "APP 接口": "api",
    "网页接口": "html",
}
CLIENT_LABEL_BY_VALUE = {value: label for label, value in CLIENT_LABELS.items()}

PROXY_LABELS = {
    "跟随系统": "system",
    "不使用代理": "none",
    "手动输入": "manual",
}
PROXY_LABEL_BY_VALUE = {value: label for label, value in PROXY_LABELS.items()}

IMAGE_SUFFIX_LABELS = {
    "保持原格式": None,
    "JPG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
}

THEME_LABELS = {
    "跟随系统": "system",
    "浅色主题": "light",
    "深色主题": "dark",
}
THEME_LABEL_BY_VALUE = {value: label for label, value in THEME_LABELS.items()}

NAMING_LABELS = {
    "按车号命名": "id",
    "按漫画名命名": "title",
}
NAMING_LABEL_BY_VALUE = {value: label for label, value in NAMING_LABELS.items()}
DIR_RULES = {
    "id": "Bd / Ajm_id / Pindextitle",
    "title": "Bd / Atitle / Pindextitle",
}
ZIP_FILENAME_RULES = {
    "id": "JM{Aid}",
    "title": "{Atitle}",
}
NAMING_HINTS = {
    "id": "作品保存为 保存目录/JM车号/章节，例如 JM123456/第01话；多话 ZIP 内直接包含各话文件夹。",
    "title": "作品保存为 保存目录/漫画名/章节，名称中的非法字符会自动处理。多话作品会打包为同名 ZIP。",
}


def default_download_dir() -> Path:
    return DEFAULT_DOWNLOAD_DIR
