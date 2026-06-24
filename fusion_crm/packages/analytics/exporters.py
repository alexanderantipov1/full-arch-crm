"""Pure tabular serializers for analytics exports (ENG-508).

Format-only layer: turn already-shaped ``ExportTable`` rows into CSV or XLSX
bytes. It holds **no** analytics logic and issues **no** queries — the
``AnalyticsExportService`` shapes a page DTO into tables and hands them here, so
an export is byte-for-byte the on-screen page's numbers for the same filters.

Design rules:

* ``openpyxl`` is imported lazily inside :func:`to_xlsx` so the CSV path (and
  every importer of this module) works even when the optional native
  dependency is absent.
* A single value formatter is shared by both writers, so CSV and XLSX render
  ``None`` (the "—" of the UI), datetimes, UUIDs, and money identically.
* Output is bounded: more than :data:`EXPORT_MAX_ROWS` data rows across all
  tables raises rather than silently truncating a financial export.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from packages.core.exceptions import ValidationError

# Defensive ceiling on total data rows in one export. The fact-backed pages are
# already small (funnel = 8 rows, cohorts = a handful of months), so this only
# guards against a pathological breakdown dimension; it never trims a normal
# page. Exceeding it raises — a truncated revenue export is worse than none.
EXPORT_MAX_ROWS = 50_000


@dataclass(frozen=True)
class ExportTable:
    """One titled grid: a header row plus data rows of scalar cells.

    ``rows`` cells are raw Python scalars (``None`` / ``str`` / ``int`` /
    ``float`` / ``UUID`` / ``datetime``); :func:`_format_cell` normalises them
    at write time, so callers never pre-stringify.
    """

    name: str
    headers: list[str]
    rows: list[list[object]] = field(default_factory=list)


def _format_cell(value: object) -> object:
    """Normalise one cell for output (shared by CSV + XLSX).

    ``None`` → empty string (the export equivalent of the UI "—"); ``datetime``
    → ISO-8601; ``UUID`` → str; numbers pass through unchanged so a spreadsheet
    keeps them numeric. Everything else falls back to ``str``.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        # bool is an int subclass — keep it as a readable token, not 0/1.
        return "true" if value else "false"
    if isinstance(value, int | float):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return str(value)


def _assert_within_cap(tables: list[ExportTable]) -> None:
    total = sum(len(table.rows) for table in tables)
    if total > EXPORT_MAX_ROWS:
        raise ValidationError(
            "analytics export exceeds the row cap",
            details={"rows": total, "max_rows": EXPORT_MAX_ROWS},
        )


def to_csv(tables: list[ExportTable]) -> bytes:
    """Serialize tables to UTF-8 CSV bytes.

    Multiple tables are stacked into one file, each preceded by a ``# <name>``
    title row and followed by a blank separator line, so a single CSV carries a
    whole multi-section page (e.g. Executive funnel + widgets + summary).
    """
    _assert_within_cap(tables)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    for index, table in enumerate(tables):
        if index > 0:
            writer.writerow([])
        writer.writerow([f"# {table.name}"])
        writer.writerow(table.headers)
        for row in table.rows:
            writer.writerow([_format_cell(cell) for cell in row])
    return buffer.getvalue().encode("utf-8")


def to_xlsx(tables: list[ExportTable]) -> bytes:
    """Serialize tables to XLSX bytes — one worksheet per table.

    ``openpyxl`` is imported here (not at module top) so importing this module —
    and the CSV path — never requires the optional native dependency.
    """
    _assert_within_cap(tables)
    try:
        from openpyxl import Workbook
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch
        raise ValidationError(
            "XLSX export requires the optional 'openpyxl' dependency",
            details={"format": "xlsx"},
        ) from exc

    workbook = Workbook()
    workbook.remove(workbook.active)
    used_titles: set[str] = set()
    for table in tables:
        worksheet = workbook.create_sheet(title=_sheet_title(table.name, used_titles))
        worksheet.append(table.headers)
        for row in table.rows:
            worksheet.append([_format_cell(cell) for cell in row])

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _sheet_title(name: str, used: set[str]) -> str:
    """Excel sheet titles cap at 31 chars, forbid ``[]:*?/\\`` and must be unique."""
    cleaned = "".join("_" if ch in '[]:*?/\\' else ch for ch in name)[:31] or "Sheet"
    title = cleaned
    suffix = 1
    while title.lower() in used:
        suffix += 1
        tag = f"_{suffix}"
        title = cleaned[: 31 - len(tag)] + tag
    used.add(title.lower())
    return title
