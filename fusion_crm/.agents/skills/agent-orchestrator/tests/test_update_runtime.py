"""Unit tests for `update_runtime()` and `refresh_tables()`.

These tests run against `tmp_path`-based mission folders so the live
`.agents/orchestration/<mission>/runtime.json` is never touched.
"""

from __future__ import annotations

import json


def test_update_runtime_creates_session_with_required_fields(launcher_module, make_args, mission_dir):
    args = make_args(mission=mission_dir, mode="background")
    prompt_path = mission_dir / "prompts" / "T-1.md"
    log_path = mission_dir / "logs" / "T-1.log"
    prompt_path.parent.mkdir()
    log_path.parent.mkdir()
    prompt_path.write_text("X", encoding="utf-8")

    launcher_module.update_runtime(args, mission_dir, mission_dir, "sess-1", prompt_path, log_path)

    payload = json.loads((mission_dir / "runtime.json").read_text(encoding="utf-8"))
    assert payload["mission_id"] == mission_dir.name
    assert "updated_at" in payload
    sessions = payload["sessions"]
    assert len(sessions) == 1
    session = sessions[0]
    for key in (
        "id", "role", "agent", "task_id", "linear_issue_id", "linear_issue_url",
        "linear_status", "linear_title", "status", "phase", "worktree",
        "branch", "last_activity", "needs_human", "risk", "current_note",
        "prompt_path", "log_path", "launch_mode",
    ):
        assert key in session, f"missing session key: {key}"


def test_update_runtime_deduplicates_session_by_id(launcher_module, make_args, mission_dir):
    args = make_args(mission=mission_dir, mode="background")
    prompt_path = mission_dir / "prompts" / "T-1.md"
    log_path = mission_dir / "logs" / "T-1.log"
    prompt_path.parent.mkdir()
    log_path.parent.mkdir()
    prompt_path.write_text("X", encoding="utf-8")

    launcher_module.update_runtime(args, mission_dir, mission_dir, "sess-1", prompt_path, log_path)
    launcher_module.update_runtime(args, mission_dir, mission_dir, "sess-1", prompt_path, log_path)
    launcher_module.update_runtime(args, mission_dir, mission_dir, "sess-2", prompt_path, log_path)

    payload = json.loads((mission_dir / "runtime.json").read_text(encoding="utf-8"))
    session_ids = sorted(s["id"] for s in payload["sessions"])
    assert session_ids == ["sess-1", "sess-2"], "sess-1 must dedupe; sess-2 must be appended"


def test_update_runtime_appends_handoff_entry(launcher_module, make_args, mission_dir):
    args = make_args(mission=mission_dir, mode="background", role="worker")
    prompt_path = mission_dir / "prompts" / "T-1.md"
    log_path = mission_dir / "logs" / "T-1.log"
    prompt_path.parent.mkdir()
    log_path.parent.mkdir()
    prompt_path.write_text("X", encoding="utf-8")

    launcher_module.update_runtime(args, mission_dir, mission_dir, "sess-1", prompt_path, log_path)

    payload = json.loads((mission_dir / "runtime.json").read_text(encoding="utf-8"))
    handoffs = payload["handoffs"]
    assert len(handoffs) == 1
    handoff = handoffs[0]
    for key in (
        "id", "created_at", "task_id", "linear_issue_id",
        "from_role", "from_agent", "to_role", "to_agent", "reason", "status",
    ):
        assert key in handoff, f"missing handoff key: {key}"
    assert handoff["from_role"] == "orchestrator"
    assert handoff["to_role"] == "worker"


def test_refresh_tables_renders_board_and_linear_sync(launcher_module, make_args, mission_dir):
    args = make_args(mission=mission_dir, mode="background", task_id="T-99")
    prompt_path = mission_dir / "prompts" / "T-99.md"
    log_path = mission_dir / "logs" / "T-99.log"
    prompt_path.parent.mkdir()
    log_path.parent.mkdir()
    prompt_path.write_text("X", encoding="utf-8")

    launcher_module.update_runtime(args, mission_dir, mission_dir, "sess-x", prompt_path, log_path)
    launcher_module.refresh_tables(mission_dir, mission_dir)

    board = (mission_dir / "board.md").read_text(encoding="utf-8")
    sync = (mission_dir / "linear-sync.md").read_text(encoding="utf-8")

    assert "| Task | Linear | Owner |" in board
    assert "T-99" in board
    assert "ENG-213" in board
    assert "| Task | Linear issue | Linear URL |" in sync
    assert "https://linear.app/x/y" in sync
