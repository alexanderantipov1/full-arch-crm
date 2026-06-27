/**
 * full-arch-crm — AI Agent Suite
 * ────────────────────────────────
 * Barrel export for all agents in the full-arch-crm agent suite.
 *
 * Import agents from here, not from their individual modules:
 *
 *   import { runTreatmentCoordinator } from "./agents";
 *   import { runCollectionsAgent }     from "./agents";
 *
 * Agent roster:
 *   - TreatmentCoordinator — nightly case acceptance scoring + follow-up drafting
 *   - CollectionsAgent     — risk scoring + payment plan automation
 */

// ─── Treatment Coordinator ────────────────────────────────────────────────────
export { runTreatmentCoordinator } from "./treatment-coordinator";

// ─── Collections Agent ────────────────────────────────────────────────────────
export { runCollectionsAgent } from "./collections-agent";

// ─── Shared types ─────────────────────────────────────────────────────────────
export type { CoordinatorReport, PatientScore, FollowUpDraft, ScoreBreakdown } from "./types";
export type { CollectionsCase, CollectionsReport, PaymentPlan } from "./types";
