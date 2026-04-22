# Guppy AI: Atoll Editorial Design System & Implementation Guide

## 1. Vision & Core Aesthetic
**The North Star:** "Sophisticated Tropical Workstation."
We are moving away from the "toy-like" feel of many AI tools towards a professional, editorial environment. The interface should feel as expansive and calming as a Caribbean horizon, but as precise as a technical manuscript.

**Key Principles:**
*   **Desktop-First Spacing:** Generous gutters, clear information density, and persistent navigation for a high-efficiency workspace.
*   **The "White Sand" Foundation:** Using warm creams and off-whites instead of stark white or sterile grey to create a premium, tangible feel.
*   **High-Energy Accents:** Using Turquoise and Sunset Orange sparingly but powerfully to draw focus to active states and primary actions.

---

## 2. Visual Tokens

### Color Palette
*   **Base (Surface):** `#FBF9F4` (White Sand / Cream)
*   **Surface Container:** `#F5F3EE` (Slightly deeper cream for card backgrounds and sidebars)
*   **Primary Accent:** `#006A6A` / `#08BDBD` (Atoll Turquoise) - Use for "In Use" states, active indicators, and branding.
*   **Secondary Accent:** `#FF6D00` (Sunset Orange) - Use for high-priority CTAs, notifications, and "Live" telemetry points.
*   **Text (Primary):** `#1B1C19` (Deep Charcoal - high contrast against cream)
*   **Text (Secondary/Muted):** `#1B1C19` at 60% opacity.

### Typography
*   **Headlines & Branding:** `Noto Serif`. Use *Italic* for the brand name ("*Editorial Intelligence*") to lean into the curator aesthetic.
*   **Interface & Data:** `Manrope` or a clean geometric Sans-Serif.
*   **Code & Metrics:** A high-quality Monospace font (e.g., `JetBrains Mono` or `Roboto Mono`).

---

## 3. UI Implementation Guidance for Coding Agents

### Layout Structure (Python/Desktop Frameworks)
*   **Sidebar:** Persistent 280px - 320px width. Use `#F5F3EE` background. No border; use a slight tonal shift to separate it from the main content.
*   **Navigation Rails:** For internal module navigation (like the "Intelligence", "Research" tabs), use `48px` height items with a `4px` left-border indicator in `#006A6A` for active states.
*   **Cards:** Use `0px` or `2px` borders. Background should be `white` or `#FBF9F4`. Shadow: `shadow-sm` or `flat`.

### Interaction States
*   **Hover:** Slight background darkening (e.g., `bg-black/5`) and a subtle `translate-x-1` for list items to feel responsive.
*   **Active/Selected:** Use the Primary Turquoise for text and icons.
*   **Buttons:** Primary buttons should be a solid Turquoise or Orange with white text. Secondary buttons should be outlined or ghost styles.

### Telemetry & Visualization
*   **Charts:** Use the Atoll Turquoise for the primary data series. Use soft cream or light grey for grid lines to keep the focus on the data.
*   **Status Indicators:** Use small, pulsing pips. 
    *   `#00C853` (Success/Optimal)
    *   `#FFD600` (Warning/Processing)
    *   `#FF3D00` (Error/Critical)

---

## 4. Brand Assets
*   **Logo:** The "Guppy G" ({{DATA:IMAGE:IMAGE_4}}) should be used at `40px` in sidebars and `24px` as a favicon/taskbar icon.
*   **Imagery:** Use glassmorphism overlays and soft-focus "editorial" style photography for empty states or feature highlights.

---

## 5. Coding Agent "Quick-Start" Prompt
When asking your coding agents to build a new view, use this prompt fragment:
> "Implement this view using the Atoll Editorial style: Base background #FBF9F4, Noto Serif for titles, Manrope for body. Use #006A6A (Turquoise) for primary accents and active states. Maintain a desktop-first layout with high information density but generous white space. Follow the 'Digital Curator' aesthetic—clean, professional, and sophisticated."
