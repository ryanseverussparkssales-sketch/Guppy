"""
ui/launcher/tokens.py
OBSIDIAN design tokens — single source of truth for all launcher UI colors,
fonts, and spacing.  Matches the Stitch / Material-You export.
"""

# ── Color palette ──────────────────────────────────────────────────────────────
PRIMARY      = "#f2ca50"   # gold accent
PRIMARY_DIM  = "#d4af37"   # dimmed gold / primary-container
SECONDARY    = "#d2bbff"   # lavender — Merlin accent
TERTIARY     = "#97b0ff"   # blue     — Council accent
ERROR        = "#ffb4ab"   # offline / error
GREEN        = "#4caf50"   # online / active

BG           = "#131313"   # surface / background base
BG0          = "#0e0e0e"   # surface-container-lowest
BG1          = "#1c1b1b"   # surface-container-low
BG2          = "#201f1f"   # surface-container
BG3          = "#2a2a2a"   # surface-container-high
BG4          = "#353534"   # surface-container-highest

TEXT         = "#e5e2e1"   # on-surface
DIM          = "#99907c"   # outline  (dim / secondary text)
BORDER       = "#4d4635"   # outline-variant (dividers)

# ── Typography ─────────────────────────────────────────────────────────────────
FF_HEAD  = "Segoe UI"   # Space Grotesk equivalent
FF_MONO  = "Consolas"   # JetBrains Mono equivalent
FF_BODY  = "Segoe UI"

FS_TINY  =  7
FS_SMALL =  8
FS_BODY  =  9
FS_LABEL = 10
FS_TITLE = 11
FS_HERO  = 16

# ── Layout ─────────────────────────────────────────────────────────────────────
SIDEBAR_W = 160
TOPBAR_H  =  52
STATUS_W  = 260
