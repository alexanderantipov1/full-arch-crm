"""Salesforce SOQL response shape.

Salesforce returns a JSON envelope with ``totalSize``, ``done``, and a
heterogeneous ``records`` list whose fields are query-dependent. We model the
envelope tightly and let callers cast individual records to whatever shape
they expect.
"""

from __future__ import annotations

from typing import Any, TypedDict


class SoqlResult(TypedDict):
    """Top-level shape of a Salesforce SOQL HTTP response."""

    totalSize: int
    done: bool
    records: list[dict[str, Any]]
