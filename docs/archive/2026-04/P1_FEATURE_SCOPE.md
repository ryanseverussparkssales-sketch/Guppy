# P1 Feature Scope: Advanced Controls & Tools Integration

**Status:** Planning phase (post-P0 completion, 2026-04-22)  
**Timeline:** May 1 - May 20, 2026 (3 weeks)  
**Objective:** Add advanced model control + basic desktop tools, achieving "smart agent" capabilities

---

## Overview

After P0 completion (Model Management, Workspaces, Chat Persistence, Settings), P1 adds:

1. **Advanced Model Control** — Fine-tune inference parameters
2. **Basic Tools Integration** — File operations, system info
3. **Library & Saves** — Bookmark conversations, export, organize

---

## Feature 1: Advanced Model Control

### What It Enables
- User can adjust how model responds (temperature, creativity, token limits)
- Different parameter sets for different use cases (fast+creative vs accurate+careful)
- Per-conversation overrides (use fast model but with high creativity)

### Components to Add

#### Frontend
- **ModelSettingsPanel** component in Settings view
- Temperature slider (0.0 - 2.0)
- Top-P slider (nucleus sampling)
- Max tokens slider (context window)
- System prompt text area
- "Reset to defaults" button
- Save as preset (fast, code, main each have presets)

#### Backend
- Extend `ChatRequest` model:
  - `temperature: Optional[float]`
  - `top_p: Optional[float]`
  - `max_tokens: Optional[int]`
  - `system_prompt: Optional[str]`
- Update chat inference call to pass parameters to Ollama API
- Store model presets in `settings` table

#### API Endpoint
```
PUT /api/models/{model_name}/parameters
  {
    "temperature": 0.7,
    "top_p": 0.9,
    "max_tokens": 2000,
    "system_prompt": "You are a helpful assistant"
  }
```

### Implementation Estimate
- Backend: 1-2 hours (extend models, add parameters to chat request)
- Frontend: 2-3 hours (sliders, forms, validation)
- Testing: 1 hour
- **Total: 4-6 hours**

---

## Feature 2: Basic Tools Integration

### What It Enables
- Agent can read/write files
- Agent can get system information
- Agent can execute safe operations
- Gating: Tools available under Settings > Tools, not in daily chat

### Components to Add

#### Tool 1: File Operations
```python
# Available tools via API
@router.get("/api/tools/files/read/{path}")
  -> read file (with sandbox path validation)

@router.post("/api/tools/files/write/{path}")
  -> write file (with confirmation)

@router.get("/api/tools/files/list/{directory}")
  -> list directory (with sandbox validation)
```

#### Tool 2: System Information
```python
@router.get("/api/tools/system/info")
  -> { cpu, memory, disk, gpu_status }

@router.get("/api/tools/system/clipboard/read")
  -> get clipboard content

@router.post("/api/tools/system/clipboard/write")
  -> set clipboard content
```

#### Frontend
- **ToolsManagerPanel** in Settings view
- Toggle per tool (enable/disable)
- Test buttons for each tool
- Log viewer (see what operations were executed)
- Confirmation dialogs for write operations

#### Safety Guardrails
- Sandbox path checking (no access outside user directory)
- Rate limiting on tool calls
- Confirmation required for write operations
- Tool use logged to conversation history
- Can disable tools per tool

### Implementation Estimate
- Backend tools: 3-4 hours (file ops, system info, validation)
- Frontend: 2-3 hours (tool panel, test buttons, logging)
- Testing & safety: 2-3 hours (validate sandboxing)
- **Total: 7-10 hours**

---

## Feature 3: Library & Saves

### What It Enables
- User can bookmark important conversations
- Export conversations (markdown, PDF, JSON)
- Organize saved items into collections
- Search saved items

### Components to Add

#### Database Schema
```sql
CREATE TABLE library_items (
  id TEXT PRIMARY KEY,
  conversation_id TEXT,
  created_at TEXT,
  title TEXT,
  description TEXT,
  tags TEXT,  -- comma-separated
  FOREIGN KEY (conversation_id) REFERENCES conversations(id)
)
```

