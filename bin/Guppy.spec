# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT = Path(__file__).resolve().parents[1]

LEAN_BUILD = os.environ.get("GUPPY_LEAN_BUILD", "0").strip().lower() in {"1", "true", "yes", "on"}

datas = [
    (str(ROOT / 'src' / 'guppy' / 'ui' / 'theme.json'), 'src/guppy/ui'),
    (str(ROOT / 'config' / 'local_llm'), 'config/local_llm'),
    (str(ROOT / 'utils'), 'utils'),
    (str(ROOT / 'ui'), 'ui'),
]
binaries = []
hiddenimports = [
    'anthropic',
    'win32com.client',
    'win11toast',
    'sounddevice',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'PySide6.QtCharts',
    'src.guppy.memory.semantic',
    'src.guppy.daemon.daemon',
    'src.guppy.memory.memory',
    'src.guppy.merlin.core',
    'src.guppy.inference.router',
    'src.guppy.tools.media',
    'src.guppy.integrations.crm_voip',
    'utils.hub_operator',
    'utils.agent_perf',
    'utils.session_logger',
    'utils.env_bootstrap',
    'utils.heartbeat',
    'utils.telemetry_window',
    'utils.diagnostics_bundle',
    'ui.components.status_strip',
    'ui.components.timeline_panel',
    'ui.components.startup_checklist',
    'ui.components.sparkline',
    'ui.components.command_palette',
    'ui.launcher',
    'ui.launcher.launcher_window',
    'ui.launcher.views.assistant_view',
    'ui.launcher.views.tools_view',
    'ui.launcher.views.settings_view',
    'ui.launcher.views.advanced_view',
    'ui.launcher.views.models_view',
    'ui.launcher.views.voices_view',
    'src.guppy.debug.console',
    'src.guppy.ui.theme',
    'psutil',
    'pyperclip',
    'keyboard',
    'requests',
    'apscheduler',
    'spotipy',
    'google.auth',
    'google.oauth2',
    'googleapiclient',
]
if not LEAN_BUILD:
    hiddenimports.extend(['soundfile', 'edge_tts', 'faster_whisper'])
if LEAN_BUILD:
    # Lean profile: skip optional heavy ML stacks that are not required for core UI startup.
    excludes = [
        'tensorflow',
        'torch',
        'sklearn',
        'scipy',
        'pandas',
        'transformers',
        'numba',
        'pyarrow',
        'nltk',
        'langchain',
        'onnxruntime',
    ]
else:
    excludes = []
tmp_ret = collect_all('anthropic')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
if not LEAN_BUILD:
    tmp_ret = collect_all('faster_whisper')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['guppy_launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Guppy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ROOT / 'assets' / 'desktop' / 'guppy_launcher_icon.ico'),
)
