# Guppy Roadmap 2026 Q2: Execution Tranches
**Created:** 2026-04-22  
**Status:** Planning Phase  
**Overall Vision:** Production-ready dual UI (Web + Desktop) with local model inference, credential management, tool use, and voice I/O.

---

## Vision Statement

Guppy is a dual-surface AI assistant platform (Web UI + Desktop Launcher) that:
- ✅ Runs locally with Ollama (qwen2.5, codellama, etc.)
- ✅ Supports cloud providers (Claude, OpenAI, Google) via API keys
- ✅ Persists chat history and settings to SQLite
- 🔄 Provides voice I/O (TTS/STT)
- 🔄 Supports tool use (function calling)
- 🔄 Manages credentials securely
- 🔄 Runs on Windows desktop + web browser

---

## Current Status Summary

| Component | Status | Completeness |
|-----------|--------|--------------|
| **Chat Persistence** | ✅ Complete | 100% |
| **Settings/Providers** | ✅ Complete | 100% |
| **AI Responses** | ✅ Complete | 100% |
| **Web UI Display** | ✅ Complete | 95% |
| **Desktop Launcher** | 🟡 Partial | 40% |
| **Voice (STT)** | ⚠️ Backend only | 50% |
| **Voice (TTS)** | ❌ Not started | 0% |
| **Tools API** | ❌ Not started | 0% |
| **Credentials Mgmt** | 🟡 Partial | 30% |
| **Local Admin Panel** | 🟡 Partial | 20% |

---

## Execution Tranches

### TRANCHE 1: Stability & Hardening (May 1-14)
**Duration:** 2 weeks  
**Goal:** Make the system production-stable  
**Owner:** DevOps/QA focus

#### T1-1: Error Handling & Recovery
- [ ] Add comprehensive error logging to all API endpoints
- [ ] Implement graceful degradation when Ollama is down
- [ ] Add retry logic with exponential backoff for API calls
- [ ] Handle malformed requests gracefully
- [ ] Add error telemetry to track common failures

**Deliverables:**
- Error handling utilities in backend
- Structured logging (JSON format)
- Client-side error boundaries in React
- Error dashboard in admin panel

#### T1-2: Database Integrity
- [ ] Add data validation on all inserts/updates
- [ ] Implement database migrations system
- [ ] Add backup/restore functionality
- [ ] Add database integrity checks
- [ ] Handle concurrent writes safely

**Deliverables:**
- Migration framework
- Backup utilities
- Data validation schemas
- Concurrency tests

#### T1-3: Performance Optimization
- [ ] Profile API response times
- [ ] Add query indexing to chat_history table
- [ ] Implement caching layer for frequent queries
- [ ] Optimize message loading (lazy load old messages)
- [ ] Add performance metrics dashboard

**Deliverables:**
- Performance baselines
- Indexing strategy
- Caching layer (Redis optional)
- Metrics dashboard

#### T1-4: Security Hardening
- [ ] Audit all endpoints for injection vulnerabilities
- [ ] Implement CORS properly
- [ ] Add rate limiting per user
- [ ] Encrypt sensitive data at rest (API keys)
- [ ] Add request signing for critical operations

**Deliverables:**
- Security audit report
- CORS configuration
- Rate limiting middleware
- Encryption utilities
- Request signing system

#### T1-5: Testing Infrastructure
- [ ] Create end-to-end test suite (chat flow, settings, etc.)
- [ ] Add integration tests for all API endpoints
- [ ] Create performance benchmarks
- [ ] Add load testing harness
- [ ] CI/CD pipeline setup

**Deliverables:**
- Test suite (50+ tests)
- CI configuration
- Performance benchmarks
- Load test results

---

### TRANCHE 2: Web UI Connection & Polishing (May 8-21)
**Duration:** 2 weeks  
**Goal:** Complete Web UI with all features wired  
**Owner:** Frontend focus

