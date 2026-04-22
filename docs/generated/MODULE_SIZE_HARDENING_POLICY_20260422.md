# Module Size Hardening Policy

Date: April 22, 2026

## Intent

This policy turns Guppy's module-size hardening guidance into an explicit repo rule:

- keep most live modules small enough to stay readable and moveable
- treat large modules as active debt before they become waiver-only hotspots
- keep the line-cap guard honest about the real live-code roots

## Size Bands

- `<=250` lines: ideal
- `251-400` lines: healthy
- `401-600` lines: review
- `601-700` lines: urgent
- `>700` lines: oversized and waiver-only

These bands are guidance for hardening and planning. The fail cap remains `700` lines unless a temporary explicit waiver exists.

## Guard Scope

`tools/check_new_module_line_cap.py` now enforces live-code size across:

- `src/guppy/`
- `ui/`
- `compat_shims/launcher_ui/ui/launcher/`
- `utils/`

The launcher compatibility tree is included because the live desktop shell currently runs there and must not drift outside the guard.

## Current Oversized Modules

As of this policy pass, the active oversized set is:

- `src/guppy/api/server_runtime_snapshot.py`
- `src/guppy/memory/memory_store.py`
- `compat_shims/launcher_ui/ui/launcher/launcher_window.py`

Each oversized file must either:

- shrink below `700`, or
- keep a pinned waiver at the current observed size with a narrow rationale

## Hardening Goal

The preferred dispersed end state is:

- wrappers and shims: `0-30` lines
- helpers, presenters, adapters: `80-180` lines
- most live modules: `180-300` lines
- dense orchestrators and domain modules: `300-450` lines

Anything above `450` lines should be considered a likely future split target even if it still passes the fail cap.

## Tranche Rule

Any tranche that touches a waived or urgent module should do one of the following:

- reduce the module measurably
- extract one coherent responsibility seam
- document the exact reason it could not shrink in that pass
