# Incidents

- 2026-05-20T04:33:18Z | ENG-190 | Blocked: codex background launch pid 79820 exited immediately and wrote an empty log. Retrying through claude-code runtime.
- 2026-05-20T04:34:44Z | ENG-190 | Blocked: claude-code background launch pid 83411 exited immediately and wrote an empty log. Manual codex exec recovery started with pid 86139.
- 2026-05-20T04:34:44Z | ENG-190 | Contract drift: launch_worker.py uses deprecated `codex exec --ask-for-approval`; current codex CLI rejected that flag. Needs follow-up launcher fix.
- 2026-05-20T04:35:25Z | ENG-190 | Blocked: manual background codex exec pid 86139 exited immediately with empty log. Foreground codex exec session 12920 is running.
- 2026-05-20T04:49:08Z | ENG-190 | Foreground worker completed code changes but could not write `.agents` report/runtime directly; Orchestrator terminated the stuck reporting process and wrote the final report after independent verification.
