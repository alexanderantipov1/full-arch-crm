import { randomUUID } from 'crypto';
import { askClaude } from '../services/ai';
import type { ScribeSession, SOAPNote, SuggestedCode } from './types';

// In-memory store (no DB migration needed)
const sessions = new Map<string, ScribeSession>();

export async function generateSOAPNote(
  dictationText: string,
  patientContext: { id: string; name: string; age?: number; existingConditions?: string }
): Promise<SOAPNote> {
  const systemPrompt = `You are an expert dental clinical documentation AI for a full-arch implant practice.

Your job is to convert a dentist's or assistant's dictated clinical notes into a structured SOAP note.

DENTAL DOCUMENTATION STANDARDS:
- Subjective: Chief complaint in patient's words, history of present illness, pain scale (0-10), duration
- Objective: Clinical exam findings, periodontal charting if mentioned, radiographic findings (describe what's visible), soft tissue exam, implant stability if applicable
- Assessment: Primary diagnosis with ICD-10 code, secondary findings, implant osseointegration status if relevant
- Plan: Specific CDT-coded procedures planned, sequencing, medications prescribed (name/dose/duration), follow-up timeline
- For implant cases: always note implant site (#tooth), system, torque value, ISQ score if dictated
- Use proper dental terminology: probing depths in mm, BOP notation, furcation classification
- ICD-10 codes: K08.101 (complete loss maxillary), K08.111 (complete loss mandibular), K08.401 (partial loss), M27.62 (osseointegration failure)

Patient context: ${JSON.stringify(patientContext)}

Respond ONLY with JSON matching this exact structure:
{
  "subjective": "string",
  "objective": "string",
  "assessment": "string",
  "plan": "string",
  "implantSpecific": null | {
    "implantSite": "string",
    "implantSystem": "string",
    "torqueValue": "string",
    "isq": "string",
    "healingAbutment": "string",
    "nextStep": "string"
  }
}`;

  const raw = await askClaude(systemPrompt, dictationText, 1500, { dataClass: 'phi' });
  try {
    return JSON.parse(raw.replace(/```json\n?|\n?```/g, '').trim()) as SOAPNote;
  } catch {
    // Fallback: structure raw text into SOAP sections
    return {
      subjective: 'See dictation below.',
      objective: dictationText,
      assessment: 'AI parsing error — manual review required.',
      plan: 'Provider to complete.',
      implantSpecific: undefined,
    };
  }
}

export async function suggestCDTCodes(soapNote: SOAPNote): Promise<SuggestedCode[]> {
  const systemPrompt = `You are a dental billing and coding expert specializing in implant dentistry.

Given a SOAP note, suggest the most appropriate CDT codes with confidence levels.

IMPLANT CDT CODES TO KNOW:
- D6010: Implant body placement (surgical)
- D6056: Prefabricated abutment
- D6058: Abutment crown - porcelain fused to titanium
- D6065: Implant crown - porcelain fused to titanium
- D6190: Radiographic/surgical implant index (by report)
- D6199: Unspecified implant procedure (by report)
- D7310: Alveoloplasty in conjunction with extractions
- D4341: Periodontal scaling and root planing - 4+ teeth per quadrant
- D0330: Panoramic radiographic image
- D0340: 2D cephalometric radiographic image
- D9930: Treatment of complications (post-surgical)

Respond ONLY with JSON array:
[{"code": "D6010", "description": "...", "fee": 2500, "confidence": "high", "rationale": "..."}]
Fee should be typical fee for California. Maximum 6 codes.`;

  const raw = await askClaude(systemPrompt, JSON.stringify(soapNote), 800, { dataClass: 'phi' });
  try {
    return JSON.parse(raw.replace(/```json\n?|\n?```/g, '').trim()) as SuggestedCode[];
  } catch {
    return [];
  }
}

export function createSession(
  patientId: string,
  patientName: string,
  providerId: string,
  providerName: string,
  dictationText: string,
  soapNote: SOAPNote,
  cdtCodes: SuggestedCode[]
): ScribeSession {
  const session: ScribeSession = {
    id: randomUUID(),
    patientId,
    patientName,
    providerId,
    providerName,
    dictationText,
    soapNote,
    cdtCodes,
    status: 'draft',
    createdAt: new Date().toISOString(),
    signedAt: null,
  };
  sessions.set(session.id, session);
  return session;
}

export function getSession(id: string): ScribeSession | undefined {
  return sessions.get(id);
}

export function getAllSessions(): ScribeSession[] {
  return Array.from(sessions.values()).sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );
}

export function updateSessionStatus(id: string, status: ScribeSession['status']): ScribeSession | null {
  const s = sessions.get(id);
  if (!s) return null;
  s.status = status;
  if (status === 'signed') s.signedAt = new Date().toISOString();
  sessions.set(id, s);
  return s;
}

export function updateSOAPNote(id: string, soapNote: SOAPNote): ScribeSession | null {
  const s = sessions.get(id);
  if (!s) return null;
  s.soapNote = soapNote;
  s.status = 'draft';
  sessions.set(id, s);
  return s;
}
