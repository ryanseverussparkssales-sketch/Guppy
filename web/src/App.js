import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Routes, Route } from 'react-router-dom';
import { useEffect } from 'react';
import Layout from './components/Layout';
import AssistantView from './views/AssistantView';
import InstancesView from './views/InstancesView';
import LibraryView from './views/LibraryView';
import ModelsView from './views/ModelsView';
import ToolsView from './views/ToolsView';
import VoicesView from './views/VoicesView';
import SettingsView from './views/SettingsView';
import StatusView from './views/StatusView';
import { useAppStore } from './store';
import api from './api/client';
import './App.css';
function App() {
    const { setStatus } = useAppStore();
    useEffect(() => {
        const checkStatus = async () => {
            try {
                const response = await api.get('/');
                setStatus(response.data);
            }
            catch (error) {
                console.error('Failed to fetch API status:', error);
            }
        };
        checkStatus();
        const interval = setInterval(checkStatus, 30000); // Check every 30s
        return () => clearInterval(interval);
    }, [setStatus]);
    return (_jsx(Layout, { children: _jsxs(Routes, { children: [_jsx(Route, { path: "/", element: _jsx(AssistantView, {}) }), _jsx(Route, { path: "/instances", element: _jsx(InstancesView, {}) }), _jsx(Route, { path: "/library", element: _jsx(LibraryView, {}) }), _jsx(Route, { path: "/models", element: _jsx(ModelsView, {}) }), _jsx(Route, { path: "/tools", element: _jsx(ToolsView, {}) }), _jsx(Route, { path: "/voices", element: _jsx(VoicesView, {}) }), _jsx(Route, { path: "/settings", element: _jsx(SettingsView, {}) }), _jsx(Route, { path: "/status", element: _jsx(StatusView, {}) })] }) }));
}
export default App;
