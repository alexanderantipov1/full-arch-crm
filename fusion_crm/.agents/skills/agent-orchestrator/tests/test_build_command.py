"""Unit tests for `build_command()`.

The launcher emits a different command list per runtime. These tests pin the
exact flag surface and assert that the deprecated `--ask-for-approval` is
gone and that `--codex-bypass-approvals` is opt-in.
"""

from __future__ import annotations


def test_codex_command_default_omits_deprecated_flag(launcher_module, make_args, tmp_path):
    """Codex command must not contain `--ask-for-approval` (deprecated)."""
    args = make_args(runtime="codex", codex_bypass_approvals=False)
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("PROMPT_BODY", encoding="utf-8")
    cmd = launcher_module.build_command(args, prompt_path)

    assert cmd[0] == "codex"
    assert cmd[1] == "exec"
    assert "--ask-for-approval" not in cmd
    assert "--dangerously-bypass-approvals-and-sandbox" not in cmd
    assert "--cd" in cmd
    assert "--sandbox" in cmd
    assert cmd[-1] == "PROMPT_BODY"


def test_codex_command_with_bypass_appends_dangerous_flag(launcher_module, make_args, tmp_path):
    """Opt-in flag must add `--dangerously-bypass-approvals-and-sandbox` before the prompt."""
    args = make_args(runtime="codex", codex_bypass_approvals=True)
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("PROMPT_BODY", encoding="utf-8")
    cmd = launcher_module.build_command(args, prompt_path)

    assert "--dangerously-bypass-approvals-and-sandbox" in cmd
    # The dangerous flag must come before the prompt argument.
    dangerous_idx = cmd.index("--dangerously-bypass-approvals-and-sandbox")
    prompt_idx = cmd.index("PROMPT_BODY")
    assert dangerous_idx < prompt_idx


def test_codex_command_with_full_auto_alias_appends_dangerous_flag(launcher_module, make_args, tmp_path):
    """`--codex-full-auto` is the orchestrator alias for non-interactive Codex workers."""
    args = make_args(runtime="codex", codex_full_auto=True)
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("PROMPT_BODY", encoding="utf-8")
    cmd = launcher_module.build_command(args, prompt_path)

    assert "--dangerously-bypass-approvals-and-sandbox" in cmd
    assert "--full-auto" not in cmd


def test_codex_sandbox_value_passed_through(launcher_module, make_args, tmp_path):
    """`--sandbox <value>` must come from `args.codex_sandbox`."""
    args = make_args(runtime="codex", codex_sandbox="read-only")
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("X", encoding="utf-8")
    cmd = launcher_module.build_command(args, prompt_path)

    sandbox_idx = cmd.index("--sandbox")
    assert cmd[sandbox_idx + 1] == "read-only"


def test_claude_command_shape(launcher_module, make_args, tmp_path):
    """Claude command keeps `-p --permission-mode <mode> <prompt>`."""
    args = make_args(runtime="claude-code", claude_permission_mode="acceptEdits")
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("PROMPT_CC", encoding="utf-8")
    cmd = launcher_module.build_command(args, prompt_path)

    assert cmd == ["claude", "-p", "--permission-mode", "acceptEdits", "PROMPT_CC"]


def test_unknown_runtime_raises(launcher_module, make_args, tmp_path):
    """Unsupported runtime must raise SystemExit early."""
    import pytest

    args = make_args(runtime="copilot")
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("X", encoding="utf-8")
    with pytest.raises(SystemExit):
        launcher_module.build_command(args, prompt_path)


def test_codex_cd_uses_resolved_worktree(launcher_module, make_args, tmp_path):
    """`--cd <dir>` must come from a resolved worktree path."""
    args = make_args(runtime="codex", worktree=str(tmp_path))
    prompt_path = tmp_path / "prompt.md"
    prompt_path.write_text("X", encoding="utf-8")
    cmd = launcher_module.build_command(args, prompt_path)

    cd_idx = cmd.index("--cd")
    assert cmd[cd_idx + 1] == str(tmp_path.resolve())
