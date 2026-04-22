"""
tokens_enforcement.py

Extracted from: ui/launcher/launcher_window.py refactoring
Purpose: Enforce design tokens and Stitch-aligned choices, eliminate color drift
Lane: TR54-B12

Design Direction Constraints (Locked):
  1. Warm-sand neutral base (SAND_0 through SAND_3)
  2. Restrained blue/orange accent system (ACCENT_TEAL, ACCENT_ORANGE)
  3. Editorial serif typography for headings only (FF_SERIF/FF_HEAD)
  4. Chat-first home layout (no competing chrome)
  5. Five-hub information architecture (Home, Models, Tools, Library, Settings)
  6. Responsive behavior with strict hide/show rules for narrow widths
  7. Progressive disclosure over always-open dense panels
  8. Simple, literal control copy (action-oriented, avoid ambiguous labels)

Color Palette (Stitch-Aligned):
  - SAND_0: #FBF9F4 (warmest light surface)
  - SAND_1: #F5F3EE (default warm surface)
  - SAND_2: #EDE9E1 (card/panel surface)
  - SAND_3: #E0DBD1 (subtle divider/border)
  - ACCENT_TEAL: #2f6f7a (secondary accent)
  - ACCENT_ORANGE: #c96a2b (primary accent)
  - TEXT: #1f252d (body text)
  - DIM: #5f574f (secondary text)
  - BORDER: #d6c5ae (border color)

Typography Rules:
  - Headings: FF_SERIF/FF_HEAD (Georgia/Cambria) - editorial feel
  - Body: FF_BODY (Bahnschrift) - plain, readable
  - Mono: FF_MONO (Cascadia Mono) - evidence, code, data
  - No decorative fonts; preserve readability
  - Size hierarchy: FS_TINY (8) → FS_SMALL (9) → FS_BODY (10) → FS_LABEL (11) → FS_TITLE (14) → FS_HERO (22)

Enforcement Rules:

1. COLOR USAGE
   ✓ Always use tokens (tokens.py) — never hardcode colors
   ✓ Use SAND_* for surfaces, never #FFFFFF for main bg
   ✓ Use ACCENT_* for highlights, never arbitrary blues/oranges
   ✗ Avoid: Primary colors that aren't ACCENT_ORANGE or ACCENT_TEAL
   ✗ Avoid: Bright gradients or theme flourishes
   ✗ Avoid: Multiple overlapping "context" destinations
   ✗ Avoid: Status labels that imply success without real evidence

2. TYPOGRAPHY USAGE
   ✓ Use FF_SERIF only for major headings (modal titles, hub names)
   ✓ Use FF_BODY for all body text
   ✓ Use FF_MONO for code snippets, evidence display, data
   ✗ Avoid: Decorative fonts or unusual typefaces
   ✗ Avoid: Mixed font families in same component
   ✗ Avoid: Hardcoded font sizes (use FS_* tokens)

3. LAYOUT & CHROME
   ✓ Topbar: Compact, < 66px height (TOPBAR_H), shows state clearly
   ✓ Sidebar: Collapsible (74px collapsed, 132px expanded)
   ✓ Status Panel: Optional, right-aligned, not always visible
   ✓ Modal/Dialog: Modal stack centered, focused content
   ✗ Avoid: Competing buttons in topbar (consolidate to essential controls)
   ✗ Avoid: Over-bright backgrounds (use SURFACE_ELEVATED, not pure white)
   ✗ Avoid: Many overlapping panels (use tabs/stack widgets)

4. SPACING & BORDERS
   ✓ Border: 1px solid with BORDER_SOFT_* tokens (opacity variants)
   ✓ Spacing: Use consistent px values (6px, 8px, 11px, 14px padding)
   ✓ Border-radius: 14-18px for panels, 16px for buttons
   ✗ Avoid: Inconsistent spacing (no arbitrary margins)
   ✗ Avoid: Heavy shadows; use SHADOW token (rgba-based, subtle)

5. RESPONSIVE BEHAVIOR
   ✓ Hide controls at narrow widths (< 1120px minimum window)
   ✓ Stack layouts vertically on small screens
   ✓ Test at: 1120px (default), 800px (tablet), 600px (phone)
   ✓ Maintain all core functionality at all widths
   ✗ Avoid: Horizontal scroll at any width
   ✗ Avoid: Truncation without tooltip
   ✗ Avoid: Desktop-only critical controls

6. CONTROL COPY
   ✓ Action-oriented: "Save Profile", "Connect Account", "Run Now"
   ✓ Literal status: "Waiting for input", "In progress...", "Ready"
   ✓ Clear affordances: "Click to expand", "Drag to resize"
   ✗ Avoid: Ambiguous labels ("Options", "Manage", "Configure")
   ✗ Avoid: Status that implies success without evidence ("All good!")
   ✗ Avoid: Jargon without explanation

7. VIEW HIERARCHY
   ✓ Five-hub architecture:
     - Home: Chat-first, focused conversation
     - Models: Model discovery, selection, configuration
     - Tools: Installed tools, marketplace, permissions
     - Library: Artifacts, notes, knowledge
     - Settings: Configuration, accounts, preferences
   ✓ Each hub has clear purpose, no feature duplication
   ✓ Settings owns account/credential/provider control plane
   ✗ Avoid: Multiple "settings" or "configuration" destinations
   ✗ Avoid: Tools/Library features in main chat view

Audit Checklist:

□ All colors referenced from tokens.py
□ No hardcoded hex colors in Python code
□ No hardcoded hex colors in QSS/stylesheet
□ All fonts use FF_* or FONT_SERIF tokens
□ No custom font families
□ All font sizes use FS_* tokens
□ Topbar height = TOPBAR_H (66px)
□ Sidebar widths match SIDEBAR_W_* tokens
□ All paddings/margins use consistent spacing (6, 8, 11, 14, 22px)
□ All borders use BORDER_* tokens
□ No inline styles (use classes in stylesheet)
□ All copy is action-oriented, literal, clear
□ View hierarchy matches 5-hub architecture
□ Responsive breakpoints tested (1120px, 800px, 600px)
□ No horizontal scrolling at any width
□ All tooltips present for non-obvious controls
□ All status labels reflect real state (no false success)

Implementation Workflow:

For each UI component:
1. Extract color values → Use tokens.T.COLOR_NAME
2. Extract fonts → Use tokens.FF_* or FONT_SERIF
3. Extract sizes → Use tokens.FS_*
4. Extract spacing → Use 6, 8, 11, 14, 22px constants
5. Move inline styles → Create .css-like class names
6. Add to stylesheet.py → Use token references
7. Update class names → Make them semantic/descriptive
8. Test responsive → 1120px, 800px, 600px widths
9. Verify copy → Check for clarity, action-orientation
10. Validate hierarchy → Ensure 5-hub alignment

Example Refactoring:

BEFORE (bad):

# Hardcoded colors
label = QLabel("Status")
label.setStyleSheet("color: #1f252d; background: #ffffff;")
button = QPushButton("Go")
button.setStyleSheet("background: #c96a2b; color: white;")
```

AFTER (good):
```python
# Token-based
from . import tokens as T
label = QLabel("Status")
label.setStyleSheet(f"color: {T.TEXT}; background: {T.SURFACE_ELEVATED};")
button = QPushButton("Go")
button.setStyleSheet(f"background: {T.ACCENT_ORANGE}; color: {T.TEXT};")
# Even better: use stylesheet classes
button.setStyleSheet(f"background: {T.ACCENT_ORANGE};")
# In stylesheet.py:
# QPushButton.primary-action { background: {T.ACCENT_ORANGE}; ... }
```

Integration Points:

1. tokens.py - Central source of truth
2. stylesheet.py - Global QSS that uses tokens
3. launcher_window.py - Main window (no inline styles)
4. All component files - Use class-based styling
5. PR reviews - Enforce zero hardcoded colors

Testing Strategy:

1. Regex scan: Find all hardcoded #[0-9a-fA-F]{6} colors
2. Color extraction: Map to nearest token, suggest replacement
3. Visual audit: Screenshot at all breakpoints
4. Semantic check: Verify responsive classes hide/show appropriately
5. Copy audit: Check for clarity and action-orientation
"""

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class TokenCategory(Enum):
    """Categories of design tokens."""
    COLOR_SURFACE = "color_surface"
    COLOR_ACCENT = "color_accent"
    COLOR_TEXT = "color_text"
    COLOR_BORDER = "color_border"
    FONT_FAMILY = "font_family"
    FONT_SIZE = "font_size"
    SPACING = "spacing"
    SIZE = "size"


