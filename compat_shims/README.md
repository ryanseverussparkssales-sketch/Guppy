Historical compatibility material lives here now.

The repo root intentionally keeps only the live daily entrypoints:
- `guppy_launcher.py`
- `guppy_api.py`
- `guppy_hub.py`

The working code should import canonical modules under `src.guppy.*`.
Repo-supported desktop/runtime paths no longer depend on the old non-UI shim
aliases that previously lived here.

Historical desktop surfaces now live under `compat_shims/legacy_surfaces/`
instead of the repo root.
