from __future__ import annotations

import atexit
import os
from dataclasses import dataclass
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]


@dataclass
class ProcessGuard:
    path: Path
    fd: int
    released: bool = False

    def release(self) -> None:
        if self.released:
            return
        self.released = True
        try:
            os.close(self.fd)
        except OSError:
            pass
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


def _pid_matches(pid: int, markers: tuple[str, ...]) -> bool:
    if pid <= 0:
        return False
    if psutil is None:
        return True
    try:
        if not psutil.pid_exists(pid):
            return False
        process = psutil.Process(pid)
        command_line = " ".join(process.cmdline()).lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError, ValueError):
        return False
    return any(marker.lower() in command_line for marker in markers)


def acquire_process_guard(path: Path, *, process_markers: tuple[str, ...]) -> ProcessGuard | None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    for _ in range(2):
        try:
            fd = os.open(str(path), flags)
        except FileExistsError:
            try:
                pid = int(path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                pid = 0
            if _pid_matches(pid, process_markers):
                return None
            try:
                path.unlink(missing_ok=True)
            except OSError:
                return None
            continue
        os.write(fd, f"{os.getpid()}\n".encode("ascii"))
        guard = ProcessGuard(path=path, fd=fd)
        atexit.register(guard.release)
        return guard
    return None
