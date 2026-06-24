"""Integrations domain — provider plumbing only.

This package owns: OAuth credentials, per-account field mappings, sync run
journals, CDC cursors, and a generic safe for provider objects without a
canonical home. NO domain data lives here — provider records (Salesforce
Lead, CareStack Patient) are mapped into the canonical schemas (`identity`,
`ops`, `phi`) via the service layer.

Provider-specific code lives in subpackages: ``salesforce/``, ``carestack/``.
"""
