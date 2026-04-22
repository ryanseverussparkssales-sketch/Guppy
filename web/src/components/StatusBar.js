import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useAppStore } from '../store';
import { Activity } from 'lucide-react';
import './StatusBar.css';
export default function StatusBar() {
    const { status } = useAppStore();
    const isHealthy = status && typeof status === 'object' && status.status === 'healthy';
    return (_jsx("footer", { className: "statusbar", children: _jsxs("div", { className: "statusbar-content", children: [_jsxs("div", { className: "statusbar-item", children: [_jsx(Activity, { size: 14, className: `status-icon ${isHealthy ? 'healthy' : 'unhealthy'}` }), _jsx("span", { className: "status-text", children: isHealthy ? 'API Connected' : 'Connecting...' })] }), _jsx("div", { className: "statusbar-spacer" }), _jsx("div", { className: "statusbar-info", children: _jsx("span", { className: "info-text", children: "Guppy API v1.0" }) })] }) }));
}
