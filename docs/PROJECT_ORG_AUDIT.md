# Project Organization Audit

## Benchmark Used
Compared against common professional Python application layouts used by:
- Desktop/CLI hybrid apps
- FastAPI services
- Mid-size internal tooling repos

## Gaps Found
1. Missing standardized project tooling config (`pyproject.toml`)
2. Missing environment template (`.env.example`)
3. Missing contributor workflow guide (`CONTRIBUTING.md`)
4. README referenced docs that did not exist (`docs/API.md`, `docs/TROUBLESHOOTING.md`)

## Fixes Applied
1. Added `pyproject.toml` with pytest + Ruff defaults
2. Added `.env.example` for all discovered runtime environment variables
3. Added `CONTRIBUTING.md` with setup, run, test, and PR checklist
4. Added `docs/API.md` and `docs/TROUBLESHOOTING.md`

## Recommended Next Structural Step (Optional, Non-breaking)
- Introduce `src/` package layout gradually:
  - New modules under `src/guppy/`
  - Keep current top-level entrypoints as thin wrappers
- This improves import hygiene and packaging readiness without disrupting existing launch scripts.
