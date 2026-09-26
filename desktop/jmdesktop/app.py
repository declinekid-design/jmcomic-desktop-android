from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from types import SimpleNamespace

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication, QMessageBox

from .constants import (
    APP_DIR,
    APP_VERSION,
    BROWSE_URL,
    RUNTIME_DIR,
    UPDATE_HELPER_PATH,
)
from .browser import run_browser_smoke_test
from .details import format_album_plain
from .downloader import DesktopDownloader
from .jm_bridge import _IMPORT_ERROR, core_version
from .session import dpapi_roundtrip
from .settings import write_startup_error
from .theme import apply_theme
from .update_manager import is_newer, parse_manifest
from .window import JMComicDesktopWindow


def smoke_test() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    window = JMComicDesktopWindow(show_window=False)
    QTimer.singleShot(100, app.quit)
    result = app.exec()
    window.close()
    return result


def self_test() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="self-test-", dir=APP_DIR) as temp_dir:
            window = JMComicDesktopWindow(show_window=False)
            window.folder_input.setText(temp_dir)
            checks = {
                "album_id": window._parse_jm_input("JM123") == ("album", "123"),
                "photo_id": window._parse_jm_input("p456") == ("photo", "456"),
                "album_link": window._parse_jm_input(
                    "https://18comic.vip/album/789/"
                )
                == ("album", "789"),
                "theme_options": set(
                    window.theme_combo.itemText(i)
                    for i in range(window.theme_combo.count())
                )
                == {"跟随系统", "浅色主题", "深色主题"},
                "naming_options": set(
                    window.naming_combo.itemText(i)
                    for i in range(window.naming_combo.count())
                )
                == {"按车号命名", "按漫画名命名"},
                "start_disabled_before_query": not window.start_button.isEnabled(),
                "chapter_range_controls": (
                    window.chapter_start_combo.count() == 0
                    and window.chapter_end_combo.count() == 0
                ),
                "login_controls": hasattr(window, "login_button")
                and hasattr(window, "logout_button"),
                "update_controls": hasattr(window, "update_button")
                and hasattr(window, "update_source_input"),
                "browse_controls": hasattr(window, "browse_button")
                and BROWSE_URL == "https://comic18j-hbd.space/",
                "portable_data_dir": (
                    APP_DIR == (RUNTIME_DIR / "data")
                    or bool(os.getenv("JMCOMIC_DESKTOP_HOME"))
                )
                and "AppData" not in str(APP_DIR),
                "session_encryption": dpapi_roundtrip(
                    b"JMComicDesktop-session-check"
                ),
                "update_version_compare": (
                    is_newer("1.5.1", "1.5.0")
                    and not is_newer("1.5.0", "1.5.0")
                ),
            }
            manifest = parse_manifest(
                json.dumps(
                    {
                        "version": "1.5.1",
                        "url": "https://example.com/update.zip",
                        "sha256": "0" * 64,
                        "size": 123,
                    }
                )
            )
            checks["update_manifest"] = (
                manifest.version == "1.5.1"
                and manifest.sha256 == "0" * 64
            )
            checks["bundled_updater"] = (
                not getattr(sys, "frozen", False)
                or UPDATE_HELPER_PATH.exists()
            )

            resolved_dark = apply_theme(app, "dark")
            checks["dark_theme_applies"] = (
                resolved_dark == "dark"
                and app.palette()
                .color(QPalette.ColorRole.WindowText)
                .lightness()
                > 180
            )
            resolved_light = apply_theme(app, "light")
            checks["light_theme_applies"] = (
                resolved_light == "light"
                and app.palette()
                .color(QPalette.ColorRole.WindowText)
                .lightness()
                < 80
            )
            apply_theme(app, window.current_theme)

            window.naming_combo.setCurrentText("按车号命名")
            id_option = window._build_option()
            checks["id_dir_rule"] = (
                id_option.dir_rule.rule_dsl == "Bd / Ajm_id / Pindextitle"
            )
            id_zip_plugins = window._build_option(pack_zip=True).deconstruct()[
                "plugins"
            ]
            checks["id_zip_rule"] = (
                id_zip_plugins["after_album"][0]["kwargs"]["filename_rule"]
                == "JM{Aid}"
            )

            window.naming_combo.setCurrentText("按漫画名命名")
            title_option = window._build_option()
            checks["title_dir_rule"] = (
                title_option.dir_rule.rule_dsl == "Bd / Atitle / Pindextitle"
            )
            title_zip_plugins = window._build_option(pack_zip=True).deconstruct()[
                "plugins"
            ]
            checks["title_zip_rule"] = (
                title_zip_plugins["after_album"][0]["kwargs"]["filename_rule"]
                == "{Atitle}"
            )
            checks["option_built"] = id_option is not None and title_option is not None

            fake_album = SimpleNamespace(
                album_id="350234",
                name="测试作品",
                authors=["Author1", "Author2"],
                pub_date="2022-06-15",
                update_date="2023-01-01",
                page_count=50,
                views="2M",
                likes="77K",
                comment_count=9801,
                tags=["标签1", "标签2"],
                actors=["角色A"],
                works=["作品1"],
                description="测试简介",
                episode_list=[
                    ("350234", "1", "上"),
                    ("350235", "2", "下"),
                ],
            )
            detail_text = format_album_plain(fake_album, "350234")
            checks["detail_format"] = (
                "📑 章节 (2):" in detail_text
                and "第2话  下" in detail_text
                and "JM350234" in detail_text
            )
            window.events.put(("detail", fake_album, None, "350234"))
            window._drain_events()
            checks["chapter_population"] = (
                window.chapter_start_combo.count() == 2
                and window.chapter_end_combo.count() == 2
                and window.start_button.isEnabled()
            )
            checks["default_chapter_range"] = (
                window._selected_chapter_range() == (0, 2, 2)
            )

            range_downloader = object.__new__(DesktopDownloader)
            range_downloader.photo_range = (1, 3)

            class FakeDetail:
                def is_album(self):
                    return True

                def __getitem__(self, item):
                    return ["话1", "话2", "话3"][item]

            fake_detail = FakeDetail()
            checks["chapter_filter"] = (
                range_downloader.do_filter(fake_detail) == ["话2", "话3"]
            )
            window.close()

            result = {
                "ok": all(checks.values()),
                "checks": checks,
                "core_version": core_version(),
                "app_version": APP_VERSION,
            }
            (APP_DIR / "self-test.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return 0 if result["ok"] else 1
    except BaseException as exc:
        (APP_DIR / "self-test.json").write_text(
            json.dumps(
                {
                    "ok": False,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return 1


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    apply_theme(app, "system")

    if _IMPORT_ERROR is not None:
        write_startup_error(f"核心模块加载失败：\n{_IMPORT_ERROR}")
        if "--smoke-test" in sys.argv:
            return 3
        QMessageBox.critical(None, "启动失败", f"核心模块加载失败：\n{_IMPORT_ERROR}")
        return 1

    if "--smoke-test" in sys.argv:
        return smoke_test()
    if "--browser-smoke-test" in sys.argv:
        return run_browser_smoke_test(app)
    if "--self-test" in sys.argv:
        return self_test()

    window = JMComicDesktopWindow()
    return app.exec()
