Shared contract: identity.person_identifier uniqueness semantics (ENG-341).
Drop blanket UNIQUE(kind,value); add partial unique index excluding phone/email.
Consumers relying on phone global-uniqueness MUST be audited (IdentityRepository,
resolve_or_create_from_hint, attach_identifier callers). Codex cross-review required.
