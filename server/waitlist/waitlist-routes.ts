import { Router } from 'express';
import { addToWaitlist, getWaitlist, updateEntryStatus, recordContactAttempt, removeFromWaitlist, openCancellationSlot, fillSlot, getOpenSlots, getWaitlistStats } from './waitlist-service';

export const waitlistRouter = Router();

waitlistRouter.post('/api/waitlist', (req, res) => {
  const entry = addToWaitlist(req.body);
  res.json(entry);
});

waitlistRouter.get('/api/waitlist', (req, res) => {
  const { status } = req.query as Record<string, string>;
  res.json(getWaitlist(status as any));
});

waitlistRouter.get('/api/waitlist/stats', (_req, res) => { res.json(getWaitlistStats()); });

waitlistRouter.patch('/api/waitlist/:id/status', (req, res) => {
  const e = updateEntryStatus(req.params.id, req.body.status);
  e ? res.json(e) : res.status(404).json({ error: 'Entry not found' });
});

waitlistRouter.post('/api/waitlist/:id/contact', (req, res) => {
  const e = recordContactAttempt(req.params.id);
  e ? res.json(e) : res.status(404).json({ error: 'Entry not found' });
});

waitlistRouter.delete('/api/waitlist/:id', (req, res) => {
  const ok = removeFromWaitlist(req.params.id);
  ok ? res.json({ removed: true }) : res.status(404).json({ error: 'Entry not found' });
});

waitlistRouter.post('/api/waitlist/slots/open', (req, res) => {
  const result = openCancellationSlot(req.body);
  res.json(result);
});

waitlistRouter.post('/api/waitlist/slots/:id/fill', (req, res) => {
  const ok = fillSlot(req.params.id, req.body.patientId);
  ok ? res.json({ filled: true }) : res.status(404).json({ error: 'Slot not found' });
});

waitlistRouter.get('/api/waitlist/slots/open', (_req, res) => { res.json(getOpenSlots()); });
