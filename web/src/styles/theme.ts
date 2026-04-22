/**
 * Stitch Design System - Atoll Editorial theme
 * Shared design tokens for Guppy web UI
 */

export const colors = {
  // Primary accents
  primary: "#FF6D00",        // Sunset orange
  secondary: "#006A6A",      // Turquoise
  accent: {
    orange: "#FF6D00",       // Primary action
    teal: "#006A6A",         // Secondary action
    brightTeal: "#08BDBD",   // Bright teal
  },

  // Status colors
  status: {
    success: "#00C853",      // Green
    warning: "#FFD600",      // Amber
    error: "#FF3D00",        // Red
    info: "#006A6A",         // Teal
  },

  // Neutral palette
  text: "#1B1C19",           // Very dark (almost black)
  textSecondary: "#6B6B6B",  // Medium gray
  textTertiary: "#9E9E9E",   // Light gray
  textInverse: "#FFFFFF",    // White for dark backgrounds

  // Backgrounds
  surface: {
    base: "#FAFAF8",         // Off-white
    elevated: "#FFFFFF",     // Pure white
    sunken: "#F5F5F3",       // Slightly darker
  },

  // Borders
  border: {
    soft: "#E8E8E8",         // Light
    default: "#D9D9D9",      // Standard
    strong: "#BFBFBF",       // Dark
  },

  // Opacity colors for overlays
  overlay: {
    dark: "rgba(0, 0, 0, 0.5)",
    light: "rgba(255, 255, 255, 0.8)",
  },

  // Semantic backgrounds
  background: {
    success: "rgba(0, 200, 83, 0.1)",
    warning: "rgba(255, 214, 0, 0.1)",
    error: "rgba(255, 61, 0, 0.1)",
    info: "rgba(0, 106, 106, 0.1)",
  },
};

export const typography = {
  fontFamilies: {
    sans: '"Manrope", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    serif: '"Noto Serif", Georgia, serif',
    mono: '"JetBrains Mono", "Courier New", monospace',
  },

  sizes: {
    xs: "12px",
    sm: "14px",
    base: "16px",
    lg: "18px",
    xl: "20px",
    "2xl": "24px",
    "3xl": "28px",
    "4xl": "32px",
    "5xl": "36px",
  },

  weights: {
    light: 300,
    normal: 400,
    medium: 500,
    semibold: 600,
    bold: 700,
    extrabold: 900,
  },

  lineHeights: {
    tight: 1.25,
    normal: 1.5,
    relaxed: 1.75,
    loose: 2,
  },
};

export const spacing = {
  0: "0",
  1: "4px",
  2: "8px",
  3: "12px",
  4: "16px",
  5: "20px",
  6: "24px",
  8: "32px",
  10: "40px",
  12: "48px",
  16: "64px",
  20: "80px",
  24: "96px",
};

export const borderRadius = {
  none: "0",
  sm: "2px",
  base: "4px",
  md: "8px",
  lg: "12px",
  xl: "16px",
  full: "9999px",
};

export const shadows = {
  sm: "0 1px 2px 0 rgba(0, 0, 0, 0.05)",
  base: "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)",
  md: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
  lg: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)",
  xl: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
};

export const breakpoints = {
  xs: "320px",
  sm: "640px",
  md: "768px",
  lg: "1024px",
  xl: "1280px",
  "2xl": "1536px",
};

export const transitions = {
  fast: "150ms ease-in-out",
  base: "200ms ease-in-out",
  slow: "300ms ease-in-out",
};

// Preset component styles
export const componentStyles = {
  button: {
    primary: {
      background: colors.accent.orange,
      color: colors.textInverse,
      border: `1px solid ${colors.accent.orange}`,
      borderRadius: borderRadius.base,
      padding: `${spacing[2]} ${spacing[4]}`,
      fontSize: typography.sizes.sm,
      fontWeight: typography.weights.semibold,
      cursor: "pointer",
      transition: transitions.base,
      "&:hover": {
        background: "#E55800",
        borderColor: "#E55800",
      },
      "&:focus": {
        outline: `2px solid ${colors.accent.orange}`,
        outlineOffset: "2px",
      },
      "&:disabled": {
        opacity: 0.5,
        cursor: "not-allowed",
      },
    },
    secondary: {
      background: colors.surface.elevated,
      color: colors.accent.teal,
      border: `1px solid ${colors.accent.teal}`,
      borderRadius: borderRadius.base,
      padding: `${spacing[2]} ${spacing[4]}`,
      fontSize: typography.sizes.sm,
      fontWeight: typography.weights.semibold,
      cursor: "pointer",
      transition: transitions.base,
      "&:hover": {
        background: colors.background.info,
      },
      "&:focus": {
        outline: `2px solid ${colors.accent.teal}`,
        outlineOffset: "2px",
      },
    },
  },

  input: {
    background: colors.surface.elevated,
    color: colors.text,
    border: `1px solid ${colors.border.soft}`,
    borderRadius: borderRadius.base,
    padding: `${spacing[2]} ${spacing[3]}`,
    fontSize: typography.sizes.base,
    fontFamily: typography.fontFamilies.mono,
    transition: transitions.base,
    "&:focus": {
      outline: "none",
      borderColor: colors.accent.teal,
      boxShadow: `0 0 0 2px ${colors.background.info}`,
    },
  },

  card: {
    background: colors.surface.elevated,
    border: `1px solid ${colors.border.soft}`,
    borderRadius: borderRadius.lg,
    padding: spacing[4],
    boxShadow: shadows.sm,
  },

  section: {
    background: colors.surface.base,
    borderRadius: borderRadius.base,
    padding: spacing[4],
  },
};

export const theme = {
  colors,
  typography,
  spacing,
  borderRadius,
  shadows,
  breakpoints,
  transitions,
  componentStyles,
};

export type Theme = typeof theme;
