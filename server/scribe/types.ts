export interface ScribeSession {
  id: string;
  patientId: string;
  patientName: string;
  providerId: string;
  providerName: string;
  dictationText: string; // raw transcription input
  soapNote: SOAPNote;
  cdtCodes: SuggestedCode[];
  status: 'draft' | 'reviewed' | 'signed';
  createdAt: string;
  signedAt: string | null;
}

export interface SOAPNote {
  subjective: string;   // Chief complaint, HPI, symptoms in patient's words
  objective: string;    // Clinical findings, vitals, radiograph findings, probing depths
  assessment: string;   // Diagnosis, differential, clinical impression
  plan: string;         // Treatment plan, CDT codes, follow-up, prescriptions
  implantSpecific?: ImplantNote; // Only if implant case
}

export interface ImplantNote {
  implantSite: string;       // e.g. "#30 (mandibular right first molar)"
  implantSystem: string;     // e.g. "Nobel Biocare, 4.3x10mm"
  torqueValue: string;       // e.g. "35 Ncm"
  isq: string;               // implant stability quotient e.g. "72"
  healingAbutment: string;   // size placed
  nextStep: string;          // e.g. "Delivery of final crown in 3 months"
}

export interface SuggestedCode {
  code: string;       // CDT code e.g. "D6010"
  description: string;
  fee: number;
  confidence: 'high' | 'medium' | 'low';
  rationale: string;
}
