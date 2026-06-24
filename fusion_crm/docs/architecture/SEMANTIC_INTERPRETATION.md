# Semantic Interpretation

Semantic interpretation turns raw and canonical data into stable operational
meaning. It is the bridge between provider fields and workflow intelligence.

## Principle

Do not make agents reason directly over raw Salesforce, CareStack, Twilio, or
other provider schemas.

Provider-specific fields must be interpreted into a controlled vocabulary before
they drive workflow or agent behavior.

## Pipeline

```text
raw event
-> canonical record
-> deterministic mapping
-> semantic interpretation
-> context object
-> workflow trigger
```

## Deterministic First

Use deterministic code and tables for facts that are clear and repeatable:

- UTM fields
- lead source
- Salesforce custom boolean fields
- appointment status
- location
- provider id
- known campaign mapping
- do-not-contact flags
- opt-out flags

Example:

```text
Double_Arch__c = true
-> treatment_intent = "full_arch"
```

```text
utm_source = "google"
utm_medium = "cpc"
-> source_channel = "paid_search"
```

## Specialized Semantic Agents

Use specialized semantic agents for ambiguous or unstructured information:

- call transcripts
- SMS replies
- email text
- form free text
- clinical-adjacent notes that require permissioned summarization
- conflicting provider fields
- unknown campaign phrases
- new objections or intent signals

Semantic agents must return structured output, not free-form decisions.

Example output:

```json
{
  "intent": "full_arch",
  "urgency": "high",
  "objections": ["financing"],
  "summary": "Interested in full-arch treatment and likely needs financing.",
  "confidence": 0.86,
  "taxonomy_version": "2026-05-15"
}
```

## Review States

Semantic outputs that affect workflow routing, taxonomy changes, financial
decisions, clinical summaries, or external actions need review state:

- `auto_accepted`
- `needs_review`
- `approved`
- `rejected`
- `superseded`

Low-risk deterministic interpretations can be auto-accepted. New labels,
taxonomy changes, PHI-sensitive summaries, and action-changing interpretations
require human approval before they become production rules.

## Versioning

Semantic interpretation must carry enough metadata to explain why a workflow
acted:

- source event ids
- canonical entity ids
- interpreter type (`rule`, `agent`, `human`)
- interpreter version
- taxonomy version
- confidence
- review status
- created_at

## Learning Loop

The system can learn, but not by silently mutating production behavior.

Approved loop:

```text
agent interpretation
-> stored semantic output
-> human review/correction
-> taxonomy or rule proposal
-> approval
-> new taxonomy/rule version
-> future interpretations use approved version
```

Unapproved loop:

```text
agent notices a pattern
-> production taxonomy changes automatically
```

The unapproved loop is forbidden.
