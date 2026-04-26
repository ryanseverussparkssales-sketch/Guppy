"""Guppy Desktop — native window wrapping the Guppy web UI.

Starts the API server if needed, then loads http://localhost:8081
in a QWebEngineView for a native desktop experience.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.guppy.apps.desktop_app import main
if __name__ == "__main__":
    main()
