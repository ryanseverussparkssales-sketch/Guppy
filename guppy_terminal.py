"""Guppy Terminal — command-line chat interface to the LLM stack.

Requires the Guppy API to be running (python guppy_api.py or launch_platform.py).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.guppy.cli.terminal_chat import main
if __name__ == "__main__":
    main()
