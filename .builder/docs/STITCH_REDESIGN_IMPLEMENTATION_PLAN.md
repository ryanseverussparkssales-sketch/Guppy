# Stitch (Atoll Editorial) UI Redesign Plan
## Current State vs. Design System - Complete Implementation Guide

**Date**: Current Session  
**Design System**: Atoll Editorial Design System (Tropical Workstation)  
**Target**: Professional, editorial, sophisticated desktop-first experience  

---

## Executive Summary

You have a **functional Python/PySide6 desktop launcher** with 43 view files that needs to be **visually redesigned** to match the **Atoll Editorial Design System** (your Stitch design).

**Key differences:**
- ❌ Current accent colors don't match Stitch
- ❌ Typography is different (Bahnschrift/Cambria vs. Noto Serif/Manrope)
- ❌ Layout spacing/hierarchy needs refinement
- ❌ Some UI patterns conflict with editorial aesthetic

**Timeline**: 2-3 weeks to fully redesign and test all views

---

## Part 1: Design System Comparison

### Color Palette

| Element | Current App | Stitch (Atoll) | Change? |
|---------|------------|----------------|---------|
| **Base Surface** | #FBF9F4 (SAND_0) | #FBF9F4 | ✅ Match |
| **Surface Container** | #F5F3EE (SAND_1) | #F5F3EE | ✅ Match |
| **Card Surface** | #EDE9E1 (SAND_2) | #FBF9F4 / #F5F3EE | ⚠️ Adjust |
| **Subtle Border** | #E0DBD1 (SAND_3) | (implicit) | ⚠️ Minor |
| **Primary Accent** | #2f6f7a (ACCENT_TEAL) | #006A6A / #08BDBD | ❌ **CHANGE** |
| **Secondary Accent** | #c96a2b (ACCENT_ORANGE) | #FF6D00 | ❌ **CHANGE** |
| **Text Primary** | #1f252d (TEXT) | #1B1C19 | ⚠️ Similar (adjust to #1B1C19) |
| **Text Secondary** | #5f574f (DIM) | #1B1C19 @ 60% | ⚠️ Adjust opacity |

**Summary**: Sand surfaces ✅ correct. Accent colors ❌ need updating. Text colors ⚠️ need minor refinement.

### Typography

| Element | Current App | Stitch (Atoll) | Change? |
|---------|------------|----------------|---------|
| **Headings** | Cambria (serif) | Noto Serif (italic for brand) | ⚠️ Switch to Noto Serif |
| **Body/UI** | Bahnschrift (sans) | Manrope (geometric sans) | ❌ **Switch to Manrope** |
| **Monospace** | Cascadia Mono | JetBrains Mono / Roboto Mono | ⚠️ Consider upgrade |
| **Serif Branding** | Georgia | Noto Serif (italic) | ⚠️ Update brand use |

**Summary**: Font family changes needed. Typography system needs update.

### Layout & Spacing

| Element | Current App | Stitch (Atoll) | Change? |
|---------|------------|----------------|---------|
| **Sidebar Width** | 74px (collapsed) / 132px (expanded) | 280-320px (persistent) | ⚠️ Rethink sidebar |
| **Navigation Style** | Collapsed rail | Persistent sidebar | ⚠️ Design change |
| **Card Styling** | Rounded corners (16-18px) | Flat or 2px border | ❌ Simplify |
| **Shadows** | Subtle (SHADOW token) | Flat styling | ⚠️ Reduce |
| **Active States** | Various | Left border 4px turquoise | ⚠️ Standardize |
| **Spacing** | Consistent (6, 8, 11, 14px) | **Generous** desktop-first | ⚠️ Increase gaps |

**Summary**: Current design is "compact tech". Stitch is "spacious editorial". Layout needs significant refinement.

### Interaction Patterns

| Pattern | Current App | Stitch (Atoll) | Change? |
|---------|------------|----------------|---------|
| **Hover States** | Border color change | Slight darkening + translate-x-1 | ⚠️ Add motion |
| **Active States** | Color highlight | Left border #006A6A | ❌ **Standardize** |
| **Button Styling** | Rounded pills | Solid turquoise/orange or ghost | ⚠️ Simplify |
| **Status Indicators** | Various labels | Pulsing pips (green/yellow/red) | ❌ Add pulsing animation |
| **Empty States** | Text messages | Glassmorphism + editorial photography | ⚠️ Add imagery |

**Summary**: Interaction patterns need modernization with animation and visual consistency.

---

## Part 2: View-by-View Redesign Tasks

### High Priority (Visible Impact)

#### 1. **TopBar Component** (497 lines)
**Current State**: Many competing buttons, compact layout  
**Stitch Goal**: Coherent strip, desktop-first spacing

