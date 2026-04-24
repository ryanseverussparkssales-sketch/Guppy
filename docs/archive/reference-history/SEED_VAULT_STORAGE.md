# Seed Vault Storage Plan

Last updated: April 12, 2026

This guide defines a practical path from USB backups now to NAS-backed storage later.

## Goals

1. Keep the assistant program and knowledge memory portable.
2. Preserve citation-quality memory data for cross-agent recall.
3. Keep restore operations simple and deterministic.

## Storage Topology

### Stage 1: USB Snapshot Backup (Now)

- Keep working copy on local machine.
- Write timestamped snapshots to an external USB path.
- Retain recent snapshots with manifest-based integrity metadata.

Example destination:

- `E:\GuppyBackups`

### Stage 2: NAS Snapshot Replication (Next)

- Use the same backup tool and point it at a NAS share path.
- Keep USB as secondary offline backup.
- Increase retention window for NAS snapshots.

Example destination:

- `\\NAS01\assistant\guppy`

## What Gets Backed Up

The backup includes:

1. Program surfaces and ops tooling (`tools`, `ui`, `utils`, `docs`, `bin`, `web`, `tests`).
2. Root launch/config files and markdown runbooks.
3. Knowledge stores and telemetry files used by memory and triage.
4. User-data memory/index stores when present:
   `guppy_memory.db`, `library.db`, semantic indexes, and MemPalace drawers under the Guppy user-data root.

## Run Commands

### USB snapshot

```powershell
python tools/backup_seed_vault.py --destination "E:\GuppyBackups" --retain 10
```

### NAS snapshot

```powershell
python tools/backup_seed_vault.py --destination "\\NAS01\assistant\guppy" --retain 30
```

### Batch wrapper (optional)

```powershell
bin\backup_seed_vault.bat --destination "E:\GuppyBackups" --retain 10
```

## Restore Approach

1. Pick snapshot folder under `snapshots/<timestamp>`.
2. Copy `data/` contents back into a clean working directory.
3. Restore user-data storage files under the Guppy user-data root if the snapshot includes them.
4. Verify key files exist: `runtime/ops_telemetry.sqlite3`, `runtime/router_scorecard.jsonl`, `docs/PROJECT_BRIEF.md`.
5. Run health checks:
  - `python tools/pilot_exit_check.py --allow-limited-go`
  - `python tools/verify_logging_health.py --emit-probe --require-fresh-core`

## Operational Notes

1. For sensitive media metadata, use encrypted USB/NAS volumes where possible.
2. Keep at least one offline copy disconnected from the machine.
3. Prefer nightly or end-of-day snapshots over ad-hoc manual copies.
