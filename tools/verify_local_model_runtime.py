from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verify_ollama_runtime import *  # noqa: F401,F403
from tools.verify_ollama_runtime import _http_ping
from tools.verify_ollama_runtime import main


if __name__ == "__main__":
    raise SystemExit(main())
