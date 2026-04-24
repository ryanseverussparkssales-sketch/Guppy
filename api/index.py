"""Vercel FastAPI ASGI entrypoint.

Vercel's Python runtime looks for an exported ``app`` symbol for ASGI apps.
This module keeps the deployment surface explicit and stable.
"""

from api.app import app

