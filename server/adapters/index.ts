/**
 * full-arch-crm — DatabaseAdapter Platform
 * ──────────────────────────────────────────
 * Barrel export. Import everything from here.
 *
 * Usage:
 *   import { adapterRegistry, bootstrapAdapters } from "../adapters";
 *   import type { DatabaseAdapter, CanonicalPatient } from "../adapters";
 *
 * AI modules NEVER import adapter implementations directly.
 * Always use: adapterRegistry.getAdapter(tenantId) or getDefaultAdapter()
 */

// ── Core types ──────────────────────────────────────────────────────────────
export type {
  // Tenant
  CanonicalTenant,
  AdapterType,
  AdapterConfig,
  HipaaConfig,
  // PHI access control
  PhiAccessContext,
  PhiAccessPurpose,
  PhiAuditEntry,
  // Patients
  CanonicalPatient,
  CanonicalPatientSummary,
  CanonicalMedicalHistory,
  // Insurance & eligibility
  CanonicalInsurance,
  CanonicalEligibilityResult,
  // Appointments
  CanonicalAppointment,
  AppointmentType,
  AppointmentStatus,
  // Treatment
  CanonicalTreatmentPlan,
  // Clinical notes
  CanonicalClinicalNote,
  // Billing
  CanonicalClaim,
  ClaimStatus,
  CanonicalPriorAuth,
  CanonicalFinancingPlan,
  // Intelligence
  AnonymizedIntelligencePattern,
  // Query options
  PatientListOptions,
  PatientListResult,
  AppointmentListOptions,
  ClaimListOptions,
  AdapterHealthStatus,
  // Mapping
  MappingSpec,
  // Enums
  PatientStage,
  InsuranceType,
  AgeBand,
} from "./types";

// ── Interface ────────────────────────────────────────────────────────────────
export type { DatabaseAdapter, CdtCodeResult, EobPosting } from "./interface";

// ── Translator ───────────────────────────────────────────────────────────────
export { SchemaTranslator, FUSION_CRM_MAPPING, GENERIC_REST_MAPPING } from "./translator";

// ── Registry ─────────────────────────────────────────────────────────────────
export { adapterRegistry, bootstrapAdapters, AdapterNotFoundError } from "./registry";

// ── Implementations (for bootstrapAdapters internal use — do not use directly) ──
// These are resolved dynamically via bootstrapAdapters(). Direct imports are
// intentionally not re-exported here to enforce registry-mediated access.
