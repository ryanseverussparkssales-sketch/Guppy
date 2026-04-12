/**
 * turnstile.js — Cloudflare Turnstile integration for Guppy Web UI
 * ================================================================
 *
 * Handles Turnstile widget initialization, token verification,
 * and authentication flow for the web interface.
 */

// Configuration
const API_BASE = window.location.origin; // Use same origin as the web server
const TURNSTILE_SITE_KEY = '0x4AAAAAAC8haN8mXd57RJ18'; // Set in Cloudflare dashboard

// Global state
let turnstileToken = null;
let authToken = null;
let websocket = null;
let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];

// DOM elements
const authSection = document.getElementById('auth-section');
const chatSection = document.getElementById('chat-section');
const authButton = document.getElementById('auth-button');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');
const voiceButton = document.getElementById('voice-button');
const chatMessages = document.getElementById('chat-messages');
const statusDiv = document.getElementById('status');
const claudeBtn = document.getElementById('claude-btn');
const ollamaBtn = document.getElementById('ollama-btn');

// Current model selection
let useClaude = true;

// Initialize Turnstile widget
function initTurnstile() {
    if (typeof turnstile !== 'undefined') {
        turnstile.render('#turnstile-widget', {
            sitekey: TURNSTILE_SITE_KEY,
            callback: function(token) {
                turnstileToken = token;
                authButton.disabled = false;
                authButton.textContent = 'Start Chatting';
                updateStatus('Security check passed! Click to continue.');
            },
            'error-callback': function() {
                turnstileToken = null;
                authButton.disabled = true;
                updateStatus('Security check failed. Please try again.');
            },
            'expired-callback': function() {
                turnstileToken = null;
                authButton.disabled = true;
                updateStatus('Security check expired. Please refresh the page.');
            }
        });
    } else {
        // Fallback for development
        console.warn('Turnstile not loaded, enabling development mode');
        turnstileToken = 'dev-token';
        authButton.disabled = false;
        authButton.textContent = 'Start Chatting (Dev Mode)';
        updateStatus('Development mode: Turnstile bypassed');
    }
}

// Authenticate with the API
async function authenticate() {
    if (!turnstileToken) {
        showError('Please complete the security check first.');
        return;
    }

    try {
        updateStatus('Authenticating...');
        authButton.disabled = true;
        authButton.innerHTML = '<div class="loading"></div> Authenticating...';

        const response = await fetch(`${API_BASE}/auth/verify`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                token: turnstileToken
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Authentication failed');
        }

        const data = await response.json();
        authToken = data.access_token;

        // Switch to chat interface
        authSection.style.display = 'none';
        chatSection.style.display = 'block';

        updateStatus('Connected! Ready to chat.');

        // Initialize WebSocket for streaming
        initWebSocket();

    } catch (error) {
        console.error('Authentication error:', error);
        showError(`Authentication failed: ${error.message}`);
        authButton.disabled = false;
        authButton.textContent = 'Start Chatting';
    }
}

// Initialize WebSocket connection
function initWebSocket() {
    try {
        const wsUrl = API_BASE.replace('http', 'ws') + '/ws';
        websocket = new WebSocket(wsUrl);

        websocket.onopen = function(event) {
            // Send authentication token
            websocket.send(JSON.stringify({ token: authToken }));
        };

        websocket.onmessage = function(event) {
            const data = JSON.parse(event.data);

            if (data.error) {
                showError(data.error);
                return;
            }

            if (data.status === 'authenticated') {
                updateStatus('WebSocket connected');
                return;
            }

            if (data.chunk) {
                // Streaming response chunk
                appendMessage(data.chunk, 'guppy', false);
                return;
            }

            if (data.done) {
                // Response complete
                finalizeLastMessage();
                messageInput.disabled = false;
                sendButton.disabled = false;
                voiceButton.disabled = false;
                return;
            }
        };

        websocket.onclose = function(event) {
            updateStatus('Connection lost. Please refresh the page.');
        };

        websocket.onerror = function(error) {
            console.error('WebSocket error:', error);
            showError('Connection error. Please try again.');
        };

    } catch (error) {
        console.error('WebSocket initialization error:', error);
        showError('Failed to connect to chat service.');
    }
}

