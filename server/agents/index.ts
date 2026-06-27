/**
 * full-arch-crm — AI Agent Suite — Barrel export for all agents
 */
export { runTreatmentCoordinator } from "./treatment-coordinator";
export { runCollectionsAgent } from "./collections-agent";
export { runSchedulingAgent, computeUrgencyScore } from "./scheduling-agent";
export { runFraudDetectionAgent } from "./fraud-detection-agent";
export { runCommunicationHub } from "./communication-hub";
export type { CoordinatorReport, PatientScore, FollowUpDraft, ScoreBreakdown, CollectionsCase, CollectionsReport, PaymentPlan, TimeSlot, BookingRecommendation, SchedulingReport, FraudFlag, FraudReport, FraudRuleId, CommunicationChannel, CommunicationTrigger, PatientMessage, CommunicationReport } from "./types";
