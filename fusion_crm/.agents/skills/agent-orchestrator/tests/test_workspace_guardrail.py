"""Unit tests for --workspace flag and --workspace self guardrail rules."""

# ruff: noqa: S603, S607
# Tests intentionally invoke `git` via subprocess against tmp repos.

from __future__ import annotations

import pytest


def _args_with(make_args, **overrides):
    base = dict(workspace=None, allow_self_execute=False, scope=None, branch_base="main")
    base.update(overrides)
    return make_args(**base)


def test_resolve_default_workspace_for_worker(launcher_module):
    assert launcher_module._resolve_default_workspace("worker") == "worktree"


def test_resolve_default_workspace_for_verifier(launcher_module):
    assert launcher_module._resolve_default_workspace("verifier") == "self"


def test_resolve_default_workspace_for_integrator(launcher_module):
    assert launcher_module._resolve_default_workspace("integrator") == "self"


def test_resolve_default_workspace_for_reviewer(launcher_module):
    assert launcher_module._resolve_default_workspace("reviewer") == "self"


def test_guardrail_refuses_self_without_allow_flag(launcher_module, make_args):
    args = _args_with(make_args, workspace="self", scope="bugfix")
    with pytest.raises(SystemExit, match="--allow-self-execute"):
        launcher_module._enforce_self_execute_guardrail(args, "short prompt")


def test_guardrail_refuses_self_above_threshold(launcher_module, make_args):
    args = _args_with(make_args, workspace="self", allow_self_execute=True, scope="bugfix")
    huge_prompt = "x" * 5001
    with pytest.raises(SystemExit, match="prompt is 5001 chars"):
        launcher_module._enforce_self_execute_guardrail(args, huge_prompt)


def test_guardrail_refuses_self_without_scope(launcher_module, make_args):
    args = _args_with(make_args, workspace="self", allow_self_execute=True, scope=None)
    with pytest.raises(SystemExit, match="--scope"):
        launcher_module._enforce_self_execute_guardrail(args, "tiny")


def test_guardrail_refuses_self_with_scope_none(launcher_module, make_args):
    args = _args_with(make_args, workspace="self", allow_self_execute=True, scope="none")
    with pytest.raises(SystemExit, match="--scope"):
        launcher_module._enforce_self_execute_guardrail(args, "tiny")


def test_guardrail_accepts_self_with_all_preconditions(launcher_module, make_args):
    args = _args_with(make_args, workspace="self", allow_self_execute=True, scope="bugfix")
    # Should not raise.
    launcher_module._enforce_self_execute_guardrail(args, "tiny prompt")


def test_guardrail_accepts_exact_threshold(launcher_module, make_args):
    args = _args_with(make_args, workspace="self", allow_self_execute=True, scope="tiny")
    # 5000 is the exact threshold; > rejects, == accepts.
    launcher_module._enforce_self_execute_guardrail(args, "x" * 5000)


def test_record_scope_marker_writes_decision_log(launcher_module, make_args, mission_spec_dir):
    args = _args_with(
        make_args,
        workspace="self",
        allow_self_execute=True,
        scope="bugfix",
        task_id="T-1",
        linear_id="ENG-225",
        linear_url="https://linear.app/x/ENG-225",
        reason="Tiny: fix typo in docstring",
    )
    launcher_module._record_scope_marker(mission_spec_dir, args, prompt_size=42)
    log = (mission_spec_dir / "decision-log.md").read_text(encoding="utf-8")
    assert "Scope: bugfix" in log
    assert "T-1" in log
    assert "ENG-225" in log
    assert "42 chars" in log


def _init_repo(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit",
         "--allow-empty", "-m", "init", "-q"],
        cwd=tmp_path,
        check=True,
    )


def test_preflight_base_passes_on_clean_tree(tmp_path, launcher_module):
    """Preflight on a freshly-init'd repo with no changes should not raise."""
    _init_repo(tmp_path)
    # Should not raise, in either mode.
    launcher_module._preflight_base(tmp_path, "main")
    launcher_module._preflight_base(tmp_path, "main", require_clean=True)


def test_preflight_base_warns_but_allows_dirty_tree_by_default(tmp_path, launcher_module, capsys):
    """A dirty canonical checkout must NOT block: worktrees are isolated."""
    _init_repo(tmp_path)
    (tmp_path / "dirty.txt").write_text("change\n")
    # Default mode: no raise, just a warning on stderr.
    launcher_module._preflight_base(tmp_path, "main")
    err = capsys.readouterr().err
    assert "dirty.txt" in err
    assert "uncommitted/untracked" in err


def test_preflight_base_refuses_dirty_tree_when_require_clean(tmp_path, launcher_module):
    _init_repo(tmp_path)
    (tmp_path / "dirty.txt").write_text("change\n")
    with pytest.raises(SystemExit, match="uncommitted changes"):
        launcher_module._preflight_base(tmp_path, "main", require_clean=True)
