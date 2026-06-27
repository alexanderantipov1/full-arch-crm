"""Actor domain — first-class executors of work.

Humans, AI agents, system jobs, and external services are all "actors".
The data model treats them uniformly so that any task / action can be
assigned to any executor without the consumer caring about the type.

Tables (schema ``actor``):
  * ``actor`` — one row per executor (human staff, AI agent, system, external service)
  * ``actor_identifier`` — maps an Actor to N external IDs (Salesforce User Id,
    CareStack Provider Id, Vapi Agent Id, email, phone, ...)

Capability and availability are deferred to Phase 5+ (M5 workflow engine);
the corresponding tables will be added in their own migrations.
"""
