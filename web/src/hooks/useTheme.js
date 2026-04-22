import { useState, useCallback, useEffect } from 'react';
export const THEME_PRESETS = {
    default: {
        light: {
            primary: '#ffffff',
            secondary: '#f5f5f5',
            accent: '#3b82f6',
            background: '#ffffff',
            text: '#1a1a1a',
            border: '#e0e0e0',
        },
        dark: {
            primary: '#0f0f0f',
            secondary: '#1a1a1a',
            accent: '#3b82f6',
            background: '#0f0f0f',
            text: '#ffffff',
            border: '#2a2a2a',
        },
    },
    cyberpunk: {
        light: {
            primary: '#ffffff',
            secondary: '#f0f0f0',
            accent: '#00ffff',
            background: '#ffffff',
            text: '#000000',
            border: '#cccccc',
        },
        dark: {
            primary: '#0a0e27',
            secondary: '#1a1f3a',
            accent: '#00ffff',
            background: '#0a0e27',
            text: '#00ffff',
            border: '#00ffff',
        },
    },
    solarized: {
        light: {
            primary: '#fdf6e3',
            secondary: '#eee8d5',
            accent: '#268bd2',
            background: '#fdf6e3',
            text: '#657b83',
            border: '#d6d0c8',
        },
        dark: {
            primary: '#002b36',
            secondary: '#073642',
            accent: '#268bd2',
            background: '#002b36',
            text: '#839496',
            border: '#073642',
        },
    },
    nord: {
        light: {
            primary: '#eceff4',
            secondary: '#e5e9f0',
            accent: '#88c0d0',
            background: '#eceff4',
            text: '#2e3440',
            border: '#d8dee9',
        },
        dark: {
            primary: '#2e3440',
            secondary: '#3b4252',
            accent: '#88c0d0',
            background: '#2e3440',
            text: '#eceff4',
            border: '#3b4252',
        },
    },
};
export const useTheme = (initialTheme = 'auto', initialPreset = 'default') => {
    const [theme, setTheme] = useState(() => localStorage.getItem('theme') || initialTheme);
    const [preset, setPreset] = useState(() => localStorage.getItem('themePreset') || initialPreset);
    const [customColors, setCustomColors] = useState(() => {
        const stored = localStorage.getItem('customThemeColors');
        return stored ? JSON.parse(stored) : {};
    });
    const getResolvedTheme = useCallback(() => {
        if (theme !== 'auto') {
            return theme;
        }
        return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }, [theme]);
    const applyTheme = useCallback((newTheme, newPreset, colors) => {
        const resolved = newTheme !== 'auto' ? newTheme : getResolvedTheme();
        const presetColors = THEME_PRESETS[newPreset]?.[resolved] || THEME_PRESETS.default[resolved];
        const finalColors = colors || presetColors;
        // Apply CSS variables
        const root = document.documentElement;
        root.style.setProperty('--color-bg-primary', finalColors.background);
        root.style.setProperty('--color-bg-secondary', finalColors.secondary);
        root.style.setProperty('--color-text-primary', finalColors.text);
        root.style.setProperty('--color-text-secondary', finalColors.text);
        root.style.setProperty('--color-accent', finalColors.accent);
        root.style.setProperty('--color-border', finalColors.border);
        // Apply to body
        document.body.style.backgroundColor = finalColors.background;
        document.body.style.color = finalColors.text;
    }, [getResolvedTheme]);
    const setThemeMode = useCallback((newTheme) => {
        setTheme(newTheme);
        localStorage.setItem('theme', newTheme);
        applyTheme(newTheme, preset);
    }, [preset, applyTheme]);
    const setThemePreset = useCallback((newPreset) => {
        setPreset(newPreset);
        localStorage.setItem('themePreset', newPreset);
        applyTheme(theme, newPreset);
    }, [theme, applyTheme]);
    const setCustomTheme = useCallback((name, colors) => {
        const updated = { ...customColors, [name]: colors };
        setCustomColors(updated);
        localStorage.setItem('customThemeColors', JSON.stringify(updated));
        applyTheme(theme, name, colors);
    }, [customColors, theme, applyTheme]);
    // Apply theme on mount and when it changes
    useEffect(() => {
        applyTheme(theme, preset);
    }, [theme, preset, applyTheme]);
    // Listen for system theme changes
    useEffect(() => {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        const handleChange = () => {
            if (theme === 'auto') {
                applyTheme('auto', preset);
            }
        };
        mediaQuery.addEventListener('change', handleChange);
        return () => mediaQuery.removeEventListener('change', handleChange);
    }, [theme, preset, applyTheme]);
    return {
        theme,
        preset,
        customColors,
        resolvedTheme: getResolvedTheme(),
        setThemeMode,
        setThemePreset,
        setCustomTheme,
        availablePresets: Object.keys(THEME_PRESETS),
        availableThemes: ['light', 'dark', 'auto'],
    };
};
