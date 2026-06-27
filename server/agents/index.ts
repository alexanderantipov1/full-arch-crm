/**
 * full-arch-crm — AI Agent Suite
 * ────────────────────────────────
 * Barrel export for all agents in the full-arch-crm agent suite.
 *
 * Agent roster:
 *   - TreatmentCoordinator — nightly case acceptance scoring + follow-up drafting
 *   - CollectionsAgent     — risk scoring + payment plan automation
 *   - SchedulingAgent      — AI-optimized appointment booking + chair utilization
 */

// ─── Treatment Coordinator ────────────────────────────────────────────────────
export { runTreatmentCoordinator } from "./treatment-coordinator";

// ─── Collections Agent ────────────────────────────────────────────────────────
export { runCollectionsAgent } from "./collections-agent";

// ─── Scheduling Agent ─────────────────────────────────────────────────────────
export { runSchedulingAgent, computeUrgencyScore } from "./scheduling-agent";

// ─── Shared types ─────────────────────────────────────────────────────────────
export type {
  CoordinatorReport,
  PatientScore,
  FollowUpDraft,
  ScoreBreakdown,
  CollectionsCase,
  CollectionsReport,
  PaymentPlan,
  TimeSlot,
  BookingRecommendation,
  SchedulingReport,
} from "./types";
