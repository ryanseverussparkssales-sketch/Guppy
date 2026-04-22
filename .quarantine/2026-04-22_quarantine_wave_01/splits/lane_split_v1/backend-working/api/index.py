"""Vercel FastAPI ASGI entrypoint.

Vercel's Python runtime looks for an exported ``app`` symbol for ASGI apps.
This module keeps the deployment surface explicit and stable.
"""

from src.guppy.api.server_runtime import app as fastapi_app

# Exported ASGI application for Vercel.
app = fastapi_app