**Changes Needed**:
- [ ] Increase padding/spacing (generous gutters)
- [ ] Simplify button layout (fewer competing items)
- [ ] Update accent colors to #006A6A (turquoise)
- [ ] Add hover animations (translate-x-1, bg-black/5)
- [ ] Ensure readiness/status indicator matches Stitch aesthetic
- [ ] Typography: update to Manrope for labels

**Estimated Lines to Change**: 150-200

---

#### 2. **Sidebar Component** (336 lines)
**Current State**: Collapsed 74px rail, expand to 132px  
**Stitch Goal**: Persistent 280-320px sidebar

**Changes Needed**:
- [ ] **Major redesign**: Expand to 280-320px persistent width
- [ ] Remove collapse/expand toggle
- [ ] Update background to #F5F3EE
- [ ] Add left border active indicator (4px, #006A6A)
- [ ] Increase item padding (larger hit targets)
- [ ] Update text to Manrope font
- [ ] Remove "The Curator" art card (adjust layout)
- [ ] Simplify nav structure for editorial aesthetic

**Estimated Lines to Change**: Complete rewrite (~200-250 lines)

---

#### 3. **Home/AssistantView** (619 lines)
**Current State**: Compact with many stacked elements  
**Stitch Goal**: Generous spacing, editorial feel

**Changes Needed**:
- [ ] Increase vertical spacing between sections
- [ ] Simplify layout (fewer competing panels)
- [ ] Update typography to Manrope body
- [ ] Update accent colors (#006A6A turquoise, #FF6D00 orange)
- [ ] Improve empty state with editorial imagery
- [ ] Add hover animations to starter buttons
- [ ] Ensure first-run banner matches aesthetic

**Estimated Lines to Change**: 200-250

---

#### 4. **Models Hub** (669 lines + 506 lines sections)
**Current State**: Dense with many sections and controls  
**Stitch Goal**: Spacious, editorial presentation

**Changes Needed**:
- [ ] Increase padding/gutters throughout
- [ ] Simplify card styling (2px border or flat)
- [ ] Update status indicators to pulsing pips
- [ ] Update accent colors
- [ ] Improve visual hierarchy with generous spacing
- [ ] Typography: Manrope for body

**Estimated Lines to Change**: 250-300

---

#### 5. **Tools View** (464 lines)
**Current State**: Grid with policy cards and filters  
**Stitch Goal**: Clean, editorial tool browser

**Changes Needed**:
- [ ] Simplify card styling
- [ ] Update accent colors
- [ ] Increase spacing between cards
- [ ] Add smooth hover animations
- [ ] Update status badges (pulsing indicators)
- [ ] Typography: Manrope

**Estimated Lines to Change**: 150-200

---

#### 6. **Library View** (620 lines)
**Current State**: Many nested cards and sections  
**Stitch Goal**: Spacious editorial knowledge browser

**Changes Needed**:
- [ ] Increase spacing between sections
- [ ] Simplify card borders (2px or none)
- [ ] Add editorial imagery to empty states
- [ ] Update accent colors
- [ ] Improve typography hierarchy
- [ ] Add hover animations

**Estimated Lines to Change**: 200-250

---

#### 7. **Settings Hub** (389 lines + sub-panels ~1200 lines)
**Current State**: Dense tabs and forms  
**Stitch Goal**: Spacious, organized settings

**Changes Needed**:
- [ ] Increase form field spacing
- [ ] Simplify button styling
- [ ] Update accent colors
- [ ] Improve visual separation between sections
- [ ] Typography: Manrope
- [ ] Add hover states to interactive elements

**Estimated Lines to Change**: 300-400 (across all settings components)

---

### Medium Priority (Visual Polish)

#### 8. **Status Panel** (383 lines)
- [ ] Update colors
- [ ] Increase padding
- [ ] Simplify styling

#### 9. **Cards & Components** (various)
- [ ] Standardize card styling (2px border)
- [ ] Update all accent colors
- [ ] Add consistent hover animations
- [ ] Simplify shadows

---

## Part 3: Implementation Strategy

### Phase 1: Design System Update (2-3 days)

**Step 1: Update tokens.py**
```python
# Current (OLD)
ACCENT_TEAL = "#2f6f7a"
ACCENT_ORANGE = "#c96a2b"

# New (Stitch/Atoll)
ACCENT_TEAL = "#006A6A"      # Atoll Turquoise (primary)
ACCENT_TEAL_BRIGHT = "#08BDBD"  # Bright variant
ACCENT_ORANGE = "#FF6D00"     # Sunset Orange (secondary)

# Success/Warning/Error (NEW)
STATUS_SUCCESS = "#00C853"
STATUS_WARNING = "#FFD600"
STATUS_ERROR = "#FF3D00"

# Text updates
TEXT = "#1B1C19"  # Deep Charcoal
TEXT_SECONDARY = "rgba(27,28,25,0.60)"  # Muted
```

**Step 2: Update stylesheet.py**
```python
# Add Noto Serif and Manrope fonts
FF_SERIF = "Noto Serif"
FF_BODY = "Manrope"
FF_MONO = "JetBrains Mono"

# Update all button/control colors to use new accents
# Update card styling to 2px borders (less rounded)
# Increase spacing constants
```

**Step 3: Create animation utilities**
```python
# Add hover animations
# - translate-x-1 (small horizontal shift)
# - bg-black/5 (subtle darkening)
# - Pulsing status indicators
```

**Tasks**:
- [ ] Update tokens.py with new colors
- [ ] Update stylesheet.py with new fonts and styles
- [ ] Add animation/interaction helper module
- [ ] Create color migration guide for all views

---

### Phase 2: Component Updates (1 week)

**Day 1: Navigation Components**
- [ ] Update TopBar colors and spacing
- [ ] Redesign Sidebar (280-320px persistent)
- [ ] Update StatusPanel styling

**Day 2-3: Primary Views**
- [ ] Redesign AssistantView (Home)
- [ ] Redesign ModelsHubView
- [ ] Update related components

**Day 4-5: Secondary Views**
- [ ] Redesign ToolsView
- [ ] Redesign LibraryView
- [ ] Redesign SettingsHub

**Day 6-7: Polish & Testing**
- [ ] Test all views at multiple widths (1120px, 800px, 600px)
- [ ] Verify accent colors consistent
- [ ] Test hover/active states
- [ ] Screenshot regression testing

**Tasks per view**:
- [ ] Update all accent color references
- [ ] Increase spacing/padding
- [ ] Simplify card styling
- [ ] Update typography to Manrope
- [ ] Add hover animations
- [ ] Test responsiveness

---

### Phase 3: Integration & Testing (3-4 days)

**Validation Checklist**:
- [ ] All views use new colors consistently
- [ ] All typography is Noto Serif / Manrope
- [ ] Spacing is generous (desktop-first)
- [ ] No rounded corners (2px borders or flat)
- [ ] Hover states have animations
- [ ] Active states use left border (4px, turquoise)
- [ ] Status indicators pulse (green/yellow/red)
- [ ] Empty states have editorial imagery
- [ ] Responsive behavior preserved at 800px/600px

**Testing**:
- [ ] Launch launcher, navigate all views
- [ ] Test all interactions (hover, click, select)
- [ ] Verify colors match Stitch spec exactly
- [ ] Screenshot comparison (before/after)
- [ ] Performance - no regressions

---

## Part 4: File-by-File Action Items

### Critical Files (High Visual Impact)

#### `ui/launcher/tokens.py` (120 lines)
**Actions**:
- [ ] Update `ACCENT_TEAL` → #006A6A
- [ ] Update `ACCENT_ORANGE` → #FF6D00
- [ ] Add `STATUS_SUCCESS`, `STATUS_WARNING`, `STATUS_ERROR`
- [ ] Update `TEXT` → #1B1C19
- [ ] Update typography constants (Noto Serif, Manrope)
- [ ] Add animation constants (translate-x, opacity values)

**Lines Changed**: ~40-50

---

#### `ui/launcher/stylesheet.py` (156 lines)
**Actions**:
- [ ] Update font families (Noto Serif, Manrope)
- [ ] Update all color references to new tokens
- [ ] Reduce border-radius (from 16px to 2px or 0px)
- [ ] Reduce/remove shadows
- [ ] Add hover state animations
- [ ] Increase padding/margins

**Lines Changed**: ~100-120

---

#### `ui/launcher/components/topbar.py` (497 lines)
**Actions**:
- [ ] Update all accent color usages
- [ ] Increase padding between elements
- [ ] Simplify button styling
- [ ] Update typography (Manrope)
- [ ] Add hover/active animations
- [ ] Improve visual hierarchy

**Lines Changed**: 150-200

---

#### `ui/launcher/components/sidebar.py` (336 lines)
**Actions**:
- [ ] **MAJOR**: Redesign from 74px rail to 280px sidebar
- [ ] Remove collapse/expand logic
- [ ] Update background color
- [ ] Add left border active indicator (4px)
- [ ] Increase padding/spacing
- [ ] Update typography (Manrope)

**Lines Changed**: Complete rewrite (200-250)

---

#### `ui/launcher/views/assistant_view.py` (619 lines)
**Actions**:
- [ ] Update accent colors
- [ ] Increase section spacing
- [ ] Update typography (Manrope body)
- [ ] Simplify card styling
- [ ] Add animations to interactive elements
- [ ] Improve empty state

**Lines Changed**: 200-250

---

#### Other Views (models, tools, library, settings)
**Similar pattern for each**:
- Update colors (3-5 minutes per file)
- Increase spacing (10-15 minutes per file)
- Update typography (5-10 minutes per file)
- Simplify styling (10-15 minutes per file)
- Add animations (5-10 minutes per file)

---

## Part 5: Color Migration Reference

### Replace These Colors

```python
# OLD → NEW

# Accents
"#2f6f7a" → "#006A6A"    # Teal primary
"#c96a2b" → "#FF6D00"    # Orange secondary

# Text
"#1f252d" → "#1B1C19"    # Primary text
"#5f574f" → "rgba(27,28,25,0.60)"  # Secondary text

# New additions
None → "#00C853"  # Success
None → "#FFD600"  # Warning
None → "#FF3D00"  # Error

# Fonts
"Bahnschrift" → "Manrope"  # Body text
"Cambria" → "Noto Serif"   # Headings
"Cascadia Mono" → "JetBrains Mono"  # Code
```

---

## Part 6: Visual Checklist

### Before Starting, Verify Current State ✅

- [x] 43 view files in ui/launcher/views
- [x] Current colors: #2f6f7a (teal), #c96a2b (orange)
- [x] Current fonts: Bahnschrift, Cambria, Cascadia Mono
- [x] Compact layout with rounded corners (16-18px)
- [x] No pulsing status indicators
- [x] Collapsed sidebar (74-132px)

### After Redesign, Verify New State

- [ ] All accent colors updated to #006A6A and #FF6D00
- [ ] All fonts updated to Noto Serif / Manrope
- [ ] Sidebar redesigned to 280-320px persistent
- [ ] Card styling simplified (2px borders or flat)
- [ ] Spacing increased throughout (generous gutters)
- [ ] Hover animations added (translate-x, darkening)
- [ ] Active states use left border (4px turquoise)
- [ ] Status indicators pulsing (green/yellow/red)
- [ ] Empty states have editorial imagery
- [ ] Typography hierarchy improved
- [ ] All views responsive at 800px/600px
- [ ] No regressions in functionality

---

## Part 7: Implementation Tips

### Color Updating (Fastest)
1. Use Find & Replace: `#2f6f7a` → `#006A6A`
2. Use Find & Replace: `#c96a2b` → `#FF6D00`
3. Verify in each file, update styling.py and tokens.py

### Typography Updating
1. Update tokens.py first
2. Update stylesheet.py with new font families
3. Update component files to use new constants

### Spacing/Layout
1. Identify sections with < 10px gaps
2. Increase to 16-20px for desktop
3. Maintain mobile responsiveness

### Animations
1. Add to stylesheet.py as CSS hover states
2. Use `translate-x-1` for horizontal shift
3. Add `background: rgba(0,0,0,0.05)` for darkening

---

## Part 8: Timeline & Effort Estimate

| Phase | Task | Duration | Difficulty |
|-------|------|----------|-----------|
| **1** | Update design tokens | 4-6 hours | Low |
| **1** | Update stylesheet | 4-6 hours | Low |
| **2** | Update navigation (TopBar, Sidebar) | 8-10 hours | Medium |
| **2** | Update primary views (Home, Models, Tools) | 12-16 hours | Medium |
| **2** | Update secondary views (Library, Settings) | 10-12 hours | Medium |
| **3** | Testing & polish | 6-8 hours | Medium |
| **3** | Screenshot regression testing | 4-6 hours | Low |
| **TOTAL** | Full redesign | **48-64 hours** | **~2 weeks** |

**Estimated Timeline**: **10 business days** if working 8 hours/day

---

## Part 9: Success Criteria

After completion, your launcher should:

✅ **Look Professional** - Editorial, sophisticated aesthetic  
✅ **Match Stitch Spec** - Colors, typography, spacing exactly  
✅ **Be Responsive** - Work at 1120px, 800px, 600px widths  
✅ **Have Polish** - Smooth animations, consistent interaction patterns  
✅ **Maintain Functionality** - All features work as before  
✅ **Feel Premium** - Generous spacing, calm, focused environment  

---

## Next Steps

1. **Confirm Timeline** - Can you commit 2 weeks for full redesign?
2. **Prioritize Views** - Which views are most important/visible?
3. **Start Phase 1** - Want me to update tokens.py and stylesheet.py first?
4. **Get Fonts** - Do you have Noto Serif and Manrope installed?

**Ready to start the actual code changes?**

