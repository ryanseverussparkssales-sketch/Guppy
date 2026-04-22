# Design System Strategy: Tropical Editorial

## 1. Overview & Creative North Star
The Creative North Star for this design system is **"The Editorial Horizon."** 

We are moving away from the "postcard" clichés of Caribbean design—no illustrative palms, no kitschy textures. Instead, we are evoking the *feeling* of a high-end boutique resort: the depth of the ocean at dusk, the warmth of the sand, and the clarity of the horizon. 

This design system breaks the "template" look through **intentional asymmetry** and **high-contrast typography**. We treat the screen not as a flat grid, but as a curated editorial layout where white space (sand) is as important as the content itself. By overlapping glass containers over deep teal gradients, we create a sense of digital immersion that feels both premium and organic.

---

## 2. Colors & Atmospheric Depth

Our palette is divided into the "Deep Ocean" (Teals), the "Solar Glint" (Oranges), and the "Sands" (Neutrals).

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using 1px solid borders to define sections or containers. Structure must be achieved through:
- **Tonal Shifts:** Placing a `surface_container_low` section against a `surface` background.
- **Negative Space:** Using the Spacing Scale to create clear visual "islands" of content.

### Surface Hierarchy & Nesting
Treat the UI as physical layers of fine paper or frosted glass. Use the `surface_container` tiers to define importance:
- **Base:** `surface` (#fcf9f3) for the primary background.
- **Low Priority/Large Areas:** `surface_container_low` (#f6f3ed).
- **Interactive Cards:** `surface_container_highest` (#e5e2dc) to "lift" elements toward the user.

### The "Glass & Gradient" Rule
To escape the "flat" look, use Glassmorphism for floating UI elements (Modals, Navigation Bars, Hovering Cards). 
- **Recipe:** Use `surface` at 70% opacity + `backdrop-blur: 20px`.
- **Signature Textures:** Apply linear gradients transitioning from `primary` (#00342b) to `primary_container` (#004d40) for hero sections and primary CTAs. This creates a "liquid" depth that solid colors cannot replicate.

---

## 3. Typography: The Boutique Voice

We use a high-contrast pairing to achieve a "Boutique Jarvis" feel—intelligent, sophisticated, and bespoke.

- **Display & Headlines (Noto Serif):** Use these for storytelling and high-level headers. The serif carries the "character" and "heritage" of the brand. `display-lg` and `headline-md` should be used with generous leading (1.2 - 1.4) to feel like a luxury magazine.
- **UI & Body (Inter):** Use Inter for all functional elements. Its geometric precision ensures readability in complex data environments. 
- **Styling Note:** Titles (`title-lg`) should always be set with a slightly tighter letter-spacing (-0.02em) to feel "tucked in" and premium.

---

## 4. Elevation & Depth

Hierarchy is conveyed through **Tonal Layering** rather than traditional structural lines or heavy shadows.

- **The Layering Principle:** Depth is achieved by stacking. A `surface_container_lowest` card placed on a `surface_container_high` background creates a natural, soft lift.
- **Ambient Shadows:** For floating elements that require a shadow, use the `on_surface` color at 6% opacity with a blur of 30px to 60px. This mimics natural light filtered through a tropical canopy—soft and expansive.
- **The "Ghost Border" Fallback:** If a border is required for accessibility, use the `outline_variant` (#bfc9c4) at 15% opacity. Never use a 100% opaque border.
- **Integration:** Use backdrop blurs on `surface_variant` containers to allow background teals to "bleed" through, making the layout feel like a single, integrated environment.

---

## 5. Components

### Buttons
- **Primary:** A gradient from `secondary_container` (#fd6c00) to `secondary` (#9f4200). Use `xl` (0.75rem) roundedness. Text is `on_secondary` (#ffffff).
- **Secondary:** Transparent background with a "Ghost Border" (15% opacity `outline`). 
- **Tertiary:** Text-only using `primary` color, strictly for low-emphasis actions.

### Inputs & Fields
- **Text Inputs:** No 4-sided boxes. Use a `surface_variant` background with an `xl` top-radius and a subtle `outline_variant` bottom-stroke (2px).
- **Focus State:** Transition the bottom-stroke to `secondary` (#9f4200) and increase the background saturation slightly.

### Cards & Lists
- **Forbid Dividers:** Do not use horizontal lines to separate list items. Use 16px–24px of vertical white space or alternating `surface_container_low` and `surface_container_lowest` backgrounds.
- **Editorial Cards:** Images should use `lg` (0.5rem) roundedness. Overlap a `title-md` text block in a glassmorphic container over the bottom-left corner of the image to break the grid.

### Navigation (The Horizon Bar)
- **Styling:** A top or side bar using the Glassmorphism recipe. Use `primary` for active icons and `outline` for inactive states.

---

## 6. Do's and Don'ts

### Do
- **Do** use intentional asymmetry. Align a headline to the left and the body text to a slightly offset right-column to create an editorial feel.
- **Do** use the `secondary` orange sparingly as a "glint"—it should guide the eye to the most important action on the page.
- **Do** allow images to bleed to the edges of the viewport in Hero sections to emphasize the "Horizon" concept.

### Don't
- **Don't** use pure black (#000000). Use `on_surface` (#1c1c18) for all text to maintain the soft, sandy warmth.
- **Don't** use standard Material Design "Drop Shadows." They are too heavy for this "Digital-First" tropical aesthetic.
- **Don't** use 1px dividers. If you feel you need a line, use white space instead. If white space doesn't work, your information architecture needs a rethink.

---

## 7. Interaction Pattern
Transitions should feel "viscous." Use `cubic-bezier(0.23, 1, 0.32, 1)` for all surface transitions. Elements shouldn't just "pop" in; they should slide and fade like a shifting tide.