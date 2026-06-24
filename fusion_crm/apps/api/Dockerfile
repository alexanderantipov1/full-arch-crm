# Fusion CRM — apps/api image (Cloud Run production target)
#
# Per ENG-115 + ADR-0002 §"Runtime":
#   * Multi-stage Python 3.12-slim
#   * Production extras only — installs `.[secrets]` so the GCP Secret
#     Manager resolver is available; never installs `.[dev]`.
#   * Non-root user uid 10001 (per apps/CLAUDE.md).
#   * Health probe on /healthz (Cloud Run uses HTTP startup + liveness
#     probes; the HEALTHCHECK instruction is preserved for local `docker
#     run` smoke tests).
#   * Listens on ${PORT:-8080}. Cloud Run injects PORT at boot; locally
#     it defaults to 8080 (the apps/api dev port is 8000, but we keep
#     this image aligned with Cloud Run's contract).

# ---------------------------------------------------------------------------
# Stage 1 — build: resolve and cache dependencies into /root/.local
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Build deps for psycopg / asyncpg / cryptography wheels. These live in
# the build stage only; the runtime stage uses libpq5 instead of -dev.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy project metadata first to leverage Docker layer caching.
COPY pyproject.toml README.md ./
COPY packages ./packages
COPY apps ./apps

# Install production deps + the `secrets` extra (GCP Secret Manager
# resolver). Explicitly DO NOT install the `dev` extra. `--user` lands
# everything under /root/.local so the runtime stage can copy a single
# directory.
RUN pip install --upgrade pip \
 && pip install --user ".[secrets]"

# ---------------------------------------------------------------------------
# Stage 2 — runtime: slim image, non-root, minimal libc + libpq
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    # Cloud Run injects PORT at boot; default to 8080 for local docker run.
    PORT=8080 \
    PATH=/home/fusion/.local/bin:${PATH}

# Runtime libs only:
#   * libpq5 — psycopg + asyncpg client lib
#   * curl, ca-certificates — HEALTHCHECK + outbound HTTPS to providers
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Non-root user per apps/CLAUDE.md.
RUN useradd --create-home --uid 10001 fusion

WORKDIR /app

# Pull in the resolved deps from the build stage. Owned by `fusion` so
# import-time pyc generation lands somewhere writable.
COPY --from=build --chown=fusion:fusion /root/.local /home/fusion/.local

# Source code. Anything outside packages/ + apps/ stays out of the image.
COPY --chown=fusion:fusion packages ./packages
COPY --chown=fusion:fusion apps ./apps
# Operational scripts (e.g. raw_event duplicate cleanup) — Cloud Run Jobs
# reuse this image, so one-shot maintenance must be runnable from it too
# (the worker image already ships infra/). ENG-401.
COPY --chown=fusion:fusion infra ./infra

USER fusion

EXPOSE 8080

# Local-only smoke probe. Cloud Run drives its own HTTP probe against
# /healthz independent of this instruction.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -fsS "http://localhost:${PORT:-8080}/healthz" || exit 1

# `sh -c` so ${PORT} expands at container start (Cloud Run injects it).
ENTRYPOINT ["sh", "-c", "exec uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