#### API Endpoints
```
POST /api/library/save
  { conversation_id, title, description, tags }

GET /api/library
  -> list all saved items

DELETE /api/library/{item_id}
  -> remove from library

POST /api/library/{item_id}/export
  { format: "markdown" | "pdf" | "json" }
```

#### Frontend
- **LibraryView** component (new tab alongside chat)
- Bookmark button on conversations
- Search/filter by tag
- Export button (format selector)
- Delete confirmation

### Implementation Estimate
- Backend: 2-3 hours (schema, endpoints, export logic)
- Frontend: 2-3 hours (library view, bookmark UI)
- Export implementation: 1-2 hours (markdown/PDF generation)
- **Total: 5-8 hours**

---

## Implementation Order

### Week 1: Advanced Model Control (May 1-7)
- Day 1-2: Backend (extend models, API endpoints)
- Day 3-4: Frontend (sliders, form, validation)
- Day 5: Testing & iteration

### Week 2: Basic Tools Integration (May 8-14)
- Day 1-2: Backend (file ops, system info, sandboxing)
- Day 3-4: Frontend (tool panel, confirmations)
- Day 5-6: Testing, security validation

### Week 3: Library & Saves (May 15-20)
- Day 1-2: Backend (schema, endpoints, export)
- Day 3-4: Frontend (library view, export UX)
- Day 5: Testing & polish

**Overlap possible:** Some tasks can run in parallel (frontend while backend is being tested)

---

## Testing Checklist

### Advanced Model Control
- [ ] Adjust temperature → verify API receives updated parameter
- [ ] Change max tokens → verify responses respect limit
- [ ] Set system prompt → verify model uses custom prompt
- [ ] Save preset → verify persists across sessions
- [ ] Switch models → verify each model has own settings

### Basic Tools Integration
- [ ] File read works → verify can read file
- [ ] File write works → verify file created with content
- [ ] File list works → verify directory listing
- [ ] System info works → verify CPU/memory/disk returned
- [ ] Clipboard read/write works
- [ ] Sandboxing validated → verify can't read outside user dir
- [ ] Rate limiting works → verify can't spam tool calls
- [ ] Confirmation required → verify write needs approval

### Library & Saves
- [ ] Save conversation → appears in library
- [ ] Export markdown → file created, content correct
- [ ] Export PDF → file created, readable
- [ ] Search tags → correct items returned
- [ ] Delete item → removed from library
- [ ] Bookmark persists → survives page refresh

---

## Risk Assessment

### Low Risk
- Advanced model control — Ollama API already supports these parameters
- File operations with sandboxing — Clear pattern to validate paths
- Library schema — Simple relational design, proven pattern

### Medium Risk
- System info exposure — Need careful permission checks
- Export format quality — PDF generation complexity
- Tool safety at scale — Not tested with many concurrent operations

### High Risk
- User confusion about tool capabilities/limitations
- Security gaps in sandboxing (path traversal attacks)
- Performance impact of tool operations on chat latency

---

## Success Criteria

### Feature Complete When:
1. ✅ All API endpoints implemented and documented
2. ✅ Frontend components built and integrated
3. ✅ All testing checklist items pass
4. ✅ Security review completed (path validation, etc.)
5. ✅ Documentation updated (TOOLS.md, tool descriptions)
6. ✅ Committed to main branch with passing tests

### Quality Metrics
- Test coverage: ≥90% for tools code
- Performance: Tool calls <500ms (file read/system info)
- Safety: No path traversal vulnerabilities
- UX: Tool features discoverable in Settings view

---

## Next Steps

1. **Today:** Review P1 scope, confirm priorities
2. **This week:** Plan P0 validation tests
3. **May 1:** Begin P1 implementation (advanced model control)
4. **May 22:** P1 complete, move to P2 (polish)
5. **June 12:** P6 freeze-readiness achieved

---

## Dependencies & Notes

- Requires P0 to be complete and tested ✅
- Requires API to be stable (currently is)
- Requires clear path sandboxing approach (well-defined)
- Tools should be hidden from casual users (gated under Settings)

---

**Ready to proceed?** Let's validate P0 first, then begin P1 implementation.
