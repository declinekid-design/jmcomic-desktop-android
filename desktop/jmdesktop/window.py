from __future__ import annotations

import logging
import os
import queue
import threading
import traceback
from functools import partial
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices, QFont, QIcon, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStyle,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .constants import (
    APP_DIR,
    APP_NAME,
    APP_VERSION,
    BROWSE_URL,
    CLIENT_LABEL_BY_VALUE,
    CLIENT_LABELS,
    DIR_RULES,
    IMAGE_SUFFIX_LABELS,
    LOG_DIR,
    NAMING_HINTS,
    NAMING_LABEL_BY_VALUE,
    NAMING_LABELS,
    PROXY_LABEL_BY_VALUE,
    PROXY_LABELS,
    THEME_LABEL_BY_VALUE,
    THEME_LABELS,
    ZIP_FILENAME_RULES,
    default_download_dir,
)
from .details import (
    chapter_label,
    format_album_html,
    format_album_plain,
    query_error_html,
    query_pending_html,
)
from .downloader import DesktopDownloader
from .jm_bridge import JmcomicText, core_version, jm_logger, jm_task_context, jmcomic, yaml
from .login import LoginDialog
from .logging_utils import QueueLogHandler
from .session import clear_session, load_session, save_session
from .settings import load_settings, save_settings
from .theme import apply_theme
from .update_manager import (
    UpdateError,
    UpdateInfo,
    download_update,
    is_newer,
    launch_updater,
    load_manifest,
)
from .widgets import SettingField


def asset_path(name: str) -> Path:
    import sys

    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / "assets" / name


