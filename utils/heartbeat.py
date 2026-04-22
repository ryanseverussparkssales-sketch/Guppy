"""
utils/heartbeat.py — Agent Heartbeat Writer
============================================
Each agent calls start_heartbeat(agent_id) on startup.
A background thread writes a timestamp to runtime/<agent_id>.heartbeat
every INTERVAL seconds.

The Hub reads these files and flags any agent whose heartbeat is stale
(older than STALE_THRESHOLD seconds) as STALLED rather than merely RUNNING.

Usage:
    from utils.heartbeat import start_heartbeat, stop_heartbeat
    start_heartbeat("guppy")    # call once in __init__
    stop_heartbeat("guppy")     # call in closeEvent (optional — process death is enough)
"""

import time
import threading
import logging
from pathlib import Path

logger = logging.getLogger("Heartbeat")

INTERVAL        = 10   # seconds between writes
STALE_THRESHOLD = 30   # seconds before Hub considers agent stalled

_HERE    = Path(__file__).parent.parent          # Guppy root
_RUNTIME = _HERE / "runtime"
_RUNTIME.mkdir(exist_ok=True)

_threads: dict[str, threading.Event] = {}


def _heartbeat_loop(agent_id: str, stop_event: threading.Event) -> None:
    hb_path = _RUNTIME / f"{agent_id}.heartbeat"
    while not stop_event.wait(INTERVAL):
        try:
            hb_path.write_text(str(time.time()), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[{agent_id}] heartbeat write failed: {e}")
    # Clean up on exit
    try:
        hb_path.unlink(missing_ok=True)
    except Exception:
        pass
    logger.info(f"[{agent_id}] heartbeat stopped.")


def start_heartbeat(agent_id: str) -> None:
    """Start the heartbeat writer for this agent. Safe to call multiple times."""
    if agent_id in _threads:
        return  # already running
    stop_event = threading.Event()
    _threads[agent_id] = stop_event
    # Write immediately so Hub sees us right away
    try:
        (_RUNTIME / f"{agent_id}.heartbeat").write_text(str(time.time()), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[{agent_id}] initial heartbeat write failed: {e}")
    t = threading.Thread(target=_heartbeat_loop, args=(agent_id, stop_event), daemon=True)
    t.start()
    logger.info(f"[{agent_id}] heartbeat started (interval={INTERVAL}s).")


def stop_heartbeat(agent_id: str) -> None:
    """Stop the heartbeat writer for this agent."""
    ev = _threads.pop(agent_id, None)
    if ev:
        ev.set()


# ---------------------------------------------------------------------------
# Activity state writer
# ---------------------------------------------------------------------------
# Agents call write_activity(agent_id, "thinking"|"speaking"|"idle") to let
# the Hub display real-time activity without polling the process.

def write_activity(agent_id: str, state: str) -> None:
    """Write the current activity state to runtime/<agent_id>.activity."""
    act_path = _RUNTIME / f"{agent_id}.activity"
    try:
        act_path.write_text(state, encoding="utf-8")
    except Exception as e:
        logger.debug(f"[{agent_id}] activity write failed: {e}")


def clear_activity(agent_id: str) -> None:
    """Remove the activity file when agent exits."""
    act_path = _RUNTIME / f"{agent_id}.activity"
    try:
        act_path.unlink(missing_ok=True)
    except Exception:
        pass