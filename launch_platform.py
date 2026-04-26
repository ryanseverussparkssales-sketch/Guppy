"""Guppy Launcher Platform — unified service control UI.

Opens a local web interface at http://127.0.0.1:8082/ where you can:
  - Start, stop, restart, and reset any Guppy service
  - View real-time health and latency for all services
  - Tail service logs with colour-coded error highlighting
  - Inspect environment, port states, and recent errors

Usage:
    python launch_platform.py [--host HOST] [--port PORT] [--no-browser]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.guppy.launcher_platform.server import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Guppy Launcher Platform")
    parser.add_argument("--host",       default="127.0.0.1")
    parser.add_argument("--port",       type=int, default=8082)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    run(host=args.host, port=args.port, open_browser=not args.no_browser)
