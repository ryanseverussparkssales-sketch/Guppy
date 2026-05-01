_DEFAULT_LEMONADE_BASE_URL = "http://localhost:13305/api/v1"
_LEMONADE_ROLE_ENV = {
    "fast": "GUPPY_LEMONADE_FAST_MODEL",
    "complex": "GUPPY_LEMONADE_COMPLEX_MODEL",
    "teach": "GUPPY_LEMONADE_TEACH_MODEL",
    "code": "GUPPY_LEMONADE_CODE_MODEL",
    "vault": "GUPPY_LEMONADE_VAULT_MODEL",
}
_LOCAL_RUNTIME_WARM_TTL_SECONDS = float(os.environ.get("GUPPY_LOCAL_RUNTIME_WARM_TTL_SECONDS", "300.0"))
_LOCAL_RUNTIME_WARM_TIMEOUT_SECONDS = float(os.environ.get("GUPPY_LOCAL_RUNTIME_WARM_TIMEOUT_SECONDS", "20.0"))
_local_runtime_warm_cache = {
    "backend": "",
    "model": "",
    "checked_at": 0.0,
    "expires_at": 0.0,
    "chat_ready": False,
    "chat_state": "UNKNOWN",
    "chat_detail": "local runtime warmup not checked yet",
}
_local_runtime_warm_lock = threading.Lock()
_local_runtime_warm_refresh_inflight = False


def _selected_local_runtime_backend() -> str:
    try:
        from src.guppy.inference.local_client import active_backend

        return active_backend()
    except Exception:
        return "llamacpp-hermes3"


def _local_runtime_base_url(backend: str) -> str:
    try:
        from src.guppy.inference.local_client import _resolve_url

        return _resolve_url((backend or "llamacpp-hermes3").strip().lower())
    except Exception:
        return "http://127.0.0.1:8087"


def _resolve_local_runtime_model(
    backend: str,
    role: str,
    *,
    fallback: str = "",
) -> str:
    normalized_backend = (backend or "llamacpp").strip().lower()
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


def _warm_ollama_chat_lane(model: str, keep_alive: str = "20m") -> tuple[bool, str]:
    del keep_alive
    normalized_model = str(model or "").strip()
    if not normalized_model:
        return False, "no local model configured for warmup"
    try:
        from src.guppy.inference.local_client import local_chat

        result = local_chat(
            normalized_model,
            [{"role": "user", "content": "ok"}],
            timeout=int(_LOCAL_RUNTIME_WARM_TIMEOUT_SECONDS),
            num_predict=1,
            max_retries=0,
            backend=_selected_local_runtime_backend(),
        )
    except Exception as exc:
        return False, f"local runtime warmup error: {exc}"
    if result is None:
        return False, "local runtime warmup returned no response"
    return True, f"{normalized_model} warm via {result.get('metadata', {}).get('backend', 'local')}"


def _current_local_runtime_chat_model(backend: str) -> str:
    role_models = _local_runtime_role_models(backend)
    return str(
        role_models.get("complex")
        or role_models.get("fast")
        or ""
    ).strip()


def _refresh_local_runtime_warm_status(force: bool = False) -> dict[str, Any]:
    backend = _selected_local_runtime_backend()
    model = _current_local_runtime_chat_model(backend)
    now = time.time()
    with _local_runtime_warm_lock:
        cached = dict(_local_runtime_warm_cache)
        if (
            not force
            and cached.get("backend") == backend
            and cached.get("model") == model
            and float(cached.get("expires_at", 0.0) or 0.0) > now
        ):
            return cached

    if backend == "lemonade":
        payload = {
            "backend": backend,
            "model": model,
            "checked_at": now,
            "expires_at": now + max(30.0, _LOCAL_RUNTIME_WARM_TTL_SECONDS),
            "chat_ready": True,
            "chat_state": "READY",
            "chat_detail": "Lemonade backend selected; chat lane treated as ready when registry is reachable",
        }
    else:
        ok, detail = _warm_ollama_chat_lane(model)
        payload = {
            "backend": backend,
            "model": model,
            "checked_at": now,
            "expires_at": now + max(30.0, _LOCAL_RUNTIME_WARM_TTL_SECONDS),
            "chat_ready": bool(ok),
            "chat_state": "READY" if ok else "WARMING",
            "chat_detail": str(detail or ("local runtime warmed" if ok else "local runtime warmup failed")),
        }
    with _local_runtime_warm_lock:
        _local_runtime_warm_cache.update(payload)
        return dict(_local_runtime_warm_cache)


