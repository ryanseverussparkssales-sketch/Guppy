"""
guppy_theme.py — Centralized palette and display settings for all Guppy UIs.

To customize, edit theme.json in the same directory and restart any UI.
All fields are optional — missing values fall back to built-in defaults.
"""
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime


@dataclass
class PersonaTheme:
    accent: str
    bg: str
    bg2: str
    bg3: str
    text: str
    dim: str
    border: str
    user_label: str = "Master Ryan"


@dataclass
class SharedTheme:
    font_family: str  = "Segoe UI"
    font_family_mono: str = "Consolas"
    font_size: int    = 10
    font_size_small: int = 8
    font_size_title: int = 22
    timestamp_font_size: int = 6
    sidebar_label_font_size: int = 7
    sidebar_width: int = 240
    bubble_radius: int = 6
    panel_radius: int = 6
    spacing_xs: int = 4
    spacing_sm: int = 8
    spacing_md: int = 12
    spacing_lg: int = 16
    control_height_sm: int = 30
    control_height_md: int = 34
    control_height_lg: int = 42
    show_timestamps: bool = True
    orb_min_size: int = 160


_GUPPY_DEFAULTS = PersonaTheme(
    accent     = "#00c8ff",
    bg         = "#07070f",
    bg2        = "#0a0a14",
    bg3        = "#111122",
    text       = "#d0d0e0",
    dim        = "#404060",
    border     = "#1a1a2e",
    user_label = "Master Ryan",
)

_MERLIN_DEFAULTS = PersonaTheme(
    accent     = "#c9a84c",
    bg         = "#0a0612",
    bg2        = "#0e0a1a",
    bg3        = "#110d1e",
    text       = "#e8dcc8",
    dim        = "#6b5e4a",
    border     = "#2a1f3d",
    user_label = "Apprentice",
)


def _merge_persona(defaults: PersonaTheme, overrides: dict) -> PersonaTheme:
    d = asdict(defaults)
    d.update({k: v for k, v in overrides.items() if k in d})
    return PersonaTheme(**d)


def _merge_shared(overrides: dict) -> SharedTheme:
    d = asdict(SharedTheme())
    d.update({k: v for k, v in overrides.items() if k in d})
    return SharedTheme(**d)


def load_theme() -> tuple[PersonaTheme, PersonaTheme, SharedTheme]:
    """Returns (guppy_theme, merlin_theme, shared_theme)."""
    theme_path = Path(__file__).parent / "theme.json"
    overrides: dict = {}
    if theme_path.exists():
        try:
            overrides = json.loads(theme_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    guppy  = _merge_persona(_GUPPY_DEFAULTS,  overrides.get("guppy",  {}))
    merlin = _merge_persona(_MERLIN_DEFAULTS, overrides.get("merlin", {}))
    shared = _merge_shared(overrides.get("shared", {}))
    return guppy, merlin, shared


# Module-level singletons — imported directly by each UI
GUPPY_THEME, MERLIN_THEME, SHARED = load_theme()


def now_str() -> str:
    """Current time as HH:MM — used for message timestamps."""
    return datetime.now().strftime("%H:%M")
