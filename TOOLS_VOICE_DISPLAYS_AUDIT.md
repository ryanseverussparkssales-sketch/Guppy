# Tools, Voice, and Displays Functionality Audit
**Date:** 2026-04-22  
**Status:** Investigation Complete

---

## Executive Summary

| Feature | Backend | Web UI | Status |
|---------|---------|--------|--------|
| **Tools** | ❌ No API endpoints | ✅ UI created (mock data) | Not Wired |
| **Voice (TTS)** | ⚠️ Support code exists | ✅ UI created (mock data) | Not Wired |
| **Voice (STT)** | ⚠️ Support code exists | ✅ UI created (mock data) | Not Wired |
| **Displays** | 📋 Not applicable | ✅ Rendering works | Not Applicable |

---

## 1. TOOLS FUNCTIONALITY

### Backend Status: ❌ NO API ENDPOINTS

**Current State:**
- `snapshot_misc_routes.py` has NO `/api/tools` endpoints
- Mock tools are defined in ToolsView.tsx (Web Search, Code Execution, File Read, etc.)
- Backend has support functions for Claude tools and Ollama tools:
  - `call_claude_with_tools()` in `realtime_inference_support.py`
  - `call_ollama_with_tools()` in `realtime_inference_support.py`

**What Would Be Needed (If Building Tools API):**
```
GET    /api/tools                    - List all available tools
POST   /api/tools                    - Create custom tool
GET    /api/tools/{id}               - Get tool details
PUT    /api/tools/{id}               - Update tool
DELETE /api/tools/{id}               - Delete tool
POST   /api/tools/{id}/enable        - Enable tool
POST   /api/tools/{id}/disable       - Disable tool
POST   /api/tools/{id}/test          - Test tool execution
GET    /api/tools/categories         - List tool categories
```

### Web UI Status: ✅ UI EXISTS (MOCK DATA)

**Current Implementation:**
- `web/src/views/ToolsView.tsx` (343 lines)
- Shows mock tools: Web Search, Code Execution, File Read/Write, Shell, API Request
- Categories: search, code, file, system, api
- Features:
  - ✅ Search/filter functionality
  - ✅ Category filtering
  - ✅ Enable/disable toggles (local state only)
  - ✅ Tool type badges (builtin, custom, mcp)
  - ✅ Add tool button (not wired)

**Missing Implementation:**
```typescript
// In ToolsView.tsx, line 167:
// TODO: Call API to persist toggle
// api.post(`/api/tools/${toolId}/${currentState ? 'disable' : 'enable'}`)
```

**Current Hook Usage:**
```typescript
const { tools: apiTools, isLoading, error } = useTools()
// Falls back to MOCK_TOOLS if apiTools is empty
const tools = apiTools.length > 0 ? apiTools : MOCK_TOOLS
```

### How Tools Are Currently Implemented (Backend)

Tools exist but are passed directly to models, not via API:

**For Claude:**
```python
# src/guppy/api/realtime_inference_support.py:311
def call_claude_with_tools(...)
  # Tools passed directly to Claude API
  response = client.messages.create(
    model=model_id,
    tools=[...],  # Tool definitions
    ...
  )
```

**For Ollama:**
```python
# src/guppy/api/realtime_inference_support.py:386
def call_ollama_with_tools(...)
  # Ollama doesn't support tools like Claude
  # Would need custom function calling setup
```

---

## 2. VOICE FUNCTIONALITY

### Backend Status: ⚠️ SUPPORT CODE EXISTS (NOT FULLY WIRED)

**Available Backend Support:**

1. **Voice Detection** (`snapshot_voice_support.py`):
   ```python
   def detect_voice_backends():
     # Returns (tts_backend, stt_backend, details)
     # TTS: kokoro, sapi (fallback)
     # STT: whisper, google (fallback), none
   ```
   - ✅ Detects if Kokoro (TTS) is installed
   - ✅ Detects if faster-whisper (STT) is installed
   - ✅ Falls back gracefully

