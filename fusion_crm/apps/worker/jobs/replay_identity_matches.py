"""ENG-544 — replay open identity match candidates under the CURRENT policy.

The old field-level name rule left a large backlog of ``identity.match_candidate``
rows ``open`` (phone or email matched, but the name looked incompatible) and a
matching population of lead-created duplicate persons. ENG-543 replaced the name
rule with word-level subset compatibility, so many of those pairs are now a
clean Tier-1 auto-accept. This job walks every OPEN candidate and re-evaluates
it through :meth:`IdentityService.replay_open_match_candidate`, which reuses the
SAME :func:`packages.identity.service._evaluate_match_policy` the live resolver
uses — it does NOT re-implement matching.

Decision per candidate:

* ``would_merge`` — the current policy yields a single Tier-1 auto-accept whose
  target is exactly the recorded candidate person. The lead duplicate
  (``merged``) collapses into the existing canonical person (``survivor``).
* ``would_stay_open`` — still genuinely ambiguous (multiple Tier-1 candidates, a
  real name disagreement, or an auto-accept to a different person). Untouched.
* ``skipped`` — no current match (shared identifier gone, a person missing, or
  an ENG-309 DOB/SSN hard veto).

**``dry_run`` is the DEFAULT and mutates NOTHING** — it produces counts and a
representative sample (including the Patrick Newton acceptance pair) so the
operator can sanity-check before any live pass. The LIVE pass (``dry_run=False``)
goes through ``IdentityService.record_merge`` (append-only ``merge_event``),
moves the merged person's source links onto the survivor, marks the candidate
``accepted``, and re-points ``ops.lead`` rows via ``OpsService.reassign_leads``.
Every merge is reversible (append-only model) and audited.

On-demand only — NO cron entry. Re-running is safe: decided rows drop out of the
``status='open'`` work-list, so a second pass resumes from what is left.

Usage (local, dry-run is default):
    python -m apps.worker.jobs.replay_identity_matches [--tenant-id UUID] [--limit N]
    python -m apps.worker.jobs.replay_identity_matches --live        # mutate (operator-only)

Usage (enqueue):
    await pool.enqueue_job("replay_identity_matches", tenant_id="<uuid>", dry_run=True)
"""

from __future__ import annotations

import asyncio
import json
import uuid

from packages.core.logging import configure_logging, get_logger
from packages.core.types import PersonUID, TenantId
from packages.db.session import async_session
from packages.identity.schemas import MatchReplayDecisionOut, MatchReplaySummaryOut
from packages.identity.service import IdentityService
from packages.ops.service import OpsService

log = get_logger("worker.replay_identity_matches")

# The ENG-544 acceptance pair: lead duplicate 'Newton Patrick' should merge into
# the canonical CareStack patient 'Patrick Newton' (same phone +19167307719).
# Always surfaced in the dry-run sample so the operator can verify it directly.
_ACCEPTANCE_FOCUS_PERSON_UIDS: tuple[str, ...] = (
    "464cc989-4c87-436b-9ca6-23074cfea7c9",
    "73e7523b-e906-4a26-96fe-cbed1c87d277",
)

_DEFAULT_PAGE_SIZE = 500
_DEFAULT_SAMPLE_SIZE = 25


def _maybe_sample(
    samples: list[MatchReplayDecisionOut],
    decision: MatchReplayDecisionOut,
    focus: set[uuid.UUID],
    sample_size: int,
) -> None:
    """Keep a bounded, representative sample.

    Always include a decision touching a focus person (the acceptance pair),
    always include the FIRST decision of each distinct outcome, and otherwise
    fill up to ``sample_size``. The cap is soft by at most (#outcomes + #focus)
    so the operator never loses the acceptance row or an outcome class.
    """
    is_focus = decision.source_person_uid in focus or decision.candidate_person_uid in focus
    have_outcome = any(s.outcome == decision.outcome for s in samples)
    already = any(s.candidate_id == decision.candidate_id for s in samples)
    if already:
        return
    if is_focus or not have_outcome or len(samples) < sample_size:
        samples.append(decision)


