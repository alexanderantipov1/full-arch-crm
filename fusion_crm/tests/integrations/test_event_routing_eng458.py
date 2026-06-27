"""Channel team-qualification for per-location routing (ENG-458).

``_qualify_channel`` prefixes a bare rule channel name with the resolved team
(``scheduls`` -> ``el-dorado/scheduls``) so one rule serves every clinic. It
leaves already-qualified names, resolved ids, and team-less emits untouched.
"""

from __future__ import annotations

from packages.integrations.chat.event_service import _qualify_channel


def test_no_team_leaves_bare_name_unchanged() -> None:
    assert _qualify_channel("scheduls", None) == "scheduls"
    assert _qualify_channel("scheduls", "") == "scheduls"


def test_team_prefixes_bare_name() -> None:
    assert _qualify_channel("scheduls", "el-dorado") == "el-dorado/scheduls"


def test_already_qualified_is_not_double_prefixed() -> None:
    assert _qualify_channel("galleria/scheduls", "el-dorado") == "galleria/scheduls"


def test_resolved_id_is_left_untouched() -> None:
    # A 26-char id must never be turned into ``team/<id>``.
    resolved = "abcdefghijklmnopqrstuvwxyz"  # 26 chars
    assert _qualify_channel(resolved, "el-dorado") == resolved
