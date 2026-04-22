import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import Sidebar from './Sidebar';
import TopBar from './TopBar';
import StatusBar from './StatusBar';
import './Layout.css';
export default function Layout({ children }) {
    return (_jsxs("div", { className: "layout", children: [_jsx(Sidebar, {}), _jsxs("div", { className: "layout-main", children: [_jsx(TopBar, {}), _jsx("main", { className: "layout-content", children: children }), _jsx(StatusBar, {})] })] }));
}
