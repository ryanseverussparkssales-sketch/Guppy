# Claude Code Handoff — Guppy Master Execution List

**Generated:** 2026-04-28
**Source:** Combined survey of TASKS.md, ROADMAP.md, docs/PROJECT_BRIEF.md, docs/MASTER_FIX_LIST.md, SHIPPING_LOG.md, PLATFORM_HARDENING_PLAN_2026-04-28.md, READINESS_REVIEW_2026-04-28.md, EXECUTION_PRIORITY_MATRIX.md, REPO_REVIEW_SUMMARY_2026-04-27.md, ROADMAP_UPDATE_2026-04-27.md, AUDIT_FINDINGS_2026_04_26.md, PHASE_1/2/3_IMPLEMENTATION_TASKS.md, plus inline TODO/FIXME survey of `src/guppy/**/*.py` and verification of `src/guppy/voice/`, `src/guppy/backends/`, `dist/`, and `git status`.

**Hard deadline:** June 12, 2026 (P6 freeze-readiness).

---

## How to use this doc

1. Read the **Verified State** section first — every claim is grounded in something checked at generation time.
2. Work the **Master List** in order. Items are ranked by gating risk, not nice-to-have.
3. Each item has: WHY it's open, WHERE the evidence is, WHAT to do, and HOW to verify. Don't mark complete without running the verify step.
4. Before/after every block, run `python tools/dev_workflow.py dev-check --guard-scope delta`. Before any commit, run `release-check`.
5. Conflicts in the source docs are flagged with **⚠ CONFLICT** — resolve those by inspection before doing the work.

---

## Verified State (as of 2026-04-28)

### What is real
- `docs/PROJECT_BRIEF.md` is dated 2026-04-28 and treats P1–P5 as complete and P6 as active.
- TR54 (full module breakup + Stitch streamlining) closed: `launcher_window.py` is 993 lines; `server_runtime_snapshot.py` is 789 lines; both at-cap waivers retained.
- Voice subsystem decomposed under `src/guppy/voice/`: `core.py`, `stt/{google,whisper,sapi,fallback_orchestrator}`, `tts/{kokoro,sapi,elevenlabs,cache,fallback_orchestrator}`, `wake_word/{energy,porcupine,detector}` all exist.
- Voice tests exist: `tests/unit/test_stt_providers.py`, `test_tts_providers.py`, `test_wake_word.py`, `test_voice_support.py`.
- Latest commits (2026-04-28): TTS api_key fix, six truncated source files reconstructed (Hermes 4/3/Rocinante backends, db_utils, image_base64, JWT WS handler), STT facade telemetry wired.
- `tools/dev_workflow.py`, `tools/check_architecture_boundaries.py` exist and are canonical.
- llama.cpp model roster live: Pepe, Gemma, Qwen3, MiniCPM, Dispatch (auto-start), Hermes 4, Hermes 3, Rocinante.
- Web UI corruption from 2026-04-26 (AUDIT_FINDINGS_2026_04_26.md) is resolved per `SHIPPING_LOG.md` ("6 corrupted source files reconstructed").

### What is NOT real (despite plans assuming it)
- `src/guppy/backends/` does **not exist** on disk. Phase 2 (Backend Registry) is paper only.
- No `dist/` directory exists. No packaged executable. PL-C15 evidence claims a `dist/` build is part of Track 1 — currently unbacked.
- 390 working-tree changes (369 modified + 21 untracked) including PHASE_1/2/3_IMPLEMENTATION_TASKS.md, READINESS_REVIEW_2026-04-28.md, SHIPPING_LOG.md, voice modules `core.py`/`integration.py`/`ppt.py`, and reconstructed static assets — none of which have been committed.
- `src/guppy/voice/ppt.py` and `src/guppy/voice/integration.py` are stub modules with placeholder docstrings, not real implementations.

