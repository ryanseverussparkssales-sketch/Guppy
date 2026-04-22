"""Status/settings summary card for hub window."""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

from .theme_config import ACNT, BG2, DIM, TEXT


class StatusSettingsCard(QFrame):
    _REMOTE_CHECK_INTERVAL = 5

    def __init__(
        self,
        load_app_settings_fn,
        recommend_runtime_profile_fn,
        check_api_server_fn,
        check_cloudflared_fn,
        check_auth_config_fn,
        cloudflare_cert_paths_fn,
        is_set_fn,
        safe_int_fn,
        parent=None,
    ):
        super().__init__(parent)
        self._load_app_settings = load_app_settings_fn
        self._recommend_runtime_profile = recommend_runtime_profile_fn
        self._check_api_server = check_api_server_fn
        self._check_cloudflared = check_cloudflared_fn
        self._check_auth_config = check_auth_config_fn
        self._cloudflare_cert_paths = cloudflare_cert_paths_fn
        self._is_set = is_set_fn
        self._safe_int = safe_int_fn

        self.setObjectName("StatusSettingsCard")
        self._refresh_counter = 0
        self._remote_cache = ("DOWN", "STOPPED", "DEV MODE")
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(2)

        title = QLabel("SYSTEM STATUS / SETTINGS")
        title.setStyleSheet(f"color:{ACNT}; background:transparent; border:none;")
        title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lay.addWidget(title)

        self._accounts_lbl = QLabel("")
        self._accounts_lbl.setStyleSheet(f"color:{TEXT}; background:transparent; border:none;")
        self._accounts_lbl.setFont(QFont("Consolas", 7))
        self._accounts_lbl.setWordWrap(True)
        lay.addWidget(self._accounts_lbl)

        self._remote_lbl = QLabel("")
        self._remote_lbl.setStyleSheet(f"color:{TEXT}; background:transparent; border:none;")
        self._remote_lbl.setFont(QFont("Consolas", 7))
        self._remote_lbl.setWordWrap(True)
        lay.addWidget(self._remote_lbl)

        self._settings_lbl = QLabel("")
        self._settings_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._settings_lbl.setFont(QFont("Consolas", 7))
        self._settings_lbl.setWordWrap(True)
        lay.addWidget(self._settings_lbl)

        self._profile_lbl = QLabel("")
        self._profile_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._profile_lbl.setFont(QFont("Consolas", 7))
        self._profile_lbl.setWordWrap(True)
        lay.addWidget(self._profile_lbl)

        self._recommend_lbl = QLabel("")
        self._recommend_lbl.setStyleSheet(f"color:{DIM}; background:transparent; border:none;")
        self._recommend_lbl.setFont(QFont("Consolas", 7))
        self._recommend_lbl.setWordWrap(True)
        lay.addWidget(self._recommend_lbl)

        self.setStyleSheet(
            f"StatusSettingsCard{{background:{BG2};"
            f"border:1px solid {ACNT}33;border-radius:6px;}}"
        )
        self.refresh()

    def refresh(self):
        settings = self._load_app_settings()
        rec = self._recommend_runtime_profile()

        gmail_creds = os.environ.get("GMAIL_CREDENTIALS_PATH", "").strip()
        gmail_ok = bool(gmail_creds and Path(gmail_creds).exists())
        cf_ok = any(p.exists() for p in self._cloudflare_cert_paths())

        try:
            from kokoro import KPipeline as _KP  # noqa: F401
            tts_backend = "KOKORO"
        except Exception:
            tts_backend = "SAPI"

        try:
            from faster_whisper import WhisperModel as _WM  # noqa: F401
            stt_backend = "WHISPER"
        except Exception:
            try:
                import speech_recognition as _sr  # noqa: F401
                stt_backend = "GOOGLE"
            except Exception:
                stt_backend = "NONE"

        accounts = [
            f"Claude: {'READY' if self._is_set('ANTHROPIC_API_KEY') else 'MISSING'}",
            f"Spotify: {'READY' if (self._is_set('SPOTIFY_CLIENT_ID') and self._is_set('SPOTIFY_CLIENT_SECRET')) else 'MISSING'}",
            f"Gmail Creds: {'READY' if gmail_ok else 'MISSING'}",
            f"Cloudflare Cert: {'READY' if cf_ok else 'MISSING'}",
            f"Voice TTS: {tts_backend}",
            f"Voice STT: {stt_backend}",
        ]
        self._accounts_lbl.setText(" | ".join(accounts))

        self._refresh_counter += 1
        if self._refresh_counter >= self._REMOTE_CHECK_INTERVAL:
            self._refresh_counter = 0
            api_state = self._check_api_server()
            tunnel_state = self._check_cloudflared()
            auth_state = self._check_auth_config()
            self._remote_cache = (api_state, tunnel_state, auth_state)
        else:
            api_state, tunnel_state, auth_state = self._remote_cache

        remote = [
            f"API Server: {api_state}",
            f"CF Tunnel: {tunnel_state}",
            f"Auth: {auth_state}",
        ]
        self._remote_lbl.setText(" | ".join(remote))

        model_settings_lines = [
            f"ANTHROPIC_MODEL={os.environ.get('ANTHROPIC_MODEL', 'claude-sonnet-4-6')}",
            f"ANTHROPIC_BACKUP_MODEL={os.environ.get('ANTHROPIC_BACKUP_MODEL', 'claude-haiku-4-5-20251001')}",
            f"OLLAMA_MODEL={os.environ.get('OLLAMA_MODEL', 'guppy')}",
            f"GUPPY_LOCAL_CODE_MODEL={os.environ.get('GUPPY_LOCAL_CODE_MODEL', 'guppy-code')}",
            f"GUPPY_LOCAL_VAULT_MODEL={os.environ.get('GUPPY_LOCAL_VAULT_MODEL', 'vault-scraper')}",
            f"GUPPY_RUNTIME_PROFILE={os.environ.get('GUPPY_RUNTIME_PROFILE', 'standard')}",
        ]
        self._settings_lbl.setText(" | ".join(model_settings_lines))
        self._profile_lbl.setText(
            " | ".join(
                [
                    f"PROFILE={str(settings.get('runtime_profile', 'standard')).upper()}",
                    f"DAEMON={'ON' if settings.get('enable_daemon', True) else 'OFF'}",
                ]
            )
        )
        self._recommend_lbl.setText(
            f"RECOMMEND={str(rec.get('profile', 'standard')).upper()} | CPU={rec.get('cpu_percent', 0)}% | "
            f"RAM={rec.get('available_ram_gb', 0)}/{rec.get('total_ram_gb', 0)}GB | OLLAMA={'READY' if rec.get('ollama_ready') else 'DOWN'}"
        )