#### T2-1: Settings & Credentials UI
- [ ] Wire SettingsView to backend (already ~70% done)
- [ ] Add credential encryption UI
- [ ] Create credential security warnings
- [ ] Add "show/hide password" for API keys
- [ ] Implement credential deletion with confirmation

**Deliverables:**
- Fully wired SettingsView
- Security indicators
- Password visibility toggle

#### T2-2: Chat UI Enhancements
- [ ] Add typing indicators while waiting for response
- [ ] Add message copy button
- [ ] Implement message deletion
- [ ] Add conversation search/filter
- [ ] Add conversation rename functionality

**Deliverables:**
- Enhanced AssistantView
- Message management UI
- Search interface

#### T2-3: Error States & Feedback
- [ ] Proper error messages on chat failures
- [ ] Toast notifications for actions
- [ ] Loading state spinners throughout
- [ ] Retry buttons on failed messages
- [ ] Network status indicator

**Deliverables:**
- Toast system
- Error boundary components
- Network status indicator

#### T2-4: Theme & Accessibility
- [ ] Implement dark/light mode toggle
- [ ] Ensure WCAG 2.1 AA compliance
- [ ] Test with screen readers
- [ ] Keyboard navigation support
- [ ] Persist theme preference

**Deliverables:**
- Theme toggle
- Accessibility audit
- WCAG compliance report

#### T2-5: Responsive Design
- [ ] Test on mobile (iOS Safari, Android Chrome)
- [ ] Optimize layout for small screens
- [ ] Fix touch interactions
- [ ] Test on tablets
- [ ] Ensure horizontal orientation works

**Deliverables:**
- Mobile-responsive design
- Device testing report
- Touch interaction polish

---

### TRANCHE 3: Voice I/O Integration (May 15-28)
**Duration:** 2 weeks  
**Goal:** Add voice input/output to chat  
**Owner:** Audio/Backend focus

#### T3-1: Voice Input (STT) - Web UI
- [ ] Add microphone button to AssistantView
- [ ] Wire to existing `/api/chat/voice` endpoint
- [ ] Add recording visualization
- [ ] Handle microphone permissions
- [ ] Display transcription result

**Deliverables:**
- Voice input button
- Recording UI
- Transcription display

#### T3-2: Voice Output (TTS) - Backend
- [ ] Create `/api/voices/tts/generate` endpoint
- [ ] Integrate Kokoro TTS backend
- [ ] Stream audio bytes to client
- [ ] Add error handling for TTS failures
- [ ] Support multiple voice configurations

**Deliverables:**
- TTS API endpoint
- Kokoro integration
- Audio streaming

#### T3-3: Voice Output (TTS) - Web UI
- [ ] Add play button next to AI messages
- [ ] Implement audio player controls
- [ ] Show playback progress
- [ ] Queue TTS for long responses
- [ ] Add volume control

**Deliverables:**
- Voice playback UI
- Audio player component
- Queue management

#### T3-4: Voice Settings API
- [ ] Create `/api/voices` GET endpoint (list backends)
- [ ] Create `/api/voices/config` GET/PUT
- [ ] Persist TTS provider selection
- [ ] Persist STT model selection
- [ ] Persist voice preference

**Deliverables:**
- Voice config endpoints
- Settings persistence
- Backend detection

#### T3-5: Voice Testing & Polish
- [ ] Test voice quality across models
- [ ] Optimize latency (pre-buffer responses)
- [ ] Add voice feedback indicators
- [ ] Error handling for missing audio devices
- [ ] Support for multiple languages

**Deliverables:**
- Voice testing report
- Performance optimizations
- Multi-language support

---

### TRANCHE 4: Tools API & Integration (May 22-June 4)
**Duration:** 2 weeks  
**Goal:** Enable AI model function calling  
**Owner:** Backend/Integration focus

