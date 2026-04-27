# D-ND_LAB — autonomous research lab
# Phase 0 scaffold. Real build in Phase 3.
#
# Image strategy: slim Python with uv as package manager. Multi-stage to
# keep runtime small. Cron + lab agent run as non-root user.

# ─── Stage 1: build ──────────────────────────────────────────────────
FROM python:3.13-slim AS builder

# Install uv (fast Python package manager)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml ./
# Note: uv.lock will be added once `uv lock` is run in Phase 1

# Install runtime deps into a venv inside /app/.venv
RUN uv venv /app/.venv && \
    uv pip install --python /app/.venv/bin/python -e .

# ─── Stage 2: runtime ───────────────────────────────────────────────
FROM python:3.13-slim

# System deps: cron + curl (notifications/health) + tini (PID 1 for clean signals)
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — lab runs as UID 1001 to match THIA/D-ND ecosystem convention
RUN useradd -u 1001 -m -s /bin/bash lab

WORKDIR /app

# Copy venv from builder + source
COPY --from=builder /app/.venv /app/.venv
COPY --chown=lab:lab core/ /app/core/
COPY --chown=lab:lab domains/ /app/domains/
COPY --chown=lab:lab config.schema.json /app/

# Data volume — seed, reports, cimitero persist here
RUN mkdir -p /data && chown -R lab:lab /data
VOLUME ["/data"]

ENV PATH="/app/.venv/bin:$PATH" \
    LAB_DATA_DIR="/data" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER lab

# Default: run one cycle then exit. For cron mode override CMD.
ENTRYPOINT ["tini", "--"]
CMD ["python", "-m", "core.cli", "run", "--domain", "physics"]
