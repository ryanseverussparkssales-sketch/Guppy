import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useTheme } from '../hooks/useTheme';
import { Moon, Sun } from 'lucide-react';
import './TopBar.css';
export default function TopBar() {
    const { theme, setThemeMode } = useTheme();
    const toggleTheme = () => {
        setThemeMode(theme === 'dark' ? 'light' : 'dark');
    };
    return (_jsx("header", { className: "topbar", children: _jsxs("div", { className: "topbar-content", children: [_jsx("h2", { className: "topbar-title", children: "Welcome" }), _jsx("button", { className: "topbar-theme-toggle", onClick: toggleTheme, "aria-label": "Toggle theme", children: theme === 'dark' ? _jsx(Sun, { size: 20 }) : _jsx(Moon, { size: 20 }) })] }) }));
}