#### T4-1: Tools Backend API
- [ ] Create `/api/tools` endpoints (LIST, CREATE, GET, UPDATE, DELETE)
- [ ] Design tools schema (name, description, parameters, category)
- [ ] Implement tool enable/disable logic
- [ ] Add tool versioning support
- [ ] Create tool execution sandbox

**Deliverables:**
- Tools REST API
- Database schema
- Tool validation system

#### T4-2: Tools Database
- [ ] Create `tools` table (id, name, description, category, enabled, schema)
- [ ] Create `tool_executions` table (tool_id, input, output, status)
- [ ] Create `user_tools` table (user_id, tool_id, custom_config)
- [ ] Add indexes for performance
- [ ] Add foreign key constraints

**Deliverables:**
- Database migration
- Schema documentation
- Index strategy

#### T4-3: Model Integration - Claude
- [ ] Wire tools to Claude API calls
- [ ] Parse tool_use blocks from Claude responses
- [ ] Execute tools in sandbox
- [ ] Return results to Claude
- [ ] Handle streaming responses

**Deliverables:**
- Claude tool integration
- Execution sandbox
- Response parsing

#### T4-4: Model Integration - Ollama
- [ ] Research Ollama function calling support
- [ ] Implement custom function calling (if not native)
- [ ] Parse function calls from responses
- [ ] Execute in sandbox
- [ ] Return results to model

**Deliverables:**
- Ollama integration (if supported)
- Custom function calling system
- Execution logging

#### T4-5: Tools Web UI
- [ ] Wire ToolsView to backend API
- [ ] Remove mock data
- [ ] Add tool enable/disable
- [ ] Create tool editor UI
- [ ] Display tool execution results in chat

**Deliverables:**
- ToolsView fully wired
- Tool editor component
- Execution results display

---

### TRANCHE 5: Credential Management (May 20-June 6)
**Duration:** 2 weeks  
**Goal:** Secure credential storage and rotation  
**Owner:** Security/Backend focus

#### T5-1: Credential Storage
- [ ] Create `credentials` table (user_id, provider, encrypted_key, created_at, updated_at)
- [ ] Implement encryption at rest (AES-256)
- [ ] Use system keyring when available (Windows DPAPI)
- [ ] Fallback to encrypted storage if keyring unavailable
- [ ] Add credential rotation support

**Deliverables:**
- Encrypted credential storage
- Keyring integration
- Rotation mechanism

#### T5-2: Credential Stubs & Validation
- [ ] Create credential validators for each provider:
  - [ ] Anthropic (Claude) - validate `sk-ant-*` format
  - [ ] OpenAI - validate `sk-*` format
  - [ ] Google (Gemini) - validate API key format
  - [ ] Hugging Face - validate token format
  - [ ] ElevenLabs (voice) - validate API key
  - [ ] Custom providers - generic validation

**Deliverables:**
- Credential validators
- Format documentation
- Validation tests

#### T5-3: Credential Endpoints
- [ ] `POST /api/credentials/{provider}` - save
- [ ] `GET /api/credentials` - list providers (without keys)
- [ ] `DELETE /api/credentials/{provider}` - delete
- [ ] `POST /api/credentials/{provider}/verify` - test key
- [ ] `POST /api/credentials/{provider}/rotate` - rotate key

**Deliverables:**
- Credential REST API
- Verification logic
- Rotation workflow

#### T5-4: Credential Security Audit
- [ ] Ensure keys never logged or exposed
- [ ] Implement access controls (only owner can see/use)
- [ ] Add credential access audit logs
- [ ] Implement credential expiration warnings
- [ ] Add breach detection (unused keys should be rotated)

**Deliverables:**
- Security audit report
- Access control system
- Audit logging
- Expiration system

#### T5-5: Credential UI
- [ ] Create CredentialManager component
- [ ] Add provider-specific help links
- [ ] Show which credentials are active
- [ ] Add credential health indicators
- [ ] Implement credential sync across devices (optional)