@dataclass
class TokenDefinition:
    """A design token definition."""
    name: str
    value: str
    category: TokenCategory
    description: str
    stitch_aligned: bool = True  # Is this Stitch-compliant?


# Stitch-aligned tokens (reference set)
STITCH_TOKENS = {
    # Warm-sand surface system
    "SAND_0": TokenDefinition(
        "SAND_0", "#FBF9F4", TokenCategory.COLOR_SURFACE,
        "Warmest light surface (near-white with warmth)"
    ),
    "SAND_1": TokenDefinition(
        "SAND_1", "#F5F3EE", TokenCategory.COLOR_SURFACE,
        "Default warm surface"
    ),
    "SAND_2": TokenDefinition(
        "SAND_2", "#EDE9E1", TokenCategory.COLOR_SURFACE,
        "Card/panel surface"
    ),
    "SAND_3": TokenDefinition(
        "SAND_3", "#E0DBD1", TokenCategory.COLOR_SURFACE,
        "Subtle divider/border"
    ),
    # Accent system
    "ACCENT_TEAL": TokenDefinition(
        "ACCENT_TEAL", "#2f6f7a", TokenCategory.COLOR_ACCENT,
        "Secondary accent (teal)"
    ),
    "ACCENT_ORANGE": TokenDefinition(
        "ACCENT_ORANGE", "#c96a2b", TokenCategory.COLOR_ACCENT,
        "Primary accent (sunset orange)"
    ),
    # Text colors
    "TEXT": TokenDefinition(
        "TEXT", "#1f252d", TokenCategory.COLOR_TEXT,
        "Body text color"
    ),
    "DIM": TokenDefinition(
        "DIM", "#5f574f", TokenCategory.COLOR_TEXT,
        "Secondary/dimmed text"
    ),
    # Border
    "BORDER": TokenDefinition(
        "BORDER", "#d6c5ae", TokenCategory.COLOR_BORDER,
        "Default border color"
    ),
    # Fonts
    "FF_SERIF": TokenDefinition(
        "FF_SERIF", "Georgia", TokenCategory.FONT_FAMILY,
        "Serif font for major headings (editorial)"
    ),
    "FF_HEAD": TokenDefinition(
        "FF_HEAD", "Cambria", TokenCategory.FONT_FAMILY,
        "Serif font for headings"
    ),
    "FF_BODY": TokenDefinition(
        "FF_BODY", "Bahnschrift", TokenCategory.FONT_FAMILY,
        "Body text font (plain, readable)"
    ),
    "FF_MONO": TokenDefinition(
        "FF_MONO", "Cascadia Mono", TokenCategory.FONT_FAMILY,
        "Monospace font for code/data"
    ),
    # Sizes
    "FS_TINY": TokenDefinition(
        "FS_TINY", "8", TokenCategory.FONT_SIZE,
        "Tiny text (8pt)"
    ),
    "FS_SMALL": TokenDefinition(
        "FS_SMALL", "9", TokenCategory.FONT_SIZE,
        "Small text (9pt)"
    ),
    "FS_BODY": TokenDefinition(
        "FS_BODY", "10", TokenCategory.FONT_SIZE,
        "Body text (10pt)"
    ),
    "FS_LABEL": TokenDefinition(
        "FS_LABEL", "11", TokenCategory.FONT_SIZE,
        "Label text (11pt)"
    ),
    "FS_TITLE": TokenDefinition(
        "FS_TITLE", "14", TokenCategory.FONT_SIZE,
        "Title text (14pt)"
    ),
    "FS_HERO": TokenDefinition(
        "FS_HERO", "22", TokenCategory.FONT_SIZE,
        "Hero text (22pt)"
    ),
    # Layout dimensions
    "TOPBAR_H": TokenDefinition(
        "TOPBAR_H", "66", TokenCategory.SIZE,
        "Topbar height in pixels"
    ),
    "SIDEBAR_W_COLLAPSED": TokenDefinition(
        "SIDEBAR_W_COLLAPSED", "74", TokenCategory.SIZE,
        "Sidebar width when collapsed"
    ),
    "SIDEBAR_W_EXPANDED": TokenDefinition(
        "SIDEBAR_W_EXPANDED", "132", TokenCategory.SIZE,
        "Sidebar width when expanded"
    ),
}


