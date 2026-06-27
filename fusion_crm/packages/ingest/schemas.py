"""Ingest DTOs."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from packages.tenant.schemas import ImportSummary


class RawEventIn(BaseModel):
    source: str = Field(..., examples=["carestack", "salesforce", "webhook.zapier"])
    event_type: str
    external_id: str | None = None
    received_at: datetime
    payload: dict[str, object]


class RawEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    event_type: str
    external_id: str | None
    received_at: datetime
    payload: dict[str, object]
    processed_at: datetime | None
    error: str | None


class NormalizedPersonHintIn(BaseModel):
    """Input DTO for :meth:`IngestService.capture_normalized_person_hint`.

    ``email`` and ``phone`` are caller-supplied raw values; the service
    normalises them (lower-case email, digits-only phone) and stores the
    normalised form. Invalid values do NOT raise — they are recorded in
    ``quality_flags`` and the column is left ``NULL`` so downstream match
    policy can decide what to do.

    ``meta`` and ``quality_flags`` MUST be non-PHI parser metadata only.
    The service rejects a deny-list of clinical / raw-payload keys before
    insert.
    """

    raw_event_id: UUID
    source_system: str = Field(..., min_length=1, max_length=32)
    source_instance: str | None = Field(default=None, max_length=96)
    source_kind: str = Field(..., min_length=1, max_length=32)
    source_id: str | None = Field(default=None, max_length=240)
    observed_at: datetime
    given_name: str | None = Field(default=None, max_length=120)
    family_name: str | None = Field(default=None, max_length=120)
    display_name: str | None = Field(default=None, max_length=240)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)
    payload_sha256: str | None = Field(default=None, max_length=64)
    quality_flags: dict[str, object] = Field(default_factory=dict)
    meta: dict[str, object] = Field(default_factory=dict)


class NormalizedPersonHintOut(BaseModel):
    """Output DTO mirroring the ORM row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    raw_event_id: UUID
    source_system: str
    source_instance: str
    source_kind: str
    source_id: str | None
    observed_at: datetime
    given_name: str | None
    family_name: str | None
    display_name: str | None
    email_normalized: str | None
    phone_normalized: str | None
    person_uid: UUID | None
    source_link_id: UUID | None
    payload_sha256: str | None
    hint_hash: str
    quality_flags: dict[str, object]
    meta: dict[str, object]
    created_at: datetime
    updated_at: datetime


class SourceDataRelationOut(BaseModel):
    """Related source-system record shown on the local dev source-data page."""

    id: str
    provider: str
    source_instance: str
    entity_kind: str
    external_id: str
    relation: str
    label: str
    person_uid: UUID | None


class SourceDataRecordOut(BaseModel):
    """PHI-minimised source-record projection for the local dev UI.

    ``payload`` is not the verbatim ``ingest.raw_event.payload``. It contains
    only allow-listed source metadata fields so the dev source-data page can
    inspect record shape without becoming a raw PHI browser.
    """

    id: UUID
    provider: str
    source_instance: str
    external_id: str
    entity_kind: str
    display_name: str | None
    email: str | None
    phone: str | None
    status: str | None
    location_name: str | None
    occurred_at: datetime | None
    fetched_at: datetime
    resolved_person_uid: UUID | None
    raw_event_id: UUID
    derived_signals: list[str]
    related_records: list[SourceDataRelationOut]
    payload: dict[str, object]


class SourceDataListOut(BaseModel):
    items: list[SourceDataRecordOut]
    total: int
    totals_by_provider: dict[str, int]


class MarketingSpendImportOut(BaseModel):
    """Summary for a marketing ad-spend ingest run (Google/Meta/TikTok).

    ``imported_count`` = metric rows captured/upserted this run;
    ``unchanged_count`` = re-pulled rows whose captured payload was identical
    (healthy overlap, skipped before any write); ``skipped_count`` = rows we
    could not parse a campaign id / date from; ``campaigns_upserted`` = distinct
    campaigns touched; ``account_count`` = ad accounts iterated.
    """

    imported_count: int = 0
    unchanged_count: int = 0
    skipped_count: int = 0
    campaigns_upserted: int = 0
    account_count: int = 0
    days: int = 0


