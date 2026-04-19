import json
import os
import socket
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    from utils.safe_io import write_json_atomic
    _ATOMIC_IO = True
except Exception:
    _ATOMIC_IO = False

    def write_json_atomic(_path, _data):
        return False

try:
    import psutil
    PSUTIL_OK = True
except Exception:
    PSUTIL_OK = False


ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT / "runtime"
SETTINGS_PATH = RUNTIME_DIR / "app_settings.json"


DEFAULT_SETTINGS = {
    "runtime_profile": "standard",
    "enable_daemon": True,
    "enable_voice": True,
    "wake_word_default": False,
    "default_mode": "auto",
    "local_runtime_backend": "ollama",
    "lemonade_base_url": "http://localhost:13305/api/v1",
    "lemonade_fast_model": "",
    "lemonade_complex_model": "",
    "lemonade_teach_model": "",
    "lemonade_code_model": "",
    "lemonade_vault_model": "",
    "local_main_model": "",
    "local_sub_model_a": "",
    "local_sub_model_b": "",
}


PROFILE_PRESETS = {
    "light": {
        "runtime_profile": "light",
        "enable_daemon": False,
        "enable_voice": True,
        "wake_word_default": False,
        "default_mode": "local",
        "env_defaults": {
            "GUPPY_TOOL_BUDGET": "4",
            "COUNCIL_TOOL_BUDGET": "3",
            "GUPPY_SLO_SIMPLE_MS": "3500",
            "GUPPY_UI_TICK_MS": "2500",
            "GUPPY_API_OWNS_DAEMON": "0",
            "GUPPY_WINDOW_POLL_INTERVAL_S": "2.0",
            "GUPPY_PROACTIVE_POLL_S": "120",
            "GUPPY_AMBIENT_POLL_S": "180",
            "GUPPY_AMBIENT_COOLDOWN_S": "900",
            "GUPPY_VOICE_TIMEOUT_SECONDS": "120",
            "GUPPY_CHAT_TIMEOUT_SECONDS": "90",
            "GUPPY_TELEMETRY_BACKEND": "sqlite+jsonl",
            "GUPPY_ENVELOPE_CPU_MAX_PCT": "70",
            "GUPPY_ENVELOPE_RAM_MAX_PCT": "80",
            "GUPPY_ENVELOPE_CHECK_S": "90",
        },
    },
    "standard": {
        "runtime_profile": "standard",
        "enable_daemon": True,
        "enable_voice": True,
        "wake_word_default": False,
        "default_mode": "auto",
        "env_defaults": {
            "GUPPY_TOOL_BUDGET": "6",
            "COUNCIL_TOOL_BUDGET": "5",
            "GUPPY_SLO_SIMPLE_MS": "3500",
            "GUPPY_UI_TICK_MS": "1800",
            "GUPPY_API_OWNS_DAEMON": "0",
            "GUPPY_WINDOW_POLL_INTERVAL_S": "1.2",
            "GUPPY_PROACTIVE_POLL_S": "90",
            "GUPPY_AMBIENT_POLL_S": "120",
            "GUPPY_AMBIENT_COOLDOWN_S": "720",
            "GUPPY_VOICE_TIMEOUT_SECONDS": "150",
            "GUPPY_CHAT_TIMEOUT_SECONDS": "120",
            "GUPPY_TELEMETRY_BACKEND": "sqlite+jsonl",
            "GUPPY_ENVELOPE_CPU_MAX_PCT": "80",
            "GUPPY_ENVELOPE_RAM_MAX_PCT": "88",
            "GUPPY_ENVELOPE_CHECK_S": "60",
        },
    },
    "power": {
        "runtime_profile": "power",
        "enable_daemon": True,
        "enable_voice": True,
        "wake_word_default": True,
        "default_mode": "auto",
        "env_defaults": {
            "GUPPY_TOOL_BUDGET": "8",
            "COUNCIL_TOOL_BUDGET": "6",
            "GUPPY_SLO_SIMPLE_MS": "3000",
            "GUPPY_UI_TICK_MS": "1400",
            "GUPPY_API_OWNS_DAEMON": "0",
            "GUPPY_WINDOW_POLL_INTERVAL_S": "0.8",
            "GUPPY_PROACTIVE_POLL_S": "60",
            "GUPPY_AMBIENT_POLL_S": "90",
            "GUPPY_AMBIENT_COOLDOWN_S": "600",
            "GUPPY_VOICE_TIMEOUT_SECONDS": "180",
            "GUPPY_CHAT_TIMEOUT_SECONDS": "120",
            "GUPPY_TELEMETRY_BACKEND": "sqlite+jsonl",
            "GUPPY_ENVELOPE_CPU_MAX_PCT": "90",
            "GUPPY_ENVELOPE_RAM_MAX_PCT": "92",
            "GUPPY_ENVELOPE_CHECK_S": "45",
        },
    },
}


