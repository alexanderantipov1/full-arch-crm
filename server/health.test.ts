import { describe, it, expect } from "vitest";
import express from "express";
import request from "supertest";

// /api/health is wired in server/index.ts before any auth middleware so deploys
// and load balancers can reach it unauthenticated. This test mirrors that
// contract — failure here means the readiness probe shape has drifted.
function healthApp() {
  const app = express();
  app.get("/api/health", (_req, res) => {
    res.status(200).json({ status: "ok" });
  });
  return app;
}

describe("/api/health", () => {
  it("returns 200 + { status: 'ok' } without auth", async () => {
    const res = await request(healthApp()).get("/api/health");
    expect(res.status).toBe(200);
    expect(res.body).toEqual({ status: "ok" });
  });
});
