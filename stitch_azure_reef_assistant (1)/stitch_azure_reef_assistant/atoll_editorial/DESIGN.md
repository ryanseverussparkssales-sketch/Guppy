```markdown
# Design System Specification: Editorial Intelligence

## 1. Overview & Creative North Star: "The Digital Curator"
This design system moves away from the sterile, "app-like" aesthetic of modern SaaS and toward the world of high-end editorial publishing and technical precision. The **Creative North Star** is **"The Digital Curator"**: an experience that feels like a bespoke intelligence briefing rather than a chat interface.

By leveraging the expansive real estate of desktop displays, we reject "mobile-first" simplification. Instead, we embrace **Intentional Asymmetry** and **Tonal Depth**. The interface should feel like high-quality stationery layered on a designer’s desk—structured by weight, light, and proximity rather than rigid lines. This is a technical tool for professionals who value both data density and aesthetic soul.

---

## 2. Colors & Surface Philosophy
The palette is rooted in the organic warmth of `#F9F7F2` (White Sand), providing a sophisticated, low-strain backdrop that feels more "paper" than "pixel."

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders to section off the UI. Separation must be achieved through:
1.  **Background Shifts:** Distinguish the persistent sidebar (`surface-container-low`) from the main workspace (`surface`) through tonal changes alone.
2.  **Proximity:** Using the spacing scale to create "islands" of information.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers. Use the `surface-container` tiers to create depth:
*   **Base Layer:** `surface` (#fbf9f4) for the widest areas.
*   **Navigational Rails:** `surface-container-low` (#f5f3ee) for persistent sidebars.
*   **Content Cards:** `surface-container-lowest` (#ffffff) to make high-priority data "pop" against the cream base.
*   **Modals/Overlays:** `surface-container-high` (#eae8e3) to imply weight and presence.

### The "Glass & Gradient" Rule
To elevate CTAs and AI-generated highlights, use the **Signature Caribbean Gradient**: a subtle transition from `primary` (#006a6a) to `primary_container` (#08bdbd) at a 135-degree angle. For floating panels, apply `backdrop-blur: 12px` to `surface_container_lowest` at 85% opacity to create a "frosted glass" effect that allows the warm sand tones to bleed through.

---

## 3. Typography: Editorial Authority
The typographic pairing is a conversation between heritage and modernity.

*   **Display & Headlines (Noto Serif):** Used for AI responses, article headers, and page titles. The serif typeface provides an "Editorial" weight, signaling that the information is curated and authoritative.
*   **UI & Data (Manrope):** A clean, geometric sans-serif used for labels, inputs, and dense data tables. Its high x-height ensures legibility in technical multi-column layouts.

**Hierarchy Intent:**
*   `display-lg` is reserved for "Hero" moments or major data milestones.
*   `title-sm` (Manrope) is the workhorse for persistent sidebar navigation, set in semi-bold for clarity.
*   `body-md` is the standard for AI-generated text, utilizing generous line-height (1.6) to ensure a premium reading experience.

---

## 4. Elevation & Depth
In this system, depth is a function of light, not lines.

*   **Tonal Layering:** Avoid shadows for static elements. Place a `surface-container-lowest` card on a `surface-container-low` background to create a "soft lift."
*   **Ambient Shadows:** For floating elements (Modals/Popovers), use a custom shadow: `0px 24px 48px -12px rgba(27, 28, 25, 0.08)`. Note the tint—the shadow uses the `on-surface` color (#1b1c19) rather than pure black to keep the warmth of the sand base.
*   **The "Ghost Border":** If a container requires definition against an identical color, use `outline-variant` (#bbc9c9) at **15% opacity**. It should be felt, not seen.

---

## 5. Components

### Buttons
*   **Primary:** Features the Caribbean turquoise gradient. `borderRadius: md (0.375rem)`. No border. Text is `on-primary` (#ffffff).
*   **Secondary:** Sunset orange (`secondary`) text on a transparent background with a "Ghost Border." Use for high-action "Warning" or "Alternative" paths.
*   **Tertiary:** `on-surface` text with no container; shifts to `surface-container-high` on hover.

### Input Fields & Text Areas
*   **Styling:** Filled style using `surface-container-highest`. No bottom line.
*   **Focus State:** A 2px "Ghost Border" using `primary` at 40% opacity.
*   **Labels:** Use `label-md` (Manrope) in `on-surface-variant` for a technical, "form-filler" feel.

### Cards & Data Displays
*   **The Grid:** Use a 12-column grid with wide gutters (32px). 
*   **No Dividers:** Lists within cards must not use horizontal lines. Use 16px of vertical padding and a `surface-container-low` hover state to indicate interactivity.
*   **Dense Data:** For technical displays, use `body-sm` (Manrope) to allow for high information density without clutter.

### AI Feedback Chips
*   **Visuals:** Small, `full` roundedness. Use `tertiary_container` (#f78f58) for "In-Progress" states and `primary_container` (#08bdbd) for "Verified" states.

---

## 6. Do’s and Don’ts

### Do:
*   **Do** embrace white space. If a layout feels crowded, increase the gutter, don't add a border.
*   **Do** use Noto Serif for long-form reading; it reduces eye strain and feels more "premium."
*   **Do** leverage the persistent left-hand sidebar for complex navigation—this is a desktop tool.
*   **Do** use the Sunset Orange (`secondary`) sparingly as a "heat" indicator for important alerts.

### Don’t:
*   **Don’t** use "Mobile Burgers" for navigation. If it’s important, keep it persistent on the screen.
*   **Don’t** use hard black (#000000) for text. Always use `on-surface` (#1b1c19) to maintain the "warm" aesthetic.
*   **Don’t** use standard 1px gray dividers. They break the editorial flow and make the UI look like a generic template.
*   **Don’t** use sharp 0px corners unless it is for a specific "Brutalist" data visualization; stick to the `md` (0.375rem) standard.

---

## 7. Signature Interaction: The "Glow Transition"
When the AI assistant is "thinking" or "processing," do not use a standard spinner. Instead, apply a subtle, pulsing `box-shadow` to the active container using `primary_fixed` (#6af7f7) with a 40px blur. This creates a "subsurface scattering" effect, as if the cream-colored paper is being lit from within by the Caribbean turquoise light.```