### ⚠ CONFLICT to resolve before executing
- **Web UI parity**: `docs/PROJECT_BRIEF.md` paragraph 13 states "Web UI Parity Complete (2026-04-28)" — but `ROADMAP_UPDATE_2026-04-27.md` (one day older) flags it as the 🔴 CRITICAL BLOCKER for June 12, the test plan in `P0_PARITY_TESTING_PLAN_2026-04-23.md` lists empty `Test Result: ✅ / ❌` checkboxes (i.e., not run), and `EXECUTION_PRIORITY_MATRIX.md` puts 3–4 weeks of parity work on the critical path. Treat parity as **unverified**: run the test plan first (Master List item #1) and let observed behavior decide.

---

## Master List (ranked)

### TIER 1 — Critical path to June 12 release

#### 1. Run P0 parity test plan and record results
- **Why:** Conflict above — multiple docs disagree. The test plan exists but its result rows are blank.
- **Where:** `P0_PARITY_TESTING_PLAN_2026-04-23.md` — Sections A (Models), B (Workspaces), C (Tools), D (Settings/Credentials).
- **Do:**
  1. Boot all three surfaces: `python src/guppy/cli/launch.py launcher` (Qt wrapper), `python src/guppy/cli/launch.py api`, web UI at `http://127.0.0.1:8080`.
  2. Run each Section A/B/C/D step. Tick each `✅ / ❌`. Capture screenshots into `runtime/parity_evidence_2026-04-28/`.
  3. For every ❌, file a follow-up under TIER 1 in this doc.
- **Verify:** All test rows have a non-empty result; failures have follow-up items linked.

#### 2. Wire the 18 button stubs blocking T1 closure
- **Why:** `ROADMAP_UPDATE_2026-04-27.md` §"Known Tech Debt" calls these out; they emit `console.log` only and break the "no operator dead-ends" north-star.
- **Where:**
  - Command Palette: Initialize Node, Start Node, Halt All Nodes (3 stubs) → wire to `POST /api/instances` lifecycle.
  - InstancesView "+ New Instance" button → instance creation flow.
  - LibraryView: copy / edit / delete on hover (3+ stubs).
  - TopBar: 3+ stubs (search workspace, model picker secondary actions).
- **Do:** Replace `console.log` handlers with `apiClient` calls (see `web/src/api/client.ts` and `queries.ts`). Add Sonner toast on success/failure (already wired for tools).
- **Verify:** Grep `web/src/` for `console.log` in onClick handlers — should be zero in primary buttons. Add a Vitest test per critical button.

#### 3. Build a real `dist/` artifact and verify on a clean machine
- **Why:** `READINESS_REVIEW_2026-04-28.md` flags "verify clean-machine build" as immediate-before-announcement; `PROJECT_BRIEF.md` PL-C15 closure required honest packaging evidence; no `dist/` exists today.
- **Where:** `bin/build_executable.bat`, `tools/validate_build_checks.py`, `src/guppy/launcher_application/packaging_audit.py`.
- **Do:**
  1. `bin/build_executable.bat` (Windows) or follow `docs/PACKAGING.md`.
  2. Confirm `dist/Guppy/Guppy.exe` exists and is non-trivial (packaging_audit.py rejects stubs).
  3. Run `tools/ensure_desktop_launcher.ps1` to point shortcut at the dist exe.
  4. Move `dist/` to a clean Windows VM with no dev tools and run smoke: launch → first-run wizard → first local model success.
- **Verify:** `python tools/dev_workflow.py release-check` passes its packaging gate, receipt under `.tmp/dev-workflow/reports/` shows real artifact size.

#### 4. Validate external auth path (Turnstile + Cloudflare tunnel)
- **Why:** `READINESS_REVIEW_2026-04-28.md` lists this as a release gate; `src/guppy/api/auth.py` already references `TURNSTILE_SECRET` validation but the production path has not been exercised.
- **Where:** `src/guppy/api/auth.py:177–210`, repair token + Turnstile verify flow in `routes_ops.py`.
- **Do:** Stand up a Cloudflare tunnel pointing at `localhost:8080`; configure `TURNSTILE_SECRET` from production keypair; run an end-to-end auth flow from a remote browser; capture failure modes (rate-limit, expired token) and ensure they fail closed.
- **Verify:** `tests/test_security_hardening.py` extended with at least one Turnstile-validate test that exercises both success and failure.

#### 5. Commit the working tree (4-tranche strategy)
- **Why:** 390 files in working tree; `ROADMAP_UPDATE_2026-04-27.md` already laid out the commit waves. Carrying this drift risks losing the TR54 / Phase 1 work to another corruption event.
- **Do:**
  - Wave 1 (docs/infra): `CLAUDE.md`, `*.md` planning docs, `docs/`, test conftest, this handoff doc.
  - Wave 2 (desktop/launcher): `ui/launcher/**`, `bin/**`, model file changes (`Modelfile.*`).
  - Wave 3 (web UI): `web/**`, `static/assets/**`.
  - Wave 4 (API + voice): `src/guppy/api/**`, `src/guppy/voice/**`, `tests/unit/test_*voice*`, `tests/unit/test_stt*`, `tests/unit/test_tts*`, `tests/unit/test_wake_word.py`.
- **Verify:** `python tools/dev_workflow.py release-check` green between each wave; `git status` empty at end.

---

### TIER 2 — Phase 1 (Audio Hardening, May 1–22)

Per `PHASE_1_IMPLEMENTATION_TASKS.md` and `PLATFORM_HARDENING_PLAN_2026-04-28.md`. TASKS.md confirms 1.1–1.4 done; 1.5 + audio-only workspace + telemetry pending.

#### 6.0 (BLOCKING) — Resolve the three parallel TTS/STT stacks
- **Why:** Audit on 2026-04-28 found three parallel voice implementations + stale `GuppyVoice` references that fail at runtime. The Phase 1 work (Stack C) is unconsumed; the live HTTP API (Stack A, `routes_voice.py`) calls a class that no longer exists; the middle stack (Stack B, `voice_runtime.py`) is dead with zero callers. Phase 1 telemetry, audio-only workspace, and stress tests cannot meaningfully run until exactly one stack is the truth.
- **Where (verified 2026-04-28):**
  - Stack A — `src/guppy/api/routes_voice.py` (476 lines, live, browser-facing). Uses Deepgram + faster-whisper-via-broken-GuppyVoice + Kokoro HTTP + ElevenLabs.
  - Stack B — `src/guppy/voice/voice_runtime.py` (556 lines) + `voice_support.py` (141 lines). Zero live callers.
  - Stack C — `src/guppy/voice/voice.py` (380 lines) + `stt/{google,whisper,sapi,fallback_orchestrator}` + `tts/{kokoro,sapi,elevenlabs,cache,fallback_orchestrator}` + `wake_word/{energy,porcupine,detector}` + `core.py` + `ppt.py` + `integration.py`. ~2,930 lines. Uses Google + OpenAI Whisper API + SAPI. Imported by `server_runtime.py:81` purely to flip `GUPPY_VOICE_AVAILABLE=True`, never called.
  - Broken `GuppyVoice` references: `routes_voice.py:268,470`; `snapshot_realtime_support.py:311`; `_server_fragment_routes_ops.py:23`; `cli/agent.py:304`; `debug/_tabs.py:332,365`; `debug/_voice_support.py` (expects old attrs); `compat_shims/launcher_ui/ui/launcher/{launcher_window.py:164, launcher_window_action_methods.py:49, views/voices_view.py:39}`; `tools/verify_voice_runtime.py:66`; tests `test_snapshot_realtime_support.py:145` + `test_voices_view_validation.py:81`.
  - Stack C latent gaps: `voice.py` `_capture_microphone_audio` returns `b""`; `_stream_microphone_audio` returns `None`; `ppt.py` `_is_valid_transition` always True; `integration.py` mocks raise `NotImplementedError`.
  - Provider asymmetry: Stack A uses **Deepgram nova-3**; Stack C has no Deepgram provider. Switching live system to Stack C changes which cloud STT vendor is hit.
- **Decision (locked 2026-04-28 by Ryan): Option 2 — Stack C wins.** Cherry-pick what's worth keeping from Stack A, build out Stack C's gaps, rewrite `routes_voice.py` as a thin HTTP wrapper over Stack C, then purge Stack B and stale `GuppyVoice` references.

- **Do — sequenced so the live web UI never breaks:**

  **Phase 6.0a — Build out Stack C gaps (no live behavior change yet):**
  1. Create `src/guppy/voice/stt/deepgram_stt.py` — port `_transcribe_deepgram_bytes` from `routes_voice.py:209–229` and `transcribe_with_deepgram` from `voice_runtime.py:39–68` into a `DeepgramSTTProvider(STTProvider)` class. Reads `DEEPGRAM_API_KEY` env. Implements `transcribe()` and `health_check()`.
  2. Update `src/guppy/voice/stt/fallback_orchestrator.py` — change chain to **Deepgram (primary) → Whisper → SAPI**. Drop GoogleSTTProvider from default chain (keep the class for compat) since the live system uses Deepgram, not Google. Order: `if DEEPGRAM_API_KEY: deepgram → whisper → sapi else: whisper → sapi`.
  3. Move static catalogs into provider modules:
     - `_KOKORO_VOICES` (routes_voice.py:45–53) → `voice/tts/kokoro_provider.py` as `KOKORO_VOICES`
     - `_ELEVENLABS_VOICES_DEFAULT` (routes_voice.py:56–64) → `voice/tts/elevenlabs_provider.py` as `ELEVENLABS_VOICES_DEFAULT`
     - `_WHISPER_MODELS` (routes_voice.py:66–71) → `voice/stt/whisper_stt.py` as `WHISPER_MODELS`
  4. Move helpers:
     - `_fetch_elevenlabs_voices` (5-min cache, routes_voice.py:109–140) → method on `ElevenLabsTTSProvider` as `list_voices()`.
     - `_probe_kokoro` (60-sec cache, routes_voice.py:92–106) → method on `KokoroTTSProvider` as `probe_health()`. Reuse if already similar; consolidate.
     - `_pcm_to_wav` (routes_voice.py:76–89) → new `voice/audio_utils.py`.
     - `clean_for_tts`, `win_hidden_popen_flags`, `resolve_kokoro_voice`, `kokoro_speed_value`, `preferred_sapi_voice`, `sapi_rate_value` from `voice_support.py` → push into the relevant provider modules (`kokoro_provider.py`, `sapi_provider.py`) or a new `voice/util.py`. `clean_for_tts` is genuinely shared, put it in `voice/util.py`.
  5. Implement real microphone capture in `src/guppy/voice/voice.py`:
     - Replace `_capture_microphone_audio` (currently returns `b""`) and `_stream_microphone_audio` (currently `None`) with real `sounddevice` capture ported from `voice_runtime.py` `record_worker()` (lines 147–185).
     - Use the same `silence_cutoff` / `speech_threshold` config from `core.VoiceConfig`.
  6. Implement `ppt.py` `_is_valid_transition`: define the actual state machine (IDLE↔LISTENING, LISTENING→TRANSCRIBING, TRANSCRIBING→IDLE, IDLE↔ACTIVE for TTS).
  7. Implement `integration.py` real audio generators (`generate_test_audio_silence`, `generate_test_audio_white_noise`, `generate_test_audio_sine_wave`) — currently `NotImplementedError`. Use numpy + struct.

  **Phase 6.0b — Switch `routes_voice.py` to Stack C (live wire flip):**
  8. Rewrite `src/guppy/api/routes_voice.py`:
     - `POST /api/voices/transcribe` → `await voice.transcribe(audio_bytes, language=...)` from Stack C facade. Return `{transcript, provider}` from the `STTResult`.
     - `POST /api/voices/speak` → `await voice.synthesize(text, voice=...)` from Stack C facade. Return `Response(content=result.audio_data, media_type=result.format)`.
     - `POST /api/voices/test` → same as `/speak` but pipes through server speakers (use Stack C `speak()` helper).
     - `POST /api/voices/stop` → call new `voice.stop()` (add this to Stack C facade if missing).
     - `GET /api/voices` → assemble the voice/provider list from `KOKORO_VOICES`, `ELEVENLABS_VOICES_DEFAULT`, `WHISPER_MODELS`, plus `voice.get_voice_config()` for active provider state.
     - `PUT /api/voices/settings` → `voice.set_voice_config(VoiceConfig(...))` instead of poking env vars directly. Persist to settings DB.
     - Delete `_get_voice_handler`, `_voice_instance`, `_synthesize_for_browser`, `_try_kokoro_api`, `_try_elevenlabs`, `_resolve_elevenlabs_voice`, `_transcribe_deepgram_bytes`, `_probe_kokoro`, `_fetch_elevenlabs_voices`, `_pcm_to_wav` (moved or replaced).
  9. Smoke-test live: web UI record → transcribe → speak. If a regression appears, do not proceed to purge.

  **Phase 6.0c — Purge dead code and stale references:**
  10. Delete files:
      - `src/guppy/voice/voice_runtime.py` (556 lines, zero callers).
      - `src/guppy/voice/voice_support.py` after migrating utilities (141 lines).
      - `src/guppy/debug/_voice_support.py` (uses old GuppyVoice attrs).
  11. Delete dead GuppyVoice paths:
      - `src/guppy/api/snapshot_realtime_support.py:311` — remove the `owner.voice.GuppyVoice` block.
      - `src/guppy/api/_server_fragment_routes_ops.py:23` — remove the `voice.GuppyVoice` block.
  12. Rewrite or delete:
      - `src/guppy/cli/agent.py:301–340` `voice_mode()` — rewrite against `voice.listen()` / `voice.speak()` async facade, OR delete the `voice` CLI subcommand entirely. Recommend delete unless the CLI REPL is a real feature.
      - `src/guppy/debug/_tabs.py:332,365` — replace `guppy_voice.TTS_ENABLED` reads/writes with `voice.get_voice_config().enable_tts` and `voice.set_voice_config(...)`. (Add `enable_tts` to `VoiceConfig` if not present.)
      - `tools/verify_voice_runtime.py:60–110` — change the GuppyVoice import probe to test the new facade: `from guppy.voice import voice; assert voice.synthesize and voice.transcribe`.
  13. Quarantine path (`compat_shims/launcher_ui/`): the Qt launcher is now wrapper-only per CLAUDE.md, but it still imports `GuppyVoice` in three places. Either:
      - **Leave as-is** with comments marking them as quarantined-broken (acceptable per `compat_shims/legacy_surfaces/` quarantine pattern), OR
      - **Migrate** to `from guppy.voice.voice import speak, synthesize` and adjust call sites.
      Recommend leave-as-is and add to Phase 3 cleanup (Tier 4 #14).
  14. Tests:
      - `tests/unit/test_voice_support.py` — rewrite to test the new util locations or delete if functionality moved into provider tests.
      - `tests/unit/test_snapshot_realtime_support.py:145` — remove the `voice=SimpleNamespace(GuppyVoice=...)` fixture; rewrite the test against the new path or delete the case if the snapshot path was removed in step 11.
      - `compat_shims/launcher_ui/tests/test_voices_view_validation.py:81` — covered by quarantine decision in step 13.

- **Verify after each phase (do not skip):**
  - After **6.0a**: `pytest tests/unit/test_stt_providers.py tests/unit/test_tts_providers.py tests/unit/test_wake_word.py` plus a new `tests/unit/test_deepgram_stt.py` — all green. No live behavior change yet.
  - After **6.0b**: web UI smoke — open `/`, record audio, see transcript, hear TTS playback. `pytest tests/unit/test_routes_voice.py` (write if missing).
  - After **6.0c**: `grep -rn "GuppyVoice" --include="*.py" src/ tools/ tests/` returns zero hits outside `compat_shims/launcher_ui/`. `grep -rn "voice\.TTS_ENABLED" --include="*.py"` returns zero hits. `python tools/verify_voice_runtime.py` exits 0. `python tools/dev_workflow.py release-check` green.

- **Estimated effort:** 4–8 focused hours. Phase 6.0a is mostly mechanical (~2–3 hours). Phase 6.0b is the risky part (~2–3 hours) — keep web UI open and re-test after every endpoint switch. Phase 6.0c is ~1–2 hours of careful deletion with a green test suite at every step.

#### 6. Phase 1.5 — stress + audio-quality + integration testing
- **Where:** `tests/integration/` (no audio integration tests yet); `PLATFORM_HARDENING_PLAN_2026-04-28.md` §1.5a–c.
- **Do:** 100-utterance loop, 2-min monologue, rapid-fire interrupt, silence detection, network-failure fallback, latency p95 baseline. Record into `runtime/audio_evidence/`.
- **Verify:** STT error rate < 5%, TTS latency p95 < 1500ms, fallback success > 98%.

#### 7. Audio-only workspace (`WorkspaceMode::AUDIO_ONLY`)
- **Where:** New: `src/guppy/workspace_governance/audio_workspace.py`; UI changes in `web/src/views/AssistantView.tsx`; spec in `PLATFORM_HARDENING_PLAN_2026-04-28.md` §1.2.
- **Do:** Add `WorkspaceMode` enum extension, `accept_text_input=False`, `force_tts_output=True`, audio waveform UI preset, star-rating quality feedback.
- **Verify:** Demo clip: voice in → voice out, no text touched.

#### 8. Audio telemetry / health endpoint
- **Where:** New: `GET /api/voice/health`; AudioEvent schema per `PLATFORM_HARDENING_PLAN_2026-04-28.md` §1.3.
- **Do:** Persist STT/TTS latency + confidence + fallback triggers per utterance. Expose dashboard in AdminPanel.
- **Verify:** Endpoint returns p50/p95/p99 latency by provider; fallback triggers show on a forced-failure run.

#### 9. Stretch: TTS true streaming + Porcupine real wake-word + microphone capture
- **Why:** TASKS.md "Someday" — but real STT pipeline depends on actual microphone capture (currently delegated to platform wrapper) and the EnergyThreshold provider is voice-activity-only, not a real wake-word.
- **Where:**
  - `src/guppy/voice/voice.py` `_capture_microphone_audio` + `_stream_microphone_audio` — wire `sounddevice` or `pyaudio`.
  - `src/guppy/voice/wake_word/porcupine_provider.py` — needs `PORCUPINE_ACCESS_KEY` + `.ppn` keyword files.
  - `src/guppy/voice/tts/*` — replace whole-then-yield with chunked streaming (Kokoro `KPipeline`, ElevenLabs streaming endpoint).
- **Verify:** Live mic test in audio-only workspace produces real STT output without platform-wrapper fallback.

---

### TIER 3 — Phase 2 (Backend Registry, May 23–Jun 5)

`src/guppy/backends/` does not exist. Spec is in `PHASE_2_IMPLEMENTATION_TASKS.md` and `PLATFORM_HARDENING_PLAN_2026-04-28.md` §2.

#### 10. Scaffold `src/guppy/backends/`
- **Do:** Create `__init__.py`, `types.py` (BackendType, BackendCapability, BackendStatus, Backend dataclass, HealthStatus), `base.py` (Backend ABC), `registry.py` (BackendRegistry single source of truth).
- **Verify:** `from guppy.backends import BackendRegistry` succeeds; line cap green.

#### 11. Migrate local + cloud providers under `backends/local/` and `backends/cloud/`
- **Do:** Move existing logic from `src/guppy/inference/local_client.py`, `provider_clients_cloud.py`, `routes_backends.py` into the new structure. Keep thin compatibility shims at the old paths so launcher/tests don't break.
- **Verify:** All 10 backends register on startup; `dev-check` passes; smoke tests still green.

#### 12. Routing + fallback orchestration
- **Do:** Implement `routing/router.py` (RoutingDecision: primary + chain + reason + estimated cost/latency), `routing/fallback.py` (parallel race with cancel-losers), `routing/latency_tracker.py`, `routing/cost_tracker.py`.
- **Verify:** Forced-timeout test: primary times out at 2s, fallback wins, RoutingEvent logged with reason.

#### 13. Backend health dashboard endpoint
- **Where:** New: `GET /api/backends/health`. JSON shape per spec §2.5.
- **Do:** Per-backend status, p95 latency, vram_used_gb (local) or cost-this-month (cloud), error_rate, last_check.
- **Verify:** Endpoint responds < 2s; AdminPanel renders the dashboard from it.

---

### TIER 4 — Phase 3 (Repo Cleanup, Jun 6–12)

Per `PHASE_3_IMPLEMENTATION_TASKS.md`. Final week before freeze.

#### 14. Archive dead code
- **Targets:**
  - `compat_shims/legacy_surfaces/` → `.archive/2026-06-XX_PHASE_3/`.
  - `compat_shims/launcher_ui/` → archive (web UI now primary).
  - `src/guppy/merlin/` → already deprecation-warned; archive after confirming zero imports.
  - `.quarantine/` README cleanup.
- **Verify:** `grep -r "from compat_shims.legacy_surfaces" src/` and `grep -r "from.*merlin" src/` both empty. `dev-check` passes.

#### 15. Module-size enforcement at <500 lines (down from current 700 cap)
- **Where:** `tools/check_new_module_line_cap.py`; current waivers on `launcher_window.py` (993), `server_runtime_snapshot.py` (789).
- **Do:** Drop the cap to 500 in stages. For each remaining waiver, decide: split further or document as intentional shell.
- **Verify:** Waiver list ≤ 2 files, each with explicit "intentional shell" justification.

#### 16. Documentation closeout
- **Where:** `README.md`, `docs/`.
- **Do:**
  - Add architecture diagram to README.md (CLAUDE.md known-issue list).
  - Create `docs/BACKENDS.md` (how to add a new backend).
  - Create `docs/AUDIO_PIPELINE.md` (TTS/STT architecture, troubleshooting).
  - Create `docs/AUDIO_ONLY_WORKSPACE.md` (user guide).
  - Update `docs/PROJECT_BRIEF.md` to final status.
- **Verify:** `python tools/check_doc_ownership.py` green; no stale references to retired modules.

---

### TIER 5 — Inline tech debt and stability extras

#### 17. Real TODO markers in source
- `src/guppy/api/routes_provider_management.py:60` — hardcoded timestamp `"2026-04-25T10:30:00Z"`. Replace with `datetime.now(timezone.utc).isoformat()`.
- `src/guppy/inference/_router_fragment_v2.py:163` — metrics table insert is `pass`. Implement with `inference_metrics` table (provider, model, task_type, latency_ms, success, cost, timestamp).

#### 18. Replace voice placeholder modules
- `src/guppy/voice/ppt.py` — currently a docstring saying "placeholder for the push-to-talk state machine." Implement real PTT state machine (state enum: IDLE/LISTENING/PROCESSING/SPEAKING, transitions, debounce).
- `src/guppy/voice/integration.py` — currently "placeholder for integration test utilities." Wire real cross-layer integration helpers used by the audio integration tests in TIER 2 #6.

#### 19. Web UI dead code + hooks
- `web/src/hooks/useApi.ts` has `useSettings` flagged as duplicate/dead in `ROADMAP_UPDATE_2026-04-27.md` Tech Debt — rename or delete.
- Fishbowl widget (`src/guppy/apps/fishbowl_app.py`) flagged untested E2E. Add a Playwright/Pytest-Qt smoke that opens the bowl, types into the input, and asserts a response.

#### 20. Chat stability hardening (per EXECUTION_PRIORITY_MATRIX critical path #2)
- Build queue + retry logic for in-flight requests during provider switch.
- Token refresh hooks that don't drop ongoing conversation.
- Error recovery banner + retry button in `web/src/views/AssistantView.tsx`.
- Test fallback chains: local timeout → cloud-tier1 → tier2.

#### 21. Credentials encryption at rest (T5)
- Currently ~40% complete per ROADMAP_UPDATE_2026-04-27. Wire Fernet encryption (already imported per SHIPPING_LOG) into the credential save path; migrate existing plaintext rows.

#### 22. Database silos consolidation
- Multiple route files create their own SQLite handles instead of going through Alembic-managed `guppy_main.db`. Consolidate or document the silo justification.

---

### TIER 6 — Optional / post-release

#### 23. Themes (Occult Dark, Rock Mag, Gonzo Dark)
- CSS files exist at repo root: `web_themes_gonzo-dark.css`, `web_themes_occult-dark.css`, `web_themes_rock-mag.css`.
- Move under `web/src/themes/`, register in theme picker, persist selection in Settings DB.
- WCAG AA contrast audit before ship.

#### 24. Router foundation (parallel track, post-release if time-tight)
- Per `EXECUTION_PRIORITY_MATRIX.md` critical path #3 + `GAP_ANALYSIS_AGENT_SPAWNING_2026-04-25.md`. Phase 1–5: provider abstraction → wire into chat → metrics dashboard → agent spawning → ML cost optimizer. Defer to v1.1 if Tiers 1–4 are not closed by June 5.

---

## Suggested execution order (1.5 FTE plan)

```
Apr 28 → May 1   (3 days)  : Tier 1 #1 (parity test) + #5 (commit waves) — UNBLOCK
May 1  → May 8   (1 week)  : Tier 1 #2 (button stubs) + #4 (auth) + Tier 5 #17–19 inline cleanup
May 8  → May 22  (2 weeks) : Tier 2 #6–8 (Phase 1 audio testing + audio-only workspace + telemetry)
May 23 → Jun 5   (2 weeks) : Tier 3 #10–13 (backend registry)
Jun 6  → Jun 10  (4 days)  : Tier 4 #14–16 (cleanup + docs) + Tier 1 #3 (real dist build) + Tier 5 #20–21 (chat stability + creds)
Jun 11 → Jun 12  (2 days)  : Final release-check, smoke, freeze
```

Stretch (post-release if room): Tier 5 #22, Tier 6.

---

## Verification protocol — run before every commit

```powershell
.venv\Scripts\activate
python tools/dev_workflow.py dev-check --guard-scope delta
python tools/dev_workflow.py test-fast
python tools/dev_workflow.py test-default
python tools/dev_workflow.py test-smoke
# Before any release branch:
python tools/dev_workflow.py release-check
```

Expected output of `release-check`: 8/8 gates green, machine-readable receipt under `.tmp/dev-workflow/reports/`.

If a gate fails, stop and fix before continuing — do not waiver-bypass without an entry added to the waiver list and a reason logged in this doc.

---

## What this doc does NOT cover

- Day-to-day persona/UX copy tweaks (handled in PR review).
- Stitch visual polish past PL-C2 (already shipped per PROJECT_BRIEF).
- Provider-specific onboarding flows past PL-C14 (already shipped).
- Anything in `docs/archive/` — historical only.
- Speculative router enhancements past Phase 1 (Tier 6 #24).

---

**Single source of truth:** When this doc and any other `.md` disagree, run the verify step on the relevant item. The repo state wins.
