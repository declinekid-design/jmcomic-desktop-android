from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QStyle,
    QVBoxLayout,
)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from .constants import APP_DIR, BROWSE_URL, DEFAULT_DOWNLOAD_DIR


class ComicWebPage(QWebEnginePage):
    def createWindow(self, _window_type) -> QWebEnginePage:
        return self


class ComicBrowserDialog(QDialog):
    def __init__(
        self,
        url: str = BROWSE_URL,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("comicBrowser")
        self.setWindowTitle("浏览漫画")
        self.setModal(False)
        self.resize(1180, 780)
        self.setMinimumSize(820, 560)

        browser_data = APP_DIR / "browser"
        storage_dir = browser_data / "storage"
        cache_dir = browser_data / "cache"
        storage_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self.back_button = self._toolbar_button(
            QStyle.StandardPixmap.SP_ArrowBack,
            "后退",
        )
        self.forward_button = self._toolbar_button(
            QStyle.StandardPixmap.SP_ArrowForward,
            "前进",
        )
        self.reload_button = self._toolbar_button(
            QStyle.StandardPixmap.SP_BrowserReload,
            "刷新",
        )
        self.url_input = QLineEdit()
        self.url_input.setClearButtonEnabled(True)
        self.url_input.setPlaceholderText("输入网址")
        self.url_input.returnPressed.connect(self._navigate_from_input)
        self.go_button = QPushButton("打开")
        self.go_button.setToolTip("打开地址栏中的网址")
        self.go_button.clicked.connect(self._navigate_from_input)
        self.external_button = self._toolbar_button(
            QStyle.StandardPixmap.SP_DialogOpenButton,
            "在系统浏览器中打开",
        )
        self.close_button = self._toolbar_button(
            QStyle.StandardPixmap.SP_DialogCloseButton,
            "关闭",
        )
        toolbar.addWidget(self.back_button)
        toolbar.addWidget(self.forward_button)
        toolbar.addWidget(self.reload_button)
        toolbar.addWidget(self.url_input, 1)
        toolbar.addWidget(self.go_button)
        toolbar.addWidget(self.external_button)
        toolbar.addWidget(self.close_button)
        layout.addLayout(toolbar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(3)
        layout.addWidget(self.progress_bar)

        self.profile = QWebEngineProfile("JMComicDesktopBrowser", self)
        self.profile.setPersistentStoragePath(str(storage_dir))
        self.profile.setCachePath(str(cache_dir))
        self.profile.setPersistentCookiesPolicy(
            QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies
        )
        self.profile.setHttpUserAgent(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
        self.profile.setHttpAcceptLanguage("zh-CN,zh;q=0.9,en;q=0.8")
        self.profile.downloadRequested.connect(self._on_download_requested)

        self.view = QWebEngineView(self)
        self.view.setPage(ComicWebPage(self.profile, self.view))
        self.view.urlChanged.connect(self._on_url_changed)
        self.view.loadStarted.connect(self._on_load_started)
        self.view.loadProgress.connect(self.progress_bar.setValue)
        self.view.loadFinished.connect(self._on_load_finished)
        self.view.titleChanged.connect(self._on_title_changed)
        layout.addWidget(self.view, 1)

        status_row = QHBoxLayout()
        status_row.setContentsMargins(2, 0, 2, 0)
        status = QLabel("网页数据保存在程序目录 data\\browser；登录状态可随网页会话保留。")
        status.setObjectName("fieldHint")
        status.setWordWrap(True)
        status_row.addWidget(status, 1)
        self.status_label = QLabel("")
        self.status_label.setObjectName("fieldHint")
        status_row.addWidget(self.status_label)
        layout.addLayout(status_row)

        self.back_button.clicked.connect(self.view.back)
        self.forward_button.clicked.connect(self.view.forward)
        self.reload_button.clicked.connect(self._reload_or_stop)
        self.external_button.clicked.connect(self._open_external)
        self.close_button.clicked.connect(self.close)
        self.view.urlChanged.connect(self._update_navigation)
        self.view.loadStarted.connect(self._update_navigation)
        self.view.loadFinished.connect(self._update_navigation)

        self.url_input.setText(url)
        self.view.setUrl(QUrl(url))
        self._update_navigation()

    def _toolbar_button(
        self,
        icon: QStyle.StandardPixmap,
        tooltip: str,
    ) -> QPushButton:
        button = QPushButton()
        button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        button.setFixedWidth(38)
        return button

    def _normalized_url(self) -> QUrl:
        text = self.url_input.text().strip()
        if not text:
            return QUrl(BROWSE_URL)
        if "://" not in text:
            text = "https://" + text
        return QUrl(text)

    def _navigate_from_input(self) -> None:
        self.view.setUrl(self._normalized_url())

    def _reload_or_stop(self) -> None:
        if self.view.page().isLoading():
            self.view.stop()
        else:
            self.view.reload()

    def _open_external(self) -> None:
        QDesktopServices.openUrl(self._normalized_url())

    def _on_url_changed(self, url: QUrl) -> None:
        self.url_input.setText(url.toString())

    def _on_title_changed(self, title: str) -> None:
        clean_title = title.strip() or "浏览漫画"
        self.setWindowTitle(f"{clean_title} - JMComic 桌面版")

    def _on_load_started(self) -> None:
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText("正在加载...")

    def _on_load_finished(self, success: bool) -> None:
        self.progress_bar.setValue(100)
        self.progress_bar.setVisible(False)
        self.status_label.setText("加载完成" if success else "网页加载失败")

    def _update_navigation(self, *_args) -> None:
        history = self.view.history()
        self.back_button.setEnabled(history.canGoBack())
        self.forward_button.setEnabled(history.canGoForward())
        self.reload_button.setToolTip(
            "停止" if self.view.page().isLoading() else "刷新"
        )

    def _on_download_requested(self, download) -> None:
        suggested_name = download.downloadFileName() or "download"
        DEFAULT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        destination, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "保存网页下载文件",
            str(DEFAULT_DOWNLOAD_DIR / suggested_name),
        )
        if not destination:
            download.cancel()
            return
        destination_path = Path(destination)
        download.setDownloadDirectory(str(destination_path.parent))
        download.setDownloadFileName(destination_path.name)
        download.accept()
        self.status_label.setText(f"开始下载：{destination_path.name}")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.view.stop()
        event.accept()


def run_browser_smoke_test(
    app: QApplication,
    timeout_ms: int = 12000,
) -> int:
    dialog = ComicBrowserDialog("about:blank")
    result = {"ok": False}
    timer = QTimer()

    def finish(success: bool) -> None:
        if timer.isActive():
            timer.stop()
        result["ok"] = bool(success)
        dialog.close()
        app.quit()

    timer.setSingleShot(True)
    timer.timeout.connect(lambda: finish(False))
    dialog.view.loadFinished.connect(finish)
    timer.start(timeout_ms)
    dialog.view.setHtml(
        "<!doctype html><html><body>JMComic browser runtime check</body></html>",
        QUrl("about:blank"),
    )
    app.exec()
    return 0 if result["ok"] else 1
