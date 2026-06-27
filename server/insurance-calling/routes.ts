import { Router } from 'express';
import { createCallTask, initiateCall, updateCallStatus, updateCallTranscript, getTask, getAllTasks, getQueueStats } from './call-service';

export const insuranceCallingRouter = Router();

insuranceCallingRouter.post('/api/insurance-calls/create', async (req, res) => {
  try {
    const task = await createCallTask(req.body);
    res.json(task);
  } catch (err: any) { res.status(500).json({ error: String(err?.message ?? err) }); }
});

insuranceCallingRouter.post('/api/insurance-calls/initiate/:id', async (req, res) => {
  try {
    const task = await initiateCall(req.params.id);
    res.json(task);
  } catch (err: any) { res.status(500).json({ error: String(err?.message ?? err) }); }
});

// Twilio status callback
insuranceCallingRouter.post('/api/insurance-calls/status/:id', (req, res) => {
  const { CallStatus, CallSid } = req.body;
  const statusMap: Record<string, any> = {
    'in-progress': 'in_progress', 'completed': 'completed', 'failed': 'failed', 'busy': 'failed', 'no-answer': 'failed',
  };
  updateCallStatus(req.params.id, statusMap[CallStatus] ?? 'queued', CallSid);
  res.sendStatus(200);
});

// Twilio transcription callback
insuranceCallingRouter.post('/api/insurance-calls/transcript/:id', (req, res) => {
  updateCallTranscript(req.params.id, req.body.TranscriptionText ?? '');
  res.sendStatus(200);
});

insuranceCallingRouter.get('/api/insurance-calls', (_req, res) => { res.json(getAllTasks()); });
insuranceCallingRouter.get('/api/insurance-calls/stats', (_req, res) => { res.json(getQueueStats()); });
insuranceCallingRouter.get('/api/insurance-calls/:id', (req, res) => {
  const t = getTask(req.params.id);
  t ? res.json(t) : res.status(404).json({ error: 'Task not found' });
});