def _local_runtime_warm_cached_or_unknown() -> dict[str, Any]:
    backend = _selected_local_runtime_backend()
    model = _current_local_runtime_chat_model(backend)
    now = time.time()
    with _local_runtime_warm_lock:
        cached = dict(_local_runtime_warm_cache)
        if (
            cached.get("backend") == backend
            and cached.get("model") == model
            and float(cached.get("expires_at", 0.0) or 0.0) > now
        ):
            return cached
    return {
        "backend": backend,
        "model": model,
        "checked_at": 0.0,
        "expires_at": 0.0,
        "chat_ready": False,
        "chat_state": "UNKNOWN",
        "chat_detail": "local runtime warmup not checked yet",
    }


def _trigger_local_runtime_warm_refresh(force: bool = False) -> None:
    global _local_runtime_warm_refresh_inflight
    with _local_runtime_warm_lock:
        if _local_runtime_warm_refresh_inflight:
            return
        if not force:
            cached = dict(_local_runtime_warm_cache)
            now = time.time()
            if float(cached.get("expires_at", 0.0) or 0.0) > now:
                return
        _local_runtime_warm_refresh_inflight = True

    def _worker() -> None:
        global _local_runtime_warm_refresh_inflight
        try:
            _refresh_local_runtime_warm_status(force=True)
        except Exception:
            pass
        finally:
            with _local_runtime_warm_lock:
                _local_runtime_warm_refresh_inflight = False

    threading.Thread(target=_worker, daemon=True).start()


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
    active_chat_model = _current_local_runtime_chat_model(backend)
    model_ids: set[str] = set()
    detail = ""
    policy: dict[str, Any] = {}
    warm_status = _local_runtime_warm_cached_or_unknown()

    try:
        from src.guppy.local_llm.manifest import get_local_llm_policy_summary, load_local_llm_manifest

        policy = get_local_llm_policy_summary(load_local_llm_manifest())
    except Exception:
        policy = {}

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
        _trigger_local_runtime_warm_refresh(force=False)
        return {
            "backend": backend,
            "base_url": _local_runtime_base_url(backend),
            "state": "MISSING",
            "detail": str(exc),
            "role_models": role_models,
            "available_roles": [],
            "missing_roles": [role for role, model in role_models.items() if model],
            "models": [],
            "policy": policy,
            "chat_ready": bool(warm_status.get("chat_ready", False)),
            "chat_state": str(warm_status.get("chat_state", "UNKNOWN") or "UNKNOWN"),
            "chat_detail": str(warm_status.get("chat_detail", "") or ""),
            "chat_model": str(warm_status.get("model", "") or active_chat_model),
        }

    # Normalize for Ollama's ":latest" suffix — "guppy-fast" matches "guppy-fast:latest"
    def _model_present(m: str) -> bool:
        return m in model_ids or f"{m}:latest" in model_ids
    available_roles = sorted([role for role, model in role_models.items() if model and _model_present(model)])
    missing_roles = sorted([role for role, model in role_models.items() if model and not _model_present(model)])
    if available_roles and not missing_roles:
        state = "READY"
    elif available_roles:
        state = "PARTIAL"
    else:
        state = "MISSING"

    if backend == "ollama" and available_roles and str(warm_status.get("chat_state", "UNKNOWN") or "UNKNOWN") == "UNKNOWN":
        _trigger_local_runtime_warm_refresh(force=False)
    if backend == "ollama" and available_roles and not bool(warm_status.get("chat_ready", False)) and state == "READY":
        state = "PARTIAL"
        detail = f"{detail} | chat lane warming"

    return {
        "backend": backend,
        "base_url": _local_runtime_base_url(backend),
        "state": state,
        "detail": detail,
        "role_models": role_models,
        "available_roles": available_roles,
        "missing_roles": missing_roles,
        "models": sorted(model_ids),
        "policy": policy,
        "chat_ready": bool(warm_status.get("chat_ready", False)),
        "chat_state": str(warm_status.get("chat_state", "UNKNOWN") or "UNKNOWN"),
        "chat_detail": str(warm_status.get("chat_detail", "") or ""),
        "chat_model": str(warm_status.get("model", "") or active_chat_model),
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
    backend = _selected_local_runtime_backend()
    warm_status = _local_runtime_warm_cached_or_unknown()
    if backend == "ollama" and not bool(warm_status.get("chat_ready", False)):
        _trigger_local_runtime_warm_refresh(force=True)
        warm_model = str(warm_status.get("model", "") or _current_local_runtime_chat_model(backend))
        warm_detail = str(warm_status.get("chat_detail", "") or "local runtime is still warming up")
        raise RuntimeError(
            f"Local runtime is still warming up for {warm_model or 'the configured model'}. {warm_detail}"
        )
    if backend == "lemonade":
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
