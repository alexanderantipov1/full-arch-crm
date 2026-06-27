export type CallStatus =
  | 'queued'
  | 'initiated'
  | 'in_progress'
  | 'completed'
  | 'failed'
  | 'mock_completed';

export type CallPurpose =
  | 'claim_status'        // check status of a submitted claim
  | 'denial_appeal'       // appeal a denied claim
  | 'prior_auth'          // request prior authorization
  | 'eligibility_verify'  // verify patient eligibility
  | 'payment_status';     // check payment status

export interface InsuranceCallTask {
  id: string;
  patientName: string;
  patientDOB: string;
  patientInsuranceId: string;
  insurerName: string;
  insurerPhone: string;
  claimNumber: string;
  procedureCodes: string[];  // CDT codes involved
  purpose: CallPurpose;
  priority: 'urgent' | 'standard' | 'low';
  callScript: string;        // AI-generated script for the call
  status: CallStatus;
  callSid: string | null;    // Twilio call SID when live
  callDuration: number | null; // seconds
  transcript: string | null;
  outcome: CallOutcome | null;
  notes: string;
  createdAt: string;
  completedAt: string | null;
}

export interface CallOutcome {
  resolved: boolean;
  summary: string;           // e.g. "Claim approved, payment processing 5-7 days"
  nextAction: string;        // e.g. "Expect ERA within 7 days"
  referenceNumber: string;   // insurer reference # from call
  followUpDate: string | null;
}

export interface CallQueueStats {
  queued: number;
  inProgress: number;
  completedToday: number;
  resolvedToday: number;
  estimatedRevenuePending: number;
}
