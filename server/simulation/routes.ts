// Express router for the simulation + self-improvement API. Mounted in
// server/routes.ts via app.use(simulationRouter).

import { Router } from "express";
import { simulationEngine } from "./engine";
import { orchestrationAgent } from "./orchestrator";
import { selfCheckAgent } from "./self-check";
import { abTestingEngine } from "./ab-testing";

export const simulationRouter = Router();

// Kick off a single synchronous batch and return the resulting state.
simulationRouter.post("/api/simulation/run", async (req, res) => {
  try {
    const patientCount = Number(req.body?.patientCount) || 20;
    const state = await simulationEngine.runBatch(patientCount);
    res.json(state);
  } catch {
    res.status(500).json({ message: "Failed to run simulation batch" });
  }
});

// Fire-and-forget continuous run. Returns immediately; clients poll
// GET /api/simulation/state (which exposes isRunning) for progress.
simulationRouter.post("/api/simulation/run-continuous", (req, res) => {
  const iterations = Number(req.body?.iterations) || 5;
  void simulationEngine.runContinuous(iterations).catch(() => {
    // Background run failures are surfaced through state, not this response.
  });
  res.json({ started: true });
});

simulationRouter.get("/api/simulation/state", (_req, res) => {
  res.json(simulationEngine.getState());
});

simulationRouter.post("/api/simulation/approve/:id", (req, res) => {
  const state = simulationEngine.approveHypothesis(req.params.id);
  res.json(state);
});

simulationRouter.post("/api/simulation/reject/:id", (req, res) => {
  const state = simulationEngine.rejectHypothesis(req.params.id);
  res.json(state);
});

simulationRouter.post("/api/simulation/reset", (_req, res) => {
  res.json(simulationEngine.resetState());
});

// Export the full state as a downloadable JSON file.
simulationRouter.get("/api/simulation/export", (_req, res) => {
  res.setHeader("Content-Type", "application/json");
  res.setHeader(
    "Content-Disposition",
    'attachment; filename="simulation-state.json"',
  );
  res.send(JSON.stringify(simulationEngine.getState(), null, 2));
});

// --- Orchestration + self-check routes ---

// Run a single orchestration cycle (batch + self-check + decision).
simulationRouter.post(
  "/api/simulation/orchestrate/run-cycle",
  async (req, res) => {
    try {
      const { patientCount = 20 } = req.body ?? {};
      const cycle = await orchestrationAgent.runCycle(Number(patientCount));
      res.json(cycle);
    } catch (err: any) {
      res.status(500).json({ error: String(err?.message ?? err) });
    }
  },
);

// Fire-and-forget autonomous loop. Returns immediately; clients poll
// GET /api/simulation/orchestrate/cycles for progress.
simulationRouter.post("/api/simulation/orchestrate/run-loop", (req, res) => {
  const { maxCycles = 20, targetScore = 85, patientCount = 20 } =
    req.body ?? {};
  if (orchestrationAgent.isCurrentlyLooping()) {
    res.status(409).json({ error: "Loop already running" });
    return;
  }
  res.json({ started: true, maxCycles, targetScore });
  orchestrationAgent
    .runLoop({
      maxCycles: Number(maxCycles),
      targetScore: Number(targetScore),
      patientCount: Number(patientCount),
    })
    .catch(console.error);
});

simulationRouter.post("/api/simulation/orchestrate/stop-loop", (_req, res) => {
  orchestrationAgent.stopLoop();
  res.json({ stopped: true });
});

simulationRouter.get("/api/simulation/orchestrate/cycles", (_req, res) => {
  res.json({
    cycles: orchestrationAgent.getCycleHistory(),
    isLooping: orchestrationAgent.isCurrentlyLooping(),
  });
});

simulationRouter.get("/api/simulation/self-check", async (_req, res) => {
  try {
    const state = simulationEngine.getState();
    const episodes = (state as any).recentEpisodes ?? state.episodes ?? [];
    const report = await selfCheckAgent.analyze(state, episodes);
    res.json(report);
  } catch (err: any) {
    res.status(500).json({ error: String(err?.message ?? err) });
  }
});

// --- A/B agent testing routes ---

simulationRouter.post("/api/simulation/ab/create", async (req, res) => {
  try {
    const test = abTestingEngine.createTest(req.body);
    res.json(test);
  } catch (err: any) {
    res.status(400).json({ error: String(err?.message ?? err) });
  }
});

simulationRouter.post("/api/simulation/ab/run/:id", async (req, res) => {
  try {
    const result = await abTestingEngine.runTest(req.params.id);
    res.json(result);
  } catch (err: any) {
    res.status(500).json({ error: String(err?.message ?? err) });
  }
});

simulationRouter.get("/api/simulation/ab/suite", (_req, res) => {
  res.json(abTestingEngine.getSuite());
});
