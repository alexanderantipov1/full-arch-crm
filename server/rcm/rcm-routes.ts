import { Router } from 'express';
import { randomUUID } from 'crypto';
import { parseEOBText, postEOB, getEOB, getAllEOBs } from './eob-service';
import { scrubClaim } from './claim-scrubber-service';

export const rcmRouter = Router();

// --- EOB Routes ---
rcmRouter.post('/api/rcm/eob/parse', async (req, res) => {
  try {
    const { rawEOBText } = req.body ?? {};
    if (!rawEOBText) return res.status(400).json({ error: 'rawEOBText required' });
    const eob = await parseEOBText(rawEOBText);
    res.json(eob);
  } catch (err: any) { res.status(500).json({ error: String(err?.message ?? err) }); }
});

rcmRouter.post('/api/rcm/eob/post/:id', async (req, res) => {
  try {
    const result = await postEOB(req.params.id);
    res.json(result);
  } catch (err: any) { res.status(500).json({ error: String(err?.message ?? err) }); }
});

rcmRouter.get('/api/rcm/eob', (_req, res) => { res.json(getAllEOBs()); });
rcmRouter.get('/api/rcm/eob/:id', (req, res) => {
  const e = getEOB(req.params.id);
  e ? res.json(e) : res.status(404).json({ error: 'EOB not found' });
});

// --- Claim Scrubbing Routes ---
rcmRouter.post('/api/rcm/claims/scrub', async (req, res) => {
  try {
    const claim = req.body;
    if (!claim?.lines?.length) return res.status(400).json({ error: 'claim.lines required' });
    if (!claim.id) claim.id = randomUUID(); // auto-assign if missing
    const result = await scrubClaim(claim);
    res.json(result);
  } catch (err: any) { res.status(500).json({ error: String(err?.message ?? err) }); }
});
