# Incident Log

Use this file to record failures, surprises, bad assumptions, and workflow friction during the mission.

## Incident Template

## INC-YYYYMMDD-NNN: Short title

Date:
Detected by:
Severity: low | medium | high | blocker
Area: planning | launch | worker | Linear | contract | ownership | integration | verification | release

### What happened

### Impact

### Root cause

### Immediate fix

### Durable lesson candidate

### Follow-up action

## INC-20260518-001: Local Salesforce callback used mock completion

Date: 2026-05-18
Detected by: user localhost pull failure
Severity: medium
Area: verification

### What happened

After the operator attempted local Salesforce reconnect, the manual Lead pull
still failed with `invalid_grant: expired access/refresh token`.

### Impact

The UI could report Salesforce as connected while every real pull/sync kept
using a dead refresh token.

### Root cause

The localhost callback page ignored the real Salesforce `code/state` query and
called the mock callback endpoint. The FastAPI OAuth callback never received
the real authorization code, so it never persisted a fresh `oauth_token`.
Separately, failed refresh did not mark the active OAuth credential as expired.

### Immediate fix

Forward the callback page to `/api/integrations/salesforce/callback` with the
original query string, and mark active Salesforce OAuth credentials `expired`
when Salesforce returns a reconnect-required auth failure.

### Durable lesson candidate

Any real OAuth callback page must pass through provider query parameters and
PKCE cookies to the backend callback. Mock callback helpers must stay isolated
to MSW/mock-only paths.

### Follow-up action

Complete a real Salesforce consent flow and then run the manual Lead pull.

## INC-20260518-002: Full repository gates expose existing debt

Date: 2026-05-18
Detected by: Codex stabilization review
Severity: medium
Area: verification

### What happened

The user-requested full verify loop did not become fully green even after the
current diff passed its focused gates. `mypy .` reports existing test typing
errors, `make test` fails on the tenant isolation Phase B fixture and existing
outreach/worker failures, and `alembic check` reports existing schema drift.

### Impact

The current credential/Salesforce package can be reviewed with focused passing
checks, but the repository cannot honestly be called fully verified. Future
agents could waste time rediscovering unrelated failures unless they are
tracked separately.

### Root cause

The repository's documented full loop includes checks that are broader than
the currently green CI-style `make verify` target. Existing tenant/test/alembic
debt predates this stabilization bundle.

### Immediate fix

Ran and recorded both the failing full checks and passing focused checks.
Fixed only fresh errors introduced by the current diff.

### Durable lesson candidate

Every stabilization report must distinguish current-diff acceptance gates from
repository-wide health gates and name known pre-existing blockers explicitly.

### Follow-up action

Create separate Linear/backlog items for full `mypy .`, full `make test`, and
Alembic drift cleanup before claiming full verify health.

## INC-20260519-001: Claude launch prompt swallowed by add-dir

Date: 2026-05-19T03:07:29.830009+00:00
Detected by: orchestrator
Severity: medium
Area: launch

### What happened

run_wave launched Claude with the prompt as a positional argument after --add-dir. The local Claude CLI treats --add-dir as variadic, swallowed the prompt as another directory, and exited with: Input must be provided either through stdin or as a prompt argument when using --print.

### Impact

Q1 first launch exited immediately with no report.

### Root cause

The launch adapter assumed --add-dir consumed exactly one argument.

### Immediate fix

Updated launch_commands.py so claude_command pipes the prompt through stdin and invokes claude --print.

### Durable lesson candidate

For Claude Code non-interactive workers, pipe prompts via stdin because --add-dir may be variadic.

### Follow-up action

Use status_wave after every launch. The failed Q1 runtime entry pid 10413 is
kept as incident evidence; the relaunched pid 12657 completed successfully and
wrote `reports/Q1.md`.

## INC-20260519-002: Wave R Linear issue mapping drift

Date: 2026-05-19
Detected by: orchestrator during Wave R launch sync
Severity: medium
Area: Linear

### What happened

