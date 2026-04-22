import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Plus } from 'lucide-react';
import './LibraryView.css';
export default function LibraryView() {
    return (_jsxs("div", { className: "view-container", children: [_jsxs("div", { className: "view-header", children: [_jsx("h2", { children: "Library" }), _jsxs("button", { className: "btn btn-primary", children: [_jsx(Plus, { size: 18 }), "New Collection"] })] }), _jsxs("div", { className: "empty-state", children: [_jsx("h3", { children: "Your library is empty" }), _jsx("p", { children: "Save prompts, templates, and artifacts for quick access" }), _jsx("button", { className: "btn btn-primary", children: "Create Collection" })] })] }));
}
