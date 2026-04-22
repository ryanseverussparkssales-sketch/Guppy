import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState, useRef, useEffect } from 'react';
import { Send, Mic, StopCircle, Plus, Download, Trash2 } from 'lucide-react';
import { useVoice } from '../hooks/useVoice';
import { useWebSocket } from '../hooks/useWebSocket';
import { useChatHistory } from '../hooks/useChatHistory';
import FileUploadZone from '../components/FileUploadZone';
import api from '../api/client';
import './AdvancedAssistantView.css';
export default function AdvancedAssistantView() {
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [showFileUpload, setShowFileUpload] = useState(false);
    const [streamingResponse, setStreamingResponse] = useState('');
    const messagesEndRef = useRef(null);
    const { isListening, isSpeaking, transcript, startListening, stopListening, speak } = useVoice({
        onTranscript: (text) => setInput(input + ' ' + text),
    });
    const { isConnected, send: sendWS } = useWebSocket({
        url: 'ws://localhost:8081/ws',
        onMessage: (data) => {
            if (data.type === 'chunk') {
                setStreamingResponse((prev) => prev + data.content);
            }
            else if (data.type === 'end') {
                setStreamingResponse('');
                setIsLoading(false);
            }
        },
        onError: () => console.error('WebSocket error'),
        reconnect: true,
    });
    const { currentSession, sessions, setCurrentSession, createSession, clearSession, addMessage, } = useChatHistory();
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };
    useEffect(() => {
        scrollToBottom();
    }, [currentSession?.messages]);
    const handleSendMessage = async (text) => {
        if (!text.trim() && selectedFiles.length === 0)
            return;
        // Add user message
        const userMessage = {
            id: Date.now().toString(),
            role: 'user',
            content: text,
            timestamp: Date.now(),
            metadata: {
                files: selectedFiles.map((f) => f.name),
            },
        };
        if (!currentSession) {
            await createSession(text.slice(0, 50) + '...');
            await addMessage(userMessage);
        }
        else {
            await addMessage(userMessage);
        }
        setInput('');
        setSelectedFiles([]);
        setShowFileUpload(false);
        setIsLoading(true);
        try {
            // Create FormData for file upload
            const formData = new FormData();
            formData.append('message', text);
            selectedFiles.forEach((file, index) => {
                formData.append(`file_${index}`, file);
            });
            // Use WebSocket if available, otherwise fall back to HTTP
            if (isConnected) {
                sendWS({ type: 'chat', message: text, files: selectedFiles.map((f) => f.name) });
            }
            else {
                const response = await api.post('/chat', formData);
                // Add assistant message
                const assistantMessage = {
                    id: (Date.now() + 1).toString(),
                    role: 'assistant',
                    content: response.data.response,
                    timestamp: Date.now(),
                    metadata: {
                        source: response.data.source,
                    },
                };
                if (currentSession) {
                    await addMessage(assistantMessage);
                }
                // Speak the response if voice is enabled
                if (isSpeaking === false) {
                    speak(response.data.response, 1, 1);
                }
            }
        }
        catch (error) {
            console.error('Failed to send message:', error);
            const errorMessage = {
                id: (Date.now() + 2).toString(),
                role: 'assistant',
                content: 'Sorry, I encountered an error processing your request.',
                timestamp: Date.now(),
            };
            if (currentSession) {
                await addMessage(errorMessage);
            }
        }
        finally {
            setIsLoading(false);
        }
    };
    const downloadChat = () => {
        if (!currentSession)
            return;
        const chatText = currentSession.messages
            .map((msg) => `${msg.role.toUpperCase()}: ${msg.content}\n(${new Date(msg.timestamp).toLocaleString()})`)
            .join('\n\n');
        const element = document.createElement('a');
        element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(chatText));
        element.setAttribute('download', `${currentSession.title}.txt`);
        element.style.display = 'none';
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
    };
    return (_jsxs("div", { className: "advanced-assistant", children: [_jsxs("div", { className: "chat-sidebar", children: [_jsxs("div", { className: "sidebar-header", children: [_jsx("h3", { children: "Chats" }), _jsx("button", { className: "sidebar-btn", onClick: () => createSession(), title: "New chat", children: _jsx(Plus, { size: 18 }) })] }), _jsx("div", { className: "chat-list", children: sessions.map((session) => (_jsxs("button", { className: `chat-item ${currentSession?.id === session.id ? 'active' : ''}`, onClick: () => setCurrentSession(session), children: [_jsx("span", { className: "chat-title", children: session.title }), _jsx("span", { className: "chat-count", children: session.messages.length })] }, session.id))) })] }), _jsx("div", { className: "chat-main", children: currentSession ? (_jsxs(_Fragment, { children: [_jsxs("div", { className: "chat-header", children: [_jsx("h2", { children: currentSession.title }), _jsxs("div", { className: "header-actions", children: [_jsx("button", { className: "header-btn", onClick: downloadChat, title: "Download chat", disabled: currentSession.messages.length === 0, children: _jsx(Download, { size: 18 }) }), _jsx("button", { className: "header-btn", onClick: () => clearSession(currentSession.id), title: "Clear chat", disabled: currentSession.messages.length === 0, children: _jsx(Trash2, { size: 18 }) })] })] }), _jsxs("div", { className: "messages-container", children: [currentSession.messages.length === 0 ? (_jsxs("div", { className: "empty-state", children: [_jsx("h3", { children: "Start a conversation" }), _jsx("p", { children: "Use voice, text, or upload files to chat with the AI" })] })) : (currentSession.messages.map((msg) => (_jsx("div", { className: `message ${msg.role}`, children: _jsxs("div", { className: "message-content", children: [_jsx("p", { children: msg.content }), msg.metadata?.files && msg.metadata.files.length > 0 && (_jsx("div", { className: "message-files", children: msg.metadata.files.map((file, idx) => (_jsxs("small", { children: ["\uD83D\uDCCE ", file] }, idx))) })), _jsx("span", { className: "message-time", children: new Date(msg.timestamp).toLocaleTimeString([], {
                                                    hour: '2-digit',
                                                    minute: '2-digit',
                                                }) })] }) }, msg.id)))), isLoading && (_jsx("div", { className: "message assistant", children: _jsx("div", { className: "message-content", children: streamingResponse ? (_jsx("p", { children: streamingResponse })) : (_jsxs("div", { className: "typing-indicator", children: [_jsx("span", {}), _jsx("span", {}), _jsx("span", {})] })) }) })), _jsx("div", { ref: messagesEndRef })] }), showFileUpload && (_jsx("div", { className: "file-upload-container", children: _jsx(FileUploadZone, { onFilesSelected: setSelectedFiles, acceptedTypes: ['*'], maxSize: 50 * 1024 * 1024 }) })), _jsxs("div", { className: "input-area", children: [_jsxs("div", { className: "input-toolbar", children: [_jsx("button", { className: "input-btn", onClick: () => setShowFileUpload(!showFileUpload), title: "Upload files", children: "\uD83D\uDCCE" }), _jsx("input", { type: "text", className: "message-input", placeholder: "Type message or press / for commands...", value: input, onChange: (e) => setInput(e.target.value), onKeyDown: (e) => {
                                                if (e.key === 'Enter' && !e.shiftKey) {
                                                    e.preventDefault();
                                                    handleSendMessage(input);
                                                }
                                            }, disabled: isLoading }), _jsx("button", { className: `input-btn voice-btn ${isListening ? 'listening' : ''}`, onClick: isListening ? stopListening : startListening, title: isListening ? 'Stop recording' : 'Start recording', children: isListening ? _jsx(StopCircle, { size: 18 }) : _jsx(Mic, { size: 18 }) }), _jsx("button", { className: "input-btn send-btn", onClick: () => handleSendMessage(input), disabled: !input.trim() || isLoading, children: _jsx(Send, { size: 18 }) })] }), transcript && (_jsx("div", { className: "transcript-preview", children: _jsxs("small", { children: ["Transcript: ", transcript] }) })), selectedFiles.length > 0 && (_jsx("div", { className: "selected-files", children: _jsxs("small", { children: [selectedFiles.length, " file(s) selected"] }) })), _jsx("small", { className: "input-hint", children: "Shift+Enter for newline \u2022 Voice support available \u2022 Drag & drop files to chat" })] })] })) : (_jsxs("div", { className: "empty-state", children: [_jsx("h2", { children: "Welcome to Guppy" }), _jsx("p", { children: "Start a new conversation or select one from the sidebar" }), _jsx("button", { className: "btn btn-primary", onClick: () => createSession('New Chat'), children: "Start New Chat" })] })) })] }));
}