The Wave R normalized-person-hint implementation was initially mapped to
`ENG-183`, but Linear `ENG-183` is `ops.inquiry`. The actual normalized hint
issue is `ENG-185`.

### Impact

`ENG-183` was briefly moved to In Progress and received a Wave R launch
comment that belonged to normalized hints.

### Root cause

Mission shorthand from the P2 implementation sequence did not match the final
Linear child issue numbering.

### Immediate fix

Updated R1/R2 mission files to map normalized hints and follow-up pipeline
planning to `ENG-185`, corrected board/goal/linear-sync records, and returned
`ENG-183` to Backlog with a correction comment.

### Durable lesson candidate

Before launching a new wave from a planning report, confirm the actual Linear
issue title for every issue identifier being moved.

### Follow-up action

Promote a mission-level lesson if another issue-mapping drift occurs.

## INC-20260519-003: Mission scaffold missing machine-check files

Date: 2026-05-19
Detected by: orchestrator during Wave S preflight
Severity: low
Area: planning

### What happened

`check_ownership.py` failed because the resumed mission folder did not contain
`ownership.yaml`. The current worker prompt generated by `run_wave.py` also
references `acceptance.md` and `verification.md`, which were absent from this
older mission folder.

### Impact

Wave S could have launched workers with broken context references and without
machine-readable ownership checks.

### Root cause

The mission folder was created before the current scaffold expectations were
fully aligned with `run_wave.py` and `check_ownership.py`.

### Immediate fix

Added mission-local `acceptance.md`, `verification.md`, and `ownership.yaml`,
then re-ran ownership checks for S1/S2/S3 with explicit file lists. Also fixed
the orchestrator helper's ruff S607 warning by resolving `git` with
`shutil.which(...)`, allowing `make verify` to pass.

### Durable lesson candidate

On mission resume, confirm scaffold files required by current launch/status
scripts exist before launching a new wave.

### Follow-up action

Consider adding a lightweight scaffold-health command to the orchestrator
scripts if this recurs.

## INC-20260519-004: Wave T workers stalled without report output

Date: 2026-05-19T05:16:14.635517+00:00
Detected by: orchestrator
Severity: medium
Area: launch

### What happened

T1/T2 Claude background workers launched at 2026-05-19T05:14:02Z stayed running with empty logs and no reports after multiple status checks; Codex stopped the hung processes before relaunching.

### Impact

Wave T did not progress during the first launch attempt; no product files or reports were written by T1/T2.

### Root cause

Likely worker CLI startup or non-streaming hang before report creation; exact cause unknown.

### Immediate fix

Stopped the stale T1/T2 worker processes and prepared a relaunch with the same ownership boundaries.

### Durable lesson candidate

If background workers show no log output and no report after repeated status checks, inspect child processes before waiting indefinitely and record the launch anomaly.

### Follow-up action

Consider adding heartbeat or timeout metadata to run_wave/status_wave.

## INC-20260519-005: Wave T Codex workers could not finish reports

Date: 2026-05-19T05:22:01.617387+00:00
Detected by: orchestrator
Severity: high
Area: launch

### What happened

After relaunching T1/T2 with codex workers, T1 edited its owned code files but no T1 report was produced; T2 hit repeated sandbox/patch rejections while writing reports/T2.md and remained running without a report. Codex orchestrator stopped the stuck processes for review and recovery.

### Impact

Wave T implementation changes exist locally but worker reports are missing; orchestrator must review actual diff and create recovery evidence before accepting the wave.

### Root cause

Background codex exec sandbox treated mission report patch writes as outside project for worker sessions; worker fallback shell write did not complete.

### Immediate fix

Stopped stuck T1/T2 codex processes and moved to orchestrator-owned recovery review/verification.

### Durable lesson candidate

For background codex workers in this repo, verify report write capability early or provide a report-writing fallback in run_wave before starting implementation work.

### Follow-up action

Patch run_wave/status protocol to use unique logs and a report heartbeat/write preflight before future codex workers.

