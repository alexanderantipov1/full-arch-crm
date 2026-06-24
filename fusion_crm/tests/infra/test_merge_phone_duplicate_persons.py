"""Unit tests for the merge decision logic (ENG-463).

The destructive repoint (``--apply``) is exercised by a DB-backed
integration test (TODO, mirror tests/integration/test_merge_split_lead_persons.py)
before any production run; here we lock the pure name-match + survivor
policy that decides WHICH persons merge and which one wins.
"""

from __future__ import annotations

import importlib.util
import uuid
from datetime import UTC, datetime
from pathlib import Path

_SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "scripts"
    / "merge_phone_duplicate_persons.py"
)
_spec = importlib.util.spec_from_file_location("merge_phone_dups", _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_name_key_is_order_insensitive() -> None:
    # "Fredrick Dixon" and "Dixon Fredrick" must collapse to one key.
    assert mod._name_key("Fredrick", "Dixon", None) == mod._name_key(
        None, None, "Dixon Fredrick"
    )
    assert mod._name_key("Fredrick", "Dixon", None) == ("dixon", "fredrick")


def test_name_key_empty_when_no_name() -> None:
    assert mod._name_key(None, None, None) == ()


def _member(**kw: object) -> dict[str, object]:
    base = {
        "person_uid": uuid.uuid4(),
        "has_cs": False,
        "has_email": False,
        "id_count": 1,
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    base.update(kw)
    return base


def test_survivor_prefers_carestack_then_email_then_idcount() -> None:
    poor = _member()
    has_email = _member(has_email=True)
    has_cs = _member(has_cs=True)
    assert mod._pick_survivor([poor, has_email]) is has_email
    assert mod._pick_survivor([has_email, has_cs]) is has_cs
    rich = _member(id_count=9)
    assert mod._pick_survivor([poor, rich]) is rich


def test_survivor_tiebreak_earliest_created_at() -> None:
    older = _member(created_at=datetime(2025, 1, 1, tzinfo=UTC))
    newer = _member(created_at=datetime(2026, 6, 1, tzinfo=UTC))
    assert mod._pick_survivor([newer, older]) is older
