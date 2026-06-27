# Fusion CRM — apps/worker image (Cloud Run + Cloud Run Jobs production target)
#
# Per ENG-115 + ADR-0002 §"Runtime":
#   * Multi-stage Python 3.12-slim.
#   * Production extras only — installs `.[secrets]` (GCP Secret
#     Manager resolver); never installs `.[dev]`.
#   * Non-root user uid 10001 (per apps/CLAUDE.md).
#   * Default ENTRYPOINT runs the arq worker. Cloud Run Jobs override
#     the entrypoint via `--command` / `--args` to run one-shot tasks
#     (alembic upgrade, bounce_poll, etc.) — see
#     infra/scripts/deploy_cloud_run.sh.
#   * Ships pg_dump + gsutil so the backup job and any operator drill
#     run inside the worker container without host shell-outs.
#
# Note on health probes: arq is a Redis pop-loop with no HTTP surface.
# Cloud Run treats the worker as a service with min=1 max=1 — the
# revision is "ready" as soon as the process starts. We do not attach
# a HEALTHCHECK; arq's internal heartbeat (poll loop) is the liveness
# signal and Redis-side metrics catch stuck workers.

# ---------------------------------------------------------------------------
# Stage 1 — build: resolve and cache dependencies into /root/.local
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

COPY pyproject.toml README.md ./
COPY packages ./packages
COPY apps ./apps

RUN pip install --upgrade pip \
 && pip install --user ".[secrets]"

# ---------------------------------------------------------------------------
# Stage 2 — runtime: slim image with pg_dump + gsutil for the backup job
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/home/fusion/.local/bin:${PATH}

# Runtime libs + tools:
#   * libpq5         — psycopg + asyncpg client lib
#   * postgresql-client — pg_dump / pg_restore for the backup job
#   * google-cloud-cli  — gsutil for GCS uploads (backup destination)
#   * curl, gnupg, lsb-release, apt-transport-https — required to
#                     install the Google Cloud SDK apt repo
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        libpq5 \
        postgresql-client \
        curl \
        ca-certificates \
        gnupg \
        lsb-release \
        apt-transport-https \
 && curl -fsSL https://packages.cloud.google.com/apt/doc/apt-key.gpg \
        | gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg \
 && echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" \
        > /etc/apt/sources.list.d/google-cloud-sdk.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends google-cloud-cli \
 && rm -rf /var/lib/apt/lists/*

# Non-root user per apps/CLAUDE.md.
RUN useradd --create-home --uid 10001 fusion

WORKDIR /app

COPY --from=build --chown=fusion:fusion /root/.local /home/fusion/.local

COPY --chown=fusion:fusion packages ./packages
COPY --chown=fusion:fusion apps ./apps
COPY --chown=fusion:fusion infra ./infra
RUN chmod +x infra/scripts/*.sh

USER fusion

# Cloud Run Jobs override --command / --args to run one-shot tasks
# (alembic upgrade, bounce_poll, etc.). The default ENTRYPOINT here is
# the long-running arq worker for the `fusion-worker` service.
ENTRYPOINT ["arq", "apps.worker.main.WorkerSettings"]
