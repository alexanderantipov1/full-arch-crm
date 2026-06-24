"""Aggregate analytics export tools.

ENG-281 V1 allows CSV export for aggregate analytics results only. XLSX,
scheduled reports, row-level exports, PHI, and raw provider payloads remain
disabled.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import UTC, datetime

from packages.audit.service import AuditService
from packages.core.exceptions import ValidationError

from .analytics_tools import (
    AnalyticsQueryId,
    analytics_query_metadata,
    canonical_analytics_query_id,
    canonical_analytics_query_literal,
    run_analytics_query,
)
from .base import ToolContext

_ALLOWED_EXPORT_DATA_CLASSES = frozenset({"ops", "integration_metadata", "billing"})


async def export_analytics_csv(
    ctx: ToolContext,
    *,
    query_id: AnalyticsQueryId,
    params: dict[str, object] | None = None,
    filename: str | None = None,
) -> dict:
    """Export an approved aggregate analytics result as CSV."""
    canonical_query_id = canonical_analytics_query_id(query_id)
    execution_params = _execution_params(params or {})
    execution = await run_analytics_query(
        ctx,
        query_id=canonical_analytics_query_literal(canonical_query_id),
        params=execution_params,
    )
    _validate_exportable_execution(execution)

    csv_content, exported_rows = analytics_execution_to_csv(execution)
    resolved_filename = _csv_filename(filename, canonical_query_id)
    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="export_analytics_csv",
        extra={
            "query_id": execution["query_id"],
            "read_model_id": execution["read_model_id"],
            "format": "csv",
            "row_count": exported_rows,
            "data_classes": execution["data_classes"],
            "billing_included": "billing" in execution["data_classes"],
            "filename": resolved_filename,
        },
    )

    return {
        "export": {
            "format": "csv",
            "content_type": "text/csv",
            "filename": resolved_filename,
            "content": csv_content,
            "row_count": exported_rows,
            "scheduled": False,
            "xlsx_available": False,
        },
        "source": {
            "query_id": execution["query_id"],
            "read_model_id": execution["read_model_id"],
            "data_classes": execution["data_classes"],
            "definition_versions": execution["definition_versions"],
            "filters": execution["filters"],
            "warnings": execution["warnings"],
        },
    }


async def save_analytics_report_definition(
    ctx: ToolContext,
    *,
    name: str,
    query_id: AnalyticsQueryId,
    params: dict[str, object] | None = None,
) -> dict:
    """Return an audited saved-report definition artifact.

    V1 creates a portable definition object for approved aggregate CSV reports.
    It does not create a persisted database row or schedule delivery.
    """
    clean_name = name.strip()
    if not clean_name:
        raise ValidationError("report name is required")
    if len(clean_name) > 120:
        raise ValidationError("report name must be 120 characters or fewer")

    canonical_query_id = canonical_analytics_query_id(query_id)
    metadata = analytics_query_metadata(canonical_query_id)
    metadata_data_classes = metadata.get("data_classes")
    if not isinstance(metadata_data_classes, list):
        raise ValidationError("report data classes are missing")
    data_classes = [str(value) for value in metadata_data_classes]
    if not _data_classes_exportable(data_classes):
        raise ValidationError(
            "report data classes are not exportable",
            details={"query_id": canonical_query_id, "data_classes": data_classes},
        )

    execution_params = _execution_params(params or {})
    definition = {
        "id": _definition_id(ctx.tenant_id, clean_name, canonical_query_id, execution_params),
        "name": clean_name,
        "query_id": canonical_query_id,
        "read_model_id": metadata["read_model_id"],
        "params": execution_params,
        "output_level": "aggregate",
        "format": "csv",
        "data_classes": data_classes,
        "scheduled": False,
        "xlsx_available": False,
        "row_level": False,
        "created_at": datetime.now(tz=UTC).isoformat(),
    }

    audit = AuditService(ctx.session)
    await audit.record_tool_call(
        principal=ctx.principal,
        tool_name="save_analytics_report_definition",
        extra={
            "definition_id": definition["id"],
            "query_id": canonical_query_id,
            "read_model_id": definition["read_model_id"],
            "format": "csv",
            "param_keys": sorted(execution_params.keys()),
            "data_classes": data_classes,
            "billing_included": "billing" in data_classes,
        },
    )
    return {"definition": definition}


def analytics_execution_to_csv(execution: dict[str, object]) -> tuple[str, int]:
    """Convert an aggregate analytics execution envelope into CSV."""
    result = execution.get("result")
    if not isinstance(result, dict):
        raise ValidationError("analytics execution result is not exportable")

    rows: list[dict[str, object]] = []
    for section, value in result.items():
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                rows.append(
                    {
                        "section": section,
                        "key": item.get("key", ""),
                        "label": item.get("label", ""),
                        "count": item.get("count", ""),
                        "metric": "",
                        "value": "",
                    }
                )
        else:
            rows.append(
                {
                    "section": "metric",
                    "key": "",
                    "label": "",
                    "count": "",
                    "metric": section,
                    "value": "" if value is None else value,
                }
            )

    stream = io.StringIO()
    writer = csv.DictWriter(
        stream,
        fieldnames=["section", "key", "label", "count", "metric", "value"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue(), len(rows)


def _validate_exportable_execution(execution: dict[str, object]) -> None:
    if execution.get("aggregation_level") != "aggregate":
        raise ValidationError("only aggregate analytics exports are allowed")
    data_classes = execution.get("data_classes")
    if not isinstance(data_classes, list):
        raise ValidationError("analytics execution data classes are missing")
    clean_data_classes = [str(value) for value in data_classes]
    if not _data_classes_exportable(clean_data_classes):
        raise ValidationError(
            "analytics data classes are not exportable",
            details={"data_classes": clean_data_classes},
        )


def _data_classes_exportable(data_classes: list[str]) -> bool:
    return all(data_class in _ALLOWED_EXPORT_DATA_CLASSES for data_class in data_classes)


def _execution_params(params: dict[str, object]) -> dict[str, object]:
    blocked = {"format", "filename", "export"}
    return {key: value for key, value in params.items() if key not in blocked}


def _csv_filename(filename: str | None, query_id: str) -> str:
    if filename is None or not filename.strip():
        return f"{query_id.replace('.', '-')}.csv"
    clean = filename.strip()
    if "/" in clean or "\\" in clean:
        raise ValidationError("filename must not contain path separators")
    return clean if clean.endswith(".csv") else f"{clean}.csv"


def _definition_id(
    tenant_id: object,
    name: str,
    query_id: str,
    params: dict[str, object],
) -> str:
    payload = json.dumps(
        {
            "tenant_id": str(tenant_id),
            "name": name,
            "query_id": query_id,
            "params": params,
        },
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"report_def_{digest}"
