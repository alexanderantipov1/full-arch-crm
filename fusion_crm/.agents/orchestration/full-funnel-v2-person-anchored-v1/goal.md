# Goal — Full Funnel v2 (person-anchored)

**Epic:** ENG-480
**Design:** `docs/analytics/full-funnel-v2-person-anchored.md`

Re-anchor the Full Funnel report from `ops.lead` (Salesforce) onto
`identity.person`, computing each stage from its system of truth
(Salesforce for marketing leads, CareStack for consultations / show /
no-show / money), with a single **Marketing / All** audience toggle.

Today's funnel measures only the Salesforce intersection: 93% of
consultation-persons and 85% of collected revenue have no SF lead and are
invisible. v2 fixes this by reusing the existing person merge (the same
anchor `project-manager/leads` already uses) — no new tables.

## Children (dependency order)

1. **ENG-481** — backend person-anchored read model + API.
2. **ENG-482** — frontend funnel page (audience toggle, Show/No-show,
   closed-won = money). Depends on ENG-481.
3. **ENG-483** — verify on real data + integration tests. Depends on both.

## Stages → source of truth

| Stage | Source |
|---|---|
| Leads | `ops.lead` ∪ `identity.source_link(carestack/patient)`, distinct `person_uid` |
| Consults scheduled | `ops.consultation` (all created) by `person_uid` |
| Showed | `ops.consultation.status='completed'` |
| No-show | `ops.consultation.status='no_show'` |
| Closed won (money) | `interaction.event` payments, Net Collected > 0 |
| Revenue | `interaction.event` (recorded − refunded − reversed) |

Marketing = person has a lead with an ad channel (google/facebook/…) via
the existing `_explorer_channel_label` resolver. All = whole universe.
Invariant: `marketing ⊆ all` per stage and month.
