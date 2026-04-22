import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Lock, Mail, Eye, EyeOff } from 'lucide-react';
import api from '../api/client';
import './LoginView.css';
export default function LoginView() {
    const navigate = useNavigate();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [isSignUp, setIsSignUp] = useState(false);
    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setIsLoading(true);
        try {
            if (isSignUp) {
                // Sign up
                await api.post('/auth/signup', { email, password });
                setError('');
                setEmail('');
                setPassword('');
                setIsSignUp(false);
            }
            else {
                // Login with Turnstile token
                const response = await api.post('/auth/verify', { token: email });
                localStorage.setItem('accessToken', response.data.access_token);
                localStorage.setItem('expiresIn', response.data.expires_in);
                navigate('/');
            }
        }
        catch (err) {
            setError(err.response?.data?.detail || 'Authentication failed');
        }
        finally {
            setIsLoading(false);
        }
    };
    const handleGuestAccess = async () => {
        setIsLoading(true);
        try {
            // Get dev token for testing
            const response = await api.post('/auth/verify', { token: 'dev-token' });
            localStorage.setItem('accessToken', response.data.access_token);
            navigate('/');
        }
        catch (err) {
            setError('Guest access failed');
        }
        finally {
            setIsLoading(false);
        }
    };
    return (_jsx("div", { className: "login-container", children: _jsxs("div", { className: "login-card", children: [_jsxs("div", { className: "login-header", children: [_jsx("h1", { children: "Guppy" }), _jsx("p", { children: "AI Assistant Platform" })] }), _jsxs("form", { onSubmit: handleSubmit, className: "login-form", children: [_jsx("h2", { children: isSignUp ? 'Create Account' : 'Login' }), error && _jsx("div", { className: "login-error", children: error }), _jsxs("div", { className: "form-group", children: [_jsxs("label", { htmlFor: "email", children: [_jsx(Mail, { size: 16 }), "Email or Token"] }), _jsx("input", { id: "email", type: isSignUp ? 'email' : 'text', placeholder: isSignUp ? 'your@email.com' : 'Enter token or dev-token', value: email, onChange: (e) => setEmail(e.target.value), disabled: isLoading, required: true })] }), isSignUp && (_jsxs("div", { className: "form-group", children: [_jsxs("label", { htmlFor: "password", children: [_jsx(Lock, { size: 16 }), "Password"] }), _jsxs("div", { className: "password-input", children: [_jsx("input", { id: "password", type: showPassword ? 'text' : 'password', placeholder: "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022", value: password, onChange: (e) => setPassword(e.target.value), disabled: isLoading, required: true }), _jsx("button", { type: "button", className: "password-toggle", onClick: () => setShowPassword(!showPassword), disabled: isLoading, children: showPassword ? _jsx(EyeOff, { size: 16 }) : _jsx(Eye, { size: 16 }) })] })] })), _jsx("button", { type: "submit", className: "btn btn-primary btn-block", disabled: isLoading, children: isLoading ? 'Loading...' : isSignUp ? 'Create Account' : 'Login' }), _jsx("div", { className: "login-divider", children: "or" }), _jsx("button", { type: "button", className: "btn btn-secondary btn-block", onClick: handleGuestAccess, disabled: isLoading, children: "Continue as Guest" })] }), _jsx("div", { className: "login-footer", children: !isSignUp ? (_jsxs(_Fragment, { children: [_jsx("p", { children: "Don't have an account?" }), _jsx("button", { className: "link-btn", onClick: () => setIsSignUp(true), disabled: isLoading, children: "Sign up" })] })) : (_jsxs(_Fragment, { children: [_jsx("p", { children: "Already have an account?" }), _jsx("button", { className: "link-btn", onClick: () => setIsSignUp(false), disabled: isLoading, children: "Login" })] })) }), _jsx("div", { className: "login-info", children: _jsxs("p", { children: ["For development: Use token ", _jsx("code", { children: "dev-token" })] }) })] }) }));
}
