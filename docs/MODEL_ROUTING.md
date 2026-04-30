# Guppy — Model Routing

**Last updated:** 2026-04-30 (Tranches 0–I complete)

---

## Always-On Stack (llama.cpp ROCm/HIP)

| Role | Key | Port | Model | VRAM |
|------|-----|------|-------|------|
| Orchestrator / session summarizer | `llamacpp-dispatch` | 8085 | Qwen2.5-3B Q4_K_M | ~2 GB |
| Companion fast chat + tools | `llamacpp-hermes3` | 8087 | Hermes 3 8B Lorablated Q8_0 | ~9 GB |
| Workspace / codespace reasoning + tools | `llamacpp-hermes4` | 8086 | Hermes 4 14B Q5_K_M | ~11 GB |

**Total always-on VRAM:** ~22 GB

---

## On-Demand Models

| Role | Key | Port | Model | VRAM | Notes |
|------|-----|------|-------|------|-------|
| Tool-call specialist | `llamacpp-xlam` | 8089 | xLAM-2-8B-fc-r Q4_K_M | ~5 GB | #1 BFCL ≤8B |
| Vision | `llamacpp-gemma` | 8080 | Gemma 4 E4B Heretic ARA | ~8.5 GB | PLE issue — degraded output |
| Fast chat Mode A | `llamacpp-pepe` | 8082 | Assistant Pepe 8B Q8_0 | ~8.5 GB | |
| Reasoning Mode B | `llamacpp-qwen3` | 8083 | Qwen3 35B-A3B MoE | ~19 GB | Solo only |
| Vision+speech | `llamacpp-minicpm` | 8084 | MiniCPM-o 4.5 Omni | ~9 GB | Needs mmproj |
| Creative/roleplay | `llamacpp-rocinante` | 8088 | Rocinante X 12B Q5_K_M | ~10 GB | |
| CPU flagship | `llamacpp-chat` | 8090 | Llama 3.3 70B Q4_K_M | 0 VRAM (~42 GB RAM) | ~4-6 tok/s |
| JSON tool_call orchestrator | `llamacpp-phi4-mini` | 8091 | Phi-4-mini-instruct Q4_K_M | ~2.5 GB | Model file needed |

---

## Surface-Locked Routing

`_get_surface_local_model()` in `routes_realtime.py` reads `surface_config` from `guppy_main.db`:

| Surface | Default local model |
|---------|-------------------|
| `companion` | `llamacpp-hermes3` (port 8087) |
| `workspace` | `llamacpp-hermes4` (port 8086) |
| `codespace` | `llamacpp-hermes4` (port 8086) |

User override always wins over surface default.

---

## Cloud Fallback

`_get_surface_cloud_model()` in `routes_realtime.py`:

| Surface | Cloud model |
|---------|-------------|
| `companion` | Claude Haiku |
| `workspace` | Claude Sonnet |
| `codespace` | Claude Sonnet |

**Strict-local mode:** if local model port is offline, returns honest error instead of silent cloud escalation (companion surface only).

---

## Warm Policy

- **KV cache auto-warming:** `_warm_kv_cache(port)` sends 1-token prefill to Hermes3 (8087) and Hermes4 (8086) on first confirmed liveness
- Re-warms after watchdog crash+restart
- Reduces first-response latency ~30–50%

---

## Tool Call Grammar

- `_TOOL_CALL_GBNF` constant — GBNF grammar passed as `grammar` param to llamacpp to constrain JSON
- `_repair_tool_json()` — trailing-comma / unclosed-brace repair applied at all three tool-call parse sites
- Grammar constraint active in: companion `/chat`, workspace `/chat`, workspace task executor

---

## Voice Fast-Path

- `is_voice=True` on `ChatRequest` routes voice transcripts to Hermes3 on companion surface
- Bypasses heavier model selection for low-latency voice responses
