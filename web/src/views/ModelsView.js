import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Settings } from 'lucide-react';
import './ModelsView.css';
export default function ModelsView() {
    return (_jsxs("div", { className: "view-container", children: [_jsxs("div", { className: "view-header", children: [_jsx("h2", { children: "Models & LLMs" }), _jsxs("button", { className: "btn btn-primary", children: [_jsx(Settings, { size: 18 }), "Configure"] })] }), _jsxs("div", { className: "empty-state", children: [_jsx("h3", { children: "No models configured" }), _jsx("p", { children: "Set up your preferred AI models (local or cloud)" }), _jsx("button", { className: "btn btn-primary", children: "Add Model" })] })] }));
}
