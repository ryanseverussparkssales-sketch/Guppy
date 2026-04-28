#!/usr/bin/env python3
"""
Run STT provider tests and report results.
This script is designed to work around bytecode caching issues.
"""

import subprocess
import sys
import os

def clear_cache():
    """Clear Python bytecode cache."""
    import shutil
    cache_dirs = [
        "tests/unit/__pycache__",
        "src/guppy/voice/__pycache__",
        "src/guppy/voice/stt/__pycache__",
    ]
    for d in cache_dirs:
        if os.path.isdir(d):
            shutil.rmtree(d, ignore_errors=True)
            print(f"Cleared {d}")

def run_tests():
    """Run pytest with fresh bytecode."""
    cmd = [
        sys.executable,
        "-B",  # Don't write bytecode
        "-m", "pytest",
        "tests/unit/test_stt_providers.py",
        "-v",
        "--tb=short",
        "--no-header",
    ]

    print("\n" + "="*70)
    print("Running STT Provider Tests")
    print("="*70 + "\n")

    result = subprocess.run(cmd, cwd=os.getcwd())
    return result.returncode

if __name__ == "__main__":
    clear_cache()
    sys.exit(run_tests())
