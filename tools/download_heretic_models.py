#!/usr/bin/env python3
"""
Download Heretic models from Hugging Face for llama.cpp inference.

Usage:
    python tools/download_heretic_models.py [--model-size small|medium|large|all]

Models downloaded:
    - Heretic 3B (ultra-fast fallback): ~2GB
    - Heretic 7B (fast): ~4GB
    - Heretic 9B (medium): ~5GB
    - Heretic 30B MoE (primary): ~18GB
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List


MODELS: Dict[str, Dict[str, str]] = {
    # Ultra-fast fallback (3B)
    "heretic-3b": {
        "repo": "TheBloke/Phi-3-mini-Heretic-GGUF",
        "file": "phi-3-mini-heretic.Q5_K_M.gguf",
        "size": "~2GB",
        "speed": "200-250 tok/s",
        "category": "small",
    },
    # Fast option (7B)
    "heretic-7b": {
        "repo": "TheBloke/Mistral-7B-Heretic-GGUF",
        "file": "mistral-7b-heretic.Q5_K_M.gguf",
        "size": "~4GB",
        "speed": "100-120 tok/s",
        "category": "small",
    },
    # Balanced option (9B)
    "heretic-9b": {
        "repo": "TheBloke/GLM-4-9B-Chat-Heretic-NEO-GGUF",
        "file": "glm-4-9b-chat-heretic-neo.Q5_K_M.gguf",
        "size": "~5GB",
        "speed": "80-100 tok/s",
        "category": "medium",
    },
    # Primary option (30B MoE)
    "heretic-30b-moe": {
        "repo": "TheBloke/GLM-4-9B-Chat-Heretic-NEO-GGUF",  # Placeholder (check actual repo)
        "file": "glm-4-9b-chat-heretic-neo-moe.Q4_K_M.gguf",
        "size": "~18GB",
        "speed": "40-50 tok/s",
        "category": "large",
    },
}


def get_model_dir() -> Path:
    """Get the models directory path."""
    guppy_root = Path(__file__).parent.parent
    models_dir = guppy_root / "local_backends" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


def check_huggingface_cli() -> bool:
    """Check if huggingface-hub CLI is installed."""
    try:
        import subprocess
        result = subprocess.run(
            ["huggingface-cli", "--version"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def download_model(model_key: str, model_info: Dict[str, str], models_dir: Path) -> bool:
    """
    Download a single model using huggingface-cli.

    Args:
        model_key: Model identifier
        model_info: Model metadata dict
        models_dir: Target directory

    Returns:
        True if download successful, False otherwise
    """
    import subprocess

    repo = model_info["repo"]
    file = model_info["file"]
    model_dir = models_dir / model_key

    print(f"\n{'='*60}")
    print(f"Downloading: {model_key}")
    print(f"  Repository: {repo}")
    print(f"  File: {file}")
    print(f"  Size: {model_info['size']}")
    print(f"  Expected Speed: {model_info['speed']}")
    print(f"  Target: {model_dir}")
    print(f"{'='*60}\n")

    try:
        cmd = [
            "huggingface-cli",
            "download",
            repo,
            file,
            "--local-dir",
            str(model_dir),
        ]

        result = subprocess.run(cmd, check=True)
        print(f"✓ Successfully downloaded {model_key}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to download {model_key}: {e}")
        return False
    except FileNotFoundError:
        print(f"✗ huggingface-cli not found. Install with:")
        print("  pip install huggingface-hub")
        return False


def list_models() -> None:
    """List all available models."""
    print("\nAvailable Heretic Models for llama.cpp:\n")

    for category in ["small", "medium", "large"]:
        print(f"\n{category.upper()} MODELS:")
        print("-" * 70)

        for model_key, info in MODELS.items():
            if info["category"] == category:
                print(f"  {model_key}")
                print(f"    Size: {info['size']}")
                print(f"    Speed: {info['speed']}")
                print(f"    Repo: {info['repo']}")
                print()


def download_all(models_dir: Path) -> None:
    """Download all models."""
    print("\nDownloading all Heretic models...")
    print(f"Target directory: {models_dir}\n")

    if not check_huggingface_cli():
        print("✗ huggingface-cli not installed")
        print("  Install with: pip install huggingface-hub")
        sys.exit(1)

    success_count = 0
    for model_key, model_info in MODELS.items():
        if download_model(model_key, model_info, models_dir):
            success_count += 1

    print(f"\n{'='*60}")
    print(f"Download Summary: {success_count}/{len(MODELS)} models")
    print(f"{'='*60}\n")


def download_by_size(size: str, models_dir: Path) -> None:
    """Download models by size category."""
    print(f"\nDownloading {size.upper()} Heretic models...")
    print(f"Target directory: {models_dir}\n")

    if not check_huggingface_cli():
        print("✗ huggingface-cli not installed")
        print("  Install with: pip install huggingface-hub")
        sys.exit(1)

    models_to_download = {
        k: v for k, v in MODELS.items()
        if v["category"] == size
    }

    success_count = 0
    for model_key, model_info in models_to_download.items():
        if download_model(model_key, model_info, models_dir):
            success_count += 1

    print(f"\n{'='*60}")
    print(f"Download Summary: {success_count}/{len(models_to_download)} models")
    print(f"{'='*60}\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download Heretic models for llama.cpp",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all available models
  python tools/download_heretic_models.py --list

  # Download only small models (3B, 7B)
  python tools/download_heretic_models.py --model-size small

  # Download all models
  python tools/download_heretic_models.py --model-size all
        """
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available models and exit"
    )

    parser.add_argument(
        "--model-size",
        choices=["small", "medium", "large", "all"],
        default="all",
        help="Model size category to download (default: all)"
    )

    args = parser.parse_args()

    if args.list:
        list_models()
        return

    models_dir = get_model_dir()

    if args.model_size == "all":
        download_all(models_dir)
    else:
        download_by_size(args.model_size, models_dir)


if __name__ == "__main__":
    main()
