# Goal — dev-lead-sources-explorer-v1

Give the clinic owner marketing-first visibility into the lead → consult →
chair pipeline per acquisition resource.

One new DEV-tools tab (`/dev/lead-sources`) shows every lead source/resource
in hierarchical order (effective source → utm_medium → utm_campaign) with
live funnel counts per node:

- leads attached to the node;
- consultations scheduled for the persons of those leads;
- consultations attended (completed) for the persons of those leads.

Filters: period over lead creation time, text search over node labels.
Clicking a node drills down into the underlying lead list with full lead
data and creation timestamps.

Linear: ENG-391
https://linear.app/fusion-dental-implants/issue/ENG-391/dev-lead-sources-explorer-hierarchical-source-tree-with-funnel-counts
