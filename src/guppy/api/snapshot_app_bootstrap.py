from __future__ import annotations

import asyncio
import os
import secrets
import time
from contextlib import asynccontextmanager
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware


def create_lifespan(owner: Any) -> Callable[[FastAPI], Any]:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        owner.validate_environment()
        owner._ensure_m2_instance_scaffold()

        owner._runtime_dir.mkdir(parents=True, exist_ok=True)
        owner._REPAIR_TOKEN = secrets.token_hex(32)
        if owner._SECRET_STORE_AVAILABLE and owner._secret_store.set_secret("repair_token", owner._REPAIR_TOKEN):
            owner.logger.info("Repair token stored in OS credential store")
            try:
                if owner._REPAIR_TOKEN_FILE.exists():
                    owner._REPAIR_TOKEN_FILE.unlink()
            except Exception as exc:
                owner.logger.warning("Could not remove stale repair token fallback file: %s", exc)
        else:
            try:
                owner._REPAIR_TOKEN_FILE.write_text(owner._REPAIR_TOKEN, encoding="utf-8")
                try:
                    os.chmod(owner._REPAIR_TOKEN_FILE, 0o600)
                except Exception:
                    pass
                owner.logger.info("Repair token written to %s", owner._REPAIR_TOKEN_FILE)
            except Exception as exc:
                owner.logger.warning("Could not write repair token: %s", exc)

        if owner._PERSONALIZATION_BOOTSTRAP_AVAILABLE:
            try:
                created = await asyncio.to_thread(owner.ensure_personalization_scaffold)
                personalization_diagnostics = {
                    "persona_config.json": (await asyncio.to_thread(owner.load_persona_config_with_diagnostics))[1],
                    "provider_registry.json": (await asyncio.to_thread(owner.load_provider_registry_with_diagnostics))[1],
                    "voice_bindings.json": (await asyncio.to_thread(owner.load_voice_bindings_with_diagnostics))[1],
                }
                if created:
                    owner.logger.info("Personalization scaffold initialized: %s", ",".join(sorted(created.keys())))
                problems = [
                    f"{name}: {messages[0]}"
                    for name, messages in personalization_diagnostics.items()
                    if messages
                ]
                if problems:
                    owner.logger.warning(
                        "Personalization scaffold normalized malformed config: %s",
                        " | ".join(problems),
                    )
            except Exception as exc:
                owner.logger.warning("Personalization scaffold initialization failed: %s", exc)

        try:
            await asyncio.to_thread(owner._startup_readiness_snapshot)
        except Exception as exc:
            owner.logger.warning("Startup readiness warmup failed: %s", exc)

        try:
            owner._trigger_local_runtime_warm_refresh(force=True)
        except Exception as exc:
            owner.logger.warning("Local runtime warmup trigger failed: %s", exc)

        owner._emit_integration_heartbeat("api_startup")

        if owner.API_OWNS_DAEMON and owner.GUPPY_DAEMON_AVAILABLE:
            try:
                daemon = owner.get_daemon_manager()
                if hasattr(daemon, "is_running") and daemon.is_running:
                    owner.logger.info("Guppy daemon already running - using existing instance")
                else:
                    daemon.start()
                    owner.logger.info("Guppy daemon started")
            except Exception as exc:
                owner.logger.error("Failed to initialize daemon: %s", exc)
                owner.logger.warning("API will run in limited mode without daemon context")
        elif owner.GUPPY_DAEMON_AVAILABLE:
            owner.logger.info("API running in supervised mode (daemon ownership disabled)")
        else:
            owner.logger.warning("Guppy daemon not available - running in API-only mode")

        try:
            yield
        finally:
            try:
                if owner._SECRET_STORE_AVAILABLE:
                    owner._secret_store.delete_secret("repair_token")
                if owner._REPAIR_TOKEN_FILE.exists():
                    owner._REPAIR_TOKEN_FILE.unlink()
            except Exception as exc:
                owner.logger.warning("Failed to remove repair token: %s", exc)
            if owner.API_OWNS_DAEMON and owner.GUPPY_AVAILABLE:
                try:
                    daemon = owner.get_daemon_manager()
                    daemon.stop()
                    owner.logger.info("Guppy daemon stopped")
                except Exception as exc:
                    owner.logger.error("Failed to stop daemon: %s", exc)

    return lifespan


def configure_app(owner: Any, *, lifespan: Callable[[FastAPI], Any]) -> FastAPI:
    app = FastAPI(
        title="Guppy API",
        description="Remote access API for Guppy AI assistant",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=owner.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Repair-Token", "X-Turnstile-Token"],
    )

    @app.middleware("http")
    async def request_timing_middleware(request: Request, call_next):
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            owner.log_session_event(
                "api",
                "request_failed",
                level="error",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                elapsed_ms=round(elapsed_ms, 2),
            )
            with owner._api_metrics_lock:
                owner._api_metrics["requests_total"] += 1
                owner._api_metrics["errors_total"] += 1
                owner._api_metrics["latency_total_ms"] += elapsed_ms
                owner._api_metrics["path_counts"][request.url.path] = owner._api_metrics["path_counts"].get(request.url.path, 0) + 1
                owner._api_metrics["status_counts"][str(status_code)] = owner._api_metrics["status_counts"].get(str(status_code), 0) + 1
                if elapsed_ms >= owner.SLOW_REQUEST_MS:
                    owner._api_metrics["slow_requests"] += 1
            raise

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"

        with owner._api_metrics_lock:
            owner._api_metrics["requests_total"] += 1
            owner._api_metrics["latency_total_ms"] += elapsed_ms
            owner._api_metrics["path_counts"][request.url.path] = owner._api_metrics["path_counts"].get(request.url.path, 0) + 1
            owner._api_metrics["status_counts"][str(status_code)] = owner._api_metrics["status_counts"].get(str(status_code), 0) + 1
            if status_code >= 500:
                owner._api_metrics["errors_total"] += 1
            if elapsed_ms >= owner.SLOW_REQUEST_MS:
                owner._api_metrics["slow_requests"] += 1

        if elapsed_ms >= owner.SLOW_REQUEST_MS:
            owner.logger.warning(
                "Slow request: %s %s -> %s in %.2fms",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
        owner._emit_integration_heartbeat("api_request")
        owner.log_session_event(
            "api",
            "request_complete",
            level="warning" if elapsed_ms >= owner.SLOW_REQUEST_MS else "info",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            elapsed_ms=round(elapsed_ms, 2),
        )
        return response

    return app