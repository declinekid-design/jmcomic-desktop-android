from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def detect_system_theme(app: QApplication) -> str:
    try:
        if app.styleHints().colorScheme() == Qt.ColorScheme.Dark:
            return "dark"
    except (AttributeError, TypeError):
        pass
    return "light"


def resolve_theme(app: QApplication, theme: str) -> str:
    if theme == "dark":
        return "dark"
    if theme == "light":
        return "light"
    return detect_system_theme(app)


def _palette(theme: str) -> QPalette:
    dark = theme == "dark"
    colors = {
        "window": "#0f141b" if dark else "#eef1f4",
        "window_text": "#edf2f7" if dark else "#172033",
        "base": "#151b24" if dark else "#ffffff",
        "alternate": "#1b232e" if dark else "#f4f6f8",
        "text": "#edf2f7" if dark else "#172033",
        "button": "#1b232e" if dark else "#ffffff",
        "button_text": "#edf2f7" if dark else "#172033",
        "highlight": "#0d9488" if dark else "#0f766e",
        "highlighted_text": "#ffffff",
        "tooltip_base": "#edf2f7" if dark else "#172033",
        "tooltip_text": "#111827" if dark else "#ffffff",
        "placeholder": "#8c98a8" if dark else "#7a8698",
        "disabled_text": "#667085",
    }

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(colors["window"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["window_text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(colors["base"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["alternate"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(colors["button"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["button_text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["highlight"]))
    palette.setColor(
        QPalette.ColorRole.HighlightedText,
        QColor(colors["highlighted_text"]),
    )
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(colors["tooltip_base"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(colors["tooltip_text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(colors["placeholder"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(colors["highlight"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ff5c5c"))
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor(colors["disabled_text"]),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(colors["disabled_text"]),
    )
    return palette


def _stylesheet(theme: str) -> str:
    dark = theme == "dark"
    c = {
        "window": "#0f141b" if dark else "#eef1f4",
        "panel": "#151b24" if dark else "#ffffff",
        "input": "#1b232e" if dark else "#ffffff",
        "hover": "#232d39" if dark else "#f7f9fa",
        "text": "#edf2f7" if dark else "#172033",
        "muted": "#a2adbb" if dark else "#667085",
        "border": "#303a48" if dark else "#d5dbe3",
        "disabled": "#1c232c" if dark else "#e9edf1",
        "disabled_text": "#667085" if dark else "#98a2b3",
        "primary": "#0d9488" if dark else "#0f766e",
        "primary_hover": "#14b8a6" if dark else "#115e59",
        "primary_disabled": "#41615e" if dark else "#9ab7b3",
        "progress": "#27313d" if dark else "#dfe5eb",
        "tooltip": "#edf2f7" if dark else "#172033",
        "tooltip_text": "#111827" if dark else "#ffffff",
    }
    return f"""
        QWidget {{
            color: {c["text"]};
            background: transparent;
        }}
        QWidget#central, QMainWindow {{
            background: {c["window"]};
        }}
        QDialog {{
            background: {c["panel"]};
        }}
        QFrame#header {{
            background: {c["panel"]};
            border-bottom: 1px solid {c["border"]};
        }}
        QFrame#settingsPanel, QFrame#logPanel {{
            background: {c["panel"]};
            border: 1px solid {c["border"]};
            border-radius: 8px;
        }}
        QLabel#title {{
            color: {c["text"]};
            font-size: 22px;
            font-weight: 700;
        }}
        QLabel#subtitle, QLabel#fieldHint {{
            color: {c["muted"]};
            font-size: 12px;
        }}
        QLabel#section {{
            color: {c["text"]};
            font-size: 15px;
            font-weight: 700;
        }}
        QLabel#notice {{
            color: {c["muted"]};
            background: {c["hover"]};
            border: 1px solid {c["border"]};
            border-radius: 5px;
            padding: 7px 9px;
            font-size: 12px;
        }}
        QLabel#status {{
            color: {c["text"]};
            font-size: 12px;
        }}
        QScrollArea {{
            border: 0;
            background: transparent;
        }}
        QScrollArea > QWidget > QWidget {{
            background: transparent;
        }}
        QLineEdit, QComboBox, QSpinBox {{
            background: {c["input"]};
            color: {c["text"]};
            border: 1px solid {c["border"]};
            border-radius: 5px;
            min-height: 30px;
            padding: 0 8px;
            selection-background-color: {c["primary"]};
            selection-color: #ffffff;
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
            border: 1px solid {c["primary"]};
        }}
        QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{
            background: {c["disabled"]};
            color: {c["disabled_text"]};
        }}
        QComboBox::drop-down {{
            border: 0;
            width: 26px;
        }}
        QComboBox QAbstractItemView {{
            background: {c["panel"]};
            color: {c["text"]};
            border: 1px solid {c["border"]};
            selection-background-color: {c["primary"]};
            selection-color: #ffffff;
            outline: 0;
        }}
        QPushButton {{
            background: {c["input"]};
            color: {c["text"]};
            border: 1px solid {c["border"]};
            border-radius: 5px;
            min-height: 30px;
            padding: 0 12px;
        }}
        QPushButton:hover {{
            background: {c["hover"]};
            border-color: {c["muted"]};
        }}
        QPushButton:disabled {{
            background: {c["disabled"]};
            color: {c["disabled_text"]};
            border-color: {c["border"]};
        }}
        QPushButton#primary {{
            background: {c["primary"]};
            color: #ffffff;
            border: 1px solid {c["primary"]};
            font-weight: 700;
            min-height: 36px;
            padding: 0 18px;
        }}
        QPushButton#primary:hover {{
            background: {c["primary_hover"]};
            border-color: {c["primary_hover"]};
        }}
        QPushButton#primary:disabled {{
            background: {c["primary_disabled"]};
            border-color: {c["primary_disabled"]};
        }}
        QPlainTextEdit {{
            background: {c["input"]};
            color: {c["text"]};
            border: 0;
            selection-background-color: {c["primary"]};
            selection-color: #ffffff;
        }}
        QTextBrowser {{
            background: {c["input"]};
            color: {c["text"]};
            border: 0;
            selection-background-color: {c["primary"]};
            selection-color: #ffffff;
        }}
        QTabWidget::pane {{
            border: 0;
            background: transparent;
        }}
        QTabBar::tab {{
            background: {c["window"]};
            color: {c["muted"]};
            border: 0;
            padding: 7px 12px;
            margin-right: 4px;
        }}
        QTabBar::tab:selected {{
            color: {c["text"]};
            border-bottom: 2px solid {c["primary"]};
        }}
        QTabBar::tab:hover {{
            color: {c["text"]};
        }}
        QProgressBar {{
            background: {c["progress"]};
            border: 0;
            border-radius: 5px;
        }}
        QProgressBar::chunk {{
            background: {c["primary"]};
            border-radius: 5px;
        }}
        QCheckBox {{
            color: {c["text"]};
            spacing: 7px;
        }}
        QToolTip {{
            background: {c["tooltip"]};
            color: {c["tooltip_text"]};
            border: 0;
            padding: 5px;
        }}
        QMessageBox {{
            background: {c["panel"]};
        }}
        QMessageBox QLabel {{
            color: {c["text"]};
        }}
        QMenu {{
            background: {c["panel"]};
            color: {c["text"]};
            border: 1px solid {c["border"]};
        }}
        QMenu::item:selected {{
            background: {c["primary"]};
            color: #ffffff;
        }}
    """


def apply_theme(app: QApplication, theme: str) -> str:
    resolved = resolve_theme(app, theme)
    app.setPalette(_palette(resolved))
    app.setStyleSheet(_stylesheet(resolved))
    return resolved
