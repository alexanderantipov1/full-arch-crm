"""Incremental sync-window helpers for CareStack ``modifiedSince`` pulls.

CareStack sync feeds (``accounting-transactions``, ``invoices``,
``treatment-procedures``) are *modified-after* feeds ordered ascending by
``lastUpdatedOn`` and paginated via ``continueToken``. A scheduled pull
that always requests ``modifiedSince = now - N days`` and caps itself at a
few pages can never reach the *newest* rows on a busy tenant: it keeps
re-reading the oldest edge of the window every run and the import date is
pinned to ``now - N days`` forever (ENG: payments frozen ~7 days behind).

The fix is a high-watermark cursor: resume each run from the highest
``lastUpdatedOn`` we have already captured (minus a small overlap so a
row sharing the boundary timestamp is never skipped — the
``(id, lastUpdatedOn)`` idempotency key dedupes the overlap). The
watermark is derived from the rows already persisted in ``ingest.raw_event``
so no extra cursor table / migration is needed.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

# Re-pull this much before the watermark so a row modified at (or a hair
# before) the boundary timestamp is never missed. Cheap: re-pulled rows
# dedupe on the ``(id, lastUpdatedOn)`` idempotency key.
DEFAULT_WATERMARK_OVERLAP = timedelta(minutes=10)

# CareStack emits up to 7 fractional-second digits (e.g.
# ``2026-06-02T23:52:17.7406657``); Python's ``datetime`` tops out at 6.
_OVERLONG_FRACTION = re.compile(r"(\.\d{6})\d+")


def parse_watermark(value: str | None) -> datetime | None:
    """Parse a CareStack ``lastUpdatedOn`` string to an aware UTC datetime.

    Tolerates a trailing ``Z``, over-long fractional seconds, and a
    missing timezone (assumed UTC). Returns ``None`` when the value is
    absent or unparseable so the caller can fall back to its default
    lookback window.
    """
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.endswith(("Z", "z")):
        raw = raw[:-1] + "+00:00"
    raw = _OVERLONG_FRACTION.sub(r"\1", raw)
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def resume_modified_since(
    watermark: str | None,
    *,
    default_since: datetime,
    overlap: timedelta = DEFAULT_WATERMARK_OVERLAP,
) -> datetime:
    """Compute the ``modifiedSince`` cursor for an incremental pull.

    When a watermark exists, resume from ``watermark - overlap``. When it
    is absent or unparseable (first run, empty tenant), fall back to
    ``default_since`` (the caller's ``now - N days`` window).
    """
    parsed = parse_watermark(watermark)
    if parsed is None:
        return default_since
    return parsed - overlap
