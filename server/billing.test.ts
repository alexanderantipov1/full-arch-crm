import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest";
import type { Express } from "express";
import request from "supertest";

// Mocks must be set up before importing ./app (which transitively loads
// ./routes → ./replit_integrations/auth/replitAuth → OIDC discovery).
// vi.hoisted lets us share the same vi.fn references between the mock factory
// (hoisted to the top of the file) and the test assertions below.
const mocks = vi.hoisted(() => ({
  storage: {
    getBillingStats: vi.fn(),
    getBillingClaims: vi.fn(),
    createBillingClaim: vi.fn(),
    updateBillingClaim: vi.fn(),
    getPreflightResult: vi.fn(),
    createAuditLog: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock("./replit_integrations/auth/replitAuth", () => ({
  // Mirrors how real setupAuth wires passport.session globally: a top-level
  // middleware populates req.user on every request. The PHI audit middleware
  // (registered later, also globally) relies on req.user being set already.
  setupAuth: vi.fn(async (app: any) => {
    app.use((req: any, _res: any, next: any) => {
      req.user = { claims: { sub: "test-user", email: "test@example.com" } };
      req.isAuthenticated = () => true;
      next();
    });
  }),
  isAuthenticated: (_req: any, _res: any, next: any) => next(),
  getSessionUserId: (req: any) => req.user?.claims?.sub ?? "test-user",
}));

vi.mock("./replit_integrations/auth/routes", () => ({
  registerAuthRoutes: vi.fn(),
}));

vi.mock("./replit_integrations/chat", () => ({
  registerChatRoutes: vi.fn(),
}));

vi.mock("./storage", () => ({
  storage: mocks.storage,
}));

let app: Express;

beforeAll(async () => {
  const { createApp } = await import("./app");
  const result = await createApp();
  app = result.app;
});

beforeEach(() => {
  vi.clearAllMocks();
  // createAuditLog default — re-attach after clearAllMocks wipes it.
  mocks.storage.createAuditLog.mockResolvedValue(undefined);
});

describe("/api/billing/stats", () => {
  it("returns the stats payload from storage", async () => {
    const stats = { totalClaims: 12, pending: 3, paid: 9, denied: 0 };
    mocks.storage.getBillingStats.mockResolvedValue(stats);

    const res = await request(app).get("/api/billing/stats");

    expect(res.status).toBe(200);
    expect(res.body).toEqual(stats);
    expect(mocks.storage.getBillingStats).toHaveBeenCalledOnce();
  });

  it("returns 500 with a generic message when storage throws", async () => {
    mocks.storage.getBillingStats.mockRejectedValue(new Error("connection refused"));

    const res = await request(app).get("/api/billing/stats");

    expect(res.status).toBe(500);
    expect(res.body.message).toBe("Failed to fetch billing stats");
    // The raw DB error must not leak.
    expect(res.body.message).not.toMatch(/connection refused/);
  });
});

describe("GET /api/billing/claims", () => {
  it("forwards patientId and status query filters to storage", async () => {
    mocks.storage.getBillingClaims.mockResolvedValue([]);

    const res = await request(app)
      .get("/api/billing/claims")
      .query({ patientId: "42", status: "pending" });

    expect(res.status).toBe(200);
    expect(mocks.storage.getBillingClaims).toHaveBeenCalledWith({
      patientId: 42,
      status: "pending",
    });
  });

  it("calls storage with an empty filter object when no query is passed", async () => {
    mocks.storage.getBillingClaims.mockResolvedValue([]);

    await request(app).get("/api/billing/claims");

    expect(mocks.storage.getBillingClaims).toHaveBeenCalledWith({});
  });
});

describe("POST /api/billing/claims", () => {
  const validClaim = {
    patientId: 1,
    serviceDate: "2026-05-10",
    procedureCode: "D6010",
    chargedAmount: "2500.00",
  };

  it("creates a claim on valid input", async () => {
    const created = { id: 101, ...validClaim, claimStatus: "pending" };
    mocks.storage.createBillingClaim.mockResolvedValue(created);

    const res = await request(app).post("/api/billing/claims").send(validClaim);

    expect(res.status).toBe(201);
    expect(res.body).toMatchObject({ id: 101, patientId: 1, procedureCode: "D6010" });
    expect(mocks.storage.createBillingClaim).toHaveBeenCalled();
  });

  it("rejects invalid input with 400 (Zod validation)", async () => {
    // Missing required fields — patientId, procedureCode, chargedAmount.
    const res = await request(app)
      .post("/api/billing/claims")
      .send({ serviceDate: "2026-05-10" });

    expect(res.status).toBe(400);
    expect(res.body.message).toBeTruthy();
    expect(mocks.storage.createBillingClaim).not.toHaveBeenCalled();
  });
});

describe("PATCH /api/billing/claims/:id — preflight gate", () => {
  it("blocks submission with 422 when no preflight result exists", async () => {
    mocks.storage.getPreflightResult.mockResolvedValue(null);

    const res = await request(app)
      .patch("/api/billing/claims/5")
      .send({ claimStatus: "submitted" });

    expect(res.status).toBe(422);
    expect(res.body).toMatchObject({
      preflightRequired: true,
      currentScore: null,
    });
    expect(mocks.storage.updateBillingClaim).not.toHaveBeenCalled();
  });

  it("blocks submission with 422 when riskScore is below 70", async () => {
    mocks.storage.getPreflightResult.mockResolvedValue({ riskScore: 55 });

    const res = await request(app)
      .patch("/api/billing/claims/5")
      .send({ claimStatus: "submitted" });

    expect(res.status).toBe(422);
    expect(res.body.currentScore).toBe(55);
    expect(mocks.storage.updateBillingClaim).not.toHaveBeenCalled();
  });

  it("allows submission and updates the claim when riskScore ≥ 70", async () => {
    mocks.storage.getPreflightResult.mockResolvedValue({ riskScore: 88 });
    mocks.storage.updateBillingClaim.mockResolvedValue({
      id: 5,
      claimStatus: "submitted",
    });

    const res = await request(app)
      .patch("/api/billing/claims/5")
      .send({ claimStatus: "submitted" });

    expect(res.status).toBe(200);
    expect(mocks.storage.updateBillingClaim).toHaveBeenCalledWith(5, { claimStatus: "submitted" });
  });

  it("skips the preflight gate for non-submission updates", async () => {
    mocks.storage.updateBillingClaim.mockResolvedValue({ id: 5, denialReason: "missing X-rays" });

    const res = await request(app)
      .patch("/api/billing/claims/5")
      .send({ denialReason: "missing X-rays" });

    expect(res.status).toBe(200);
    expect(mocks.storage.getPreflightResult).not.toHaveBeenCalled();
  });

  it("returns 404 when the claim does not exist", async () => {
    mocks.storage.updateBillingClaim.mockResolvedValue(undefined);

    const res = await request(app)
      .patch("/api/billing/claims/9999")
      .send({ denialReason: "wrong code" });

    expect(res.status).toBe(404);
  });
});

describe("PHI audit logging for billing routes", () => {
  it("writes an audit log entry after a successful billing request", async () => {
    mocks.storage.getBillingStats.mockResolvedValue({});

    await request(app).get("/api/billing/stats");

    // The audit middleware fires inside res.on('finish'), so wait one tick.
    await new Promise((resolve) => setImmediate(resolve));

    expect(mocks.storage.createAuditLog).toHaveBeenCalled();
    const call = mocks.storage.createAuditLog.mock.calls[0][0];
    expect(call).toMatchObject({
      userId: "test-user",
      resourceType: "billing_claim",
      action: "view",
      phiAccessed: true,
    });
  });

  it("does not write an audit log entry for failed (>=400) requests", async () => {
    mocks.storage.getBillingStats.mockRejectedValue(new Error("boom"));

    await request(app).get("/api/billing/stats");
    await new Promise((resolve) => setImmediate(resolve));

    expect(mocks.storage.createAuditLog).not.toHaveBeenCalled();
  });
});
