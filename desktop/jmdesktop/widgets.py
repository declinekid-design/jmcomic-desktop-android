from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class SettingField(QWidget):
    def __init__(
        self,
        label: str,
        control: QWidget,
        hint: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        label_widget = QLabel(label)
        label_widget.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        hint_widget = QLabel(hint)
        hint_widget.setObjectName("fieldHint")
        hint_widget.setWordWrap(True)

        layout.addWidget(label_widget)
        layout.addWidget(control)
        layout.addWidget(hint_widget)

    def set_hint(self, hint: str) -> None:
        labels = self.findChildren(QLabel, "fieldHint")
        if labels:
            labels[0].setText(hint)
