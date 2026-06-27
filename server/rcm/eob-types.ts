export interface EOBLineItem {
  procedureCode: string;     // CDT code e.g. D6010
  toothNumber: string;       // e.g. "30" or "Upper Right Quadrant"
  billedAmount: number;
  allowedAmount: number;
  insurancePaid: number;
  patientResponsibility: number;
  adjustments: number;
  denialCode: string | null; // CO-45, PR-96, etc.
  denialReason: string | null;
}

export interface ParsedEOB {
  id: string;
  patientName: string;
  patientId: string;
  insurerName: string;
  claimNumber: string;
  serviceDate: string;
  processingDate: string;
  totalBilled: number;
  totalAllowed: number;
  totalInsurancePaid: number;
  totalPatientResponsibility: number;
  lineItems: EOBLineItem[];
  postingStatus: 'pending' | 'posted' | 'error' | 'needs_review';
  postingNotes: string;
  parsedAt: string;
}

export interface EOBPostingResult {
  eobId: string;
  linesPosted: number;
  totalPosted: number;
  deniedLines: number;
  patientBalanceCreated: number;
  appealCandidates: EOBLineItem[];
  postingStatus: ParsedEOB['postingStatus'];
  message: string;
}
