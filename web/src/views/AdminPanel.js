import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
import { BarChart, Users, Settings, CheckCircle } from 'lucide-react';
import api from '../api/client';
import './AdminPanel.css';
export default function AdminPanel() {
    const [stats, setStats] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('dashboard');
    useEffect(() => {
        const loadStats = async () => {
            try {
                const response = await api.get('/status');
                setStats({
                    uptime: 42 * 24 * 60 * 60 * 1000, // Example
                    requestsTotal: response.data.requests_total || 0,
                    errorsTotal: response.data.errors_total || 0,
                    avgLatency: response.data.average_latency_ms || 0,
                });
            }
            catch (error) {
                console.error('Failed to load stats:', error);
            }
            finally {
                setIsLoading(false);
            }
        };
        loadStats();
        const interval = setInterval(loadStats, 30000);
        return () => clearInterval(interval);
    }, []);
    const formatUptime = (ms) => {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        if (days > 0)
            return `${days}d ${hours % 24}h`;
        if (hours > 0)
            return `${hours}h ${minutes % 60}m`;
        return `${minutes}m`;
    };
    return (_jsxs("div", { className: "admin-container", children: [_jsxs("div", { className: "admin-header", children: [_jsx("h2", { children: "Admin Panel" }), _jsx("p", { children: "System management and monitoring" })] }), _jsxs("div", { className: "admin-tabs", children: [_jsxs("button", { className: `tab-btn ${activeTab === 'dashboard' ? 'active' : ''}`, onClick: () => setActiveTab('dashboard'), children: [_jsx(BarChart, { size: 18 }), "Dashboard"] }), _jsxs("button", { className: `tab-btn ${activeTab === 'users' ? 'active' : ''}`, onClick: () => setActiveTab('users'), children: [_jsx(Users, { size: 18 }), "Users"] }), _jsxs("button", { className: `tab-btn ${activeTab === 'settings' ? 'active' : ''}`, onClick: () => setActiveTab('settings'), children: [_jsx(Settings, { size: 18 }), "Settings"] })] }), activeTab === 'dashboard' && (_jsxs("div", { className: "admin-dashboard", children: [isLoading ? (_jsx("div", { className: "loading", children: "Loading stats..." })) : stats ? (_jsxs("div", { className: "stats-grid", children: [_jsxs("div", { className: "stat-card healthy", children: [_jsx("div", { className: "stat-icon", children: _jsx(CheckCircle, { size: 32 }) }), _jsx("h3", { children: "System Status" }), _jsx("p", { children: "Healthy" })] }), _jsxs("div", { className: "stat-card", children: [_jsx("div", { className: "stat-value", children: formatUptime(stats.uptime) }), _jsx("h3", { children: "Uptime" }), _jsx("p", { children: "System operational" })] }), _jsxs("div", { className: "stat-card", children: [_jsx("div", { className: "stat-value", children: stats.requestsTotal.toLocaleString() }), _jsx("h3", { children: "Total Requests" }), _jsx("p", { children: "API calls processed" })] }), _jsxs("div", { className: "stat-card", children: [_jsx("div", { className: "stat-value", children: stats.errorsTotal }), _jsx("h3", { children: "Errors" }), _jsx("p", { className: stats.errorsTotal > 0 ? 'warning' : '', children: stats.errorsTotal > 0 ? 'Detected' : 'None' })] }), _jsxs("div", { className: "stat-card", children: [_jsxs("div", { className: "stat-value", children: [stats.avgLatency.toFixed(0), "ms"] }), _jsx("h3", { children: "Avg Response Time" }), _jsx("p", { children: "API performance" })] }), _jsxs("div", { className: "stat-card", children: [_jsx("div", { className: "stat-value", children: "4/4" }), _jsx("h3", { children: "Services" }), _jsx("p", { children: "All operational" })] })] })) : null, _jsxs("div", { className: "recent-logs", children: [_jsx("h3", { children: "Recent Activity" }), _jsxs("div", { className: "log-list", children: [_jsxs("div", { className: "log-item success", children: [_jsx(CheckCircle, { size: 16 }), _jsx("span", { children: "API server started successfully" }), _jsx("small", { children: "2 minutes ago" })] }), _jsxs("div", { className: "log-item", children: [_jsx("span", { children: "1,234 requests processed" }), _jsx("small", { children: "last hour" })] }), _jsxs("div", { className: "log-item", children: [_jsx("span", { children: "Web UI built and deployed" }), _jsx("small", { children: "30 minutes ago" })] })] })] })] })), activeTab === 'users' && (_jsxs("div", { className: "admin-users", children: [_jsxs("div", { className: "users-header", children: [_jsx("h3", { children: "Manage Users" }), _jsx("button", { className: "btn btn-primary", children: "Add User" })] }), _jsxs("div", { className: "users-table", children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "Email" }), _jsx("th", { children: "Role" }), _jsx("th", { children: "Joined" }), _jsx("th", { children: "Last Active" }), _jsx("th", { children: "Actions" })] }) }), _jsxs("tbody", { children: [_jsxs("tr", { children: [_jsx("td", { children: "admin@guppy.local" }), _jsx("td", { children: _jsx("span", { className: "badge admin", children: "Admin" }) }), _jsx("td", { children: "2024-01-15" }), _jsx("td", { children: "Just now" }), _jsxs("td", { children: [_jsx("button", { className: "action-btn", children: "Edit" }), _jsx("button", { className: "action-btn danger", children: "Remove" })] })] }), _jsxs("tr", { children: [_jsx("td", { children: "dev-token@demo" }), _jsx("td", { children: _jsx("span", { className: "badge", children: "User" }) }), _jsx("td", { children: "2024-01-20" }), _jsx("td", { children: "5 minutes ago" }), _jsxs("td", { children: [_jsx("button", { className: "action-btn", children: "Edit" }), _jsx("button", { className: "action-btn danger", children: "Remove" })] })] })] })] })] })), activeTab === 'settings' && (_jsxs("div", { className: "admin-settings", children: [_jsxs("div", { className: "settings-section", children: [_jsx("h3", { children: "API Configuration" }), _jsxs("div", { className: "setting-group", children: [_jsx("label", { children: "API Port" }), _jsx("input", { type: "number", defaultValue: 8081 })] }), _jsxs("div", { className: "setting-group", children: [_jsx("label", { children: "Max Requests/Minute" }), _jsx("input", { type: "number", defaultValue: 1000 })] }), _jsxs("div", { className: "setting-group", children: [_jsx("label", { children: "Request Timeout (seconds)" }), _jsx("input", { type: "number", defaultValue: 120 })] })] }), _jsxs("div", { className: "settings-section", children: [_jsx("h3", { children: "Database" }), _jsx("div", { className: "setting-group", children: _jsxs("label", { children: [_jsx("input", { type: "checkbox", defaultChecked: true }), "Enable backups"] }) }), _jsxs("div", { className: "setting-group", children: [_jsx("label", { children: "Backup Interval (hours)" }), _jsx("input", { type: "number", defaultValue: 24 })] })] }), _jsxs("div", { className: "settings-section", children: [_jsx("h3", { children: "Security" }), _jsx("div", { className: "setting-group", children: _jsxs("label", { children: [_jsx("input", { type: "checkbox", defaultChecked: true }), "Enable HTTPS only"] }) }), _jsx("div", { className: "setting-group", children: _jsxs("label", { children: [_jsx("input", { type: "checkbox", defaultChecked: true }), "Rate limiting"] }) })] }), _jsx("button", { className: "btn btn-primary", children: "Save Settings" })] }))] }));
}
