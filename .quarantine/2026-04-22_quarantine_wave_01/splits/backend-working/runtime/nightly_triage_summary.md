# Nightly Triage Summary

Timestamp (UTC): 2026-04-18T18:10:41.323018+00:00
Pilot verdict: UNKNOWN
Overnight run result: UNKNOWN

## Alerts
- pilot_verdict=UNKNOWN

## Regression Signals
- regression: NO
- new_failures: none
- recovered: gate_2_local_model_fleet_ready

## Scorecard
- pilot_ready: False
- gate_failures: 0
- stale_core: 0
- offhours_failures: 0

## Suggested Morning Action
- Run targeted verifiers before full launch:
  - python tools/verify_logging_health.py --emit-probe --require-fresh-core
  - python tools/verify_ollama_runtime.py --prompt ok
  - python tools/verify_provider_runtime.py
