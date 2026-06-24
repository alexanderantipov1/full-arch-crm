// Express router for the simulation + self-improvement API. Mounted in
// server/routes.ts via app.use(simulationRouter).

import { Router } from "express";
import { simulationEngine } from "./engine";

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
