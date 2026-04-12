# Step 3 Stability Checklist (Live Validation)

Date: 2026-04-12

## Added from live session feedback

1. Voice quality check
- Confirm runtime TTS backend in UI/API status.
- If fallback is `sapi`, log warning and treat voice quality as degraded (robotic expected).
- Prefer Kokoro backend for natural voice before release testing.

2. Build mode clarity check
- Verify startup mode label is accurate (`AUTO` / `CLAUDE` / `OLLAMA`).
- Verify `.env` is loaded so `ANTHROPIC_API_KEY` is seen when launching from tasks.
- If key is missing, expect local mode and explicit warning.

3. PTT functional check
- Hold-to-talk starts listening state and logs event.
- If STT backend is unavailable, show explicit user-facing error.
- Validate transcription event appears in session logs.

## Run order
1. `python tests/test_runtime_smoke.py`
2. `python tests/test_ptt.py`
3. Launch `guppy_ui.py`, `merlin_ui.py`, `council_ui.py`
4. Exercise one PTT input in Guppy and check `runtime/session_events.jsonl`
