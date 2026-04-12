# Claude Code Handoff Notes

Date: April 11, 2026
Owner transition: temporary handoff from Copilot to Claude Code

## Executive Summary
- Sales and CRM expansion work is parked for now.
- Current priority is stability-first execution.
- Voice path and UI launch path were stabilized in the latest cycle.

## What Changed Most Recently

### 1) Voice runtime compatibility and resilience
File: guppy_voice.py
- Added import-safe optional dependency handling.
- Restored compatibility API expected by UIs and tests:
  - VoiceConfig
  - listen_once
  - stop_listening
  - toggle_quiet
  - stop_tts
- Preserved fallback behavior when Kokoro is not installed.

### 2) UI thinking-stream crash fix
Files:
- guppy_ui.py
- merlin_ui.py
- council_ui.py

Change:
- Thinking-stream label updates now use safe text retrieval and assignment.
- Removed crash path caused by assuming QLabel had a custom _text field.

## Current Known Conditions
- Anthropic requests may fail when Claude credits are exhausted.
- Kokoro may not be available in local env; fallback mode should carry voice path.
- Hugging Face warns when unauthenticated (HF_TOKEN not set).
- Chroma semantic backend is intentionally parked for now. Keep semantic memory on SQLite by default.

## Deferred Note: Chroma (Debug + Optional Connect)
- Status: deferred
- Why deferred: current Windows env can throw native access-violation crashes in Chroma Rust upsert path.
- Current policy:
   - default semantic backend remains SQLite
   - Chroma must stay opt-in only
- Resume criteria:
   1. Debug crash root cause (Rust backend / telemetry thread interaction)
   2. Validate no process crashes in repeated upsert/query soak test
   3. Keep hard fallback to SQLite if Chroma fails at runtime
   4. Only then connect Chroma as an optional backend in normal flow

## Suggested First Actions for Claude Code
1. Run GUI smoke tests:
   - python guppy_ui.py
   - python merlin_ui.py
   - python council_ui.py
2. Run voice test path:
   - python tests/test_ptt.py
3. Add explicit voice backend status in visible runtime surfaces:
   - API status payload
   - UI status indicator
4. Align voice docs with runtime behavior:
   - docs/VOICE.md
   - README.md

## Guardrails During Handoff
- Do not resume CRM/sales feature expansion until stability checklist is complete.
- Keep fallback paths non-fatal for optional dependencies.
- Prefer small, verifiable changes and smoke-test each launch path.

## Completion Signal to Resume Product Work
Resume roadmap feature expansion only after all are true:
- Guppy, Merlin, Council launch cleanly.
- Voice path reports clear backend status and degrades gracefully.
- Docs match observed runtime behavior.
- Remote hardening checks pass for core routes.
