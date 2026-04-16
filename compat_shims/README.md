Compatibility shims and retired top-level helpers live here now.

The repo root intentionally keeps only the live daily entrypoints:
- `guppy_launcher.py`
- `guppy_api.py`
- `guppy_hub.py`

The working code should import canonical modules under `src.guppy.*`.
Files in this folder are retained only for fallback or manual compatibility
while older docs and references are cleaned up.

Historical desktop surfaces now live under `compat_shims/legacy_surfaces/`
instead of the repo root.
