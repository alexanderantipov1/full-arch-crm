# Decision Log

- 2026-05-23T06:31:28Z: Handoff accepted from Strategy into Orchestrator
  planning. Linear parent ENG-235 and child issues ENG-236 through ENG-244
  created. No workers launched yet.

## 2026-05-23T21:20:00Z — Open human decisions resolved

Orchestrator collected the four contract-listed open decisions from the human
partner before assigning the first worker. All four resolutions are now binding
for execution and any future verifier or integrator pass:

1. **Timeline route name** — `GET /persons/{uid}/operational-timeline`.
   Reason: keeps a separate, narrowly scoped path so a future broader
   `/persons/{uid}/timeline` (e.g. clinical/PHI variant) does not collide.
   Applies to: Task G / ENG-242.

2. **Call URLs visibility in the first UI workbench** — visible to authorized
   builders. Authorized staff see the call URL in the workbench immediately;
   builders are responsible for treating the URL as sensitive surface and
   gating it behind the authorization layer. Storage shape unchanged: call
   URLs land on `interaction.event` with source reference + data class.
   Applies to: Task F / ENG-241 and Task G / ENG-242 (output shaping).

3. **Salesforce Task action-oriented rows** — create `ops.followup_task`
   immediately, in addition to emitting `interaction.event task_created`.
   Reason: shortens the lead-to-action loop for the operational pipeline.
   Risk to mitigate at implementation: deterministic classification must be
   tight; mis-classified `ops.followup_task` rows are not acceptable.
   Applies to: Task E / ENG-240.

4. **Event taxonomy literal format** — snake_case in both DB and the
   API/tool surface. Reason: existing `interaction.event.kind` literals are
   already snake_case; a second dotted vocabulary adds translation cost
   without product value at this stage.
   Applies to: Task A / ENG-236 (and consequently B, C, E, F, G).

Workers must not request re-confirmation on these four points. New questions
that arise during implementation go through standard `Needs decision:` runlog
markers.
