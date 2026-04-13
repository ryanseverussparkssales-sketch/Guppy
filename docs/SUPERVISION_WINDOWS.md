# Windows Supervision Model

Use an external supervisor for API and background processes.
Do not rely on FastAPI app startup hooks to manage daemon lifecycle.

## Recommended Pattern

- API process: supervised independently.
- Daemon/background services: supervised independently.
- UI processes: user-launched, not service-managed.

The API now defaults to supervised mode:

- `GUPPY_API_OWNS_DAEMON=0`
- `GUPPY_API_RELOAD=0`

## Quick Start (Task Scheduler)

Create a startup task that runs:

- Program/script: `cmd.exe`
- Arguments: `/c C:\Users\Ryan\Guppy\bin\launch_api_supervised.bat`
- Start in: `C:\Users\Ryan\Guppy`

Enable these task settings:

- Run whether user is logged on or not
- Restart every 1 minute, up to 3 attempts
- Stop task if running longer than disabled

## NSSM Example

```powershell
nssm install GuppyApi "C:\Users\Ryan\Guppy\bin\launch_api_supervised.bat"
nssm set GuppyApi AppDirectory "C:\Users\Ryan\Guppy"
nssm set GuppyApi AppStdout "C:\Users\Ryan\Guppy\runtime\api-supervisor.out.log"
nssm set GuppyApi AppStderr "C:\Users\Ryan\Guppy\runtime\api-supervisor.err.log"
nssm start GuppyApi
```

## Notes

- Keep `GUPPY_DEV_MODE=0` in production.
- Keep telemetry enabled with `GUPPY_TELEMETRY_BACKEND=sqlite+jsonl`.
- Keep low-power defaults in runtime profiles unless profiling proves headroom.
