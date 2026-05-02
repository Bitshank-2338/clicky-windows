from PyQt6.QtGui import QColor, QFont

# ── Palette ───────────────────────────────────────────────────────────────────
BLUE_GLOW       = QColor(0, 120, 255)
BLUE_GLOW_DIM   = QColor(0, 80, 200, 160)
SURFACE         = QColor(18, 18, 22)
SURFACE_RAISED  = QColor(28, 28, 34)
BORDER          = QColor(60, 60, 75)
TEXT_PRIMARY    = QColor(240, 240, 245)
TEXT_SECONDARY  = QColor(140, 140, 160)
TEXT_MUTED      = QColor(80, 80, 100)
SUCCESS         = QColor(50, 200, 100)
WARNING         = QColor(255, 180, 0)
ERROR           = QColor(255, 70, 70)

# State colors
STATE_IDLE      = QColor(80, 80, 100)
STATE_LISTENING = QColor(50, 200, 100)
STATE_THINKING  = QColor(0, 120, 255)
STATE_SPEAKING  = QColor(255, 140, 0)

# ── Fonts ─────────────────────────────────────────────────────────────────────
def font(size: int = 13, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont("Segoe UI", size)
    f.setWeight(weight)
    return f

FONT_LABEL    = font(12)
FONT_STATUS   = font(13, QFont.Weight.Medium)
FONT_TITLE    = font(15, QFont.Weight.Bold)
FONT_RESPONSE = font(13)

# ── Geometry ──────────────────────────────────────────────────────────────────
PANEL_WIDTH   = 340
PANEL_HEIGHT  = 480
PANEL_RADIUS  = 16
CURSOR_RADIUS = 18

# ── Animation ────────────────────────────────────────────────────────────────
ANIM_FAST_MS  = 150
ANIM_SLOW_MS  = 400
CURSOR_ANIM_MS = 600

# ── Stylesheets ───────────────────────────────────────────────────────────────
PANEL_QSS = f"""
QWidget#panel {{
    background-color: rgba(18, 18, 22, 235);
    border: 1px solid rgba(60, 60, 75, 180);
    border-radius: {PANEL_RADIUS}px;
}}
QLabel {{
    color: rgb(240, 240, 245);
    background: transparent;
}}
QLabel#title {{
    font-size: 15px;
    font-weight: bold;
    color: rgb(240, 240, 245);
}}
QLabel#status {{
    font-size: 12px;
    color: rgb(140, 140, 160);
}}
QLabel#response {{
    font-size: 13px;
    color: rgb(220, 220, 230);
    padding: 8px;
}}
QPushButton#hotkey_btn {{
    background-color: rgba(0, 120, 255, 30);
    border: 1.5px solid rgba(0, 120, 255, 180);
    border-radius: 10px;
    color: rgb(240, 240, 245);
    font-size: 13px;
    font-weight: 600;
    padding: 10px 20px;
}}
QPushButton#hotkey_btn:hover {{
    background-color: rgba(0, 120, 255, 60);
}}
QPushButton#hotkey_btn:pressed {{
    background-color: rgba(0, 120, 255, 100);
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 4px;
}}
QScrollBar::handle:vertical {{
    background: rgba(100, 100, 120, 120);
    border-radius: 2px;
}}
"""

WAVEFORM_QSS = """
QWidget#waveform {
    background: transparent;
}
"""