**Deliverables:**
- Credential UI component
- Health indicators
- Help documentation

---

### TRANCHE 6: Local Admin Panel (June 3-16)
**Duration:** 2 weeks  
**Goal:** System administration and monitoring  
**Owner:** Backend/Ops focus

#### T6-1: Admin Dashboard
- [ ] Create `/admin` route in web UI
- [ ] Show system status (API running, Ollama running, DB healthy)
- [ ] Display resource usage (CPU, memory, disk)
- [ ] Show uptime statistics
- [ ] Display active sessions

**Deliverables:**
- Admin dashboard
- Status indicators
- Resource monitors

#### T6-2: Logs & Telemetry
- [ ] Centralize logging to SQLite
- [ ] Create log viewer in admin panel
- [ ] Add filtering by level/component/timestamp
- [ ] Show recent errors and warnings
- [ ] Export logs to CSV/JSON

**Deliverables:**
- Centralized logging
- Log viewer UI
- Export functionality

#### T6-3: User Management
- [ ] Create user management interface
- [ ] Show active users and sessions
- [ ] Reset user password/credentials
- [ ] Delete user data
- [ ] View user activity

**Deliverables:**
- User management UI
- Session management
- Activity logs

#### T6-4: Model Management
- [ ] Show available models from Ollama
- [ ] Allow model pulling from UI
- [ ] Show model sizes and VRAM requirements
- [ ] Unload unused models
- [ ] Show inference performance metrics

**Deliverables:**
- Model management UI
- Performance metrics
- Model control

#### T6-5: Configuration Management
- [ ] Admin can change system settings
- [ ] Configure default model
- [ ] Set API timeouts
- [ ] Configure backup schedule
- [ ] Set retention policies (e.g., delete old messages after N days)

**Deliverables:**
- Settings UI
- Configuration API
- Validation system

---

### TRANCHE 7: Desktop Launcher Enhancement (June 10-23)
**Duration:** 2 weeks  
**Goal:** Full-featured desktop application  
**Owner:** Desktop/Qt focus

#### T7-1: Desktop UI Parity
- [ ] Ensure desktop UI matches web UI
- [ ] Implement same chat interface
- [ ] Add same settings/voice/tools views
- [ ] Match keyboard shortcuts
- [ ] Match color scheme/theme

**Deliverables:**
- Desktop UI parity
- Shortcut documentation

#### T7-2: System Integration
- [ ] Register file types (open with Guppy)
- [ ] Add to system tray with quick access
- [ ] Keyboard shortcut to open Guppy (Win+Shift+G?)
- [ ] Clipboard monitor for pasting
- [ ] File drag-and-drop support

**Deliverables:**
- System integration
- File type handlers
- Hotkey support

#### T7-3: Offline Mode
- [ ] Cache recent conversations
- [ ] Allow local model inference when offline
- [ ] Queue messages for sync when online
- [ ] Show sync status indicator
- [ ] Conflict resolution for offline edits

**Deliverables:**
- Offline cache
- Sync queue
- Status indicators

#### T7-4: Performance & Optimization
- [ ] Profile desktop app startup time
- [ ] Lazy load views
- [ ] Memory optimization
- [ ] Background task management
- [ ] Efficient resource cleanup

**Deliverables:**
- Performance profiles
- Optimization report

#### T7-5: Distribution & Updates
- [ ] Create Windows installer
- [ ] Implement auto-update mechanism
- [ ] Code signing for executable
- [ ] Create update rollback feature
- [ ] Version management

**Deliverables:**
- Windows installer
- Update system
- Version tracking

---

## API Keys & Credentials Required

### Cloud LLM Providers

#### 1. Anthropic (Claude)
- **What:** API key for Claude 3 models
- **Format:** `sk-ant-v0-...` (starts with `sk-ant-`)
- **Get it:** https://console.anthropic.com/account/keys
- **Cost:** Pay-as-you-go ($0.003/1K input, $0.015/1K output tokens)
- **For:** Cloud AI responses, tool use, advanced reasoning
- **Stub Validator:**
  ```python
  def validate_anthropic_key(key: str) -> bool:
    return key.startswith('sk-ant-v0-') and len(key) > 20
  ```