async def _replay_tenant(
    tenant_id: TenantId,
    *,
    dry_run: bool,
    limit: int | None,
    page_size: int,
    sample_size: int,
    focus_person_uids: set[uuid.UUID],
) -> MatchReplaySummaryOut:
    summary = MatchReplaySummaryOut(tenant_id=tenant_id, dry_run=dry_run)
    samples: list[MatchReplayDecisionOut] = []
    after_id: uuid.UUID | None = None
    processed = 0
    # Within-pass dedup: a source person is merged at most once. If an earlier
    # candidate already retired this source, the remaining open candidates for
    # the same tombstone are skipped without re-evaluating. The service-side
    # retired guard is the authoritative backstop (it also covers re-runs and
    # cross-page sources); this set just avoids a redundant policy evaluation.
    merged_source_uids: set[uuid.UUID] = set()

    while True:
        # One session per PAGE. In dry-run it is read-only; in a live pass the
        # page's merges commit together at context exit (bounded transaction,
        # resumable per page because decided rows leave the open work-list).
        async with async_session() as session:
            identity = IdentityService(session)
            ops = OpsService(session)
            page = await identity.list_open_match_candidates(
                tenant_id, after_id=after_id, limit=page_size
            )
            if not page:
                break

            for candidate in page:
                if limit is not None and processed >= limit:
                    break
                summary.scanned += 1
                processed += 1
                after_id = candidate.id

                src_uid = candidate.source_person_uid
                if (
                    not dry_run
                    and src_uid is not None
                    and src_uid in merged_source_uids
                ):
                    # Source already merged earlier in this pass — a second open
                    # candidate for the same tombstone. Skip, never re-merge.
                    summary.skipped += 1
                    continue

                decision = await identity.replay_open_match_candidate(
                    tenant_id, candidate, apply=not dry_run
                )

                if decision.outcome == "would_merge":
                    summary.would_merge += 1
                    if decision.applied and not dry_run:
                        summary.merged_applied += 1
                        if decision.merged_person_uid is not None:
                            merged_source_uids.add(decision.merged_person_uid)
                        if (
                            decision.merged_person_uid is not None
                            and decision.survivor_person_uid is not None
                        ):
                            moved = await ops.reassign_leads(
                                tenant_id,
                                PersonUID(decision.merged_person_uid),
                                PersonUID(decision.survivor_person_uid),
                            )
                            summary.leads_reassigned += moved
                elif decision.outcome == "stay_open":
                    summary.would_stay_open += 1
                else:
                    summary.skipped += 1

                _maybe_sample(samples, decision, focus_person_uids, sample_size)

        if limit is not None and processed >= limit:
            break

    summary.samples = samples
    log.info(
        "replay_identity_matches.tenant_done",
        tenant_id=str(tenant_id),
        dry_run=dry_run,
        scanned=summary.scanned,
        would_merge=summary.would_merge,
        would_stay_open=summary.would_stay_open,
        skipped=summary.skipped,
        merged_applied=summary.merged_applied,
        leads_reassigned=summary.leads_reassigned,
    )
    return summary


async def replay_identity_matches(
    ctx: dict[str, object],
    *,
    tenant_id: str | None = None,
    dry_run: bool = True,
    limit: int | None = None,
    page_size: int = _DEFAULT_PAGE_SIZE,
    sample_size: int = _DEFAULT_SAMPLE_SIZE,
    sample_person_uids: list[str] | None = None,
) -> list[dict[str, object]]:
    """arq entrypoint. Replays one tenant (``tenant_id``) or every tenant.

    ``dry_run`` defaults to ``True`` — nothing is mutated unless an operator
    explicitly enqueues with ``dry_run=False``.
    """
    del ctx
    configure_logging()

    focus = {
        uuid.UUID(value) for value in (*_ACCEPTANCE_FOCUS_PERSON_UIDS, *(sample_person_uids or []))
    }

    if tenant_id is not None:
        tenant_ids = [TenantId(uuid.UUID(tenant_id))]
    else:
        from packages.tenant.service import TenantService

        async with async_session() as session:
            tenant_ids = [TenantId(t.id) for t in await TenantService(session).list_tenants()]

    out: list[dict[str, object]] = []
    for tid in tenant_ids:
        summary = await _replay_tenant(
            tid,
            dry_run=dry_run,
            limit=limit,
            page_size=page_size,
            sample_size=sample_size,
            focus_person_uids=focus,
        )
        out.append(summary.model_dump(mode="json"))

    log.info(
        "replay_identity_matches.complete",
        tenants=len(out),
        dry_run=dry_run,
    )
    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Replay open identity match candidates under the current policy."
    )
    parser.add_argument("--tenant-id", default=None, help="Single tenant UUID.")
    parser.add_argument("--limit", type=int, default=None, help="Cap candidate rows.")
    parser.add_argument("--page-size", type=int, default=_DEFAULT_PAGE_SIZE, help="Rows per page.")
    parser.add_argument(
        "--sample-size", type=int, default=_DEFAULT_SAMPLE_SIZE, help="Sample rows."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="MUTATE: perform merges (operator-only). Default is dry-run.",
    )
    args = parser.parse_args()

    result = asyncio.run(
        replay_identity_matches(
            {},
            tenant_id=args.tenant_id,
            dry_run=not args.live,
            limit=args.limit,
            page_size=args.page_size,
            sample_size=args.sample_size,
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