class JMComicDesktopWindow(QMainWindow):
    def __init__(self, show_window: bool = True):
        super().__init__()
        self.app = QApplication.instance() or QApplication([])
        self.events: queue.Queue = queue.Queue()
        self.running = False
        self.querying = False
        self.update_checking = False
        self.update_downloading = False
        self.update_info: UpdateInfo | None = None
        self.browser_dialog: Any = None
        self.current_album = None
        self.settings = load_settings()
        saved_session = load_session() or {}
        self.session_cookies: dict[str, str] = {
            str(key): str(value)
            for key, value in dict(
                saved_session.get("cookies") or {}
            ).items()
        }
        self.session_username = str(saved_session.get("username") or "")
        self.current_theme = str(self.settings.get("theme") or "system")
        self.resolved_theme = "light"
        self.app_logger = logging.getLogger("JMComicDesktop")

        self._configure_logging()
        self._configure_window()
        self._build_ui()
        self._connect_theme_signals()
        self._apply_theme()
        self._drain_events()

        self.event_timer = QTimer(self)
        self.event_timer.setInterval(100)
        self.event_timer.timeout.connect(self._drain_events)
        self.event_timer.start()

        if show_window:
            self.show()
            if (
                bool(self.settings.get("auto_check_update", True))
                and self.update_source_input.text().strip()
            ):
                QTimer.singleShot(1800, self._check_update)

    def _configure_window(self) -> None:
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.setMinimumSize(980, 680)
        icon_path = asset_path("app.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        geometry = str(self.settings.get("geometry") or "").strip()
        if geometry:
            try:
                x, y, width, height = (int(part) for part in geometry.split(","))
                self.setGeometry(x, y, max(width, 980), max(height, 680))
            except (TypeError, ValueError):
                self.resize(1120, 760)
        else:
            self.resize(1120, 760)

    def _configure_logging(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.app_logger.setLevel(logging.INFO)
        self.app_logger.propagate = False

        if not self.app_logger.handlers:
            file_handler = RotatingFileHandler(
                LOG_DIR / "desktop.log",
                maxBytes=2 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
            )
            self.app_logger.addHandler(file_handler)

        jm_logger.setLevel(logging.INFO)
        jm_logger.propagate = False
        for handler in list(jm_logger.handlers):
            jm_logger.removeHandler(handler)
        queue_handler = QueueLogHandler(self.events)
        queue_handler.setFormatter(logging.Formatter("%(message)s"))
        jm_logger.addHandler(queue_handler)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._build_header(root_layout)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(22, 18, 22, 12)
        body_layout.setSpacing(18)
        root_layout.addWidget(body, 1)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        body_layout.addWidget(left_panel, 5)

        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        left_layout.addWidget(settings_scroll, 1)

        settings_panel = QFrame()
        settings_panel.setObjectName("settingsPanel")
        settings_scroll.setWidget(settings_panel)
        self.settings_layout = QVBoxLayout(settings_panel)
        self.settings_layout.setContentsMargins(16, 14, 16, 16)
        self.settings_layout.setSpacing(12)

        self._build_download_section()
        self._add_separator()
        self._build_save_section()
        self._add_separator()
        self._build_network_section()
        self._add_separator()
        self._build_account_update_section()
        self._add_separator()
        self._build_behavior_section()
        self._build_action_bar(left_layout)

        self._build_log_panel(body_layout)
        self._build_footer(root_layout)

        self._update_naming_hint()
        self._update_proxy_state()
        self._update_zip_state()
        self._update_login_status()
        self._update_action_state()
        self.append_log("应用已就绪。请输入作品车号或禁漫链接。")
        self.append_log(f"程序数据目录：{APP_DIR}")

    def _build_header(self, root_layout: QVBoxLayout) -> None:
        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 15, 22, 14)

        title_column = QVBoxLayout()
        title_column.setSpacing(3)
        title = QLabel("JMComic 桌面版")
        title.setObjectName("title")
        subtitle = QLabel("先查询作品详情，选择章节范围，再下载或打包为 ZIP")
        subtitle.setObjectName("subtitle")
        title_column.addWidget(title)
        title_column.addWidget(subtitle)
        header_layout.addLayout(title_column)
        header_layout.addStretch(1)

        theme_label = QLabel("界面主题")
        theme_label.setObjectName("subtitle")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEME_LABELS)
        self.theme_combo.setCurrentText(
            THEME_LABEL_BY_VALUE.get(
                self.current_theme,
                THEME_LABEL_BY_VALUE["system"],
            )
        )
        self.theme_combo.setMinimumWidth(112)
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        header_layout.addWidget(theme_label)
        header_layout.addWidget(self.theme_combo)

        self.browse_button = QPushButton("浏览漫画")
        self.browse_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon)
        )
        self.browse_button.setToolTip("打开应用内网页，挑选漫画后再复制车号查询")
        self.browse_button.clicked.connect(self._open_comic_browser)
        header_layout.addSpacing(8)
        header_layout.addWidget(self.browse_button)

        version = QLabel(f"v{APP_VERSION} · 核心 {core_version()}")
        version.setObjectName("subtitle")
        header_layout.addSpacing(8)
        header_layout.addWidget(version)
        root_layout.addWidget(header)

    def _build_download_section(self) -> None:
        self._add_section(
            "下载目标",
            "先查询作品详情，再选择要下载的章节范围。",
        )

        target_widget = QWidget()
        target_layout = QHBoxLayout(target_widget)
        target_layout.setContentsMargins(0, 0, 0, 0)
        target_layout.setSpacing(8)
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("例如 123456、JM123456、p123456 或禁漫链接")
        self.id_input.textEdited.connect(self._invalidate_detail)
        self.query_button = QPushButton("查询详情")
        self.query_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        )
        self.query_button.clicked.connect(self._query_detail)
        target_layout.addWidget(self.id_input, 1)
        target_layout.addWidget(self.query_button)
        self.settings_layout.addWidget(
            SettingField(
                "车号 / 章节 / 链接",
                target_widget,
                "支持纯车号、JM123456、章节编号 p123456，以及 albums 或 photos 页面链接。查询不会下载图片。",
            )
        )

        self.query_status = QLabel("尚未查询作品详情。")
        self.query_status.setObjectName("fieldHint")
        self.query_status.setWordWrap(True)
        self.settings_layout.addWidget(self.query_status)

        range_widget = QWidget()
        range_layout = QHBoxLayout(range_widget)
        range_layout.setContentsMargins(0, 0, 0, 0)
        range_layout.setSpacing(8)
        self.chapter_start_combo = QComboBox()
        self.chapter_end_combo = QComboBox()
        self.chapter_start_combo.setEnabled(False)
        self.chapter_end_combo.setEnabled(False)
        self.chapter_start_combo.currentIndexChanged.connect(
            self._on_chapter_start_changed
        )
        self.chapter_end_combo.currentIndexChanged.connect(
            self._on_chapter_end_changed
        )
        range_label = QLabel("到")
        range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.all_chapters_button = QPushButton("全部章节")
        self.all_chapters_button.setEnabled(False)
        self.all_chapters_button.clicked.connect(self._select_all_chapters)
        range_layout.addWidget(self.chapter_start_combo, 1)
        range_layout.addWidget(range_label)
        range_layout.addWidget(self.chapter_end_combo, 1)
        range_layout.addWidget(self.all_chapters_button)
        self.settings_layout.addWidget(
            SettingField(
                "章节范围",
                range_widget,
                "查询后可选择起始话和结束话；包含起始和结束章节。",
            )
        )

    def _build_save_section(self) -> None:
        self._add_section(
            "保存与命名",
            "目录结构和作品文件夹名称会在每次任务开始时读取。",
        )

        folder_widget = QWidget()
        folder_layout = QHBoxLayout(folder_widget)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        folder_layout.setSpacing(8)
        self.folder_input = QLineEdit(
            str(self.settings.get("folder") or default_download_dir())
        )
        self.browse_button = QPushButton("浏览")
        self.browse_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        self.browse_button.clicked.connect(self._browse_folder)
        folder_layout.addWidget(self.folder_input, 1)
        folder_layout.addWidget(self.browse_button)
        self.settings_layout.addWidget(
            SettingField(
                "保存目录",
                folder_widget,
                "所有作品都保存到该目录；目录不存在时会自动创建。",
            )
        )

        self.naming_combo = QComboBox()
        self.naming_combo.addItems(NAMING_LABELS)
        naming_value = str(self.settings.get("naming") or "id")
        self.naming_combo.setCurrentText(
            NAMING_LABEL_BY_VALUE.get(naming_value, NAMING_LABEL_BY_VALUE["id"])
        )
        self.naming_combo.currentTextChanged.connect(self._update_naming_hint)
        self.naming_field = SettingField(
            "作品文件夹命名",
            self.naming_combo,
            NAMING_HINTS["id"],
        )
        self.settings_layout.addWidget(self.naming_field)

        self.pack_zip_check = QCheckBox("多话作品打包为 ZIP")
        self.pack_zip_check.setChecked(bool(self.settings.get("pack_zip", True)))
        self.pack_zip_check.toggled.connect(self._update_zip_state)
        self.settings_layout.addWidget(
            SettingField(
                "ZIP 打包",
                self.pack_zip_check,
                "选择多话时，生成“车号或漫画名.zip”，ZIP 内保留各章文件夹；单话不打包。",
            )
        )

        self.delete_after_zip_check = QCheckBox("打包成功后删除中间文件夹")
        self.delete_after_zip_check.setChecked(
            bool(self.settings.get("delete_after_zip", True))
        )
        self.settings_layout.addWidget(
            SettingField(
                "ZIP 清理",
                self.delete_after_zip_check,
                "仅在 ZIP 创建成功后删除本次下载产生的中间文件夹，不处理已有文件。",
            )
        )

    def _build_network_section(self) -> None:
        self._add_section(
            "下载与网络",
            "默认参数适合大多数网络环境，遇到限速或失败时再调整。",
        )

        self.client_combo = QComboBox()
        self.client_combo.addItems(CLIENT_LABELS)
        client_value = str(self.settings.get("client") or "api")
        self.client_combo.setCurrentText(
            CLIENT_LABEL_BY_VALUE.get(client_value, CLIENT_LABEL_BY_VALUE["api"])
        )
        self.settings_layout.addWidget(
            SettingField(
                "作品接口",
                self.client_combo,
                "APP 接口通常更稳定；网页接口在部分网络下速度更快。",
            )
        )

        self.image_threads_spin = QSpinBox()
        self.image_threads_spin.setRange(1, 50)
        self.image_threads_spin.setValue(
            int(self.settings.get("image_threads") or 10)
        )
        self.image_threads_spin.setSuffix(" 张")
        self.settings_layout.addWidget(
            SettingField(
                "图片并发",
                self.image_threads_spin,
                "同时下载的图片数；数值越高越快，但会增加站点压力和失败概率，建议 8 到 16。",
            )
        )

        self.chapter_threads_spin = QSpinBox()
        self.chapter_threads_spin.setRange(1, 64)
        self.chapter_threads_spin.setValue(
            int(
                self.settings.get("chapter_threads")
                or min(os.cpu_count() or 4, 8)
            )
        )
        self.chapter_threads_spin.setSuffix(" 章")
        self.settings_layout.addWidget(
            SettingField(
                "章节并发",
                self.chapter_threads_spin,
                "同时处理的章节数；长作品可适当提高，普通网络建议保持 4 到 8。",
            )
        )

        self.suffix_combo = QComboBox()
        self.suffix_combo.addItems(IMAGE_SUFFIX_LABELS)
        saved_suffix = self.settings.get("image_suffix")
        suffix_label = next(
            (
                label
                for label, value in IMAGE_SUFFIX_LABELS.items()
                if value == saved_suffix
            ),
            "保持原格式",
        )
        self.suffix_combo.setCurrentText(suffix_label)
        self.settings_layout.addWidget(
            SettingField(
                "图片格式",
                self.suffix_combo,
                "保持原格式不会二次转码；JPG、PNG、WEBP 会在下载后转换，耗时略增。",
            )
        )

        self.proxy_combo = QComboBox()
        self.proxy_combo.addItems(PROXY_LABELS)
        proxy_value = str(self.settings.get("proxy_mode") or "system")
        self.proxy_combo.setCurrentText(
            PROXY_LABEL_BY_VALUE.get(proxy_value, PROXY_LABEL_BY_VALUE["system"])
        )
        self.proxy_combo.currentTextChanged.connect(self._update_proxy_state)
        self.settings_layout.addWidget(
            SettingField(
                "代理方式",
                self.proxy_combo,
                "跟随系统会读取 Windows 代理；无法联网时可尝试不使用代理或手动填写。",
            )
        )

        self.proxy_input = QLineEdit(str(self.settings.get("proxy") or ""))
        self.proxy_input.setPlaceholderText("例如 127.0.0.1:7890")
        self.settings_layout.addWidget(
            SettingField(
                "手动代理地址",
                self.proxy_input,
                "仅在选择“手动输入”时生效，填写本机代理服务监听的地址和端口。",
            )
        )

    def _build_account_update_section(self) -> None:
        self._add_section(
            "账号与更新",
            "登录会话和自更新文件都保存在程序目录，不使用 AppData。",
        )

        login_widget = QWidget()
        login_layout = QVBoxLayout(login_widget)
        login_layout.setContentsMargins(0, 0, 0, 0)
        login_layout.setSpacing(6)
        self.login_status_label = QLabel("")
        self.login_status_label.setObjectName("fieldHint")
        self.login_status_label.setWordWrap(True)
        login_buttons = QHBoxLayout()
        self.login_button = QPushButton("登录")
        self.login_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_DialogApplyButton
            )
        )
        self.login_button.clicked.connect(self._open_login_dialog)
        self.logout_button = QPushButton("退出登录")
        self.logout_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_DialogDiscardButton
            )
        )
        self.logout_button.clicked.connect(self._logout)
        login_buttons.addWidget(self.login_button)
        login_buttons.addWidget(self.logout_button)
        login_buttons.addStretch(1)
        login_layout.addWidget(self.login_status_label)
        login_layout.addLayout(login_buttons)
        self.settings_layout.addWidget(
            SettingField(
                "账号登录",
                login_widget,
                "弹窗输入账号密码；密码不会保存，保持登录时仅加密保存服务器会话。",
            )
        )

        update_source_widget = QWidget()
        update_source_layout = QVBoxLayout(update_source_widget)
        update_source_layout.setContentsMargins(0, 0, 0, 0)
        update_source_layout.setSpacing(6)
        self.update_source_input = QLineEdit(
            str(self.settings.get("update_manifest_url") or "")
        )
        self.update_source_input.setPlaceholderText(
            "HTTPS 更新清单地址或本地 JSON 文件"
        )
        update_buttons = QHBoxLayout()
        self.auto_check_update_check = QCheckBox("启动后自动检查")
        self.auto_check_update_check.setChecked(
            bool(self.settings.get("auto_check_update", True))
        )
        self.update_button = QPushButton("检查更新")
        self.update_button.setIcon(
            self.style().standardIcon(
                QStyle.StandardPixmap.SP_BrowserReload
            )
        )
        self.update_button.clicked.connect(lambda: self._check_update(True))
        update_buttons.addWidget(self.auto_check_update_check)
        update_buttons.addStretch(1)
        update_buttons.addWidget(self.update_button)
        self.update_status_label = QLabel("尚未检查更新。")
        self.update_status_label.setObjectName("fieldHint")
        self.update_status_label.setWordWrap(True)
        update_source_layout.addWidget(self.update_source_input)
        update_source_layout.addLayout(update_buttons)
        update_source_layout.addWidget(self.update_status_label)
        self.settings_layout.addWidget(
            SettingField(
                "自更新源",
                update_source_widget,
                "清单需包含 version、url、sha256、size 和可选 notes；更新包内的 data 与 downloads 不会被覆盖。",
            )
        )

        location = QLabel(f"当前程序数据：{APP_DIR}")
        location.setObjectName("fieldHint")
        location.setWordWrap(True)
        location.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.settings_layout.addWidget(location)

    def _build_behavior_section(self) -> None:
        self._add_section("完成动作", "任务结束后的辅助操作，不影响下载结果。")
        self.open_folder_check = QCheckBox("下载完成后自动打开保存目录")
        self.open_folder_check.setChecked(
            bool(self.settings.get("open_folder", False))
        )
        self.settings_layout.addWidget(
            SettingField(
                "完成后操作",
                self.open_folder_check,
                "任务全部成功时打开保存目录，便于快速查看下载结果。",
            )
        )

        notice = QLabel(
            "本软件是官方 jmcomic Python API 的图形界面；下载内容由第三方站点提供，"
            "请确认你已成年并有权访问和保存相关内容。"
        )
        notice.setObjectName("notice")
        notice.setWordWrap(True)
        self.settings_layout.addWidget(notice)

    def _build_action_bar(self, layout: QVBoxLayout) -> None:
        button_row = QHBoxLayout()
        self.start_button = QPushButton("开始下载")
        self.start_button.setObjectName("primary")
        self.start_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        )
        self.start_button.clicked.connect(self._start_download)
        self.start_button.setEnabled(False)
        self.open_button = QPushButton("打开目录")
        self.open_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        self.open_button.clicked.connect(self._open_folder)
        button_row.addWidget(self.start_button, 1)
        button_row.addWidget(self.open_button)
        layout.addLayout(button_row)

    def _build_log_panel(self, body_layout: QHBoxLayout) -> None:
        panel = QFrame()
        panel.setObjectName("logPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        panel_layout.setSpacing(0)
        body_layout.addWidget(panel, 4)

        self.right_tabs = QTabWidget()
        self.right_tabs.setDocumentMode(True)
        panel_layout.addWidget(self.right_tabs)

        self.detail_tab = QWidget()
        detail_layout = QVBoxLayout(self.detail_tab)
        detail_layout.setContentsMargins(6, 8, 6, 6)
        self.detail_browser = QTextBrowser()
        self.detail_browser.setOpenExternalLinks(True)
        self.detail_browser.setPlaceholderText("输入车号并点击“查询详情”后显示作品信息。")
        detail_layout.addWidget(self.detail_browser)
        self.right_tabs.addTab(self.detail_tab, "作品详情")

        self.log_tab = QWidget()
        log_layout = QVBoxLayout(self.log_tab)
        log_layout.setContentsMargins(6, 8, 6, 6)
        log_layout.setSpacing(8)

        log_header = QHBoxLayout()
        log_title = QLabel("运行日志")
        log_title.setObjectName("section")
        self.clear_button = QPushButton("清空")
        self.clear_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton)
        )
        self.clear_button.clicked.connect(self._clear_log)
        log_header.addWidget(log_title)
        log_header.addStretch(1)
        log_header.addWidget(self.clear_button)
        log_layout.addLayout(log_header)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(2500)
        self.log_text.setFont(QFont("Cascadia Mono", 9))
        self.log_text.setPlaceholderText("任务日志会显示在这里")
        log_layout.addWidget(self.log_text, 1)
        self.right_tabs.addTab(self.log_tab, "运行日志")

    def _build_footer(self, root_layout: QVBoxLayout) -> None:
        footer = QFrame()
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(22, 0, 22, 16)
        footer_layout.setSpacing(6)
        self.status_label = QLabel("等待任务")
        self.status_label.setObjectName("status")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(10)
        footer_layout.addWidget(self.status_label)
        footer_layout.addWidget(self.progress_bar)
        root_layout.addWidget(footer)

    def _add_section(self, title: str, description: str) -> None:
        title_label = QLabel(title)
        title_label.setObjectName("section")
        description_label = QLabel(description)
        description_label.setObjectName("fieldHint")
        description_label.setWordWrap(True)
        self.settings_layout.addWidget(title_label)
        self.settings_layout.addWidget(description_label)

    def _add_separator(self) -> None:
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Plain)
        self.settings_layout.addWidget(separator)

    def _connect_theme_signals(self) -> None:
        try:
            self.app.styleHints().colorSchemeChanged.connect(
                self._on_system_color_scheme_changed
            )
        except AttributeError:
            pass

    def _apply_theme(self) -> None:
        self.resolved_theme = apply_theme(self.app, self.current_theme)

    def _on_theme_changed(self, label: str) -> None:
        self.current_theme = THEME_LABELS.get(label, "system")
        self._apply_theme()
        self.settings["theme"] = self.current_theme
        save_settings(self.settings)
        self.append_log(f"界面主题已切换为：{label}")

    def _on_system_color_scheme_changed(self, *_args: Any) -> None:
        if self.current_theme == "system":
            self._apply_theme()

    def _browse_folder(self) -> None:
        initial = self.folder_input.text().strip()
        selected = QFileDialog.getExistingDirectory(
            self,
            "选择下载目录",
            initial if initial and Path(initial).exists() else str(Path.home()),
            QFileDialog.Option.ShowDirsOnly,
        )
        if selected:
            self.folder_input.setText(selected)

    def _update_proxy_state(self, _text: str = "") -> None:
        manual = self.proxy_combo.currentText() == "手动输入"
        self.proxy_input.setEnabled(
            manual and not self.running and not self.querying
        )

    def _update_naming_hint(self, _text: str = "") -> None:
        naming = NAMING_LABELS.get(self.naming_combo.currentText(), "id")
        self.naming_field.set_hint(NAMING_HINTS[naming])

    def _update_zip_state(self, _checked: bool = False) -> None:
        self.delete_after_zip_check.setEnabled(
            self.pack_zip_check.isChecked()
            and not self.running
            and not self.querying
        )

    def _update_login_status(self) -> None:
        if self.session_cookies:
            account = (
                f"：{self.session_username}"
                if self.session_username
                else ""
            )
            self.login_status_label.setText(
                f"已保持登录{account}，会话项 {len(self.session_cookies)} 个。"
            )
            self.login_button.setText("重新登录")
        else:
            self.login_status_label.setText(
                "当前未登录，不影响公开作品；受限作品需要登录会话。"
            )
            self.login_button.setText("登录")
        self.logout_button.setEnabled(bool(self.session_cookies))
        if hasattr(self, "update_button"):
            self._update_action_state()

    def _open_login_dialog(self) -> None:
        if self.running or self.querying or self.update_checking:
            return
        try:
            option = self._build_option(pack_zip=False, use_session=False)
        except Exception as exc:
            QMessageBox.critical(self, "无法打开登录", str(exc))
            return

        dialog = LoginDialog(
            option,
            username=self.session_username,
            parent=self,
        )
        if dialog.exec() != LoginDialog.DialogCode.Accepted:
            return
        self.session_cookies = dict(dialog.cookies)
        self.session_username = dialog.username
        try:
            save_session(
                self.session_cookies,
                self.session_username,
                persist=dialog.persist,
            )
        except BaseException as exc:
            QMessageBox.warning(
                self,
                "会话保存失败",
                f"登录成功，但会话无法保存到程序目录：{exc}",
            )
        self._update_login_status()
        self.append_log(
            "账号登录成功，之后的查询和下载将使用当前会话。"
        )

    def _logout(self) -> None:
        if not self.session_cookies:
            return
        answer = QMessageBox.question(
            self,
            "退出登录",
            "清除保存在程序目录中的加密登录会话？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        clear_session()
        self.session_cookies = {}
        self.session_username = ""
        self._update_login_status()
        self.append_log("已清除登录会话。")

    def _proxy_config(self) -> dict[str, str] | None:
        mode = PROXY_LABELS[self.proxy_combo.currentText()]
        if mode == "system":
            return None
        if mode == "none":
            return {}
        proxy = self.proxy_input.text().strip()
        if not proxy:
            raise ValueError("已选择手动代理，但代理地址为空。")
        return {"http": proxy, "https": proxy}

    def _check_update(self, manual: bool = True) -> None:
        if (
            self.running
            or self.querying
            or self.update_checking
            or self.update_downloading
        ):
            return
        source = self.update_source_input.text().strip()
        if not source:
            if manual:
                QMessageBox.information(
                    self,
                    "未配置更新源",
                    "请在“自更新源”中填写 HTTPS 清单地址或本地 JSON 文件。",
                )
            return
        try:
            proxies = self._proxy_config()
        except ValueError as exc:
            QMessageBox.critical(self, "无法检查更新", str(exc))
            return

        self.settings["update_manifest_url"] = source
        self.settings["auto_check_update"] = (
            self.auto_check_update_check.isChecked()
        )
        save_settings(self.settings)
        self.update_checking = True
        self.update_status_label.setText("正在检查更新...")
        self._update_action_state()
        if manual:
            self.append_log("正在检查程序更新...")
        threading.Thread(
            target=self._update_check_worker,
            args=(source, proxies, manual),
            daemon=True,
        ).start()

    def _update_check_worker(
        self,
        source: str,
        proxies: dict[str, str] | None,
        manual: bool,
    ) -> None:
        try:
            info = load_manifest(source, proxies)
            self.events.put(
                ("update_checked", info, is_newer(info.version), manual)
            )
        except BaseException as exc:
            self.events.put(
                (
                    "update_error",
                    "检查更新失败："
                    + (str(exc) or exc.__class__.__name__),
                    manual,
                )
            )

    def _download_update(self, info: UpdateInfo) -> None:
        if self.update_downloading or self.running:
            return
        try:
            proxies = self._proxy_config()
        except ValueError as exc:
            QMessageBox.critical(self, "无法下载更新", str(exc))
            return
        self.update_info = info
        self.update_downloading = True
        self.update_status_label.setText("正在下载更新...")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._update_action_state()
        self.append_log(f"开始下载更新：v{info.version}")
        threading.Thread(
            target=self._update_download_worker,
            args=(info, proxies),
            daemon=True,
        ).start()

    def _update_download_worker(
        self,
        info: UpdateInfo,
        proxies: dict[str, str] | None,
    ) -> None:
        try:
            package = download_update(
                info,
                proxies,
                progress=lambda done, total: self.events.put(
                    ("update_progress", done, total)
                ),
            )
            self.events.put(("update_ready", info, package))
        except BaseException as exc:
            self.events.put(
                (
                    "update_error",
                    "下载更新失败："
                    + (str(exc) or exc.__class__.__name__),
                    True,
                )
            )

    def _launch_ready_update(
        self,
        info: UpdateInfo,
        package: Path,
    ) -> None:
        answer = QMessageBox.question(
            self,
            "更新已下载",
            f"JMComic 桌面版 v{info.version} 已下载并通过校验。\n"
            "现在关闭程序并安装更新？\n\n"
            "程序目录中的 data 和 downloads 会原样保留。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.update_status_label.setText(
                f"v{info.version} 已下载，退出后不会自动安装。"
            )
            self.append_log(
                f"更新包已保存：{package}；已暂缓安装。"
            )
            return
        try:
            launch_updater(package, info.sha256)
        except UpdateError as exc:
            QMessageBox.critical(self, "无法安装更新", str(exc))
            return
        self.update_status_label.setText("正在启动更新器...")
        self.append_log("更新器已启动，程序即将退出。")
        QTimer.singleShot(250, self.app.quit)

    def _invalidate_detail(self, _text: str = "") -> None:
        if self.running or self.querying:
            return
        self.current_album = None
        self.query_status.setText("目标已修改，请重新查询作品详情。")
        self.detail_browser.setPlainText("目标已修改，请重新查询作品详情。")
        self._clear_chapter_range()
        self._update_action_state()

    def _clear_chapter_range(self) -> None:
        for combo in (self.chapter_start_combo, self.chapter_end_combo):
            combo.blockSignals(True)
            combo.clear()
            combo.setEnabled(False)
            combo.blockSignals(False)
        self.all_chapters_button.setEnabled(False)

    def _query_detail(self) -> None:
        if self.running or self.querying:
            return

        raw_text = self.id_input.text().strip()
        try:
            query_type, jm_id = self._parse_jm_input(raw_text)
        except Exception as exc:
            QMessageBox.critical(self, "无法查询", str(exc))
            return

        self.current_album = None
        self._clear_chapter_range()
        self.querying = True
        self.query_status.setText("正在查询作品详情，请稍候...")
        self.detail_browser.setHtml(query_pending_html(raw_text))
        self.right_tabs.setCurrentWidget(self.detail_tab)
        self.append_log(f"🔍 正在查询 禁漫车号 - [{jm_id}] 的详情...")
        self._update_action_state()

        worker = threading.Thread(
            target=self._query_worker,
            args=(query_type, jm_id, raw_text),
            daemon=True,
        )
        worker.start()

    def _query_worker(self, query_type: str, jm_id: str, raw_text: str) -> None:
        try:
            option = self._build_option(pack_zip=False)
            client = option.build_jm_client()
            focus_photo_id = None
            if query_type == "photo":
                photo = client.get_photo_detail(jm_id)
                focus_photo_id = photo.photo_id
                album = photo.from_album or client.get_album_detail(photo.album_id)
            else:
                album = client.get_album_detail(jm_id)
            self.events.put(("detail", album, focus_photo_id, raw_text))
        except BaseException as exc:
            self.app_logger.error("详情查询失败\n%s", traceback.format_exc())
            self.events.put(("query_error", str(exc) or exc.__class__.__name__))
        finally:
            self.events.put(("query_done",))

    def _populate_chapter_range(self, album, focus_photo_id: str | None) -> None:
        for combo in (self.chapter_start_combo, self.chapter_end_combo):
            combo.blockSignals(True)
            combo.clear()
            for position, (photo_id, photo_index, photo_name) in enumerate(
                album.episode_list
            ):
                combo.addItem(
                    chapter_label(int(photo_index), str(photo_name), str(photo_id)),
                    str(photo_id),
                )
            combo.setEnabled(True)
            combo.blockSignals(False)

        last_index = max(self.chapter_start_combo.count() - 1, 0)
        start_index = 0
        end_index = last_index
        if focus_photo_id:
            focused_index = self.chapter_start_combo.findData(str(focus_photo_id))
            if focused_index >= 0:
                start_index = focused_index
                end_index = focused_index

        self.chapter_start_combo.blockSignals(True)
        self.chapter_end_combo.blockSignals(True)
        self.chapter_start_combo.setCurrentIndex(start_index)
        self.chapter_end_combo.setCurrentIndex(end_index)
        self.chapter_start_combo.blockSignals(False)
        self.chapter_end_combo.blockSignals(False)
        self.all_chapters_button.setEnabled(True)

    def _on_chapter_start_changed(self, index: int) -> None:
        if index < 0:
            return
        if self.chapter_end_combo.currentIndex() < index:
            self.chapter_end_combo.blockSignals(True)
            self.chapter_end_combo.setCurrentIndex(index)
            self.chapter_end_combo.blockSignals(False)

    def _on_chapter_end_changed(self, index: int) -> None:
        if index < 0:
            return
        if self.chapter_start_combo.currentIndex() > index:
            self.chapter_start_combo.blockSignals(True)
            self.chapter_start_combo.setCurrentIndex(index)
            self.chapter_start_combo.blockSignals(False)

    def _select_all_chapters(self) -> None:
        if self.chapter_start_combo.count() == 0:
            return
        self.chapter_start_combo.blockSignals(True)
        self.chapter_end_combo.blockSignals(True)
        self.chapter_start_combo.setCurrentIndex(0)
        self.chapter_end_combo.setCurrentIndex(
            self.chapter_start_combo.count() - 1
        )
        self.chapter_start_combo.blockSignals(False)
        self.chapter_end_combo.blockSignals(False)

    def _selected_chapter_range(self) -> tuple[int, int, int]:
        if self.current_album is None:
            raise ValueError("请先查询作品详情，再开始下载。")
        start = self.chapter_start_combo.currentIndex()
        end = self.chapter_end_combo.currentIndex()
        if start < 0 or end < start:
            raise ValueError("请选择有效的章节范围。")
        return start, end + 1, end - start + 1

    def _update_action_state(self) -> None:
        busy = (
            self.running
            or self.querying
            or self.update_checking
            or self.update_downloading
        )
        for widget in (
            self.id_input,
            self.query_button,
            self.client_combo,
            self.image_threads_spin,
            self.chapter_threads_spin,
            self.suffix_combo,
            self.proxy_combo,
        ):
            widget.setEnabled(not busy)
        self.folder_input.setEnabled(not busy)
        self.browse_button.setEnabled(not busy)
        self.naming_combo.setEnabled(not busy)
        self.pack_zip_check.setEnabled(not busy)
        self.open_folder_check.setEnabled(not busy)
        self.open_button.setEnabled(not busy)
        self.login_button.setEnabled(not busy)
        self.logout_button.setEnabled(
            not busy and bool(self.session_cookies)
        )
        self.update_source_input.setEnabled(not busy)
        self.auto_check_update_check.setEnabled(not busy)
        self.update_button.setEnabled(not busy)
        self.chapter_start_combo.setEnabled(
            not busy and self.chapter_start_combo.count() > 0
        )
        self.chapter_end_combo.setEnabled(
            not busy and self.chapter_end_combo.count() > 0
        )
        self.all_chapters_button.setEnabled(
            not busy and self.chapter_start_combo.count() > 0
        )
        self.start_button.setEnabled(
            not busy and self.current_album is not None
        )
        if busy:
            self.proxy_input.setEnabled(False)
        else:
            self._update_proxy_state()
        self._update_zip_state()

    def _open_folder(self) -> None:
        folder = Path(self.folder_input.text().strip())
        try:
            folder.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        except Exception as exc:
            QMessageBox.critical(self, "无法打开目录", str(exc))

    def _open_comic_browser(self) -> None:
        try:
            from .browser import ComicBrowserDialog

            if self.browser_dialog is None:
                self.browser_dialog = ComicBrowserDialog(parent=self)
            self.browser_dialog.show()
            self.browser_dialog.raise_()
            self.browser_dialog.activateWindow()
        except BaseException as exc:
            self.app_logger.error(
                "网页浏览窗口打开失败\n%s",
                traceback.format_exc(),
            )
            QMessageBox.critical(
                self,
                "无法打开网页",
                f"应用内网页组件加载失败：{exc}",
            )

    def _clear_log(self) -> None:
        self.log_text.clear()

    def append_log(self, message: str) -> None:
        self.log_text.appendPlainText(message.rstrip())
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def _set_running(self, running: bool) -> None:
        self.running = running
        self._update_action_state()

    def _parse_jm_input(self, raw_text: str) -> tuple[str, str]:
        text = raw_text.strip()
        if not text:
            raise ValueError("请输入作品车号、章节车号或禁漫链接。")

        if len(text) >= 2 and text[0].lower() == "p":
            return "photo", JmcomicText.parse_to_jm_id(text[1:].strip())

        lower_text = text.lower()
        if "/photo/" in lower_text or "/photos/" in lower_text:
            return "photo", JmcomicText.parse_to_jm_id(text)

        return "album", JmcomicText.parse_to_jm_id(text)

    def _build_option(
        self,
        pack_zip: bool = False,
        use_session: bool = True,
    ):
        client = CLIENT_LABELS[self.client_combo.currentText()]
        naming = NAMING_LABELS[self.naming_combo.currentText()]
        proxy_mode = PROXY_LABELS[self.proxy_combo.currentText()]
        if proxy_mode == "system":
            proxies: Any = "system"
        elif proxy_mode == "none":
            proxies = None
        else:
            proxies = self.proxy_input.text().strip()
            if not proxies:
                raise ValueError("已选择手动代理，但代理地址为空。")

        folder_text = self.folder_input.text().strip()
        if not folder_text:
            raise ValueError("请选择下载目录。")
        folder = Path(folder_text).expanduser()
        folder.mkdir(parents=True, exist_ok=True)

        option_dict = {
            "log": True,
            "dir_rule": {
                "base_dir": str(folder),
                "rule": DIR_RULES[naming],
            },
            "download": {
                "cache": True,
                "image": {
                    "decode": True,
                    "suffix": IMAGE_SUFFIX_LABELS[self.suffix_combo.currentText()],
                },
                "threading": {
                    "image": self.image_threads_spin.value(),
                    "photo": self.chapter_threads_spin.value(),
                },
            },
            "client": {
                "impl": client,
                "retry_times": 5,
                "postman": {
                    "meta_data": {
                        "timeout": 30,
                        "proxies": proxies,
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
                            "filename_rule": ZIP_FILENAME_RULES[naming],
                            "suffix": "zip",
                            "level": "album",
                            "delete_original_file": self.delete_after_zip_check.isChecked(),
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
        if use_session and self.session_cookies:
            option.update_cookies(self.session_cookies)
        return option

    def _start_download(self) -> None:
        if self.running:
            return

        try:
            start, end, selected_count = self._selected_chapter_range()
            album_id = self.current_album.album_id
            pack_zip = self.pack_zip_check.isChecked() and selected_count > 1
            option = self._build_option(pack_zip=pack_zip)
        except Exception as exc:
            QMessageBox.critical(self, "无法开始下载", str(exc))
            return

        self._save_current_settings()
        self._set_running(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText("正在获取作品信息...")
        self.right_tabs.setCurrentWidget(self.log_tab)
        self.append_log(
            f"开始任务：JM{album_id}，章节 {start + 1} 到 {end}，"
            f"共 {selected_count} 话"
        )
        if pack_zip:
            self.append_log("下载完成后将按当前命名方式打包为 ZIP。")

        worker = threading.Thread(
            target=self._download_worker,
            args=(
                album_id,
                option,
                start,
                end,
                pack_zip,
                self.delete_after_zip_check.isChecked(),
            ),
            daemon=True,
        )
        worker.start()

    def _download_worker(
        self,
        album_id: str,
        option,
        start: int,
        end: int,
        pack_zip: bool,
        delete_after_zip: bool,
    ) -> None:
        try:
            downloader = partial(
                DesktopDownloader,
                events=self.events,
                photo_range=(start, end),
            )
            with jm_task_context(download_type="album", jm_id=album_id):
                result = jmcomic.download_album(album_id, option, downloader)
            if (
                pack_zip
                and delete_after_zip
                and result.downloader.export_filepaths
            ):
                album_root = Path(
                    option.dir_rule.decide_album_root_dir(result.detail)
                )
                try:
                    if album_root.exists() and not any(album_root.iterdir()):
                        album_root.rmdir()
                        self.events.put(("cleaned", str(album_root)))
                except OSError:
                    pass
            self.events.put(("done", True, album_id))
        except BaseException as exc:
            self.app_logger.error("下载失败\n%s", traceback.format_exc())
            self.events.put(("error", str(exc) or exc.__class__.__name__))
            self.events.put(("done", False, album_id))

    def _drain_events(self) -> None:
        processed = 0
        while processed < 300:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            processed += 1
            kind = event[0]

            if kind == "log":
                _, level, message = event
                prefix = (
                    "[错误] "
                    if level >= logging.ERROR
                    else "[警告] "
                    if level >= logging.WARNING
                    else ""
                )
                self.append_log(prefix + message)
            elif kind == "album":
                _, title, author, chapters, pages, total_chapters = event
                self.status_label.setText(f"正在下载：{title}")
                self.progress_bar.setRange(0, max(pages, 1))
                self.progress_bar.setValue(0)
                self.append_log(
                    f"作品：{title} · 作者：{author} · 本次 {chapters}/{total_chapters} 话"
                )
            elif kind == "chapter":
                _, name, index, count, images = event
                self.status_label.setText(
                    f"第 {index}/{count} 章：{name}（{images} 张）"
                )
            elif kind == "progress":
                _, completed, total = event
                self.progress_bar.setRange(0, max(total, 1))
                self.progress_bar.setValue(completed)
                self.status_label.setText(f"正在下载：{completed}/{total} 张图片")
            elif kind == "detail":
                _, album, focus_photo_id, query_text = event
                self.current_album = album
                self._populate_chapter_range(album, focus_photo_id)
                self.query_status.setText(
                    f"已获取《{album.name}》，共 {len(album.episode_list)} 话，"
                    "请选择章节范围。"
                )
                self.detail_browser.setHtml(format_album_html(album, query_text))
                self.append_log(format_album_plain(album, query_text))
                self.right_tabs.setCurrentWidget(self.detail_tab)
                self._update_action_state()
            elif kind == "query_error":
                _, message = event
                self.current_album = None
                self._clear_chapter_range()
                self.query_status.setText("详情查询失败。")
                self.detail_browser.setHtml(query_error_html(message))
                self.append_log(f"查询失败：{message}")
                QMessageBox.critical(self, "查询失败", message)
            elif kind == "query_done":
                self.querying = False
                self._update_action_state()
            elif kind == "update_checked":
                _, info, newer, manual = event
                self.update_checking = False
                if newer:
                    self.update_info = info
                    notes = info.notes or "本次更新没有附说明。"
                    self.update_status_label.setText(
                        f"发现新版本 v{info.version}。"
                    )
                    self.append_log(f"发现新版本：v{info.version}")
                    answer = QMessageBox.question(
                        self,
                        "发现新版本",
                        f"当前版本：v{APP_VERSION}\n"
                        f"最新版本：v{info.version}\n\n"
                        f"{notes}\n\n是否下载并更新？",
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No,
                        QMessageBox.StandardButton.Yes,
                    )
                    if answer == QMessageBox.StandardButton.Yes:
                        self._download_update(info)
                else:
                    self.update_info = None
                    self.update_status_label.setText(
                        f"当前已是最新版本 v{APP_VERSION}。"
                    )
                    if manual:
                        QMessageBox.information(
                            self,
                            "检查更新",
                            f"当前已是最新版本 v{APP_VERSION}。",
                        )
                self._update_action_state()
            elif kind == "update_progress":
                _, done, total = event
                if total > 0:
                    self.progress_bar.setRange(0, total)
                    self.progress_bar.setValue(done)
                    self.update_status_label.setText(
                        f"正在下载更新：{done * 100 // total}%"
                    )
                else:
                    self.update_status_label.setText(
                        f"正在下载更新：{done // 1024} KB"
                    )
            elif kind == "update_ready":
                _, info, package = event
                self.update_downloading = False
                self.update_status_label.setText(
                    f"v{info.version} 已下载并通过校验。"
                )
                self.append_log(f"更新包已就绪：{package}")
                self._update_action_state()
                self._launch_ready_update(info, Path(package))
            elif kind == "update_error":
                _, message, manual = event
                self.update_checking = False
                self.update_downloading = False
                self.update_status_label.setText(message)
                self.append_log(message)
                self._update_action_state()
                if manual:
                    QMessageBox.critical(self, "更新失败", message)
            elif kind == "export":
                _, filepath = event
                self.append_log(f"已生成压缩包：{filepath}")
                self.status_label.setText(f"已生成压缩包：{Path(filepath).name}")
            elif kind == "cleaned":
                _, filepath = event
                self.append_log(f"已删除空的中间目录：{filepath}")
            elif kind == "error":
                _, message = event
                self.append_log(f"下载失败：{message}")
                self.status_label.setText("任务失败")
                QMessageBox.critical(self, "下载失败", message)
            elif kind == "done":
                _, success, completed_id = event
                self._set_running(False)
                if success:
                    self.progress_bar.setValue(self.progress_bar.maximum())
                    self.status_label.setText(f"下载完成：{completed_id}")
                    self.append_log(f"任务完成：{completed_id}")
                    if self.open_folder_check.isChecked():
                        self._open_folder()
                else:
                    self.status_label.setText("下载未完成")

    def _save_current_settings(self) -> None:
        geometry = self.geometry()
        self.settings.update(
            {
                "folder": self.folder_input.text().strip(),
                "client": CLIENT_LABELS[self.client_combo.currentText()],
                "image_threads": self.image_threads_spin.value(),
                "chapter_threads": self.chapter_threads_spin.value(),
                "proxy_mode": PROXY_LABELS[self.proxy_combo.currentText()],
                "proxy": self.proxy_input.text().strip(),
                "image_suffix": IMAGE_SUFFIX_LABELS[self.suffix_combo.currentText()],
                "naming": NAMING_LABELS[self.naming_combo.currentText()],
                "pack_zip": self.pack_zip_check.isChecked(),
                "delete_after_zip": self.delete_after_zip_check.isChecked(),
                "theme": self.current_theme,
                "open_folder": self.open_folder_check.isChecked(),
                "update_manifest_url": (
                    self.update_source_input.text().strip()
                ),
                "auto_check_update": (
                    self.auto_check_update_check.isChecked()
                ),
                "geometry": (
                    f"{geometry.x()},{geometry.y()},"
                    f"{geometry.width()},{geometry.height()}"
                ),
            }
        )
        save_settings(self.settings)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.running:
            QMessageBox.warning(
                self,
                "任务进行中",
                "当前仍有下载任务，请等待任务结束后再关闭。",
            )
            event.ignore()
            return
        self._save_current_settings()
        event.accept()
