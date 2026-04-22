import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useRef, useEffect } from 'react';
import { Send, Mic, Plus } from 'lucide-react';
import { useAppStore } from '../store';
import api from '../api/client';
import './AssistantView.css';
export default function AssistantView() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isListening, setIsListening] = useState(false);
    const messagesEndRef = useRef(null);
    const { isLoading: globalLoading } = useAppStore();
    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };
    useEffect(() => {
        scrollToBottom();
    }, [messages]);
    const handleSendMessage = async (text) => {
        if (!text.trim())
            return;
        const userMessage = {
            id: Date.now().toString(),
            role: 'user',
            content: text,
            timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMessage]);
        setInput('');
        setIsLoading(true);
        try {
            // Call the chat endpoint
            const response = await api.post('/chat', {
                message: text,
                mode: 'auto',
            });
            const assistantMessage = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: response.data.response || response.data.message || 'No response',
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, assistantMessage]);
        }
        catch (error) {
            console.error('Failed to send message:', error);
            const errorMessage = {
                id: (Date.now() + 2).toString(),
                role: 'assistant',
                content: 'Sorry, I encountered an error processing your request.',
                timestamp: new Date(),
            };
            setMessages((prev) => [...prev, errorMessage]);
        }
        finally {
            setIsLoading(false);
        }
    };
    const toggleVoiceInput = () => {
        setIsListening(!isListening);
        // TODO: Implement voice input using Web Audio API
    };
    const startNewChat = () => {
        setMessages([]);
        setInput('');
    };
    return (_jsxs("div", { className: "assistant-view", children: [messages.length === 0 ? (_jsx("div", { className: "assistant-welcome", children: _jsxs("div", { className: "welcome-content", children: [_jsx("h1", { children: "Welcome to Guppy" }), _jsx("p", { children: "Your AI assistant is ready to help. Start a conversation below." }), _jsxs("div", { className: "welcome-suggestions", children: [_jsx("button", { className: "suggestion-btn", onClick: () => setInput('What can you help me with?'), children: "What can you help me with?" }), _jsx("button", { className: "suggestion-btn", onClick: () => setInput('Tell me about yourself'), children: "Tell me about yourself" }), _jsx("button", { className: "suggestion-btn", onClick: () => setInput('Help me code something'), children: "Help me code something" })] })] }) })) : (_jsxs("div", { className: "assistant-messages", children: [messages.map((msg) => (_jsx("div", { className: `message ${msg.role}`, children: _jsxs("div", { className: "message-content", children: [_jsx("p", { children: msg.content }), _jsx("span", { className: "message-time", children: msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) })] }) }, msg.id))), isLoading && (_jsx("div", { className: "message assistant", children: _jsx("div", { className: "message-content", children: _jsxs("div", { className: "typing-indicator", children: [_jsx("span", {}), _jsx("span", {}), _jsx("span", {})] }) }) })), _jsx("div", { ref: messagesEndRef })] })), _jsx("div", { className: "assistant-input-area", children: _jsxs("div", { className: "input-toolbar", children: [_jsx("button", { className: "input-btn", onClick: startNewChat, title: "Start new chat", disabled: messages.length === 0, children: _jsx(Plus, { size: 18 }) }), _jsx("input", { type: "text", className: "message-input", placeholder: "Type your message... or press / for commands", value: input, onChange: (e) => setInput(e.target.value), onKeyDown: (e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSendMessage(input);
                                }
                            }, disabled: isLoading }), _jsx("button", { className: "input-btn voice-btn", onClick: toggleVoiceInput, title: "Voice input", disabled: isLoading, children: _jsx(Mic, { size: 18, className: isListening ? 'active' : '' }) }), _jsx("button", { className: "input-btn send-btn", onClick: () => handleSendMessage(input), disabled: !input.trim() || isLoading, title: "Send message (Ctrl+Enter)", children: _jsx(Send, { size: 18 }) })] }) })] }));
}
