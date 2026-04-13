# Nightly Triage Summary

Timestamp (UTC): 2026-04-13T02:35:36.072431+00:00
Pilot verdict: NO_GO
Overnight run result: ATTENTION

## Alerts
- pilot_verdict=NO_GO
- failed_gates=gate_1_core_runtime_stability, gate_5_provider_fallback_baseline

## Regression Signals
- regression: YES
- new_failures: gate_1_core_runtime_stability, gate_5_provider_fallback_baseline
- recovered: none

## Scorecard
- pilot_ready: False
- gate_failures: 2
- stale_core: 0
- offhours_failures: 0

## Suggested Morning Action
- Run targeted verifiers before full launch:
  - python tools/verify_logging_health.py --emit-probe --require-fresh-core
  - python tools/verify_ollama_runtime.py --prompt ok
  - python tools/verify_provider_runtime.py
