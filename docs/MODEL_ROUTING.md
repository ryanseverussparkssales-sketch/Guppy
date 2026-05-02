# Guppy — Model Routing

**Last updated:** 2026-05-03

---

## Always-On Stack (llama.cpp ROCm/HIP)

Managed by the watchdog in `routes_backends.py` — auto-restarted on crash.

| Role | Key | Port | Model | VRAM |
|------|-----|------|-------|------|
| Embedding server | `llamacpp-nomic-embed` | 8092 | nomic-embed-text-v1.5 | ~1 GB |
| Orchestrator / session summarizer | `llamacpp-phi4-mini` | 8091 | Phi-4-mini-instruct Q4_K_M | ~2.5 GB |
| Companion watchdog fallback | `llamacpp-hermes3` | 8087 | Hermes 3 8B Lorablated Q8_0 | ~9 GB |
| Workspace / codespace reasoning + tools | `llamacpp-hermes4` | 8086 | Hermes 4 14B Q5_K_M | ~11 GB |
| Lightweight router | `llamacpp-dispatch` | 8085 | Qwen2.5-3B Q4_K_M | ~2 GB |

**Total always-on VRAM:** ~25.5 GB

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
| Dispatcher fallback | `llamacpp-dispatch` | 8085 | Qwen2.5-3B Q4_K_M | ~2 GB | Lightweight router |

---

## Surface-Locked Routing

`_get_surface_local_model()` in `routes_realtime.py` reads `surface_config` from `guppy_main.db`. The cascade in `router_surface.py` tries models in order, falling through on 0-token responses.

| Surface | Primary model | Fallback |
|---------|--------------|---------|
| `companion` | `llamacpp-rocinante` (port 8088) | hermes3 (8087) → Haiku |
| `workspace` | `llamacpp-hermes4` (port 8086) | phi4-mini/dispatch (small-ctx) → Sonnet |
| `codespace` | `llamacpp-hermes4` (port 8086) | hermes3 (8087) → Sonnet |

User override always wins. Rocinante is the companion **primary** but not watchdog-managed — Hermes3 is the always-on fallback for companion.

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

- **KV cache auto-warming:** `_warm_kv_cache(port)` sends 1-token prefill to Rocinante (8088), Hermes3 (8087), and Hermes4 (8086) on first confirmed liveness
- Re-warms after watchdog crash+restart
- Reduces first-response latency ~30–50%

---

## Tool Call Grammar

- `_TOOL_CALL_GBNF` constant — GBNF grammar passed as `grammar` param to llamacpp to constrain JSON
- `_repair_tool_json()` — trailing-comma / unclosed-brace repair applied at all three tool-call parse sites
- Grammar constraint active in: companion `/chat`, workspace `/chat`, workspace task executor

---

## Voice Fast-Path

- `is_voice=True` on `ChatRequest` routes voice transcripts to the companion surface model (Rocinante, or Hermes3 fallback)
- Bypasses heavier model selection for low-latency voice responses