class TokenEnforcer:
    """Enforce design token usage and Stitch alignment."""

    COLOR_HEX_PATTERN = re.compile(r"#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}")

    def __init__(self) -> None:
        """Initialize token enforcer."""
        self.violations: list[str] = []
        self.warnings: list[str] = []

    def scan_file_for_hardcoded_colors(self, file_path: Path) -> list[str]:
        """
        Scan a Python or QSS file for hardcoded color values.

        Args:
            file_path: Path to file to scan

        Returns:
            List of hardcoded colors found
        """
        if not file_path.exists():
            return []

        content = file_path.read_text()
        matches = self.COLOR_HEX_PATTERN.findall(content)
        return list(set(matches))  # Unique colors

    def suggest_token_for_color(self, color_hex: str) -> Optional[str]:
        """
        Suggest a token name for a hardcoded color.

        Args:
            color_hex: Hex color code (e.g., "#c96a2b")

        Returns:
            Suggested token name or None if not found
        """
        color_lower = color_hex.lower()

        # Exact matches
        for token_name, token_def in STITCH_TOKENS.items():
            if token_def.value.lower() == color_lower:
                return token_name

        # Closest match (simple string distance)
        best_match = None
        best_distance = float("inf")

        for token_name, token_def in STITCH_TOKENS.items():
            if token_def.category not in (
                TokenCategory.COLOR_SURFACE,
                TokenCategory.COLOR_ACCENT,
                TokenCategory.COLOR_TEXT,
                TokenCategory.COLOR_BORDER,
            ):
                continue

            distance = self._string_distance(
                color_lower, token_def.value.lower()
            )
            if distance < best_distance:
                best_distance = distance
                best_match = token_name

        return best_match if best_distance < 100 else None

    @staticmethod
    def _string_distance(s1: str, s2: str) -> int:
        """Simple string distance for color matching."""
        # Treat as character codes
        dist = 0
        for c1, c2 in zip(s1, s2):
            dist += abs(ord(c1) - ord(c2))
        return dist

    def get_stitch_audit_report(self) -> str:
        """
        Get a formatted Stitch alignment audit report.

        Returns:
            Formatted audit report
        """
        lines = [
            "Stitch Design Token Audit Report",
            "=" * 50,
            "",
            "Token Categories Defined:",
        ]

        for category in TokenCategory:
            tokens = [t for t, d in STITCH_TOKENS.items() if d.category == category]
            lines.append(f"  {category.value}: {len(tokens)} tokens")
            for token in tokens[:5]:  # Show first 5
                lines.append(f"    - {token}")
            if len(tokens) > 5:
                lines.append(f"    ... and {len(tokens) - 5} more")

        lines.extend([
            "",
            "Design Direction Constraints (LOCKED):",
            "  ✓ Warm-sand neutral base (SAND_0-3)",
            "  ✓ Restrained blue/orange accents (ACCENT_TEAL, ACCENT_ORANGE)",
            "  ✓ Editorial serif headings only (FF_SERIF/FF_HEAD)",
            "  ✓ Chat-first home layout (no competing chrome)",
            "  ✓ Five-hub architecture (Home, Models, Tools, Library, Settings)",
            "  ✓ Responsive at 1120px, 800px, 600px",
            "  ✓ Progressive disclosure over dense panels",
            "  ✓ Action-oriented, literal control copy",
            "",
            "Enforcement Rules (Zero Tolerance):",
            "  ✗ No hardcoded colors (use tokens.T.COLOR_NAME)",
            "  ✗ No decorative fonts (use FF_* tokens)",
            "  ✗ No hardcoded font sizes (use FS_* tokens)",
            "  ✗ No inline styles (use stylesheet classes)",
            "  ✗ No competing topbar chrome",
            "  ✗ No horizontal scroll at any width",
            "  ✗ No status labels without real evidence",
            "",
        ])

        return "\n".join(lines)

    def validate_file(self, file_path: Path) -> tuple[bool, list[str]]:
        """
        Validate a file for token compliance.

        Args:
            file_path: Path to file to validate

        Returns:
            Tuple of (is_compliant, violation_messages)
        """
        violations = []

        # Check for hardcoded colors
        colors = self.scan_file_for_hardcoded_colors(file_path)
        for color in colors:
            token = self.suggest_token_for_color(color)
            if token:
                violations.append(
                    f"Hardcoded color {color} found - use tokens.T.{token} instead"
                )
            else:
                violations.append(
                    f"Unknown hardcoded color {color} - should use a token"
                )

        # Check for hardcoded fonts
        content = file_path.read_text()
        font_patterns = [
            r'"(Arial|Helvetica|Times|Courier|Comic Sans)"',
            r"'(Arial|Helvetica|Times|Courier|Comic Sans)'",
        ]
        for pattern in font_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                violations.append(
                    f"Hardcoded font family found - use tokens.FF_* instead"
                )

        is_compliant = len(violations) == 0
        return is_compliant, violations


def create_token_enforcer() -> TokenEnforcer:
    """Factory function to create a token enforcer."""
    return TokenEnforcer()
