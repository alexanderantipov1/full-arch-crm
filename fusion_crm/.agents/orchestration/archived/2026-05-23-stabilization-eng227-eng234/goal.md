# Mission Goal

Stabilize the backend verification line after the CareStack location profile
work by resolving ENG-227 through ENG-232 without weakening tenant isolation,
PHI/audit boundaries, or the repository/service architecture.

Extend the same mission state through ENG-233 and ENG-234 so Salesforce OAuth
connections remain alive autonomously and production Cloud Run Jobs plus Cloud
Scheduler entries are activated through the canonical operator deploy path.
The production activation evidence covers the Salesforce token keepalive job,
Salesforce scheduled pull job, and CareStack scheduled pull job.

This mission also keeps the follow-up scope explicit before PR preparation:
production-reviewer work in commit `44d704e` is separate from current dirty
web, strategy, and mission-state changes.
