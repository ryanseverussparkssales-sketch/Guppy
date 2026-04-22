/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Atoll Editorial Design System
        // Base surfaces - "White Sand" foundation
        surface: {
          DEFAULT: '#fbf9f4',
          container: {
            DEFAULT: '#f0eee9',
            low: '#f5f3ee',
            high: '#eae8e3',
            highest: '#e4e2dd',
            lowest: '#ffffff',
          },
          variant: '#e4e2dd',
          dim: '#dbdad5',
          bright: '#fbf9f4',
        },
        // Primary - Atoll Turquoise
        primary: {
          DEFAULT: '#006a6a',
          container: '#08bdbd',
          fixed: '#6af7f7',
          'fixed-dim': '#47dada',
        },
        // Secondary - Sunset Orange
        secondary: {
          DEFAULT: '#ab3500',
          container: '#fe6a34',
          fixed: '#ffdbd0',
          'fixed-dim': '#ffb59d',
        },
        // Tertiary - Coral
        tertiary: {
          DEFAULT: '#994615',
          container: '#f78f58',
          fixed: '#ffdbcb',
          'fixed-dim': '#ffb692',
        },
        // Text colors
        'on-surface': '#1b1c19',
        'on-surface-variant': '#3c4949',
        'on-primary': '#ffffff',
        'on-primary-container': '#004646',
        'on-secondary': '#ffffff',
        'on-secondary-container': '#5d1900',
        'on-tertiary': '#ffffff',
        'on-tertiary-container': '#6c2a00',
        // Outline
        outline: {
          DEFAULT: '#6c7a79',
          variant: '#bbc9c9',
        },
        // Inverse
        'inverse-surface': '#30312e',
        'inverse-on-surface': '#f2f1ec',
        'inverse-primary': '#47dada',
        // Error
        error: '#ba1a1a',
        'error-container': '#ffdad6',
        'on-error': '#ffffff',
        'on-error-container': '#93000a',
        // Background (same as surface for consistency)
        background: '#fbf9f4',
        'on-background': '#1b1c19',
        // Semantic status colors
        success: {
          DEFAULT: '#00c853',
          foreground: '#ffffff',
        },
        warning: {
          DEFAULT: '#ffd600',
          foreground: '#1b1c19',
        },
        destructive: {
          DEFAULT: '#ff3d00',
          foreground: '#ffffff',
        },
      },
      borderRadius: {
        DEFAULT: '0.125rem',
        sm: '0.125rem',
        md: '0.25rem',
        lg: '0.5rem',
        xl: '0.75rem',
        '2xl': '1rem',
        full: '9999px',
      },
      fontFamily: {
        headline: ['Noto Serif', 'Georgia', 'serif'],
        body: ['Manrope', 'system-ui', 'sans-serif'],
        label: ['Manrope', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Menlo', 'monospace'],
      },
      boxShadow: {
        'soft': '0 4px 30px rgba(27, 28, 25, 0.06)',
        'soft-lg': '0 10px 60px rgba(27, 28, 25, 0.08)',
        'ghost': '0 0 0 1px rgba(187, 201, 201, 0.15)',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(0)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
      },
      animation: {
        'fade-in': 'fade-in 0.3s cubic-bezier(0.23, 1, 0.32, 1)',
        'slide-in': 'slide-in 0.4s cubic-bezier(0.23, 1, 0.32, 1)',
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
      },
      transitionTimingFunction: {
        'viscous': 'cubic-bezier(0.23, 1, 0.32, 1)',
      },
    },
  },
  plugins: [],
}
