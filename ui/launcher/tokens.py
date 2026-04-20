"""
ui/launcher/tokens.py
Launcher design tokens for the calm productivity shell.
"""

# Color palette
PRIMARY = "#c96a2b"
PRIMARY_DIM = "#a85720"
SECONDARY = "#2f6f7a"
TERTIARY = "#4662c7"
ERROR = "#b74942"
GREEN = "#2c7b59"

BG = "#f4efe7"
BG0 = "#fffdf8"
BG1 = "#efe7da"
BG2 = "#e5d8c6"
BG3 = "#d5c4ae"
BG4 = "#18202a"

TEXT = "#1f252d"
DIM = "#6e665f"
BORDER = "#d6c5ae"

ART_RED = "#ff6d43"
ART_GOLD = "#f4a83d"
ART_PINK = "#ef72c8"
ART_PLUM = "#8365ff"
ART_BLUE = "#4567ff"
ART_SKY = "#bcd2ff"
INK = "#16202b"

SHADOW = "rgba(29, 28, 26, 0.10)"

# Stitch-guided warm sand surface system
SAND_0 = "#FBF9F4"   # warmest light surface (near-white with warmth)
SAND_1 = "#F5F3EE"   # default warm surface
SAND_2 = "#EDE9E1"   # card/panel surface
SAND_3 = "#E0DBD1"   # subtle divider/border

# Accent system (turquoise + sunset orange — aligns with existing primary/secondary)
ACCENT_TEAL   = "#2f6f7a"   # existing secondary, now named explicitly
ACCENT_ORANGE = "#c96a2b"   # existing primary, now named explicitly
ACCENT_GLOW   = "#e8935a"   # warm sunset highlight (lighter orange glow)

# Gradient definitions for QSS use
GRADIENT_SUNSET = "qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #2f6f7a,stop:1 #c96a2b)"
GRADIENT_SAND   = "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #FBF9F4,stop:1 #EDE9E1)"

# Typography — add serif headline pairing
FONT_SERIF = "Georgia"   # editorial headline serif (Noto Serif fallback)

# Typography
FF_HEAD = "Cambria"
FF_MONO = "Cascadia Mono"
FF_BODY = "Bahnschrift"

FS_TINY = 8
FS_SMALL = 9
FS_BODY = 10
FS_LABEL = 11
FS_TITLE = 14
FS_HERO = 22

# Layout
SIDEBAR_W_COLLAPSED = 74
SIDEBAR_W_EXPANDED = 132
SIDEBAR_W = SIDEBAR_W_EXPANDED
TOPBAR_H = 66
STATUS_W = 236