class MarketingMetricImportOut(BaseModel):
    """Summary for a marketing analytics ingest run (GA4, Search Console, …).

    ``imported_count`` = rows captured/upserted; ``unchanged_count`` = re-pulled
    rows whose captured payload was identical (skipped before any write);
    ``skipped_count`` = rows we could not parse a key/date from.
    """

    imported_count: int = 0
    unchanged_count: int = 0
    skipped_count: int = 0
    days: int = 0


class CareStackPatientImportOut(BaseModel):
    """Summary for a bounded CareStack Patient ingest run."""

    imported_count: int
    # ENG-381: healthy capture-guard skips (provider stamp unchanged).
    unchanged_count: int = 0
    skipped_count: int
    page_count: int
    next_continue_token: str | None = None
    sync_run_id: UUID | None = None


class CareStackAppointmentImportOut(BaseModel):
    """Summary for a bounded CareStack Appointment ingest run."""

    imported_count: int
    skipped_count: int
    unchanged_count: int = 0
    page_count: int
    next_continue_token: str | None = None
    sync_run_id: UUID | None = None


class CareStackTreatmentImportOut(BaseModel):
    """Summary for a bounded CareStack Treatment Procedure ingest run."""

    imported_count: int
    skipped_count: int
    unchanged_count: int = 0
    page_count: int
    next_continue_token: str | None = None
    sync_run_id: UUID | None = None


class CareStackTreatmentPlanImportOut(BaseModel):
    """Summary for a per-patient CareStack TreatmentPlan ingest sweep (ENG-511).

    The TreatmentPlan endpoint is per-patient (no bulk feed), so the sweep walks
    already-linked CareStack patients. ``accepted_count`` = ``treatment_accepted``
    timeline events freshly emitted (TreatmentPlan ``StatusId=3`` observed for the
    first time); ``unchanged_count`` = plan rows whose verbatim payload matched
    the latest capture (content-dedup, skipped before any write) PLUS accepted
    plans whose ``treatment_accepted`` event already existed;
    ``captured_count`` = raw plan rows captured this run; ``skipped_count`` = plan
    rows with no usable plan id; ``patient_count`` = patients swept;
    ``error_count`` = patients whose plan fetch failed (failure-isolated).
    """

    captured_count: int = 0
    accepted_count: int = 0
    unchanged_count: int = 0
    skipped_count: int = 0
    error_count: int = 0
    patient_count: int = 0


class CareStackInvoiceImportOut(BaseModel):
    """Summary for a bounded CareStack Invoice ingest run."""

    imported_count: int
    skipped_count: int
    unchanged_count: int = 0
    page_count: int
    next_continue_token: str | None = None
    sync_run_id: UUID | None = None


class CareStackAccountingTransactionImportOut(BaseModel):
    """Summary for a bounded CareStack Accounting Transaction ingest run (ENG-257).

    ``imported_count`` counts rows whose ``patientId`` resolved to a
    linked Person AND produced a fresh payment timeline event.
    ``unchanged_count`` (ENG-329) counts rows that resolved + mapped to
    a payment event but deduped at
    :meth:`packages.interaction.service.InteractionService.create_event_idempotent`
    (``was_created is False``) — a HEALTHY idempotent re-pull, NOT a
    failure. ``skipped_count`` now counts ONLY genuine non-imports: rows
    still captured to ``ingest.raw_event`` but with no usable source id,
    missing ``patientId``, no source link yet from the patient pull, or a
    non-payment folio row.
    ``patient_ids`` (ENG-305) is the distinct, sorted set of CareStack
    patient ids whose rows were imported on this run — the live signal
    the scheduled job feeds into
    :meth:`packages.ingest.carestack_payment_summary_service.CareStackPaymentSummaryIngestService.import_payment_summary_for_patients`
    so the authoritative balance is refreshed for patients who just
    moved money. Empty when no rows were imported.
    """

    imported_count: int
    skipped_count: int
    unchanged_count: int = 0
    page_count: int
    next_continue_token: str | None = None
    sync_run_id: UUID | None = None
    patient_ids: list[str] = Field(default_factory=list)


