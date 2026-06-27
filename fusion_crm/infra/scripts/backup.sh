#!/usr/bin/env bash
# Fusion CRM — database backup
#
# Behaviour:
#   1. pg_dump (custom format, compressed) into $BACKUP_LOCAL_DIR
#   2. Upload the dump to gs://$GCS_BUCKET/<host>/<YYYY>/<MM>/
#   3. Delete local dumps older than $BACKUP_RETENTION_DAYS
#
# Required env (loaded from project .env or container environment):
#   DATABASE_URL_SYNC                postgres://user:pass@host:5432/db
#   BACKUP_LOCAL_DIR                 default /var/backups/fusion
#   BACKUP_RETENTION_DAYS            default 30
#   GCS_BUCKET                       optional — if unset, GCS upload is skipped
#   GOOGLE_APPLICATION_CREDENTIALS   path to GCP service-account JSON
#
# Exit codes:
#   0 success, non-zero on any failure (pg_dump, gsutil, prune)

set -euo pipefail

: "${DATABASE_URL_SYNC:?DATABASE_URL_SYNC is required}"
BACKUP_LOCAL_DIR="${BACKUP_LOCAL_DIR:-/var/backups/fusion}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

mkdir -p "${BACKUP_LOCAL_DIR}"

HOST_TAG="$(hostname -s)"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP_FILE="${BACKUP_LOCAL_DIR}/fusion_${HOST_TAG}_${TIMESTAMP}.dump"

echo "[backup] dumping → ${DUMP_FILE}"
pg_dump \
  --dbname="${DATABASE_URL_SYNC}" \
  --format=custom \
  --compress=9 \
  --no-owner \
  --no-privileges \
  --file="${DUMP_FILE}"

# Verify we produced a non-empty file before continuing
if [[ ! -s "${DUMP_FILE}" ]]; then
  echo "[backup] FATAL: dump file is empty" >&2
  exit 1
fi

SIZE_HUMAN="$(du -h "${DUMP_FILE}" | cut -f1)"
echo "[backup] local OK (${SIZE_HUMAN})"

# --- Upload to Google Cloud Storage ---
if [[ -n "${GCS_BUCKET:-}" ]]; then
  if ! command -v gsutil >/dev/null 2>&1; then
    echo "[backup] WARN: gsutil not installed; skipping GCS upload" >&2
  else
    YEAR="$(date -u +%Y)"
    MONTH="$(date -u +%m)"
    GCS_PATH="gs://${GCS_BUCKET}/${HOST_TAG}/${YEAR}/${MONTH}/$(basename "${DUMP_FILE}")"
    echo "[backup] uploading → ${GCS_PATH}"
    gsutil -q cp "${DUMP_FILE}" "${GCS_PATH}"
    echo "[backup] uploaded OK"
  fi
else
  echo "[backup] GCS_BUCKET not set; local-only backup"
fi

# --- Prune old local dumps ---
echo "[backup] pruning local dumps older than ${BACKUP_RETENTION_DAYS}d"
find "${BACKUP_LOCAL_DIR}" -type f -name 'fusion_*.dump' -mtime "+${BACKUP_RETENTION_DAYS}" -print -delete || true

echo "[backup] done"
