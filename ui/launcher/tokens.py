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
DIM = "#5f574f"
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

# Quiet-hierarchy surfaces (bounded PL-C2 pass)
SURFACE_BASE = SAND_1
SURFACE_ELEVATED = SAND_0
SURFACE_PANEL = SAND_2
BORDER_SOFT = "rgba(224,219,209,0.85)"
BORDER_STRONG = "rgba(214,197,174,0.90)"

# Launcher chrome warm-sand alpha system
SURFACE_BASE_90 = "rgba(245,243,238,0.90)"
SURFACE_BASE_88 = "rgba(245,243,238,0.88)"
SURFACE_BASE_84 = "rgba(245,243,238,0.84)"
SURFACE_BASE_82 = "rgba(245,243,238,0.82)"
SURFACE_BASE_72 = "rgba(245,243,238,0.72)"
SURFACE_ELEVATED_92 = "rgba(251,249,244,0.92)"
SURFACE_ELEVATED_88 = "rgba(251,249,244,0.88)"
SURFACE_ELEVATED_86 = "rgba(251,249,244,0.86)"
SURFACE_ELEVATED_78 = "rgba(251,249,244,0.78)"
SURFACE_ELEVATED_72 = "rgba(251,249,244,0.72)"
SURFACE_ELEVATED_68 = "rgba(251,249,244,0.68)"
SURFACE_ELEVATED_45 = "rgba(251,249,244,0.45)"

BORDER_SOFT_72 = "rgba(224,219,209,0.72)"
BORDER_SOFT_68 = "rgba(224,219,209,0.68)"
BORDER_SOFT_64 = "rgba(224,219,209,0.64)"
BORDER_SOFT_62 = "rgba(224,219,209,0.62)"
BORDER_SOFT_60 = "rgba(224,219,209,0.60)"
BORDER_SOFT_58 = "rgba(224,219,209,0.58)"
BORDER_SOFT_54 = "rgba(224,219,209,0.54)"
BORDER_SOFT_48 = "rgba(224,219,209,0.48)"

BORDER_MID_35 = "rgba(214,197,174,0.35)"
BORDER_MID_30 = "rgba(214,197,174,0.30)"
BORDER_MID_22 = "rgba(214,197,174,0.22)"

TEXT_DIM_72 = "rgba(115,96,79,0.72)"
TEXT_DIM_78 = "rgba(115,96,79,0.78)"
TEXT_INVERSE_92 = "rgba(255,255,255,0.92)"
TEXT_INVERSE_88 = "rgba(255,255,255,0.88)"

WHITE = "#ffffff"
WHITE_SOFT = "#fff7f2"

HOVER_TERTIARY_SOFT = "rgba(70,98,199,0.08)"
HOVER_TERTIARY_MED = "rgba(70,98,199,0.46)"
HOVER_PRIMARY_SOFT = "rgba(201,106,43,0.08)"
HOVER_PRIMARY_MED = "rgba(201,106,43,0.14)"

# Accent system (turquoise + sunset orange — aligns with existing primary/secondary)
ACCENT_TEAL   = "#2f6f7a"   # existing secondary, now named explicitly
ACCENT_ORANGE = "#c96a2b"   # existing primary, now named explicitly
ACCENT_GLOW   = "#e8935a"   # warm sunset highlight (lighter orange glow)
ACCENT_TEAL_TEXT = "#295963"   # darker teal for active labels on light sand
ACCENT_ORANGE_TEXT = "#8f4c20"   # darker orange for small text on warm sand

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