// Send message via WebSocket
async function sendMessage(message) {
    if (!websocket || websocket.readyState !== WebSocket.OPEN) {
        showError('Connection lost. Please refresh the page.');
        return;
    }

    try {
        // Add user message to UI
        appendMessage(message, 'user');

        // Disable input while processing
        messageInput.disabled = true;
        sendButton.disabled = true;
        voiceButton.disabled = true;

        // Send via WebSocket
        websocket.send(JSON.stringify({
            message: message,
            use_claude: useClaude
        }));

        // Clear input
        messageInput.value = '';

    } catch (error) {
        console.error('Send message error:', error);
        showError('Failed to send message. Please try again.');
        messageInput.disabled = false;
        sendButton.disabled = false;
        voiceButton.disabled = false;
    }
}

// Voice recording functionality
async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.ondataavailable = function(event) {
            audioChunks.push(event.data);
        };

        mediaRecorder.onstop = async function() {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            await sendVoiceMessage(audioBlob);
            // Stop all tracks
            stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorder.start();
        isRecording = true;
        voiceButton.classList.add('recording');
        voiceButton.textContent = '🔴';
        updateStatus('Recording... Tap to stop.');

    } catch (error) {
        console.error('Recording error:', error);
        showError('Could not access microphone. Please check permissions.');
    }
}

function stopRecording() {
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
        isRecording = false;
        voiceButton.classList.remove('recording');
        voiceButton.textContent = '🎤';
        updateStatus('Processing voice message...');
    }
}

async function sendVoiceMessage(audioBlob) {
    try {
        const formData = new FormData();
        formData.append('file', audioBlob, 'voice.wav');
        formData.append('use_claude', useClaude.toString());

        const response = await fetch(`${API_BASE}/chat/voice`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`
            },
            body: formData
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Voice processing failed');
        }

        const data = await response.json();

        // Add transcription and response to UI
        appendMessage(`🎤 ${data.transcription}`, 'user');
        appendMessage(data.response, 'guppy');

        updateStatus('Voice message processed successfully.');

    } catch (error) {
        console.error('Voice message error:', error);
        showError(`Voice processing failed: ${error.message}`);
    }
}

// UI helper functions
function appendMessage(text, sender, finalize = true) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    messageDiv.textContent = text;
    chatMessages.appendChild(messageDiv);

    if (finalize) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function finalizeLastMessage() {
    // Ensure last message is fully visible
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error';
    errorDiv.textContent = message;

    // Insert at top of messages
    chatMessages.insertBefore(errorDiv, chatMessages.firstChild);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (errorDiv.parentNode) {
            errorDiv.remove();
        }
    }, 5000);
}

function updateStatus(message) {
    statusDiv.textContent = message;
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Turnstile
    initTurnstile();

    // Auth button
    authButton.addEventListener('click', authenticate);

    // Message input
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            const message = messageInput.value.trim();
            if (message) {
                sendMessage(message);
            }
        }
    });

    // Send button
    sendButton.addEventListener('click', function() {
        const message = messageInput.value.trim();
        if (message) {
            sendMessage(message);
        }
    });

    // Voice button
    voiceButton.addEventListener('click', function() {
        if (isRecording) {
            stopRecording();
        } else {
            startRecording();
        }
    });

    // Model toggle
    claudeBtn.addEventListener('click', function() {
        useClaude = true;
        claudeBtn.classList.add('active');
        ollamaBtn.classList.remove('active');
    });

    ollamaBtn.addEventListener('click', function() {
        useClaude = false;
        ollamaBtn.classList.add('active');
        claudeBtn.classList.remove('active');
    });
});

// Handle page unload
window.addEventListener('beforeunload', function() {
    if (websocket) {
        websocket.close();
    }
    if (mediaRecorder && isRecording) {
        mediaRecorder.stop();
    }
});