#### 2. OpenAI
- **What:** API key for GPT models
- **Format:** `sk-...` (starts with `sk-`)
- **Get it:** https://platform.openai.com/account/api-keys
- **Cost:** Pay-as-you-go (varies by model)
- **For:** Alternative LLM provider, voice TTS (optional), tools
- **Stub Validator:**
  ```python
  def validate_openai_key(key: str) -> bool:
    return key.startswith('sk-') and len(key) > 20
  ```

#### 3. Google (Gemini)
- **What:** API key for Gemini models
- **Format:** Usually long alphanumeric string
- **Get it:** https://aistudio.google.com/app/apikey
- **Cost:** Free tier available, then pay-as-you-go
- **For:** Alternative LLM provider, multimodal support
- **Stub Validator:**
  ```python
  def validate_google_key(key: str) -> bool:
    return len(key) > 30 and key.isalnum()
  ```

### Voice Services (Optional)

#### 4. ElevenLabs
- **What:** API key for high-quality TTS
- **Format:** Usually alphanumeric string
- **Get it:** https://elevenlabs.io/account/account
- **Cost:** Free tier (10K characters/month), then $5-99/month
- **For:** Premium voice synthesis
- **Stub Validator:**
  ```python
  def validate_elevenlabs_key(key: str) -> bool:
    return len(key) > 20 and key.isalnum()
  ```

### Optional/Future

#### 5. Hugging Face
- **What:** API token for model access
- **Format:** `hf_...`
- **Get it:** https://huggingface.co/settings/tokens
- **Cost:** Free
- **For:** Model access, inference API
- **Stub Validator:**
  ```python
  def validate_hf_key(key: str) -> bool:
    return key.startswith('hf_') and len(key) > 20
  ```

#### 6. Anthropic Bedrock (AWS)
- **What:** AWS access key ID + secret key
- **Format:** AWS format
- **Get it:** AWS Console → IAM → Users
- **Cost:** Bundled with AWS pricing
- **For:** Running Claude via AWS Bedrock
- **Stub Validator:**
  ```python
  def validate_aws_keys(access_key: str, secret_key: str) -> bool:
    return (access_key.startswith('AKIA') and 
            len(secret_key) > 30)
  ```

---

## Credential Stub Implementation Plan

### Location
`src/guppy/api/credential_validators.py` - New file

### Structure
```python
from enum import Enum
from typing import Optional

class CredentialProvider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    ELEVENLABS = "elevenlabs"
    HUGGINGFACE = "huggingface"
    AWS_BEDROCK = "aws_bedrock"

class CredentialValidator:
    validators = {
        CredentialProvider.ANTHROPIC: validate_anthropic,
        CredentialProvider.OPENAI: validate_openai,
        # ... etc
    }
    
    @staticmethod
    def validate(provider: CredentialProvider, key: str) -> tuple[bool, Optional[str]]:
        """Returns (is_valid, error_message)"""
        validator = CredentialValidator.validators.get(provider)
        if not validator:
            return False, f"Unknown provider: {provider}"
        return validator(key)

class CredentialEncryption:
    """Encrypt/decrypt credentials"""
    @staticmethod
    def encrypt(plaintext: str, key: Optional[str] = None) -> str:
        # Use system keyring or AES-256
        pass
    
    @staticmethod
    def decrypt(ciphertext: str, key: Optional[str] = None) -> str:
        pass

class CredentialStore:
    """Database operations for credentials"""
    def save(self, user_id: str, provider: CredentialProvider, key: str) -> None:
        # Validate, encrypt, store
        pass
    
    def get(self, user_id: str, provider: CredentialProvider) -> Optional[str]:
        # Retrieve, decrypt
        pass
    
    def delete(self, user_id: str, provider: CredentialProvider) -> None:
        pass
    
    def list_providers(self, user_id: str) -> List[CredentialProvider]:
        pass
```