class CareStackPaymentSummaryImportOut(BaseModel):
    """Summary for a bounded CareStack Payment Summary snapshot sweep (ENG-257).

    ``snapshot_count`` counts patients for which a snapshot was captured
    to ``ingest.raw_event``; ``skipped_count`` counts patients we
    intentionally skipped (no usable CareStack patient id on the source
    link); ``error_count`` counts patients whose ``get_payment_summary``
    call failed and were logged but did not poison the sweep.
    """

    snapshot_count: int
    # ENG-381: healthy content-dedupe skips (snapshot identical to the
    # latest stored one for the patient).
    unchanged_count: int = 0
    skipped_count: int
    error_count: int
    patient_count: int
    sync_run_id: UUID | None = None


class LatestPaymentSummaryBalancesOut(BaseModel):
    """Dashboard-safe outstanding balance aggregate (ENG-257 / ENG-266).

    Sums the LATEST ``carestack.payment_summary.snapshot`` raw_event per
    CareStack patient id. ``outstanding_total`` is patient + insurance —
    the single number the PM treatment/payments widget needs.

    ``ar_risk_count`` (ENG-266) is the number of patients whose LATEST
    ``balanceDuePatient`` is strictly greater than the
    ``AR_RISK_BALANCE_THRESHOLD`` module constant in
    ``packages.ingest.service``. ``ar_risk_threshold`` echoes the
    threshold used so the dashboard widget can show the cut-off
    alongside the count.
    """

    balance_due_patient: float = 0.0
    balance_due_insurance: float = 0.0
    outstanding_total: float = 0.0
    patient_count: int = 0
    ar_risk_count: int = 0
    ar_risk_threshold: float = 0.0


class CarestackOriginRowOut(BaseModel):
    """Per-CareStack-patient-id origin context for the person card (ENG-308 / ENG-310).

    One row per ``carestack/patient`` source_link on the person. The
    fields trace the CareStack-side reality that ``source_link.first_seen_at``
    (= "First ingest" on the UI) does NOT capture:

    * ``earliest_activity_at`` / ``latest_activity_at`` — the
      ``MIN`` / ``MAX`` of the CareStack-side activity timestamps
      (appointment ``createdOn`` and accounting ``TransactionDate``).
      Both ``None`` when no activity has been captured.
    * ``default_location_id`` / ``default_location_name`` — the
      latest ``carestack.patient.upsert``'s ``defaultLocationId`` and
      its resolved location name (when the locations directory is
      populated).
    * ``default_provider_id`` / ``default_provider_name`` — the
      latest ``defaultProviderId`` and its resolved "Dr First Last"
      via the ENG-308 providers directory. The UI never renders the
      raw integer.
    * ``city`` / ``state`` — extracted from the latest patient
      payload's ``addressDetail`` object.

    ENG-310: also carries per-pid identity surface fields read from the
    latest ``carestack.patient.upsert`` payload. Names drive the
    multi-link expander row label (``First Last · pid``). The patient
    details panel (click-to-reveal) reads DOB / gender / phones / email
    / full address / patientIdentifier / accountId. SSN is intentionally
    NOT surfaced in v1 (decision: even masked tail digits expand the PHI
    surface for v1; defer to a later ticket if operators ask for it).
    The previous HIPAA Safe-Harbor city/state-only carve-out was scoped
    to the ENG-308 origin card; the 2026-06-01 PHI policy update
    permits these fields on the staff frontend behind an intentional
    click-to-reveal panel.
    """

    patient_id: str
    earliest_activity_at: datetime | None = None
    latest_activity_at: datetime | None = None
    default_location_id: int | None = None
    default_location_name: str | None = None
    default_provider_id: int | None = None
    default_provider_name: str | None = None
    city: str | None = None
    state: str | None = None
    # ENG-310 — per-pid identity / patient details (latest patient.upsert).
    first_name: str | None = None
    last_name: str | None = None
    dob: str | None = None
    gender: str | None = None
    marital_status: str | None = None
    mobile: str | None = None
    phone_with_ext: str | None = None
    work_phone_with_ext: str | None = None
    email: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    address_zip: str | None = None
    patient_identifier: str | None = None
    account_id: str | None = None


