# ENG-550 — worker report (orchestrator-executed)

- Task: ENG-550 (child of ENG-541) — wire + run on-demand Cloud Run Job to replay identity matches on prod.
- Linear: https://linear.app/fusion-dental-implants/issue/ENG-550 — Done.
- Role/agent: orchestrator (claude-code), inline. Codex cross-review (PASS, reports/ENG-550-codex-review.md).
- Branch/PR: eduardk/eng-550-prod-identity-replay-job → PR #203 (squash-merged c823cd6).
- Date: 2026-06-21.

## What changed
- `infra/scripts/deploy_cloud_run.sh`: added on-demand `fusion-job-identity-replay` (ENG-510 pattern, default dry-run; live via explicit `--args` override). +23 lines. No new secret/env/scheduler/migration/model change.

## Prod execution
1. Provisioned the Job surgically (single idempotent `gcloud run jobs deploy`, pinned to validated image fusion-api:c823cd6, sibling-mirrored SA/vpc/env/secrets). No service redeploy.
2. PROD dry-run (f9ktj): scanned 1328 / would_merge 178 / stay_open 1144 / skip 6 / merged_applied 0 (read-only).
3. PROD LIVE (clx2m): merged_applied **178**, leads_reassigned **163**, 0 errors.
4. Verify dry-run (2cffx): scanned 1150 (−178), would_merge **0**, stay_open 1144 — idempotent, drained.

## Verification
- bash -n on deploy script: OK. Codex cross-review: PASS.
- In-band data verification via before/after dry-run counts (above). No errors in any execution; all containers exit(0).

## Risks / notes
- 1144 candidates remain `open` by design (genuinely ambiguous phone_only/email_only, different names) — surfaced on the card per ENG-542, not auto-merged.
- Reversible: append-only `identity.merge_event`; companion un-merge `infra/scripts/split_wrong_merged_persons.py` (ENG-311).
- No PHI in logs (DTO/CLI uid-only per ENG-544 fix).

## Do-not-merge / follow-ups
- None outstanding for ENG-550. Follow-up (separate, structural): ENG-341 (drop global UNIQUE phone/email).