def _bool_env(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_profile(value: str | None) -> str:
    profile = (value or "standard").strip().lower()
    return profile if profile in PROFILE_PRESETS else "standard"


def load_app_settings() -> dict[str, Any]:
    settings = deepcopy(DEFAULT_SETTINGS)
    profile = _normalize_profile(os.environ.get("GUPPY_RUNTIME_PROFILE", settings["runtime_profile"]))
    settings.update({k: v for k, v in PROFILE_PRESETS[profile].items() if k != "env_defaults"})

    try:
        if SETTINGS_PATH.exists():
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                settings.update({k: v for k, v in data.items() if k in settings})
    except Exception:
        pass

    env_profile = os.environ.get("GUPPY_RUNTIME_PROFILE")
    if env_profile:
        settings["runtime_profile"] = _normalize_profile(env_profile)

    env_default_mode = os.environ.get("GUPPY_DEFAULT_MODE", "").strip().lower()
    if env_default_mode in {"auto", "claude", "ollama", "local", "code", "teaching"}:
        settings["default_mode"] = env_default_mode

    for setting_key, env_name in (
        ("enable_daemon", "GUPPY_ENABLE_DAEMON"),
        ("enable_voice", "GUPPY_ENABLE_VOICE"),
        ("wake_word_default", "GUPPY_WAKE_WORD_DEFAULT"),
    ):
        env_value = _bool_env(env_name)
        if env_value is not None:
            settings[setting_key] = env_value

    local_runtime_backend = os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", "").strip().lower()
    if local_runtime_backend in {"ollama", "lemonade"}:
        settings["local_runtime_backend"] = local_runtime_backend

    for setting_key, env_name in (
        ("lemonade_base_url", "GUPPY_LEMONADE_BASE_URL"),
        ("lemonade_fast_model", "GUPPY_LEMONADE_FAST_MODEL"),
        ("lemonade_complex_model", "GUPPY_LEMONADE_COMPLEX_MODEL"),
        ("lemonade_teach_model", "GUPPY_LEMONADE_TEACH_MODEL"),
        ("lemonade_code_model", "GUPPY_LEMONADE_CODE_MODEL"),
        ("lemonade_vault_model", "GUPPY_LEMONADE_VAULT_MODEL"),
        ("local_main_model", "GUPPY_MAIN_MODEL"),
        ("local_sub_model_a", "GUPPY_SUB_MODEL_A"),
        ("local_sub_model_b", "GUPPY_SUB_MODEL_B"),
    ):
        env_value = os.environ.get(env_name)
        if env_value is not None:
            settings[setting_key] = str(env_value)

    return settings


def save_app_settings(settings: dict[str, Any]) -> Path:
    merged = load_app_settings()
    merged.update({k: v for k, v in settings.items() if k in DEFAULT_SETTINGS})
    merged["runtime_profile"] = _normalize_profile(merged.get("runtime_profile"))
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if _ATOMIC_IO:
        if not write_json_atomic(SETTINGS_PATH, merged):
            raise OSError(f"Failed to write settings atomically: {SETTINGS_PATH}")
    else:
        SETTINGS_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    return SETTINGS_PATH


def apply_settings_to_env(settings: dict[str, Any]) -> dict[str, Any]:
    merged = load_app_settings()
    merged.update({k: v for k, v in settings.items() if k in DEFAULT_SETTINGS})
    profile = _normalize_profile(merged.get("runtime_profile"))
    merged["runtime_profile"] = profile

    env_defaults = PROFILE_PRESETS[profile].get("env_defaults", {})
    for key, value in env_defaults.items():
        os.environ.setdefault(key, str(value))

    os.environ["GUPPY_RUNTIME_PROFILE"] = profile
    os.environ["GUPPY_DEFAULT_MODE"] = str(merged.get("default_mode", "auto"))
    os.environ.pop("GUPPY_DEFAULT_SURFACE", None)
    os.environ.pop("GUPPY_SHOW_ADVANCED_SURFACES", None)
    os.environ["GUPPY_ENABLE_DAEMON"] = "1" if merged.get("enable_daemon") else "0"
    os.environ["GUPPY_ENABLE_VOICE"] = "1" if merged.get("enable_voice") else "0"
    os.environ["GUPPY_WAKE_WORD_DEFAULT"] = "1" if merged.get("wake_word_default") else "0"
    os.environ["GUPPY_LOCAL_RUNTIME_BACKEND"] = str(merged.get("local_runtime_backend", "ollama") or "ollama").strip().lower()
    os.environ["GUPPY_LEMONADE_BASE_URL"] = str(
        merged.get("lemonade_base_url", "http://localhost:13305/api/v1") or "http://localhost:13305/api/v1"
    ).strip()
    os.environ["GUPPY_LEMONADE_FAST_MODEL"] = str(merged.get("lemonade_fast_model", "") or "").strip()
    os.environ["GUPPY_LEMONADE_COMPLEX_MODEL"] = str(merged.get("lemonade_complex_model", "") or "").strip()
    os.environ["GUPPY_LEMONADE_TEACH_MODEL"] = str(merged.get("lemonade_teach_model", "") or "").strip()
    os.environ["GUPPY_LEMONADE_CODE_MODEL"] = str(merged.get("lemonade_code_model", "") or "").strip()
    os.environ["GUPPY_LEMONADE_VAULT_MODEL"] = str(merged.get("lemonade_vault_model", "") or "").strip()
    main_model = str(merged.get("local_main_model", "") or "").strip()
    sub_model_a = str(merged.get("local_sub_model_a", "") or "").strip()
    sub_model_b = str(merged.get("local_sub_model_b", "") or "").strip()
    os.environ["GUPPY_MAIN_MODEL"] = main_model
    os.environ["GUPPY_SUB_MODEL_A"] = sub_model_a
    os.environ["GUPPY_SUB_MODEL_B"] = sub_model_b
    if main_model:
        os.environ["OLLAMA_MODEL"] = main_model
        os.environ["GUPPY_LOCAL_COMPLEX_MODEL"] = main_model
    if sub_model_a:
        os.environ["OLLAMA_FAST_MODEL"] = sub_model_a
        os.environ["GUPPY_LOCAL_FAST_MODEL"] = sub_model_a
    if sub_model_b:
        os.environ["OLLAMA_CODE_MODEL"] = sub_model_b
        os.environ["GUPPY_LOCAL_CODE_MODEL"] = sub_model_b
    return merged


def recommend_runtime_profile() -> dict[str, Any]:
    cpu_percent = 0.0
    total_ram_gb = 0.0
    available_ram_gb = 0.0
    reasons: list[str] = []

    if PSUTIL_OK:
        try:
            cpu_percent = float(psutil.cpu_percent(interval=0.15))
            vm = psutil.virtual_memory()
            total_ram_gb = round(vm.total / (1024 ** 3), 1)
            available_ram_gb = round(vm.available / (1024 ** 3), 1)
        except Exception:
            pass

    ollama_ready = False
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.4):
            ollama_ready = True
    except OSError:
        ollama_ready = False

    profile = "standard"
    if (total_ram_gb and total_ram_gb < 16.0) or (available_ram_gb and available_ram_gb < 4.0):
        profile = "light"
        reasons.append("RAM headroom is limited for always-on local-heavy features.")
    elif cpu_percent >= 65.0:
        profile = "light"
        reasons.append("Current CPU load is already elevated, so lighter defaults are safer.")
    elif total_ram_gb >= 32.0 and available_ram_gb >= 12.0 and cpu_percent < 45.0 and ollama_ready:
        profile = "power"
        reasons.append("The machine has enough memory headroom for heavier local and multi-surface workflows.")
    else:
        reasons.append("Balanced defaults fit the current machine state better than minimal or power-user presets.")

    if not ollama_ready:
        reasons.append("Ollama is not currently reachable, so cloud-first defaults are safer.")
        if profile == "power":
            profile = "standard"
    else:
        reasons.append("Ollama is available for local fallback or teaching workflows.")

    if not reasons:
        reasons.append("No strong hardware signal detected; standard is the safest baseline.")

    return {
        "profile": profile,
        "cpu_percent": round(cpu_percent, 1),
        "total_ram_gb": total_ram_gb,
        "available_ram_gb": available_ram_gb,
        "ollama_ready": ollama_ready,
        "reasons": reasons,
    }


