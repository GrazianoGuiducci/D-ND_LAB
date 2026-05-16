# D-ND_LAB — autonomous research lab
#
# Multi-stage build:
#   Stage 1 (builder): uv installs Python deps into a venv
#   Stage 2 (runtime): slim image with venv + source, runs as non-root
#
# Build:  docker build -t d-nd-lab:latest .
# Run:    docker run --env-file .env -v lab_data:/data d-nd-lab:latest
#
# For full deployment use docker-compose.yml.

# ─── Stage 1: build ──────────────────────────────────────────────────
FROM python:3.13-slim AS builder

# uv: fast Python package manager (pinned tag avoids surprises in 'latest')
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv

WORKDIR /app

# Copy minimum needed to install deps (better cache hit on source-only changes)
COPY pyproject.toml README.md LICENSE ./
COPY core/__init__.py ./core/__init__.py

# Create venv + install runtime deps (NOT physics extras — those are
# installed in this image because physics is the default reinstallable demo)
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python --no-cache \
        "openai>=2.0" \
        "networkx>=3.4" \
        "click>=8.2" \
        "jsonschema>=4.23" \
        "httpx>=0.28" \
        "pyyaml>=6.0" \
        "numpy>=2.0" \
        "scipy>=1.14" \
        "sympy>=1.13" \
        "mpmath>=1.3" \
        "matplotlib>=3.9"

# Optional: install MCP later in Phase 2.5 if the lab uses MCP tool servers
# RUN /app/.venv/bin/pip install --no-cache-dir "mcp>=1.20"

# ─── Stage 2: runtime ───────────────────────────────────────────────
FROM python:3.13-slim

# System deps:
#   tini   — PID 1 for clean signal forwarding
#   curl   — healthcheck + outbound webhook (notify)
#   cron   — optional, used if cron-mode entrypoint is selected
RUN apt-get update && apt-get install -y --no-install-recommends \
        tini curl cron \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — UID 1001 matches the THIA/D-ND ecosystem convention
RUN useradd -u 1001 -m -s /bin/bash lab

WORKDIR /app

# Copy venv from builder + sources owned by lab user
COPY --from=builder --chown=lab:lab /app/.venv /app/.venv
COPY --chown=lab:lab core/ /app/core/
COPY --chown=lab:lab domains/ /app/domains/
COPY --chown=lab:lab config.schema.json /app/

# Data volume — seed, reports, cimitero, graph all persist here
RUN mkdir -p /data && chown -R lab:lab /data
VOLUME ["/data"]

# Default env (overridable via --env-file or -e flags)
ENV PATH="/app/.venv/bin:$PATH" \
    LAB_DATA_DIR=/data \
    LAB_DOMAIN=physics \
    LLM_BASE_URL=https://openrouter.ai/api/v1 \
    LLM_MAX_TURNS=25 \
    LLM_TIMEOUT_SECONDS=1200 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER lab

# Healthcheck: verify the package imports cleanly
HEALTHCHECK --interval=60s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import core; import core.lab_agent; import core.tools" || exit 1

# Default: run a single cycle and exit. Override CMD for cron-mode or
# inspection (`docker run d-nd-lab inspect --domain physics`).
ENTRYPOINT ["tini", "--", "python", "-m", "core.cli"]
CMD ["run", "--domain", "physics"]
