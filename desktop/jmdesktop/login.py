from __future__ import annotations

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)


class LoginWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, option, username: str, password: str):
        super().__init__()
        self.option = option
        self.username = username
        self.password = password

    def run(self) -> None:
        try:
            client = self.option.build_jm_client()
            client.login(self.username, self.password)
            cookies = {
                str(key): str(value)
                for key, value in dict(client["cookies"]).items()
            }
            if not cookies:
                raise RuntimeError("登录成功，但服务器没有返回会话。")
            self.succeeded.emit(cookies)
        except BaseException as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)


class LoginDialog(QDialog):
    def __init__(
        self,
        option,
        username: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("loginDialog")
        self.setWindowTitle("登录 JMComic")
        self.setModal(True)
        self.setMinimumWidth(430)
        self.option = option
        self.worker: LoginWorker | None = None
        self.cookies: dict[str, str] = {}
        self.username = username
        self.persist = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        heading = QLabel("登录后，查询和下载会使用你的账号会话。")
        heading.setObjectName("section")
        layout.addWidget(heading)

        hint = QLabel(
            "密码只用于本次登录，不会保存。勾选保持登录时，仅将服务器返回的会话"
            "加密后保存到程序目录 data/session.bin；优先使用 Windows DPAPI。"
        )
        hint.setObjectName("fieldHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setSpacing(9)
        self.username_input = QLineEdit(username)
        self.username_input.setPlaceholderText("账号或邮箱")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("密码")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._submit)
        form.addRow("账号", self.username_input)
        form.addRow("密码", self.password_input)
        layout.addLayout(form)

        self.remember_check = QCheckBox("保持登录")
        self.remember_check.setChecked(True)
        layout.addWidget(self.remember_check)

        self.status_label = QLabel("")
        self.status_label.setObjectName("fieldHint")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.buttons = QDialogButtonBox()
        self.login_button = self.buttons.addButton(
            "登录",
            QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self.cancel_button = self.buttons.addButton(
            "取消",
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        self.login_button.clicked.connect(self._submit)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.buttons)

        self.username_input.setFocus()

    def _set_busy(self, busy: bool) -> None:
        self.username_input.setEnabled(not busy)
        self.password_input.setEnabled(not busy)
        self.remember_check.setEnabled(not busy)
        self.login_button.setEnabled(not busy)
        self.cancel_button.setEnabled(not busy)

    def _submit(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not username:
            QMessageBox.warning(self, "无法登录", "请输入账号。")
            self.username_input.setFocus()
            return
        if not password:
            QMessageBox.warning(self, "无法登录", "请输入密码。")
            self.password_input.setFocus()
            return

        self._set_busy(True)
        self.status_label.setText("正在登录，请稍候...")
        self.worker = LoginWorker(self.option, username, password)
        self.worker.succeeded.connect(
            lambda cookies: self._on_success(username, cookies)
        )
        self.worker.failed.connect(self._on_failure)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_success(
        self,
        username: str,
        cookies: dict[str, str],
    ) -> None:
        self.cookies = cookies
        self.username = username
        self.persist = self.remember_check.isChecked()
        self.password_input.clear()
        self.accept()

    def _on_failure(self, message: str) -> None:
        self._set_busy(False)
        self.status_label.setText(message)
        QMessageBox.critical(self, "登录失败", message)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.status_label.setText("登录请求正在处理中，请稍候。")
            event.ignore()
            return
        self.password_input.clear()
        event.accept()
