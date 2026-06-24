"""Tests for aggregate analytics export helpers."""

from __future__ import annotations

import pytest

from packages.core.exceptions import ValidationError
from packages.tools.export_tools import analytics_execution_to_csv


def _execution() -> dict[str, object]:
    return {
        "query_id": "lead_conversion_funnel.v1",
        "read_model_id": "lead_conversion",
        "aggregation_level": "aggregate",
        "data_classes": ["ops", "integration_metadata"],
        "definition_versions": {"lead_source": "v1"},
        "filters": {"limit": 10},
        "warnings": [],
        "result": {
            "lead_status": [
                {"key": "new", "label": "New", "count": 4},
                {"key": "booked", "label": "Booked", "count": 2},
            ],
            "pipeline_total": 6,
        },
    }


def test_analytics_execution_to_csv_flattens_buckets_and_metrics() -> None:
    content, row_count = analytics_execution_to_csv(_execution())

    assert row_count == 3
    assert "section,key,label,count,metric,value" in content
    assert "lead_status,new,New,4,," in content
    assert "metric,,,,pipeline_total,6" in content


def test_analytics_execution_to_csv_rejects_missing_result() -> None:
    with pytest.raises(ValidationError):
        analytics_execution_to_csv({"query_id": "lead_conversion_funnel.v1"})
