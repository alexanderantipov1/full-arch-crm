"""Auth domain — credentials, sessions, API keys (and reserved portal accounts).

Polymorphic auth: ``credential`` and ``session`` rows belong to either an
``actor`` (staff, AI, system, external service) or a ``portal_account``
(reserved for M11 patient portal). The same machinery serves both subjects;
their lifecycles and policies differ but the storage shape is unified.

API keys are service-to-service only and ALWAYS link to an Actor — used by
the MCP server, Codex, CI tooling, and any future external integration.

Runtime permission enforcement (``permission_grant`` evaluation, BAA-eligibility
checks, data-class sentinels) is **deferred to M8**. This package owns the
shape and the storage; M8 wires the runtime gate.
"""
