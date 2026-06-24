# Lessons Learned

Use this file for accepted reusable rules derived from incidents.

## Lesson Template

## LES-YYYYMMDD-NNN: Short rule

Source incident:
Applies to:
Rule:
Protocol/template/script update:
Verification:
Status: proposed | accepted | superseded

## LES-20260519-001: Pipe Claude prompts through stdin

Source incident: INC-20260519-001
Applies to: Claude Code non-interactive worker launches.
Rule: Launch Claude Code workers with the prompt piped through stdin when
using `--print`; do not rely on a trailing positional prompt after
`--add-dir`, because the local CLI can treat `--add-dir` as variadic.
Protocol/template/script update: `launch_commands.py` was updated before the
successful Q1 relaunch to pipe the prompt through stdin.
Verification: Q1 relaunch pid 12657 completed and wrote `reports/Q1.md`.
Status: accepted

## LES-20260519-002: Preflight worker report writes under `.agents`

Source incident: INC-20260519-005
Applies to: Codex background worker launches that must write mission reports.
Rule: Before launching a Codex background worker against a mission folder,
verify the worker mode can create or update its assigned `reports/<task>.md`
path under `.agents/**`. If the preflight fails, do not start product edits
with that worker mode; use a mode with write access or assign the report write
to the orchestrator explicitly.
Protocol/template/script update: pending follow-up to `run_wave.py` /
`status_wave.py`.
Verification: Wave T required orchestrator recovery reports because T1/T2
could not write reports from background Codex worker sessions.
Status: accepted
