import { Router } from 'express';
import { generateSOAPNote, suggestCDTCodes, createSession, getSession, getAllSessions, updateSessionStatus, updateSOAPNote } from './scribe-service';

export const scribeRouter = Router();

// POST /api/scribe/generate — dictation text → SOAP note + CDT codes
scribeRouter.post('/api/scribe/generate', async (req, res) => {
  try {
    const { dictationText, patientId, patientName, patientAge, providerId, providerName, existingConditions } = req.body ?? {};
    if (!dictationText) return res.status(400).json({ error: 'dictationText is required' });

    const patientContext = { id: patientId ?? 'unknown', name: patientName ?? 'Patient', age: patientAge, existingConditions };
    const soapNote = await generateSOAPNote(dictationText, patientContext);
    const cdtCodes = await suggestCDTCodes(soapNote);
    const session = createSession(patientId ?? 'unknown', patientName ?? 'Patient', providerId ?? 'provider', providerName ?? 'Provider', dictationText, soapNote, cdtCodes);

    res.json(session);
  } catch (err: any) {
    res.status(500).json({ error: String(err?.message ?? err) });
  }
});

// GET /api/scribe/sessions — all sessions
scribeRouter.get('/api/scribe/sessions', (_req, res) => {
  res.json(getAllSessions());
});

// GET /api/scribe/sessions/:id
scribeRouter.get('/api/scribe/sessions/:id', (req, res) => {
  const s = getSession(req.params.id);
  s ? res.json(s) : res.status(404).json({ error: 'Session not found' });
});

// PATCH /api/scribe/sessions/:id/status — { status: 'reviewed' | 'signed' }
scribeRouter.patch('/api/scribe/sessions/:id/status', (req, res) => {
  const s = updateSessionStatus(req.params.id, req.body.status);
  s ? res.json(s) : res.status(404).json({ error: 'Session not found' });
});

// PATCH /api/scribe/sessions/:id/soap — update SOAP note after provider edits
scribeRouter.patch('/api/scribe/sessions/:id/soap', (req, res) => {
  const s = updateSOAPNote(req.params.id, req.body.soapNote);
  s ? res.json(s) : res.status(404).json({ error: 'Session not found' });
});
