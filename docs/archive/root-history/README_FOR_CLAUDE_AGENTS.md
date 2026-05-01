# Claude Agent Quick Start

**You are working on Guppy: a local LLM harness for PC automation, workflow automation, task management, and research.**

This guide tells you what to read first and where to find answers. Read this before touching any code.

---

## ⭐ Read in This Order

### 1. Your Memory (5 min) — **Start here**
**File:** `MEMORY.md` in your workspace

This is your current context: what Ryan is focused on, deadlines, what's shipping now, active initiatives. It's maintained and current.

**What to find:**
- Current roadmap and timeline
- What's shipping this week
- Active blockers or initiatives
- Your past decisions and learnings

---

### 2. This File (CLAUDE.md) (5 min) — **Architecture & conventions**
**File:** `CLAUDE.md` in the repo root

This is the reference guide: architecture, module paths, how to build/test, security practices, known issues.

**What to find:**
- How the codebase is organized
- Build & test commands
- Module paths and key classes
- How auth works
- What's verified working

---

### 3. Project Docs (as needed) — **Deep dives**
**Files:**
- `docs/PROJECT_BRIEF.md` — Active roadmap, current status, blockers, timeline
- `docs/LIVE_ARCHITECTURE.md` — Architecture deep-dive, design decisions, trade-offs

**When to read:**
- If you need to understand *why* a decision was made
- If you're implementing a new feature and need architectural context
- If you're debugging something complex

---

## Where to Find Answers

| Question | Answer |
|----------|--------|
| "What is Ryan working on right now?" | `MEMORY.md` |
| "When is the next deadline?" | `MEMORY.md` (Roadmap section) |
| "How do I build/test Guppy?" | `CLAUDE.md` (Build & Test section) |
| "What's the architecture?" | `CLAUDE.md` (Architecture Overview) then `docs/LIVE_ARCHITECTURE.md` |
| "How do I run the Web UI?" | `CLAUDE.md` (Launcher Patterns section) |
| "What models are available?" | `CLAUDE.md` (Model Roster tables) |
| "How does auth work?" | `CLAUDE.md` (Security & Repair Token section) |
| "What features shipped recently?" | `SHIPPING_LOG.md` (detailed implementation notes) |
| "Is X already implemented?" | `CLAUDE.md` (Verified Working section) |

---

## One Key Pitfall

**Don't get confused by multiple docs.**

There are many docs in this repo. But you only need three:
1. **MEMORY.md** (current state)
2. **CLAUDE.md** (reference)
3. **PROJECT_BRIEF.md** (context, if needed)

Everything else is either:
- Historical context (archived, useful for understanding decisions)
- Detailed implementation notes (SHIPPING_LOG.md, useful for code review but not for understanding current state)
- Architecture deep-dives (LIVE_ARCHITECTURE.md, only if you're making major design decisions)

**If you feel lost, go back to MEMORY.md. It's the source of truth for what's happening right now.**

---

## Before You Start Work

1. ✅ Read the three files above (takes 15 min total)
2. ✅ Check `MEMORY.md` to see what Ryan is focused on
3. ✅ Run `python tools/dev_workflow.py dev-check --guard-scope delta` to verify the environment
4. ✅ If you're making changes, update CLAUDE.md (this file) if you change architecture

---

## Quick Reference

**Build & test:**
```powershell
python tools/dev_workflow.py dev-check --guard-scope delta
python tools/dev_workflow.py test-fast         # Unit tests only
python tools/dev_workflow.py test-default      # Unit + integration
```

**Run the Web UI:**
- One-click: `Guppy_WebUI_Launcher.bat` in the repo
- Or: `python tools/dev_workflow.py launch`

**Key env vars:**
- `GUPPY_DEV_MODE` — Enables dev endpoints and logging
- `GUPPY_JWT_SECRET` — JWT signing key (fallback if keyring unavailable)
- `OLLAMA_HOST` — Ollama endpoint (default `http://127.0.0.1:11434`)

**Dependencies:**
- Python ≥ 3.12
- Ollama running on `http://127.0.0.1:11434`

---

## When You're Stuck

1. **Code question?** → Read `CLAUDE.md` (Architecture or Modules section)
2. **Why was X designed this way?** → Check `MEMORY.md` for context, then `docs/LIVE_ARCHITECTURE.md`
3. **Build/test error?** → Run `python tools/dev_workflow.py dev-check` to diagnose
4. **Unsure what to work on?** → Check `MEMORY.md` (Active Tasks section)
5. **Everything else?** → Check `docs/PROJECT_BRIEF.md` (Status & Roadmap)

---

## File Locations Cheat Sheet

```
Guppy/
├── CLAUDE.md                          ← REFERENCE (read this)
├── README_FOR_CLAUDE_AGENTS.md        ← YOU ARE HERE
├── SHIPPING_LOG.md                    ← Detailed feature notes (optional)
├── docs/
│   ├── PROJECT_BRIEF.md               ← Active roadmap & status
│   ├── LIVE_ARCHITECTURE.md           ← Architecture deep-dive
│   ├── LEGACY_QUARANTINE_PROTOCOL.md  ← For context on deprecated code
│   └── ...
├── src/guppy/
│   ├── cli/launch.py                  ← All launcher entry points
│   ├── api/                           ← FastAPI backend
│   ├── launcher_application/          ← Shared workflow catalog
│   └── apps/launcher_app.py           ← Qt wrapper (spawns server)
├── tools/
│   ├── dev_workflow.py                ← Use this for everything
│   ├── verify_local_model_runtime.py  ← Check if the local model runtime is ready
│   └── ...
└── config/
    └── instances.json                 ← Runtime instances (guppy-primary, etc.)
```

---

**Last updated:** 2026-04-28

**Questions?** Check `MEMORY.md` first. If not there, check `CLAUDE.md`. Still stuck? Check `docs/PROJECT_BRIEF.md`.