2. **Voice Response Endpoint** (`snapshot_misc_routes.py:89-102`):
   ```python
   @app.post("/chat/voice")
   async def chat_voice(
     file: UploadFile,          # Audio file
     session_id: Optional[str],
     use_claude: Optional[bool],
   ):
     # Returns: { transcription, response, session_id }
   ```
   - ✅ Accepts audio file upload
   - ✅ Transcribes audio (STT)
   - ✅ Gets AI response
   - ✅ Can optionally use Claude vs local model

3. **Voice Processing** (`snapshot_voice_support.py` + `snapshot_realtime_support.py:292-373`):
   ```python
   async def chat_voice_response(owner, file, session_id, use_claude):
     # 1. Transcribe audio (STT)
     transcription = voice_handler.transcribe_audio(temp_path)
     
     # 2. Get AI response
     response = await owner._call_unified_inference(
       transcription,
       system_prompt,
       ...
     )
     
     # 3. Persist both to memory
     owner.memory.save_message(session_id, "user", f"[Voice] {transcription}")
     owner.memory.save_message(session_id, "assistant", response)
     
     # 4. Return results
     return {
       "transcription": transcription,
       "response": response,
       "session_id": session_id
     }
   ```

### Web UI Status: ✅ UI EXISTS (MOCK DATA)

**Current Implementation:**
- `web/src/views/VoicesView.tsx` (300+ lines)
- Shows TTS providers: Kokoro, ElevenLabs, OpenAI, System
- Shows STT models: Whisper Large/Medium/Small/Tiny
- Shows voice options: Alloy, Echo, Fable, Onyx, Nova, Shimmer
- Features:
  - ✅ TTS provider selection
  - ✅ Voice selection dropdown
  - ✅ Speed/pitch sliders
  - ✅ Auto-detect language toggle
  - ✅ Test audio button (simulated)
  - ✅ STT model selection

**Missing Implementation:**
```typescript
// In VoicesView.tsx, line 86:
// Simulate audio test - replace with actual API call
// await api.post('/api/voices/test', { provider, voice })
```

**What Would Be Needed:**
```
GET    /api/voices                   - Get voice provider config
GET    /api/voices/backends          - Get available TTS/STT backends
PUT    /api/voices/tts               - Update TTS settings
PUT    /api/voices/stt               - Update STT settings
POST   /api/voices/test              - Test audio playback
POST   /api/voices/tts/generate      - Generate speech from text
```

### Integration Path for Voice

**TTS (Text-to-Speech) in Chat:**
Currently NOT wired. Would need:
1. AssistantView detects when voice is enabled
2. After AI response is received, call TTS API
3. Play audio response

**STT (Speech-to-Text) in Chat:**
Currently available but NOT wired in Web UI. Backend endpoint works:
```python
POST /api/chat/voice
- Upload audio file
- Returns: transcription + AI response
```

---

## 3. DISPLAYS FUNCTIONALITY

### Status: ✅ RENDERING WORKS (UI Framework)

**What "Displays" Means in Guppy:**
- Display components (Cards, Buttons, Input fields, Sidebar)
- Theme support (light/dark mode)
- Layout system (flexbox, grid)
- Responsive design (mobile, tablet, desktop)

**Current Implementation:**
- ✅ All UI views render correctly
- ✅ Theme tokens defined in Tailwind
- ✅ Components use proper semantic HTML
- ✅ Responsive breakpoints working
- ✅ Icons from lucide-react working

**Display/Theme System:**
```css
/* src/guppy/web/src/index.css */
:root {
  --foreground: ...
  --background: ...
  --primary: ...
  --muted-foreground: ...
  /* etc */
}
```

**Component Library:**
- ✅ Button
- ✅ Input
- ✅ Card
- ✅ ScrollArea
- ✅ Select/Dropdown (Headless UI)

**What Could Be Enhanced (Not Needed for P0):**
- Theme customization API
- Custom display modes (compact, list, grid)
- Accessibility audit
- Dark mode toggle persistence

---

## Functional Status by Feature

