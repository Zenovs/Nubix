"""Centralized dark theme for Nubix."""

from __future__ import annotations

# ── Palette ───────────────────────────────────────────────────────────────────
BG = "#0D0D14"
SURFACE = "#161625"
CARD = "#1E1E32"
CARD_HOVER = "#252542"
CARD_BORDER = "#2E2E50"

ACCENT = "#7C5CFC"
ACCENT_HOVER = "#9070FF"
ACCENT_PRESSED = "#6040E0"

TEXT = "#E2E2F0"
TEXT_MUTED = "#8888AA"
TEXT_DISABLED = "#4A4A6A"

SUCCESS = "#4ADE80"
SUCCESS_BG = "#0D2A1A"
WARNING = "#FB923C"
WARNING_BG = "#2A1500"
ERROR = "#F87171"
ERROR_BG = "#2A0A0A"
INFO = "#60A5FA"
INFO_BG = "#0A1A30"
IDLE = "#6B7280"
IDLE_BG = "#1A1A2A"

SEPARATOR = "#1E1E38"

# ── Global stylesheet ──────────────────────────────────────────────────────────
STYLESHEET = f"""
/* ── Base ── */
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-family: "Segoe UI", "Ubuntu", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background-color: {BG};
}}

/* ── Scroll bars ── */
QScrollArea, QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: {SURFACE};
    width: 6px;
    border-radius: 3px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {CARD_BORDER};
    border-radius: 3px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
QScrollBar:horizontal {{
    background: {SURFACE};
    height: 6px;
    border-radius: 3px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: {CARD_BORDER};
    border-radius: 3px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Buttons ── */
QPushButton {{
    background-color: {ACCENT};
    color: #FFFFFF;
    border: none;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: 600;
    font-size: 13px;
}}
QPushButton:hover {{ background-color: {ACCENT_HOVER}; }}
QPushButton:pressed {{ background-color: {ACCENT_PRESSED}; }}
QPushButton:disabled {{
    background-color: {CARD};
    color: {TEXT_DISABLED};
}}
QPushButton[secondary="true"] {{
    background-color: {CARD};
    color: {TEXT};
    border: 1px solid {CARD_BORDER};
}}
QPushButton[secondary="true"]:hover {{
    background-color: {CARD_HOVER};
    border-color: {ACCENT};
}}
QPushButton[flat="true"] {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 4px 8px;
}}
QPushButton[flat="true"]:hover {{
    background: {CARD};
    color: {TEXT};
}}
QPushButton[danger="true"] {{
    background-color: {ERROR_BG};
    color: {ERROR};
    border: 1px solid {ERROR};
}}
QPushButton[danger="true"]:hover {{
    background-color: {ERROR};
    color: white;
}}

/* ── Inputs ── */
QLineEdit, QSpinBox, QDoubleSpinBox, QTimeEdit {{
    background: {CARD};
    border: 1px solid {CARD_BORDER};
    border-radius: 8px;
    padding: 7px 12px;
    color: {TEXT};
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTimeEdit:focus {{
    border-color: {ACCENT};
    background: {CARD_HOVER};
}}
QLineEdit:disabled, QSpinBox:disabled {{
    color: {TEXT_DISABLED};
    background: {SURFACE};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QTimeEdit::up-button, QTimeEdit::down-button {{
    background: {CARD_BORDER};
    border: none;
    border-radius: 4px;
    width: 16px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover,
QTimeEdit::up-button:hover, QTimeEdit::down-button:hover {{
    background: {ACCENT};
}}

/* ── ComboBox ── */
QComboBox {{
    background: {CARD};
    border: 1px solid {CARD_BORDER};
    border-radius: 8px;
    padding: 7px 12px;
    color: {TEXT};
}}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background: {CARD};
    border: 1px solid {CARD_BORDER};
    border-radius: 8px;
    selection-background-color: {ACCENT};
    color: {TEXT};
    padding: 4px;
}}

/* ── CheckBox ── */
QCheckBox {{
    color: {TEXT};
    spacing: 10px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {CARD_BORDER};
    border-radius: 5px;
    background: transparent;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QCheckBox::indicator:hover {{ border-color: {ACCENT}; }}

/* ── Progress bar ── */
QProgressBar {{
    border: none;
    border-radius: 4px;
    background: {CARD_BORDER};
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    border-radius: 4px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {ACCENT}, stop:1 {ACCENT_HOVER});
}}

/* ── Tabs ── */
QTabWidget::pane {{
    border: 1px solid {CARD_BORDER};
    border-radius: 10px;
    background: {SURFACE};
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXT_MUTED};
    padding: 9px 22px;
    border: none;
    margin-right: 2px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {TEXT};
    border-bottom: 2px solid {ACCENT};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{ color: {TEXT}; }}

/* ── Splitter ── */
QSplitter::handle {{ background: {SEPARATOR}; }}

/* ── Text areas ── */
QTextEdit, QPlainTextEdit {{
    background: {SURFACE};
    border: 1px solid {CARD_BORDER};
    border-radius: 8px;
    color: {TEXT};
    selection-background-color: {ACCENT};
    font-family: "JetBrains Mono", "Fira Code", "Cascadia Code", monospace;
    font-size: 12px;
}}

/* ── Menu ── */
QMenuBar {{
    background: {BG};
    color: {TEXT};
    border-bottom: 1px solid {SEPARATOR};
}}
QMenuBar::item:selected {{ background: {CARD}; border-radius: 4px; }}
QMenu {{
    background: {CARD};
    border: 1px solid {CARD_BORDER};
    border-radius: 8px;
    color: {TEXT};
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 20px;
    border-radius: 5px;
}}
QMenu::item:selected {{ background: {ACCENT}; color: white; }}
QMenu::separator {{
    height: 1px;
    background: {SEPARATOR};
    margin: 4px 8px;
}}

/* ── Tooltip ── */
QToolTip {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {CARD_BORDER};
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
}}

/* ── Slider ── */
QSlider::groove:horizontal {{
    background: {CARD_BORDER};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{ background: {ACCENT_HOVER}; }}
QSlider::sub-page:horizontal {{
    background: {ACCENT};
    border-radius: 2px;
}}

/* ── List widget ── */
QListWidget {{
    background: transparent;
    border: none;
    outline: none;
    color: {TEXT};
}}
QListWidget::item {{
    padding: 10px 14px;
    border-radius: 8px;
    margin: 2px 6px;
}}
QListWidget::item:selected {{
    background: {ACCENT};
    color: white;
}}
QListWidget::item:hover:!selected {{
    background: {CARD};
}}

/* ── Group box ── */
QGroupBox {{
    border: 1px solid {CARD_BORDER};
    border-radius: 10px;
    margin-top: 16px;
    padding: 12px 8px 8px 8px;
    font-weight: 600;
    color: {TEXT_MUTED};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 12px;
}}

/* ── Sync card ── */
QFrame#SyncStatusCard {{
    background: {CARD};
    border: 1px solid {CARD_BORDER};
    border-radius: 14px;
}}
QFrame#SyncStatusCard:hover {{
    border-color: {ACCENT};
    background: {CARD_HOVER};
}}

/* ── Label ── */
QLabel {{ background: transparent; color: {TEXT}; }}
"""
