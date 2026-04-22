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
    const { logout } = useAppStore();
    const [isMobileOpen, setIsMobileOpen] = useState(false);
    const handleLogout = () => {
        localStorage.removeItem('accessToken');
        logout();
    };
    const isActive = (path) => {
        return location.pathname === path;
    };
    return (_jsxs(_Fragment, { children: [_jsx("button", { className: "sidebar-mobile-toggle", onClick: () => setIsMobileOpen(!isMobileOpen), children: isMobileOpen ? _jsx(X, { size: 24 }) : _jsx(Menu, { size: 24 }) }), _jsxs("aside", { className: `sidebar ${isMobileOpen ? 'sidebar-open' : ''}`, children: [_jsx("div", { className: "sidebar-header", children: _jsx("h1", { className: "sidebar-title", children: "Guppy" }) }), _jsxs("nav", { className: "sidebar-nav", children: [_jsxs("div", { className: "nav-section", children: [_jsx("div", { className: "nav-section-title", children: "Main" }), navItems.map((item) => (_jsxs(Link, { to: item.path, className: `nav-item ${isActive(item.path) ? 'active' : ''}`, onClick: () => setIsMobileOpen(false), children: [_jsx(item.icon, { size: 20 }), _jsx("span", { children: item.label })] }, item.path)))] }), _jsxs("div", { className: "nav-section", children: [_jsx("div", { className: "nav-section-title", children: "Admin" }), adminItems.map((item) => (_jsxs(Link, { to: item.path, className: `nav-item ${isActive(item.path) ? 'active' : ''}`, onClick: () => setIsMobileOpen(false), children: [_jsx(item.icon, { size: 20 }), _jsx("span", { children: item.label })] }, item.path)))] })] }), _jsxs("button", { className: "sidebar-logout", onClick: handleLogout, children: [_jsx(LogOut, { size: 20 }), _jsx("span", { children: "Logout" })] })] })] }));
}
