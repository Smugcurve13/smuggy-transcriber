"""Green-on-black design language for SmuggyTranscriber.

Palette, fonts and the global Qt stylesheet, lifted from the redesign
concept (Space Grotesk + JetBrains Mono, bright green accent on near-black).
"""

import os
import sys

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QLabel

# --- palette -------------------------------------------------------------
BG = "#0d0f0e"          # outermost background
SURFACE = "#0f1311"     # the app "card"
SURFACE_2 = "#121613"   # inner panels (drop zone, transcript, result)
INPUT_BG = "#1a201c"
BTN_BG = "#151a17"
BORDER = "#232b26"
BORDER_2 = "#2c352f"
BORDER_HI = "#3a463e"
DIVIDER = "#1c231e"

TEXT = "#e8efe9"        # primary
TEXT_2 = "#c4d0c8"      # step / button text
TEXT_3 = "#9fb0a4"      # secondary
MUTED = "#6b7a70"       # captions
DISABLED = "#566058"
BODY = "#d4ddd6"        # transcript body

ACCENT = "#3ee07e"      # primary green
ACCENT_HI = "#4cec88"   # brighter green (links / numbers)
ACCENT_DEEP = "#22c06a"  # gradient bottom
ON_ACCENT = "#07140c"   # text on a green fill

SANS = "Space Grotesk"
MONO = "JetBrains Mono"


def _asset_dir():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets")


def load_fonts():
    """Register the bundled Space Grotesk / JetBrains Mono families."""
    fonts_dir = os.path.join(_asset_dir(), "fonts")
    if not os.path.isdir(fonts_dir):
        return
    for name in sorted(os.listdir(fonts_dir)):
        if name.lower().endswith((".ttf", ".otf")):
            QFontDatabase.addApplicationFont(os.path.join(fonts_dir, name))


def logo_path():
    return os.path.join(_asset_dir(), "logo.png")


def font(family=SANS, px=14, weight=QFont.Normal, spacing=0.0):
    f = QFont(family)
    f.setPixelSize(px)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


def label(text, *, family=SANS, px=14, weight=QFont.Normal, color=TEXT_2,
          spacing=0.0, upper=False, wrap=False):
    lbl = QLabel(text.upper() if upper else text)
    lbl.setFont(font(family, px, weight, spacing))
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    lbl.setWordWrap(wrap)
    return lbl


STYLESHEET = f"""
QWidget {{
    background: {SURFACE};
    color: {TEXT_2};
    font-family: "{SANS}";
    font-size: 14px;
}}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 2px 2px 2px 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_2}; border-radius: 5px; min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: {BORDER_HI}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QLabel {{ background: transparent; color: {TEXT_2}; }}

QFrame#card {{ background: {SURFACE}; }}
QFrame#panel {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 12px;
}}
QFrame#dropzone {{
    background: {SURFACE_2}; border: 2px dashed {BORDER_2}; border-radius: 16px;
}}
QFrame#chip {{
    background: {BTN_BG}; border: 1px solid {BORDER_2}; border-radius: 10px;
}}

QLineEdit {{
    background: {INPUT_BG};
    border: 1px solid {BORDER_2};
    border-radius: 10px;
    padding: 0 14px;
    min-height: 44px;
    color: {TEXT};
    font-family: "{MONO}";
    font-size: 14px;
    selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
}}
QLineEdit:focus {{ border: 1px solid {ACCENT}; }}

QPlainTextEdit {{
    background: {SURFACE_2};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 12px 14px;
    color: {BODY};
    font-family: "{SANS}";
    font-size: 15px;
    selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
}}

QPushButton {{
    background: {BTN_BG};
    border: 1px solid {BORDER_2};
    border-radius: 10px;
    padding: 0 18px;
    min-height: 44px;
    color: {TEXT_2};
    font-family: "{SANS}";
    font-size: 14px;
    font-weight: 600;
}}
QPushButton:hover {{ border: 1px solid {BORDER_HI}; background: #181e1a; }}
QPushButton:disabled {{
    background: {INPUT_BG}; border: 1px solid {BORDER}; color: {DISABLED};
}}

QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
                stop:0 {ACCENT_HI}, stop:1 {ACCENT_DEEP});
    border: none; color: {ON_ACCENT}; font-weight: 700;
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0.5, y2:1,
                stop:0 #5cf396, stop:1 #28cc72);
}}
QPushButton#primary:disabled {{
    background: {INPUT_BG}; border: 1px solid {BORDER}; color: {DISABLED};
}}

QPushButton#link {{
    background: transparent; border: none; color: {MUTED};
    font-weight: 500; font-size: 13px; padding: 0 4px; min-height: 0;
}}
QPushButton#link:hover {{ color: {TEXT_3}; background: transparent; border: none; }}

QComboBox {{
    background: {BTN_BG}; border: 1px solid {BORDER_2}; border-radius: 10px;
    padding: 0 14px; min-height: 44px; color: {TEXT_2}; font-weight: 500;
}}
QComboBox:hover {{ border: 1px solid {BORDER_HI}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {BTN_BG}; border: 1px solid {BORDER_2}; border-radius: 8px;
    color: {TEXT_2}; padding: 4px;
    selection-background-color: #1f2723; selection-color: {TEXT};
    outline: none;
}}

QProgressBar {{
    background: #161b18; border: none; border-radius: 3px; max-height: 6px;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 3px; }}

QToolTip {{
    background: {BTN_BG}; color: {TEXT_2}; border: 1px solid {BORDER_2};
    padding: 4px 8px;
}}
QMessageBox {{ background: {SURFACE}; }}
QMessageBox QLabel {{ color: {TEXT_2}; background: transparent; }}
"""


def apply(app):
    """Load fonts and apply the global theme to a QApplication."""
    load_fonts()
    base = font(SANS, 14)
    app.setFont(base)
    app.setStyleSheet(STYLESHEET)
