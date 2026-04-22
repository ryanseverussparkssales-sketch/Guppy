import { Fragment as _Fragment, jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Routes, Route, Navigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { useTheme } from './hooks/useTheme';
import Layout from './components/Layout';
import AdvancedAssistantView from './views/AdvancedAssistantView';
import InstancesView from './views/InstancesView';
import LibraryView from './views/LibraryView';
import ModelsView from './views/ModelsView';
import ToolsView from './views/ToolsView';
import VoicesView from './views/VoicesView';
import AdminPanel from './views/AdminPanel';
import ThemeSettings from './views/ThemeSettings';
import LoginView from './views/LoginView';
import StatusView from './views/StatusView';
import api from './api/client';
import './App.css';
// Protected route component
function ProtectedRoute({ children }) {
    const token = localStorage.getItem('accessToken');
    return token ? _jsx(_Fragment, { children: children }) : _jsx(Navigate, { to: "/login", replace: true });
}
function App() {
    const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('accessToken'));
    const { setThemeMode, setThemePreset } = useTheme();
    // Check authentication on mount
    useEffect(() => {
        const token = localStorage.getItem('accessToken');
        setIsLoggedIn(!!token);
        // Load saved theme preferences
        const savedTheme = localStorage.getItem('theme');
        const savedPreset = localStorage.getItem('themePreset');
        if (savedTheme)
            setThemeMode(savedTheme);
        if (savedPreset)
            setThemePreset(savedPreset);
    }, [setThemeMode, setThemePreset]);
    // Check token validity
    useEffect(() => {
        const verifyToken = async () => {
            const token = localStorage.getItem('accessToken');
            if (!token)
                return;
            try {
                await api.get('/auth/self-check');
            }
            catch {
                // Token is invalid or expired
                localStorage.removeItem('accessToken');
                setIsLoggedIn(false);
            }
        };
        if (isLoggedIn) {
            verifyToken();
            const interval = setInterval(verifyToken, 5 * 60 * 1000); // Check every 5 minutes
            return () => clearInterval(interval);
        }
    }, [isLoggedIn]);
    if (!isLoggedIn) {
        return _jsx(LoginView, {});
    }
    return (_jsx(Layout, { children: _jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(ProtectedRoute, { children: _jsx(AdvancedAssistantView, {}) }) }), _jsx(Route, { path: "/instances", element: _jsx(ProtectedRoute, { children: _jsx(InstancesView, {}) }) }), _jsx(Route, { path: "/library", element: _jsx(ProtectedRoute, { children: _jsx(LibraryView, {}) }) }), _jsx(Route, { path: "/models", element: _jsx(ProtectedRoute, { children: _jsx(ModelsView, {}) }) }), _jsx(Route, { path: "/tools", element: _jsx(ProtectedRoute, { children: _jsx(ToolsView, {}) }) }), _jsx(Route, { path: "/voices", element: _jsx(ProtectedRoute, { children: _jsx(VoicesView, {}) }) }), _jsx(Route, { path: "/themes", element: _jsx(ProtectedRoute, { children: _jsx(ThemeSettings, {}) }) }), _jsx(Route, { path: "/admin", element: _jsx(ProtectedRoute, { children: _jsx(AdminPanel, {}) }) }), _jsx(Route, { path: "/status", element: _jsx(ProtectedRoute, { children: _jsx(StatusView, {}) }) }), _jsx(Route, { path: "/login", element: _jsx(LoginView, {}) }), _jsx(Route, { path: "*", element: _jsx(Navigate, { to: "/", replace: true }) })] }) }));
}
export default App;
