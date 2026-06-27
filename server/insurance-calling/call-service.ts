import { randomUUID } from 'crypto';
import { askClaude } from '../services/ai';
import type { InsuranceCallTask, CallPurpose, CallQueueStats } from './types';

const callStore = new Map<string, InsuranceCallTask>();

// Check if Twilio is configured
const TWILIO_AVAILABLE = !!(
  process.env.TWILIO_ACCOUNT_SID &&
  process.env.TWILIO_AUTH_TOKEN &&
  process.env.TWILIO_FROM_NUMBER
);

// Generate AI call script for the agent/staff making the call
export async function generateCallScript(
  purpose: CallPurpose,
  task: Omit<InsuranceCallTask, 'id' | 'callScript' | 'status' | 'callSid' | 'callDuration' | 'transcript' | 'outcome' | 'createdAt' | 'completedAt' | 'notes'>
): Promise<string> {
  const purposeMap: Record<CallPurpose, string> = {
    claim_status: 'checking the status of a submitted claim',
    denial_appeal: 'appealing a denied claim',
    prior_auth: 'requesting prior authorization for a procedure',
    eligibility_verify: 'verifying patient insurance eligibility and benefits',
    payment_status: 'checking payment status on an approved claim',
  };

  const systemPrompt = `You are a dental insurance specialist at a full-arch implant practice.

Generate a professional, concise call script for ${purposeMap[purpose]}.

The script should:
1. Opening: State practice name, caller name placeholder [NAME], call purpose
2. Patient verification: read back patient name, DOB, and insurance ID
3. Core ask: specific question or request with claim number and CDT codes
4. Key questions to ask (numbered list)
5. Information to document: what to write down during the call
6. Closing: reference number request, name of rep, callback number

For implant claim appeals (D6010, D6056, D6065):
- Reference medical necessity: edentulous ridge, masticatory dysfunction (ICD-10 K08.1)
- Cite CDT to CPT cross-coding opportunity (D6010 → CPT 21248)
- Ask if medical insurance can be billed instead

Keep script under 300 words. Use [BRACKETS] for fill-in variables.`;

  const userMessage = `Purpose: ${purpose}
Patient: ${task.patientName}, DOB: ${task.patientDOB}, Insurance ID: ${task.patientInsuranceId}
Insurer: ${task.insurerName}
Claim #: ${task.claimNumber}
Procedures: ${task.procedureCodes.join(', ')}`;

  return await askClaude(systemPrompt, userMessage, 600, { dataClass: 'phi' });
}

export async function createCallTask(input: {
  patientName: string;
  patientDOB: string;
  patientInsuranceId: string;
  insurerName: string;
  insurerPhone: string;
  claimNumber: string;
  procedureCodes: string[];
  purpose: CallPurpose;
  priority?: InsuranceCallTask['priority'];
}): Promise<InsuranceCallTask> {
  const taskPartial = {
    patientName: input.patientName,
    patientDOB: input.patientDOB,
    patientInsuranceId: input.patientInsuranceId,
    insurerName: input.insurerName,
    insurerPhone: input.insurerPhone,
    claimNumber: input.claimNumber,
    procedureCodes: input.procedureCodes,
    purpose: input.purpose,
    priority: input.priority ?? 'standard',
  };

  const callScript = await generateCallScript(input.purpose, taskPartial);

  const task: InsuranceCallTask = {
    id: randomUUID(),
    ...taskPartial,
    callScript,
    status: 'queued',
    callSid: null,
    callDuration: null,
    transcript: null,
    outcome: null,
    notes: '',
    createdAt: new Date().toISOString(),
    completedAt: null,
  };

  callStore.set(task.id, task);
  return task;
}

export async function initiateCall(taskId: string): Promise<InsuranceCallTask> {
  const task = callStore.get(taskId);
  if (!task) throw new Error(`Task ${taskId} not found`);

  if (TWILIO_AVAILABLE) {
    // Live Twilio call
    try {
      // Dynamic import to avoid crash when twilio not installed
      const twilio = require('twilio');
      const client = twilio(process.env.TWILIO_ACCOUNT_SID, process.env.TWILIO_AUTH_TOKEN);

      // TwiML: read the script and record
      const twiml = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna">This is an automated call from Fusion Dental. ${task.callScript.substring(0, 200)}...</Say>
  <Record maxLength="300" transcribe="true" transcribeCallback="/api/insurance-calls/transcript/${taskId}" />
</Response>`;

      const call = await client.calls.create({
        twiml,
        to: task.insurerPhone,
        from: process.env.TWILIO_FROM_NUMBER,
        statusCallback: `${process.env.APP_URL ?? 'https://localhost:5000'}/api/insurance-calls/status/${taskId}`,
        statusCallbackMethod: 'POST',
      });

      task.callSid = call.sid;
      task.status = 'initiated';
    } catch (err: any) {
      task.status = 'failed';
      task.notes = `Twilio error: ${err.message}`;
    }
  } else {
    // Mock mode — simulate a completed call
    task.status = 'mock_completed';
    task.callSid = `MOCK-${randomUUID().substring(0, 8).toUpperCase()}`;
    task.callDuration = Math.floor(Math.random() * 480) + 120; // 2-10 min
    task.transcript = `[MOCK TRANSCRIPT]\nAgent: This is Fusion Dental calling about claim #${task.claimNumber} for ${task.patientName}.\nInsurer Rep: Thank you for calling. Let me pull up that claim.\nAgent: We're following up on ${task.procedureCodes.join(', ')}.\nInsurer Rep: I see the claim. It's currently in processing. Expected payment in 7-10 business days.\nAgent: Thank you. Can I get a reference number?\nInsurer Rep: Reference number is REF-${Math.random().toString(36).substring(2, 8).toUpperCase()}.`;
    task.outcome = {
      resolved: true,
      summary: `Mock: Claim ${task.claimNumber} confirmed in processing. Expected payment 7-10 days.`,
      nextAction: 'Monitor ERA within 10 business days',
      referenceNumber: `REF-${Math.random().toString(36).substring(2, 8).toUpperCase()}`,
      followUpDate: new Date(Date.now() + 10 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    };
    task.completedAt = new Date().toISOString();
  }

  callStore.set(taskId, task);
  return task;
}

export function updateCallStatus(taskId: string, status: InsuranceCallTask['status'], callSid?: string): void {
  const task = callStore.get(taskId);
  if (!task) return;
  task.status = status;
  if (callSid) task.callSid = callSid;
  if (status === 'completed') task.completedAt = new Date().toISOString();
  callStore.set(taskId, task);
}

export function updateCallTranscript(taskId: string, transcript: string): void {
  const task = callStore.get(taskId);
  if (!task) return;
  task.transcript = transcript;
  callStore.set(taskId, task);
}

export function getTask(id: string): InsuranceCallTask | undefined { return callStore.get(id); }
export function getAllTasks(): InsuranceCallTask[] {
  return Array.from(callStore.values()).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
}

export function getQueueStats(): CallQueueStats {
  const all = getAllTasks();
  const today = new Date().toISOString().split('T')[0];
  return {
    queued: all.filter(t => t.status === 'queued').length,
    inProgress: all.filter(t => t.status === 'in_progress' || t.status === 'initiated').length,
    completedToday: all.filter(t => t.completedAt?.startsWith(today)).length,
    resolvedToday: all.filter(t => t.completedAt?.startsWith(today) && t.outcome?.resolved).length,
    estimatedRevenuePending: all.filter(t => t.status === 'queued').length * 2500, // avg implant claim
  };
}
