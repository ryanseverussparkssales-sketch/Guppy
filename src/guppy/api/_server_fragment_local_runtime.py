_DEFAULT_LEMONADE_BASE_URL = "http://localhost:13305/api/v1"
_LEMONADE_ROLE_ENV = {
    "fast": "GUPPY_LEMONADE_FAST_MODEL",
    "complex": "GUPPY_LEMONADE_COMPLEX_MODEL",
    "teach": "GUPPY_LEMONADE_TEACH_MODEL",
    "code": "GUPPY_LEMONADE_CODE_MODEL",
    "vault": "GUPPY_LEMONADE_VAULT_MODEL",
}


def _selected_local_runtime_backend() -> str:
    backend = str(os.environ.get("GUPPY_LOCAL_RUNTIME_BACKEND", "ollama") or "ollama").strip().lower()
    return backend if backend in {"ollama", "lemonade"} else "ollama"


def _local_runtime_base_url(backend: str) -> str:
    normalized = (backend or "ollama").strip().lower()
    if normalized == "lemonade":
        return str(os.environ.get("GUPPY_LEMONADE_BASE_URL", _DEFAULT_LEMONADE_BASE_URL) or _DEFAULT_LEMONADE_BASE_URL).strip()
    return "http://127.0.0.1:11434"


def _resolve_local_runtime_model(
    backend: str,
    role: str,
    *,
    fallback: str = "",
) -> str:
    normalized_backend = (backend or "ollama").strip().lower()
    normalized_role = (role or "").strip().lower()
    if normalized_backend == "lemonade":
        env_name = _LEMONADE_ROLE_ENV.get(normalized_role)
        if env_name:
            return str(os.environ.get(env_name, fallback) or fallback).strip()
        return str(fallback or "").strip()

    if INFERENCE_ROUTER_AVAILABLE:
        try:
            router = get_router()
            if normalized_role == "fast":
                return str(getattr(router, "LOCAL_FAST_MODEL", fallback) or fallback).strip()
            if normalized_role == "complex":
                return str(getattr(router, "LOCAL_MODEL", fallback) or fallback).strip()
            if normalized_role == "teach":
                return str(getattr(router, "LOCAL_TEACH_MODEL", fallback) or fallback).strip()
            if normalized_role == "code":
                return str(getattr(router, "LOCAL_CODE_MODEL", fallback) or fallback).strip()
            if normalized_role == "vault":
                return str(getattr(router, "LOCAL_VAULT_MODEL", fallback) or fallback).strip()
        except Exception:
            pass
    return str(fallback or "").strip()


def _local_runtime_role_models(backend: str) -> dict[str, str]:
    return {
        "fast": _resolve_local_runtime_model(backend, "fast", fallback="guppy-fast"),
        "complex": _resolve_local_runtime_model(backend, "complex", fallback="guppy"),
        "teach": _resolve_local_runtime_model(backend, "teach", fallback="guppy-teach"),
        "code": _resolve_local_runtime_model(backend, "code", fallback="guppy-code"),
        "vault": _resolve_local_runtime_model(backend, "vault", fallback="vault-scraper"),
    }


def _fetch_lemonade_model_ids(timeout: float = 4.0) -> set[str]:
    req = urllib.request.Request(
        f"{_local_runtime_base_url('lemonade').rstrip('/')}/models",
        headers={"Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    items = data.get("data", []) if isinstance(data, dict) else []
    return {
        str(item.get("id", "")).strip()
        for item in items
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }


def _build_local_runtime_status() -> dict[str, Any]:
    backend = _selected_local_runtime_backend()
    role_models = _local_runtime_role_models(backend)
    model_ids: set[str] = set()
    detail = ""

    try:
        if backend == "lemonade":
            model_ids = _fetch_lemonade_model_ids()
            detail = "Lemonade model registry reachable"
        else:
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/tags",
                headers={"Accept": "application/json"},
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read())
            items = data.get("models", []) if isinstance(data, dict) else []
            model_ids = {
                str(item.get("name", "")).strip()
                for item in items
                if isinstance(item, dict) and str(item.get("name", "")).strip()
            }
            detail = "Ollama model registry reachable"
    except Exception as exc:
        return {
            "backend": backend,
            "base_url": _local_runtime_base_url(backend),
            "state": "MISSING",
            "detail": str(exc),
            "role_models": role_models,
            "available_roles": [],
            "missing_roles": [role for role, model in role_models.items() if model],
            "models": [],
        }

    available_roles = sorted([role for role, model in role_models.items() if model and model in model_ids])
    missing_roles = sorted([role for role, model in role_models.items() if model and model not in model_ids])
    if available_roles and not missing_roles:
        state = "READY"
    elif available_roles:
        state = "PARTIAL"
    else:
        state = "MISSING"

    return {
        "backend": backend,
        "base_url": _local_runtime_base_url(backend),
        "state": state,
        "detail": detail,
        "role_models": role_models,
        "available_roles": available_roles,
        "missing_roles": missing_roles,
        "models": sorted(model_ids),
    }


def _call_lemonade_chat(
    user_text: str,
    system_prompt: str,
    *,
    model_override: Optional[str] = None,
) -> str:
    model_name = str(model_override or "").strip()
    if not model_name:
        role_models = _local_runtime_role_models("lemonade")
        model_name = role_models.get("complex", "")
    if not model_name:
        raise RuntimeError("No Lemonade model configured for this route.")

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
    }
    req = urllib.request.Request(
        f"{_local_runtime_base_url('lemonade').rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=CHAT_TIMEOUT_SECONDS) as resp:
        data = json.loads(resp.read())
    choices = data.get("choices", []) if isinstance(data, dict) else []
    if not choices:
        raise RuntimeError("Lemonade returned no chat choices.")
    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    content = str(message.get("content", "") or "").strip()
    if not content:
        raise RuntimeError("Lemonade returned an empty response.")
    return content


def _call_selected_local_runtime(
    user_text: str,
    system_prompt: str,
    *,
    instance_name: Optional[str] = None,
    instance_type: Optional[str] = None,
    model_override: Optional[str] = None,
) -> str:
    if _selected_local_runtime_backend() == "lemonade":
        return _call_lemonade_chat(
            user_text,
            system_prompt,
            model_override=model_override,
        )
    return _call_ollama_with_tools(
        user_text,
        system_prompt,
        instance_name=instance_name,
        instance_type=instance_type,
        model_override=model_override,
    )
