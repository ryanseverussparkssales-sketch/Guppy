import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { MessageCircle, Package, Library, Cpu, Wrench, Volume2, Palette, Shield, Activity, Menu, X, LogOut, } from 'lucide-react';
import { useAppStore } from '../store';
import './Sidebar.css';
const navItems = [
    { path: '/', label: 'Assistant', icon: MessageCircle },
    { path: '/instances', label: 'Instances', icon: Package },
    { path: '/library', label: 'Library', icon: Library },
    { path: '/models', label: 'Models', icon: Cpu },
    { path: '/tools', label: 'Tools', icon: Wrench },
    { path: '/voices', label: 'Voices', icon: Volume2 },
    { path: '/themes', label: 'Themes', icon: Palette },
];
const adminItems = [
    { path: '/admin', label: 'Admin Panel', icon: Shield },
    { path: '/status', label: 'Status', icon: Activity },
];
export default function Sidebar() {
    const location = useLocation();
    const [mobileOpen, setMobileOpen] = useState(false);
    const { sidebarOpen, setSidebarOpen } = useAppStore();
    const handleLogout = () => {
        localStorage.removeItem('accessToken');
        window.location.href = '/login';
    };
    return (_jsxs(_Fragment, { children: [_jsx("button", { className: "sidebar-toggle", onClick: () => setMobileOpen(!mobileOpen), children: mobileOpen ? _jsx(X, { size: 20 }) : _jsx(Menu, { size: 20 }) }), _jsxs("aside", { className: `sidebar ${mobileOpen ? 'mobile-open' : ''} ${sidebarOpen ? 'expanded' : 'collapsed'}`, children: [_jsxs("div", { className: "sidebar-header", children: [_jsx("h1", { className: "sidebar-title", children: "Guppy" }), _jsx("button", { className: "sidebar-collapse-btn", onClick: () => setSidebarOpen(!sidebarOpen), title: sidebarOpen ? 'Collapse' : 'Expand', children: sidebarOpen ? '▶' : '◀' })] }), _jsxs("nav", { className: "sidebar-nav", children: [_jsx("div", { className: "nav-section", children: navItems.map((item) => {
                                    const Icon = item.icon;
                                    const isActive = location.pathname === item.path;
                                    return (_jsxs(Link, { to: item.path, className: `sidebar-nav-item ${isActive ? 'active' : ''}`, onClick: () => setMobileOpen(false), children: [_jsx(Icon, { size: 20, className: "nav-icon" }), sidebarOpen && _jsx("span", { className: "nav-label", children: item.label })] }, item.path));
                                }) }), _jsx("div", { className: "nav-divider" }), _jsx("div", { className: "nav-section", children: adminItems.map((item) => {
                                    const Icon = item.icon;
                                    const isActive = location.pathname === item.path;
                                    return (_jsxs(Link, { to: item.path, className: `sidebar-nav-item ${isActive ? 'active' : ''}`, onClick: () => setMobileOpen(false), children: [_jsx(Icon, { size: 20, className: "nav-icon" }), sidebarOpen && _jsx("span", { className: "nav-label", children: item.label })] }, item.path));
                                }) })] }), _jsxs("div", { className: "sidebar-footer", children: [_jsxs("button", { className: "logout-btn", onClick: handleLogout, title: "Logout", children: [_jsx(LogOut, { size: 18 }), sidebarOpen && _jsx("span", { children: "Logout" })] }), _jsx("div", { className: "sidebar-version", children: sidebarOpen && _jsx("span", { children: "v1.0.0" }) })] })] })] }));
}
