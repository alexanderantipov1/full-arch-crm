# raw/ — Immutable Source Layer

> **Karpathy Rule I: Sources Are Immutable**
>
> "Everything you save lands in raw/ and is never edited after it lands.
> Articles, transcripts, PDFs, screenshots: the source of truth.
> Adding is fine; editing raw/ destroys the model's ability to trace truth back to the source."
> — Andrej Karpathy, LLM-WIKI.md

---

## What Goes Here

Raw source events are written here BEFORE wiki ingestion. Once written, they are NEVER modified.
The wiki/ pages are the compiled view. This folder is the ground truth.

## Sub-folders

| Folder | Contents | Written by |
|--------|----------|-----------|
| `eob/` | Raw EOB events per claim line (JSON) | `eob-service.ts` |
| `simulation/` | Raw simulation batch results (JSON) | `engine.ts` |
| `appointments/` | Raw appointment completion events (JSON) | Appointment service |
| `adapter/` | Raw adapter sync events (JSON) | DatabaseAdapterRegistry |
| `agent-decisions/` | Raw agent decision events (JSON) | OrchestrationAgent |

## Naming Convention

Files are named: `{YYYY-MM-DD}_{eventType}_{ulid}.json`

Examples:
- `eob/2026-06-27_EOB_DENIED_01J3XK5F2G8H9JKMNPQRSTUVWX.json`
- `simulation/2026-06-27_BATCH_COMPLETE_01J3XK5F2G8H9JKMNPQRSTUVWX.json`
- `agent-decisions/2026-06-27_ORCHESTRATION_CYCLE_01J3XK5F2G8H9JKMNPQRSTUVWX.json`

## PHI Policy

**No PHI ever enters raw/**. Before writing, all identifying fields are stripped:
- `patientId` → replaced with anonymized `personHash` (SHA-256 of tenantId + personUid)
- Patient name, DOB, SSN, address → NEVER written
- Only clinical patterns and statistical values are kept

This is enforced in `rawSourceWriter.ts` before any file write.

## Lint Rules for raw/

1. Files older than **180 days** with no wiki page citing them → flagged as orphan sources
2. Files with `phi_fields_detected: true` → immediate alert + quarantine
3. More than **10,000 files** in a subfolder → trigger archival to cold storage

## Relationship to Wiki

```
raw/{event}.json          ← immutable ground truth
    ↓  wikiService.ingest()
wiki/{page}.md            ← compiled, LLM-synthesized, human-readable
    ↓  wikiService.query()
Agents → better decisions ← the whole point
```