class HouseholdMemberOut(BaseModel):
    """ENG-310 — sibling person sharing a normalised phone or email.

    Household here means "different people sharing one phone or email"
    (Torosyan-shape: a parent + adult child sharing a mobile, a spouse
    sharing an inbox). It is NOT identity merge: financials,
    consultations, and notes stay on each ``person_uid``. The card
    surfaces a navigational link only.

    Resolved by :meth:`packages.ingest.service.IngestService.person_household_members`
    against the verbatim ``carestack.patient.upsert`` payload — NOT
    ``identity.person_identifier`` (the global ``UNIQUE(kind, value)``
    constraint puts a shared phone on a single Person row after the
    ENG-311 split, so PersonIdentifier would miss the siblings). The
    accountId field is forbidden as a household key (it is a
    clinic-level default value worth ~55K patients).

    * ``person_uid`` — the sibling person's id; the UI builds
      ``/persons/<uid>`` link.
    * ``display_name`` — best-effort label (``identity.person`` name
      first, else CareStack payload ``firstName + lastName``).
    * ``shared_via`` — ``"phone"`` | ``"email"`` | ``"both"``.
    * ``shared_value_masked`` — last-4 phone (``"···4258"``) or
      masked email local-part (``"g···@gmail.com"``). Never raw.
    """

    person_uid: str
    display_name: str | None = None
    shared_via: str
    shared_value_masked: str


class ProviderImportOut(BaseModel):
    """Summary for one CareStack provider directory import run (ENG-308).

    ``imported`` is the number of rows the repository upsert call
    returned (insert + update). ``total_seen`` is the number of usable
    entries after dropping rows without an integer ``id``.
    ``error_count`` is the number of repository batches that raised an
    exception during the sweep.
    """

    imported: int = 0
    total_seen: int = 0
    error_count: int = 0


class PersonPaymentFinancialSummaryOut(BaseModel):
    """Per-person financial summary surfaced on the person detail card (ENG-306).

    ``paid`` and ``balance`` come from the LATEST CareStack
    ``payment-summary`` snapshot for each CareStack patient id linked to
    the person (authoritative).  ``billed`` and ``adjustments`` are gross
    context derived from the accounting journal raw_events for those same
    patient ids, deduped by ``external_id`` (latest ``received_at`` wins).

    ``snapshot_received_at`` is the most recent payment-summary
    ``received_at`` across the patient ids — ``None`` when no snapshot
    has been captured yet (the UI uses this to show the four-em-dash
    empty state instead of zero dollars).

    ``carestack_patient_ids`` is the list of CareStack patient ids that
    fed this row (zero, one, or rarely many when a single person has
    multiple CS source links). ``patient_count`` is its length.
    """

    billed: float = 0.0
    adjustments: float = 0.0
    paid: float = 0.0
    balance: float = 0.0
    snapshot_received_at: datetime | None = None
    carestack_patient_ids: list[str] = Field(default_factory=list)
    patient_count: int = 0


class CareStackPullOut(BaseModel):
    """Aggregated summary for the combined CareStack pull.

    The ``/integrations/carestack/pull`` endpoint sequences locations
    first, then patients, then appointments. CareStack locations are the
    authoritative clinic context for appointments, so appointment ingest
    can resolve ``locationId`` into ``ops.consultation.location_id``.
    """

    locations: ImportSummary
    patients: CareStackPatientImportOut
    appointments: CareStackAppointmentImportOut
    sync_run_id: UUID | None = None


class SfEventImportOut(BaseModel):
    """Summary for a bounded Salesforce Event ingest run (ENG-220)."""

    imported_count: int
    # ENG-381: healthy capture-guard skips (provider stamp unchanged).
    unchanged_count: int = 0
    skipped_count: int
    queried_count: int
    sync_run_id: UUID | None = None


class SfTaskImportOut(BaseModel):
    """Summary for a bounded Salesforce Task ingest run (ENG-240)."""

    imported_count: int
    # ENG-381: healthy capture-guard skips (provider stamp unchanged).
    unchanged_count: int = 0
    skipped_count: int
    queried_count: int
    sync_run_id: UUID | None = None


class SfOpportunityImportOut(BaseModel):
    """Summary for a bounded Salesforce Opportunity capture run."""

    imported_count: int
    # ENG-381: healthy capture-guard skips (provider stamp unchanged).
    unchanged_count: int = 0
    skipped_count: int
    queried_count: int
    sync_run_id: UUID | None = None


