"""Unit tests for error_handler.py.

Covers format_error_response, map_exception_to_error_code, APIErrorResponse,
and the api_error_handler decorator — all without spinning up a FastAPI app.
"""
from __future__ import annotations

import asyncio
import pytest

from src.guppy.api.error_codes import ErrorCode
from src.guppy.api.error_handler import (
    APIErrorResponse,
    api_error_handler,
    format_error_response,
    map_exception_to_error_code,
)


_REQ_ID = "test1234"


# ── format_error_response ─────────────────────────────────────────────────────

def test_format_error_response_required_fields():
    resp = format_error_response(ErrorCode.SYSTEM_INTERNAL_ERROR, "oops", 500, _REQ_ID)
    assert resp["code"] == "SYSTEM_INTERNAL_ERROR"
    assert resp["message"] == "oops"
    assert resp["statusCode"] == 500
    assert resp["requestId"] == _REQ_ID
    assert "timestamp" in resp


def test_format_error_response_details_included_when_present():
    resp = format_error_response(
        ErrorCode.VALIDATION_INVALID_INPUT, "bad", 422, _REQ_ID, details={"field": "name"}
    )
    assert resp["details"] == {"field": "name"}


def test_format_error_response_details_omitted_when_empty():
    resp = format_error_response(ErrorCode.SYSTEM_INTERNAL_ERROR, "oops", 500, _REQ_ID)
    assert "details" not in resp


def test_format_error_response_details_omitted_when_none():
    resp = format_error_response(ErrorCode.SYSTEM_INTERNAL_ERROR, "oops", 500, _REQ_ID, details=None)
    assert "details" not in resp


# ── APIErrorResponse ──────────────────────────────────────────────────────────

def test_api_error_response_defaults():
    err = APIErrorResponse(ErrorCode.SYSTEM_INTERNAL_ERROR)
    assert err.code is ErrorCode.SYSTEM_INTERNAL_ERROR
    assert isinstance(err.message, str) and err.message
    assert err.details == {}
    assert err.status_code == 500


def test_api_error_response_custom_message_and_details():
    err = APIErrorResponse(ErrorCode.VALIDATION_INVALID_INPUT, "bad field", {"field": "x"})
    assert err.message == "bad field"
    assert err.details == {"field": "x"}


# ── map_exception_to_error_code ───────────────────────────────────────────────

def test_map_value_error():
    code, msg, details = map_exception_to_error_code(ValueError("bad value"), _REQ_ID)
    assert code is ErrorCode.VALIDATION_INVALID_INPUT
    assert "bad value" in msg
    assert details is None


def test_map_key_error():
    code, msg, details = map_exception_to_error_code(KeyError("missing_field"), _REQ_ID)
    assert code is ErrorCode.VALIDATION_MISSING_FIELD
    assert "missing_field" in msg


def test_map_type_error():
    code, msg, details = map_exception_to_error_code(TypeError("wrong type"), _REQ_ID)
    assert code is ErrorCode.VALIDATION_INVALID_FORMAT


def test_map_timeout_error():
    code, msg, details = map_exception_to_error_code(TimeoutError("timed out"), _REQ_ID)
    assert code is ErrorCode.SYSTEM_TIMEOUT


def test_map_unknown_exception():
    code, msg, details = map_exception_to_error_code(RuntimeError("surprise"), _REQ_ID)
    assert code is ErrorCode.SYSTEM_INTERNAL_ERROR


# ── api_error_handler decorator ───────────────────────────────────────────────

def _run(coro):
    return asyncio.run(coro)


def test_decorator_passes_through_on_success():
    @api_error_handler
    async def handler():
        return {"ok": True}

    result = _run(handler())
    assert result == {"ok": True}


def test_decorator_catches_api_error_response():
    from fastapi.responses import JSONResponse

    @api_error_handler
    async def handler():
        raise APIErrorResponse(ErrorCode.SYSTEM_INTERNAL_ERROR, "deliberate error")

    result = _run(handler())
    assert isinstance(result, JSONResponse)
    assert result.status_code == 500


def test_decorator_catches_value_error():
    from fastapi.responses import JSONResponse

    @api_error_handler
    async def handler():
        raise ValueError("something invalid")

    result = _run(handler())
    assert isinstance(result, JSONResponse)
    assert result.status_code == 400


def test_decorator_catches_generic_exception():
    from fastapi.responses import JSONResponse

    @api_error_handler
    async def handler():
        raise RuntimeError("unexpected crash")

    result = _run(handler())
    assert isinstance(result, JSONResponse)
    assert result.status_code == 500
