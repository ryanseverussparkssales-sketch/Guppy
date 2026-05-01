# Archived Deprecated Modules

These modules were removed from the active codebase but preserved here for reference.

## merlin/

Old "Merlin" specialist/tutor architecture — predates the three-surface design.
Was emitting `DeprecationWarning` on import; no active code referenced it.
Archived 2026-05-01.

## compat_launcher_ui/

Old Qt desktop launcher UI (`launcher_app.py` + 90 view/component files).
The desktop launcher was re-architected as a thin wrapper that spawns the
FastAPI server and opens a browser window; all UI lives in the React web UI.
Archived 2026-05-01.
