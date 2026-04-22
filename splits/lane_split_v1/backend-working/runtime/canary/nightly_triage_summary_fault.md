# Nightly Triage Summary

Timestamp (UTC): 2026-04-13T02:40:44.910256+00:00
Pilot verdict: NO_GO
Overnight run result: ATTENTION

## Alerts
- pilot_verdict=NO_GO
- failed_gates=gate_1_core_runtime_stability, gate_5_provider_fallback_baseline
- stale_core_streams=session_events.jsonl
- offhours_failures=1

## Regression Signals
- regression: YES
- new_failures: gate_1_core_runtime_stability, gate_5_provider_fallback_baseline
- recovered: none

## Scorecard
- pilot_ready: False
- gate_failures: 2
- stale_core: 1
- offhours_failures: 1

## Suggested Morning Action
- Run targeted verifiers before full launch:
  - python tools/verify_logging_health.py --emit-probe --require-fresh-core
  - python tools/verify_ollama_runtime.py --prompt ok
  - python tools/verify_provider_runtime.py
