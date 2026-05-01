# Guppy FastAPI application container
#
# Builds a minimal production image for the Guppy FastAPI backend.
# Static React assets must be pre-built into static/ before building this image.
#
# Build:
#   docker build -t guppy-api .
#
# Run standalone (binds to host port 8080):
#   docker run -p 8080:8080 --env-file .env guppy-api
#
# Or use docker-compose:
#   docker compose up -d
#
# ── Required environment variables ──────────────────────────────────────────
# GUPPY_JWT_SECRET   — 32+ character random string for JWT signing
#
# ── Optional environment variables ──────────────────────────────────────────
# GUPPY_DEV_MODE              — set to "1" to enable dev endpoints (local only)
# ANTHROPIC_API_KEY           — for Claude Sonnet cloud fallback
# OPENAI_API_KEY              — for OpenAI cloud fallback
# GOOGLE_CLIENT_ID            — for Gmail/Calendar sync
# GOOGLE_CLIENT_SECRET        — ditto
# GOOGLE_REFRESH_TOKEN        — ditto
# TWILIO_ACCOUNT_SID          — for outbound calling
# TWILIO_AUTH_TOKEN           — ditto
# TWILIO_FROM_NUMBER          — ditto
# HUBSPOT_API_KEY             — for CRM live writes
# ────────────────────────────────────────────────────────────────────────────

FROM python:3.12-slim AS base

# Runtime dependencies only (no build tools needed for a pure-Python stack)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cached layer)
COPY requirements.txt ./
COPY requirements-optional.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-optional.txt || true

# Copy application source
COPY pyproject.toml ./
COPY src/ ./src/
COPY guppy_api.py ./
COPY config/ ./config/
COPY static/ ./static/
COPY utils/ ./utils/
COPY migrations/ ./migrations/
COPY alembic.ini ./

# Persistent data volumes — runtime state, databases, logs
VOLUME ["/app/runtime", "/app/data"]

# Expose the API port
EXPOSE 8080

# Health check — probes /health which is served by FastAPI
HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=30s \
    CMD curl -sf http://localhost:8080/health || exit 1

# Non-root user for security
RUN addgroup --system guppy && adduser --system --ingroup guppy guppy
USER guppy

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

CMD ["python", "-m", "uvicorn", "src.guppy.api.server_runtime:app", \
     "--host", "0.0.0.0", "--port", "8080", \
     "--workers", "1", "--log-level", "info"]