def apply_runtime_profile() -> dict[str, Any]:
    settings = load_app_settings()
    return apply_settings_to_env(settings)


def get_runtime_envelope_config(profile: str | None = None) -> dict[str, Any]:
    """Return active resource envelope thresholds for the selected runtime profile."""
    active_profile = _normalize_profile(profile or os.environ.get("GUPPY_RUNTIME_PROFILE", "standard"))
    defaults = PROFILE_PRESETS.get(active_profile, PROFILE_PRESETS["standard"]).get("env_defaults", {})

    cpu_default = float(defaults.get("GUPPY_ENVELOPE_CPU_MAX_PCT", "80"))
    ram_default = float(defaults.get("GUPPY_ENVELOPE_RAM_MAX_PCT", "88"))
    check_default = int(defaults.get("GUPPY_ENVELOPE_CHECK_S", "60"))

    try:
        cpu_max = float(os.environ.get("GUPPY_ENVELOPE_CPU_MAX_PCT", str(cpu_default)))
    except Exception:
        cpu_max = cpu_default
    try:
        ram_max = float(os.environ.get("GUPPY_ENVELOPE_RAM_MAX_PCT", str(ram_default)))
    except Exception:
        ram_max = ram_default
    try:
        check_s = int(os.environ.get("GUPPY_ENVELOPE_CHECK_S", str(check_default)))
    except Exception:
        check_s = check_default

    return {
        "profile": active_profile,
        "cpu_max_pct": max(10.0, min(cpu_max, 99.0)),
        "ram_max_pct": max(10.0, min(ram_max, 99.0)),
        "check_interval_s": max(15, min(check_s, 600)),
    }
