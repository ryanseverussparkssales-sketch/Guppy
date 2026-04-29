"""
System monitoring tools — CPU, RAM, disk, processes, uptime.
Uses psutil (already a runtime dep).
"""
from __future__ import annotations

from typing import Any

import humanize
import psutil


def system_info() -> dict[str, Any]:
    """Return a snapshot of CPU, RAM, disk, and uptime."""
    import arrow

    cpu_pct = psutil.cpu_percent(interval=0.5)
    cpu_count = psutil.cpu_count(logical=True)
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    boot_time = psutil.boot_time()

    disks: list[dict] = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            disks.append({
                "mount": part.mountpoint,
                "device": part.device,
                "fstype": part.fstype,
                "total": humanize.naturalsize(usage.total),
                "used": humanize.naturalsize(usage.used),
                "free": humanize.naturalsize(usage.free),
                "percent": usage.percent,
            })
        except PermissionError:
            continue

    return {
        "cpu": {
            "percent": cpu_pct,
            "cores_logical": cpu_count,
            "cores_physical": psutil.cpu_count(logical=False),
        },
        "ram": {
            "total": humanize.naturalsize(mem.total),
            "used": humanize.naturalsize(mem.used),
            "available": humanize.naturalsize(mem.available),
            "percent": mem.percent,
        },
        "swap": {
            "total": humanize.naturalsize(swap.total),
            "used": humanize.naturalsize(swap.used),
            "percent": swap.percent,
        },
        "disks": disks,
        "uptime": arrow.get(boot_time).humanize(),
        "boot_time": arrow.get(boot_time).isoformat(),
    }


def top_processes(limit: int = 10, sort_by: str = "cpu") -> list[dict[str, Any]]:
    """Return top N processes sorted by CPU or memory usage."""
    sort_key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    procs: list[dict] = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
        try:
            info = proc.info
            procs.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": round(info["cpu_percent"] or 0, 1),
                "memory_percent": round(info["memory_percent"] or 0, 2),
                "status": info["status"],
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return sorted(procs, key=lambda p: p[sort_key], reverse=True)[:limit]


def disk_usage(path: str = "/") -> dict[str, Any]:
    """Return disk usage for a specific path."""
    usage = psutil.disk_usage(path)
    return {
        "path": path,
        "total": humanize.naturalsize(usage.total),
        "used": humanize.naturalsize(usage.used),
        "free": humanize.naturalsize(usage.free),
        "percent": usage.percent,
    }


def network_stats() -> dict[str, Any]:
    """Return network I/O counters since boot."""
    net = psutil.net_io_counters()
    return {
        "bytes_sent": humanize.naturalsize(net.bytes_sent),
        "bytes_recv": humanize.naturalsize(net.bytes_recv),
        "packets_sent": humanize.intcomma(net.packets_sent),
        "packets_recv": humanize.intcomma(net.packets_recv),
        "errin": net.errin,
        "errout": net.errout,
    }
