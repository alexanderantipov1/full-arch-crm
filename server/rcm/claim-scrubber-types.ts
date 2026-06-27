export interface ClaimLine {
  procedureCode: string;    // CDT code
  toothNumber: string;
  surface?: string;
  fee: number;
  diagnosisCode?: string;   // ICD-10
  dateOfService: string;
}

export interface ClaimToScrub {
  id: string;
  patientName: string;
  patientDOB: string;
  patientInsuranceId: string;
  insurerName: string;
  providerNPI: string;
  dateOfService: string;
  lines: ClaimLine[];
}

export type ScrubSeverity = 'error' | 'warning' | 'info';

export interface ScrubIssue {
  code: string;           // e.g. "MISSING_TOOTH_NUMBER"
  severity: ScrubSeverity;
  affectedLine: string;   // procedure code
  message: string;
  suggestion: string;
  autoFixable: boolean;
}

export interface ScrubResult {
  claimId: string;
  passedScrub: boolean;
  issues: ScrubIssue[];
  errorCount: number;
  warningCount: number;
  estimatedDenialRisk: 'low' | 'medium' | 'high';
  cleanClaimScore: number; // 0-100
  readyToSubmit: boolean;
  scrubbedAt: string;
}