class SfContactImportOut(BaseModel):
    """Summary for a bounded Salesforce Contact ingest run (ENG-382)."""

    imported_count: int
    # ENG-381: healthy capture-guard skips (provider stamp unchanged).
    unchanged_count: int = 0
    skipped_count: int
    queried_count: int
    sync_run_id: UUID | None = None


class SfAccountImportOut(BaseModel):
    """Summary for a bounded Salesforce Account ingest run (ENG-382)."""

    imported_count: int
    # ENG-381: healthy capture-guard skips (provider stamp unchanged).
    unchanged_count: int = 0
    skipped_count: int
    queried_count: int
    linked_count: int = 0
    sync_run_id: UUID | None = None


class SfOpportunityHistoryImportOut(BaseModel):
    """Summary for a bounded Salesforce OpportunityHistory ingest run (ENG-382)."""

    imported_count: int
    # ENG-381: healthy capture-guard skips (history rows are immutable,
    # so any re-read of a captured row is unchanged by definition).
    unchanged_count: int = 0
    skipped_count: int
    queried_count: int
    sync_run_id: UUID | None = None


class SfCaseImportOut(BaseModel):
    """Summary for a bounded Salesforce Case capture run."""

    imported_count: int
    # ENG-381: healthy capture-guard skips (provider stamp unchanged).
    unchanged_count: int = 0
    skipped_count: int
    queried_count: int
    sync_run_id: UUID | None = None


class SalesforcePullOut(BaseModel):
    """Aggregated summary for the combined Salesforce leads + events pull.

    ``/integrations/salesforce/pull`` sequences leads first (so the
    ``identity.source_link`` rows exist), then events (which resolve
    ``WhoId`` against those links). Mirrors :class:`CareStackPullOut`.
    """

    leads_imported: int
    events: SfEventImportOut
    sync_run_id: UUID | None = None


class SfLeadOut(BaseModel):
    """DTO for a Salesforce-origin lead surfaced to the operator UI.

    Joins ``ops.lead`` (one row per person, Phase 1) with
    ``identity.person`` for the display name and email/phone identifiers.
    Provider-specific fields (``sf_lead_id``, ``is_reactivation``,
    ``sf_created_at``) live on ``Lead.extra`` and are flattened here.

    No clinical content. ``email`` and ``phone`` are surfaced because
    `ops.lead` is a marketing/CRM domain — not PHI.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    person_uid: UUID
    sf_lead_id: str
    display_name: str | None
    email: str | None
    phone: str | None
    company: str | None
    lead_source: str | None
    lead_status: str | None
    is_reactivation: bool
    sf_created_at: str | None  # SF returns ISO-8601 string; keep verbatim
    created_at: datetime  # local-DB row creation timestamp


# --- Full-fidelity schema registry (ENG-426) ---


class ObservedFieldIn(BaseModel):
    """One field observed on a source object during a schema derivation.

    ``readable`` is True when the integration user can actually read the
    field (SF: queryable and passes Field-Level Security; REST: seen in a
    payload). A field that exists on the object but is FLS-blocked is passed
    with ``readable=False`` so the registry can record the gap.

    ``meta`` carries provider-specific flags (e.g. SF ``custom``, ``queryable``,
    ``compound``) — non-PHI schema metadata only, never sample values.
    """

    name: str = Field(..., min_length=1, max_length=255)
    field_type: str | None = Field(default=None, max_length=64)
    readable: bool = True
    meta: dict[str, object] = Field(default_factory=dict)


class SourceObjectFieldOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    object_name: str
    field_name: str
    field_type: str | None
    readable: bool
    active: bool
    first_seen_at: datetime
    last_seen_at: datetime


class FieldTypeChange(BaseModel):
    field: str
    old_type: str | None
    new_type: str | None


class SchemaDiffOut(BaseModel):
    """Result of reconciling an observed schema against the registry.

    This is the drift-event shape (ENG-426). ``added`` includes both
    genuinely new fields and previously-inactive fields that reappeared.
    Block C surfaces this via a structured log line and ``sync_run.meta``.
    """

    provider: str
    object_name: str
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    type_changed: list[FieldTypeChange] = Field(default_factory=list)
    became_readable: list[str] = Field(default_factory=list)
    became_unreadable: list[str] = Field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.added
            or self.removed
            or self.type_changed
            or self.became_readable
            or self.became_unreadable
        )