---

## Database Schema Additions (All Tranches)

```sql
-- Credentials table
CREATE TABLE credentials (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    encrypted_key TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id, provider),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Tools table
CREATE TABLE tools (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    schema JSON NOT NULL,
    type TEXT DEFAULT 'builtin',  -- builtin, custom, mcp
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tool executions table
CREATE TABLE tool_executions (
    id INTEGER PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    input JSON NOT NULL,
    output JSON,
    status TEXT DEFAULT 'pending',  -- pending, success, error
    error_message TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(conversation_id) REFERENCES conversations(id),
    FOREIGN KEY(tool_id) REFERENCES tools(id)
);

-- Voice settings table
CREATE TABLE voice_config (
    user_id TEXT PRIMARY KEY,
    tts_provider TEXT DEFAULT 'kokoro',
    tts_voice TEXT DEFAULT 'default',
    stt_model TEXT DEFAULT 'whisper-medium',
    tts_speed REAL DEFAULT 1.0,
    tts_pitch REAL DEFAULT 1.0,
    auto_detect_language BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

-- Admin logs table
CREATE TABLE admin_logs (
    id INTEGER PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id TEXT,
    description TEXT,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- System health table
CREATE TABLE system_health (
    id INTEGER PRIMARY KEY,
    check_type TEXT NOT NULL,
    status TEXT NOT NULL,  -- healthy, warning, error
    details JSON,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Timeline Overview

```
May 1-14:    Tranche 1 (Stability)           
May 8-21:    Tranche 2 (Web UI)          ← Overlaps
May 15-28:   Tranche 3 (Voice)           ← Overlaps
May 20-Jun 6: Tranche 5 (Credentials)    ← Overlaps
May 22-Jun 4: Tranche 4 (Tools)          ← Overlaps
Jun 3-16:    Tranche 6 (Admin)           ← Overlaps
Jun 10-23:   Tranche 7 (Desktop)         ← Overlaps

Total Duration: ~7 weeks (May 1 - June 23)
With parallel execution, could finish in ~4 weeks if fully staffed
```

---

## Success Criteria

### By End of Tranche 1 (May 14)
- ✅ Zero unhandled exceptions in production
- ✅ API has <2% error rate
- ✅ Database is fully backed up
- ✅ All critical endpoints have rate limiting

### By End of Tranche 2 (May 21)
- ✅ Web UI fully functional and responsive
- ✅ All SettingsView features wired to backend
- ✅ Chat UI has proper error handling
- ✅ 95% WCAG 2.1 AA compliance

### By End of Tranche 3 (May 28)
- ✅ Voice input/output working in chat
- ✅ STT accuracy >95%
- ✅ TTS latency <500ms

### By End of Tranche 4 (June 4)
- ✅ Tools API fully implemented
- ✅ Claude can use tools
- ✅ Ollama has custom function calling
- ✅ ToolsView fully wired

### By End of All Tranches (June 23)
- ✅ Production-ready system
- ✅ Full feature parity Web UI ↔ Desktop UI
- ✅ All credentials encrypted
- ✅ Admin panel fully functional
- ✅ >95% test coverage
- ✅ Documentation complete

---

## Notes & Assumptions

1. **Parallel Execution:** Tranches overlap intentionally for faster delivery
2. **Team:** Assumes team of 3-4 people (frontend, backend, DevOps, QA)
3. **Solo Execution:** If solo, expect 12-16 weeks instead of 7
4. **Priorities:** Can skip desktop tranche initially; web UI is more important
5. **API Keys:** Users will provide their own; system doesn't require any by default
6. **Ollama:** Assumes Ollama is already running locally (setup doc provided)

