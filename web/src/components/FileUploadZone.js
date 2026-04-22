import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useRef, useState } from 'react';
import { Upload, X } from 'lucide-react';
import './FileUploadZone.css';
export default function FileUploadZone({ onFilesSelected, maxSize = 10 * 1024 * 1024, // 10MB
acceptedTypes = ['*'], }) {
    const [isDragging, setIsDragging] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const inputRef = useRef(null);
    const handleDragEnter = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(true);
    };
    const handleDragLeave = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
    };
    const handleDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDragging(false);
        const files = Array.from(e.dataTransfer.files);
        processFiles(files);
    };
    const handleInputChange = (e) => {
        if (e.target.files) {
            const files = Array.from(e.target.files);
            processFiles(files);
        }
    };
    const processFiles = (files) => {
        const validFiles = files.filter((file) => {
            if (file.size > maxSize) {
                console.warn(`File ${file.name} exceeds size limit`);
                return false;
            }
            if (acceptedTypes[0] !== '*' && !acceptedTypes.includes(file.type)) {
                console.warn(`File ${file.name} has unsupported type`);
                return false;
            }
            return true;
        });
        setSelectedFiles(validFiles);
        onFilesSelected?.(validFiles);
    };
    const removeFile = (index) => {
        const updated = selectedFiles.filter((_, i) => i !== index);
        setSelectedFiles(updated);
        onFilesSelected?.(updated);
    };
    return (_jsxs("div", { className: "file-upload-zone", children: [_jsx("input", { ref: inputRef, type: "file", multiple: true, onChange: handleInputChange, className: "file-input", accept: acceptedTypes.join(','), style: { display: 'none' } }), _jsxs("div", { className: `drop-zone ${isDragging ? 'dragging' : ''}`, onDragEnter: handleDragEnter, onDragLeave: handleDragLeave, onDragOver: (e) => e.preventDefault(), onDrop: handleDrop, onClick: () => inputRef.current?.click(), children: [_jsx(Upload, { size: 32, className: "upload-icon" }), _jsx("p", { className: "drop-text", children: "Drag files here or click to upload" }), _jsxs("small", { children: ["Max ", Math.floor(maxSize / 1024 / 1024), "MB per file"] })] }), selectedFiles.length > 0 && (_jsxs("div", { className: "file-list", children: [_jsxs("h4", { children: ["Selected Files (", selectedFiles.length, ")"] }), selectedFiles.map((file, index) => (_jsxs("div", { className: "file-item", children: [_jsx("span", { className: "file-name", children: file.name }), _jsxs("span", { className: "file-size", children: ["(", (file.size / 1024).toFixed(1), "KB)"] }), _jsx("button", { className: "file-remove", onClick: () => removeFile(index), title: "Remove file", children: _jsx(X, { size: 16 }) })] }, `${file.name}-${index}`)))] }))] }));
}
