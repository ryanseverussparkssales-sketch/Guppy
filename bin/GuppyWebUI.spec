# -*- mode: python ; coding: utf-8 -*-
#
# GuppyWebUI.spec — PyInstaller spec for the web-UI-first distribution.
#
# Entry point : guppy_webui.py  (project root)
# Output      : dist/GuppyWebUI/GuppyWebUI.exe  (onedir)
#
# What's bundled:
#   • FastAPI + uvicorn server (src.guppy.api.*)
#   • Pre-built React UI (static/)
#   • Config data (config/)
#   • Runtime registry (runtime/launcher_registry.json)
#   • utils/ helpers
#
# What's NOT bundled (runtime deps the user installs separately):
#   • Ollama / llama.cpp model servers
#   • faster_whisper / torch (STT — runtime-optional)
#   • PySide6 / Qt (legacy desktop surface — not used by web UI)

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).parent  # project root (bin/../)

# ── Collect dynamic-import-heavy packages ────────────────────────────────────
uvicorn_datas, uvicorn_binaries, uvicorn_hiddenimports = collect_all("uvicorn")
fastapi_datas, fastapi_binaries, fastapi_hiddenimports = collect_all("fastapi")
starlette_datas, starlette_binaries, starlette_hiddenimports = collect_all("starlette")
anyio_datas, anyio_binaries, anyio_hiddenimports = collect_all("anyio")

# ── Data files ────────────────────────────────────────────────────────────────
added_datas = [
    # Pre-built React UI
    (str(ROOT / "static"), "static"),
    # Server config (instances.json, booklet.json, etc.)
    (str(ROOT / "config"), "config"),
    # Runtime registry (launcher_registry.json)
    (str(ROOT / "runtime" / "launcher_registry.json"), "runtime"),
    # utils package (env_bootstrap, db_utils, secret_store, …)
    (str(ROOT / "utils"), "utils"),
    # Collected package data
    *uvicorn_datas,
    *fastapi_datas,
    *starlette_datas,
    *anyio_datas,
]

# ── Hidden imports ────────────────────────────────────────────────────────────
hidden = [
    # uvicorn / fastapi / starlette internals
    *uvicorn_hiddenimports,
    *fastapi_hiddenimports,
    *starlette_hiddenimports,
    *anyio_hiddenimports,
    # jose (JWT)
    "jose",
    "jose.jwt",
    "jose.exceptions",
    "jose.backends",
    "jose.backends.cryptography_backend",
    "jose.constants",
    # cryptography (jose dependency)
    "cryptography",
    "cryptography.hazmat.primitives.asymmetric",
    "cryptography.hazmat.primitives.asymmetric.rsa",
    "cryptography.hazmat.primitives.ciphers",
    "cryptography.hazmat.primitives.hashes",
    "cryptography.hazmat.backends",
    "cryptography.hazmat.backends.openssl",
    # python-multipart (FastAPI form/file uploads)
    "multipart",
    # httpx
    "httpx",
    "httpx._transports.default",
    # openai + anthropic (cloud inference — optional but imported conditionally)
    "openai",
    "anthropic",
    # sqlalchemy (ORM)
    "sqlalchemy",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.orm",
    "sqlalchemy.ext.declarative",
    # alembic (migrations)
    "alembic",
    "alembic.config",
    "alembic.runtime.migration",
    # pydantic / pydantic-settings
    "pydantic",
    "pydantic_settings",
    "pydantic.v1",
    # rich (CLI output)
    "rich",
    "rich.console",
    "rich.text",
    # loguru
    "loguru",
    # guppy source modules — only include API-critical paths.
    # Voice, inference, and launcher_application have heavy optional deps
    # (transformers, spacy, etc.) that inflate the bundle; they degrade
    # gracefully behind try/except when absent.
    *collect_submodules("src.guppy.api"),
    *collect_submodules("src.guppy.memory"),
    *collect_submodules("src.guppy.experience_config"),
    *collect_submodules("src.guppy.paths"),
    *collect_submodules("src.guppy.daemon"),
    # Windows keyring (secret store)
    "keyring",
    "keyring.backends",
    "keyring.backends.Windows",
    # email / MIME (stdlib — sometimes missed)
    "email.mime.text",
    "email.mime.multipart",
]

# ── Analysis ──────────────────────────────────────────────────────────────────
a = Analysis(
    [str(ROOT / "guppy_webui.py")],
    pathex=[str(ROOT)],
    binaries=[*uvicorn_binaries, *fastapi_binaries, *starlette_binaries, *anyio_binaries],
    datas=added_datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ── Heavy ML / desktop — NOT needed to start the web server ──────────
        "PySide6", "PyQt5", "PyQt6", "tkinter",
        # PyTorch family
        "torch", "torchvision", "torchaudio", "functorch",
        # STT/audio (runtime-optional, huge)
        "faster_whisper", "whisper", "speech_recognition",
        "sounddevice", "soundfile",
        # HuggingFace / NLP
        "transformers", "tokenizers", "huggingface_hub", "hf_xet",
        "datasets", "evaluate",
        # spaCy + thinc + blis
        "spacy", "thinc", "blis", "srsly", "cymem", "preshed", "wasabi",
        "murmurhash", "confection", "catalogue",
        # Data / science
        "numpy", "scipy", "sklearn", "scikit_learn", "pandas",
        "pyarrow", "polars", "dask",
        # Vision
        "PIL", "Pillow", "cv2", "skimage",
        # ONNX / ML inference
        "onnxruntime", "onnx", "openvino",
        # Audio/video processing
        "av", "librosa", "audioread", "resampy",
        # Google APIs (pulled in by google-genai etc.)
        "googleapiclient", "google.api_core", "google.cloud",
        "google.generativeai", "google.genai",
        # gRPC
        "grpc", "grpcio",
        # AWS
        "botocore", "boto3", "s3transfer",
        # Jupyter / notebook
        "jupyter", "IPython", "notebook", "ipykernel", "ipywidgets",
        # Plotting
        "matplotlib", "plotly", "seaborn",
        # DB engines (only sqlite needed)
        "psycopg2", "psycopg", "pymysql", "cx_Oracle", "asyncpg",
        # TensorFlow / Keras (not used at all)
        "tensorflow", "keras", "jax",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GuppyWebUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,       # keep console so startup errors are visible
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='bin/guppy.ico',  # uncomment if you add an icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="GuppyWebUI",
)
