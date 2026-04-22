import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Plus } from 'lucide-react';
import './InstancesView.css';
export default function InstancesView() {
    return (_jsxs("div", { className: "view-container", children: [_jsxs("div", { className: "view-header", children: [_jsx("h2", { children: "Instances" }), _jsxs("button", { className: "btn btn-primary", children: [_jsx(Plus, { size: 18 }), "New Instance"] })] }), _jsxs("div", { className: "empty-state", children: [_jsx("h3", { children: "No instances yet" }), _jsx("p", { children: "Create your first instance to get started with Guppy" }), _jsx("button", { className: "btn btn-primary", children: "Create Instance" })] })] }));
}