### ✅ FULLY WORKING
- Chat (text): User messages ✅ → AI responses ✅ → Persistence ✅
- Settings: Provider config ✅ → Activation ✅ → Persistence ✅
- Display/UI: All views render ✅, responsive ✅, themed ✅
- Voice STT: Backend endpoint exists, but not exposed in Web UI

### ⚠️ PARTIALLY WORKING
- Voice TTS: Backend support exists (Kokoro detected), but:
  - No API endpoint to generate speech
  - No UI to trigger TTS
  - No audio playback in chat

### ❌ NOT IMPLEMENTED
- Tools API: No backend endpoints created
- Tools UI: Uses mock data, no API integration
- Voice TTS: No API endpoint for text-to-speech generation
- Voice UI: Uses mock data, no real backend integration
- Voice STT in Web UI: Endpoint exists but not wired to chat

---

## Recommended Next Steps

### Phase 3B: Voice Integration (If Pursuing)
1. **STT in Chat:**
   - Add voice input button to AssistantView
   - Call existing `/api/chat/voice` endpoint
   - Receive transcription + AI response
   - Display both in chat

2. **TTS in Chat:**
   - Create `/api/voices/tts/generate` endpoint
   - Take text, return audio bytes (MP3/WAV)
   - Add play button next to AI messages
   - Stream audio to client

3. **Voice Settings API:**
   - Create `/api/voices` GET endpoint
   - Create `/api/voices/tts` PUT endpoint
   - Create `/api/voices/stt` PUT endpoint
   - Persist to database

### Phase 4: Tools API (If Pursuing)
1. **Create Backend Endpoints:**
   - `/api/tools` GET/POST/DELETE
   - `/api/tools/{id}` GET/PUT/DELETE
   - `/api/tools/{id}/enable|disable` POST

2. **Wire ToolsView:**
   - Connect to backend API
   - Remove mock data
   - Add/edit/delete tools
   - Test tool execution

3. **Integrate with Chat:**
   - Pass enabled tools to model inference
   - Handle tool calls in responses
   - Display tool results in chat

---

## Current API Endpoints Inventory

### Working Endpoints
```
GET    /api/workspaces                  ✅ Chat persistence
POST   /api/workspaces                  ✅ Chat persistence
GET    /api/chat/history                ✅ Chat persistence
POST   /api/chat/history                ✅ Chat persistence
GET    /api/chat/history/{id}           ✅ Chat persistence
POST   /api/chat/history/{id}/messages  ✅ Chat persistence
POST   /api/chat                        ✅ AI responses
POST   /api/chat/voice                  ⚠️ Voice (not wired in UI)
POST   /api/settings/credentials        ✅ Settings
POST   /api/settings/provider           ✅ Settings
GET    /api/settings                    ✅ Settings
```

### Missing Endpoints
```
GET    /api/tools                       ❌ Tools
POST   /api/voices                      ❌ Voice config
GET    /api/voices                      ❌ Voice config
PUT    /api/voices/tts                  ❌ TTS settings
PUT    /api/voices/stt                  ❌ STT settings
POST   /api/voices/tts/generate         ❌ TTS synthesis
```

---

## Conclusion

**What's Production-Ready (P0):**
- ✅ Chat with persistence (user + AI messages)
- ✅ Settings (provider selection)
- ✅ Display/UI (all views render correctly)

**What's Ready for Phase 3B (Voice):**
- ⚠️ Backend support code exists (Kokoro TTS, Whisper STT)
- ⚠️ `/api/chat/voice` endpoint works but not exposed in Web UI
- ❌ Web UI doesn't have voice input/output controls
- ❌ No TTS API endpoint for synthesis

**What's Not Started (Tools):**
- ❌ No backend API endpoints
- ❌ Web UI has mock data only
- ⚠️ Backend has tool calling functions for Claude/Ollama

**Recommendation:**
If you want to add voice or tools, start with:
1. Voice STT: Wire AssistantView to existing `/api/chat/voice` endpoint
2. Voice TTS: Create `/api/voices/tts/generate` endpoint + UI playback
3. Tools: Design and implement `/api/tools` REST API structure

Currently, the system is feature-complete for text-based chat with persistence.
