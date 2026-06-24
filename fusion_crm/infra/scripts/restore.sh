#!/usr/bin/env bash
# Fusion CRM — database restore
#
# Usage:
#   ./infra/scripts/restore.sh <local-file.dump>
#   ./infra/scripts/restore.sh gs://bucket/path/to/file.dump
#
# WARNING: this DROPS and recreates objects (--clean --if-exists). Run only
# against the target environment you intend to overwrite.
#
# Required env:
#   DATABASE_URL_SYNC                postgres://user:pass@host:5432/db
#   GOOGLE_APPLICATION_CREDENTIALS   if restoring from GCS

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <local-file.dump | gs://bucket/path/file.dump>" >&2
  exit 2
fi

: "${DATABASE_URL_SYNC:?DATABASE_URL_SYNC is required}"

SOURCE="$1"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "${WORKDIR}"' EXIT

if [[ "${SOURCE}" == gs://* ]]; then
  if ! command -v gsutil >/dev/null 2>&1; then
    echo "[restore] FATAL: gsutil required for GCS source" >&2
    exit 1
  fi
  LOCAL="${WORKDIR}/$(basename "${SOURCE}")"
  echo "[restore] downloading ${SOURCE} → ${LOCAL}"
  gsutil -q cp "${SOURCE}" "${LOCAL}"
else
  LOCAL="${SOURCE}"
fi

if [[ ! -s "${LOCAL}" ]]; then
  echo "[restore] FATAL: source file missing or empty: ${LOCAL}" >&2
  exit 1
fi

# Confirm we have not pointed at production by accident.
echo "[restore] target DB: ${DATABASE_URL_SYNC%%@*}@<redacted>"
if [[ -t 0 && "${FORCE:-0}" != "1" ]]; then
  read -r -p "Type 'RESTORE' to proceed: " CONFIRM
  if [[ "${CONFIRM}" != "RESTORE" ]]; then
    echo "[restore] aborted"
    exit 3
  fi
fi

echo "[restore] running pg_restore"
pg_restore \
  --dbname="${DATABASE_URL_SYNC}" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --jobs=4 \
  "${LOCAL}"

echo "[restore] done"
