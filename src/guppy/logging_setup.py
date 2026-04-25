"""Central logging configuration using loguru.

Call configure_logging() once at startup. After that, any module can do:
    from loguru import logger
    logger.info("...")

Stdlib logging (FastAPI, uvicorn, httpx, etc.) is intercepted and forwarded
to loguru so everything appears in one consistent stream.
"""
from __future__ import annotations

import logging
import sys

from loguru import logger


class _StdlibInterceptHandler(logging.Handler):
    """Route stdlib log records into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno  # type: ignore[assignment]

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back  # type: ignore[assignment]
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def configure_logging(*, level: str = "INFO", dev_mode: bool = False) -> None:
    """Configure loguru and intercept stdlib logging.

    Args:
        level: Minimum log level for production (e.g. "INFO", "WARNING").
        dev_mode: If True, emit DEBUG logs with full source location.
    """
    logger.remove()

    fmt_dev = (
        "<green>{time:HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
        "<level>{message}</level>"
    )
    fmt_prod = (
        "{time:YYYY-MM-DD HH:mm:ss} | "
        "{level: <8} | "
        "{name}:{line} — {message}"
    )

    logger.add(
        sys.stderr,
        level="DEBUG" if dev_mode else level,
        format=fmt_dev if dev_mode else fmt_prod,
        colorize=dev_mode,
        backtrace=dev_mode,
        diagnose=dev_mode,
    )

    # Intercept all stdlib loggers (uvicorn, fastapi, httpx, etc.)
    logging.basicConfig(handlers=[_StdlibInterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "httpx"):
        logging.getLogger(name).handlers = [_StdlibInterceptHandler()]
        logging.getLogger(name).propagate = False
