/**
 * full-arch-crm — AI Agent Suite
 * ────────────────────────────────
 * Barrel export for all agents in the full-arch-crm agent suite.
 *
 * Import agents from here, not from their individual modules:
 *
 *   import { runTreatmentCoordinator } from "./agents";
 *
 * Agent roster:
 *   - TreatmentCoordinator — nightly case acceptance scoring + follow-up drafting
 */

// ─── Treatment Coordinator ────────────────────────────────────────────────────
export { runTreatmentCoordinator } from "./treatment-coordinator";

// ─── Shared types ─────────────────────────────────────────────────────────────
export type { CoordinatorReport, PatientScore, FollowUpDraft, ScoreBreakdown } from "./types";
