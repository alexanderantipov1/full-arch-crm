"""ENG-516 (B2.3) — Marketing Performance derived-metric layer (pure unit).

Covers ``AnalyticsPagesService._marketing_group_out`` — the per-group ROI /
cost-per-stage composition over a ``MarketingGroupRow``. Pure (no DB): the
real-Postgres aggregation is exercised in ``tests/integration/
test_analytics_pages.py``. The cardinal rule: a metric with no (or a
missing-spend) denominator is ``None``, never a fabricated 0.
"""

from __future__ import annotations

import pytest

from packages.analytics.metrics_service import AnalyticsPagesService
from packages.analytics.queries import MarketingGroupRow


def _row(**overrides: object) -> MarketingGroupRow:
    base: dict[str, object] = {
        "group_id": None,
        "group_label": "Spring Implants",
        "spend": 200.0,
        "leads": 4,
        "consults": 2,
        "shows": 1,
        "surgeries": 1,
        "revenue": 10000.0,
        "collected": 6000.0,
    }
    base.update(overrides)
    return MarketingGroupRow(**base)  # type: ignore[arg-type]


def test_group_out_derived_metrics_connected() -> None:
    out = AnalyticsPagesService._marketing_group_out(_row(), connected=True)
    assert out.spend == pytest.approx(200.0)
    assert out.cost_per_lead == pytest.approx(50.0)  # 200 / 4
    assert out.cost_per_consult == pytest.approx(100.0)  # 200 / 2
    assert out.cost_per_show == pytest.approx(200.0)  # 200 / 1
    assert out.cost_per_surgery == pytest.approx(200.0)
    assert out.roi == pytest.approx(50.0)  # 10000 / 200


def test_group_out_spend_none_when_not_connected() -> None:
    out = AnalyticsPagesService._marketing_group_out(_row(), connected=False)
    # No spend source connected → spend + every spend-derived metric is None.
    assert out.spend is None
    assert out.roi is None
    assert out.cost_per_lead is None
    assert out.cost_per_consult is None
    # Outcome counts + revenue still surface honestly.
    assert out.leads == 4
    assert out.revenue == pytest.approx(10000.0)
    assert out.collected == pytest.approx(6000.0)


def test_group_out_div_by_zero_to_none() -> None:
    out = AnalyticsPagesService._marketing_group_out(
        _row(leads=0, consults=0, shows=0, surgeries=0, spend=0.0, revenue=0.0),
        connected=True,
    )
    assert out.cost_per_lead is None
    assert out.cost_per_consult is None
    assert out.roi is None  # 0 / 0 → None, not an error
