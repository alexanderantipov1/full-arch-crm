"""Unit tests for `build_worker_prompt()`."""

from __future__ import annotations


def test_prompt_includes_required_fields(launcher_module, make_args):
    args = make_args(
        runtime="codex",
        role="worker",
        task_id="T-42",
        linear_id="ENG-213",
        linear_url="https://linear.app/x/y",
        linear_title="Sample task",
    )
    rendered = launcher_module.build_worker_prompt(args, "sess-abc", "do the work")

    for needle in (
        "Fusion CRM worker agent",
        "Task id: T-42",
        "Linear issue: ENG-213",
        "Linear URL: https://linear.app/x/y",
        "Linear title: Sample task",
        "Runtime: codex",
        "Session id: sess-abc",
        "do the work",
    ):
        assert needle in rendered, f"missing in rendered prompt: {needle!r}"


def test_prompt_mentions_mission_runtime_files(launcher_module, make_args, tmp_path):
    args = make_args(mission=tmp_path / "mission")
    rendered = launcher_module.build_worker_prompt(args, "sess-id", "do x")

    # The prompt must instruct the worker to update runtime.json and runlog.md and
    # write the final report under reports/.
    assert "runtime.json" in rendered
    assert "runlog.md" in rendered
    assert "reports/" in rendered


def test_prompt_uses_role_in_header(launcher_module, make_args):
    args = make_args(role="verifier")
    rendered = launcher_module.build_worker_prompt(args, "s", "p")
    assert "Fusion CRM verifier agent" in rendered


def test_prompt_supports_reviewer_role(launcher_module, make_args):
    args = make_args(role="reviewer")
    rendered = launcher_module.build_worker_prompt(args, "s", "review the mission")
    assert "Fusion CRM reviewer agent" in rendered
    assert "review the mission" in rendered
