import { randomUUID } from 'crypto';
import { askClaude } from '../services/ai';
import type { ParsedEOB, EOBPostingResult, EOBLineItem } from './eob-types';

const eobStore = new Map<string, ParsedEOB>();

export async function parseEOBText(rawEOBText: string): Promise<ParsedEOB> {
  const systemPrompt = `You are a dental insurance EOB (Explanation of Benefits) parsing expert.

Parse the provided EOB text and extract structured data. EOBs contain:
- Patient info (name, ID, DOB)
- Claim number and service/processing dates
- Insurer name
- Line items: each procedure with CDT code, billed/allowed/paid amounts, patient responsibility
- Adjustment codes (CO = contractual obligation, PR = patient responsibility, OA = other adjustment)
- Denial codes if any (CO-4 = inconsistent with patient age, CO-45 = charges exceed fee schedule, PR-96 = non-covered charge)

For dental implant EOBs specifically:
- D6010 (implant body) is commonly cross-coded with CPT 21248 for medical insurance
- Insurance often denies D6010 as "not a covered benefit" — flag these for appeal
- D4341 (SRP) denials for frequency need date tracking

Respond ONLY with JSON:
{
  "patientName": "string",
  "patientId": "string",
  "insurerName": "string",
  "claimNumber": "string",
  "serviceDate": "YYYY-MM-DD",
  "processingDate": "YYYY-MM-DD",
  "totalBilled": number,
  "totalAllowed": number,
  "totalInsurancePaid": number,
  "totalPatientResponsibility": number,
  "lineItems": [
    {
      "procedureCode": "string",
      "toothNumber": "string",
      "billedAmount": number,
      "allowedAmount": number,
      "insurancePaid": number,
      "patientResponsibility": number,
      "adjustments": number,
      "denialCode": "string or null",
      "denialReason": "string or null"
    }
  ]
}`;

  const raw = await askClaude(systemPrompt, rawEOBText, 2000, { dataClass: 'phi' });
  const parsed = JSON.parse(raw.replace(/```json\n?|\n?```/g, '').trim());

  const eob: ParsedEOB = {
    id: randomUUID(),
    ...parsed,
    postingStatus: 'pending',
    postingNotes: '',
    parsedAt: new Date().toISOString(),
  };
  eobStore.set(eob.id, eob);
  return eob;
}

export async function postEOB(eobId: string): Promise<EOBPostingResult> {
  const eob = eobStore.get(eobId);
  if (!eob) throw new Error(`EOB ${eobId} not found`);

  const deniedLines = eob.lineItems.filter(l => l.denialCode);
  const postedLines = eob.lineItems.filter(l => !l.denialCode);
  const totalPosted = postedLines.reduce((s, l) => s + l.insurancePaid, 0);
  const patientBalance = eob.lineItems.reduce((s, l) => s + l.patientResponsibility, 0);

  // Flag implant denials as appeal candidates
  const appealCandidates = deniedLines.filter(l =>
    ['D6010', 'D6056', 'D6058', 'D6065'].includes(l.procedureCode) ||
    l.denialCode === 'CO-45' ||
    l.denialCode === 'PR-96'
  );

  eob.postingStatus = deniedLines.length > 0 ? 'needs_review' : 'posted';
  eob.postingNotes = `Posted ${postedLines.length} lines ($${totalPosted.toFixed(2)}). ${deniedLines.length} denied lines require action. Patient balance: $${patientBalance.toFixed(2)}.`;
  eobStore.set(eobId, eob);

  return {
    eobId,
    linesPosted: postedLines.length,
    totalPosted,
    deniedLines: deniedLines.length,
    patientBalanceCreated: patientBalance,
    appealCandidates,
    postingStatus: eob.postingStatus,
    message: eob.postingNotes,
  };
}

export function getEOB(id: string): ParsedEOB | undefined { return eobStore.get(id); }
export function getAllEOBs(): ParsedEOB[] {
  return Array.from(eobStore.values()).sort((a, b) => new Date(b.parsedAt).getTime() - new Date(a.parsedAt).getTime());
}
