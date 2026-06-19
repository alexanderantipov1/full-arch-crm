import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest";
import type { Express } from "express";
import request from "supertest";

// Mock the storage at the boundary — same shape as the other route tests.
const mocks = vi.hoisted(() => ({
  storage: {
    getPaymentPostings: vi.fn(),
    updatePaymentPosting: vi.fn().mockResolvedValue(undefined),
    getFollowUps: vi.fn(),
    createFollowUp: vi.fn().mockResolvedValue({ id: 1 }),
    createAuditLog: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock("./replit_integrations/auth/replitAuth", () => ({
  setupAuth: vi.fn(async (app: any) => {
    app.use((req: any, _res: any, next: any) => {
      req.user = { claims: { sub: "ops-user", email: "ops@test" } };
      req.isAuthenticated = () => true;
      next();
    });
  }),
  isAuthenticated: (_req: any, _res: any, next: any) => next(),
  getSessionUserId: (req: any) => req.user?.claims?.sub ?? "ops-user",
}));
vi.mock("./replit_integrations/auth/routes", () => ({ registerAuthRoutes: vi.fn() }));
vi.mock("./replit_integrations/chat", () => ({ registerChatRoutes: vi.fn() }));
vi.mock("./services/ai", () => ({
  askClaude: vi.fn(),
  anthropic: {} as any,
  hasSignedAnthropicBaa: vi.fn(() => true),
}));
vi.mock("./storage", () => ({ storage: mocks.storage }));

let app: Express;

beforeAll(async () => {
  const { createApp } = await import("./app");
  const result = await createApp();
  app = result.app;
});

beforeEach(() => {
  vi.clearAllMocks();
  mocks.storage.createAuditLog.mockResolvedValue(undefined);
  mocks.storage.createFollowUp.mockResolvedValue({ id: 1 });
  mocks.storage.updatePaymentPosting.mockResolvedValue(undefined);
  mocks.storage.getFollowUps.mockResolvedValue([]);
});

describe("POST /api/era/auto-post-all — variance → Work Queue", () => {
  it("auto-posts non-variance pending postings AND queues a follow-up for each variance-flagged one", async () => {
    mocks.storage.getPaymentPostings.mockResolvedValue([
      { id: 1, patientId: 100, postingStatus: "pending", varianceFlag: false, paymentAmount: "200.00" },
      { id: 2, patientId: 200, postingStatus: "pending", varianceFlag: true, varianceReason: "underpayment", paymentAmount: "150.00", payerName: "Aetna" },
      { id: 3, patientId: 200, postingStatus: "posted", varianceFlag: false, paymentAmount: "300.00" },
    ]);

    const res = await request(app).post("/api/era/auto-post-all").send({});

    expect(res.status).toBe(200);
    expect(res.body).toEqual({ posted: 1, variancesQueued: 1 });

    // The non-variance pending posting got auto-posted.
    expect(mocks.storage.updatePaymentPosting).toHaveBeenCalledWith(1, {
      postingStatus: "posted",
      autoPosted: true,
    });
    // The variance one was NOT posted (still needs a human).
    const updateIds = mocks.storage.updatePaymentPosting.mock.calls.map((c) => c[0]);
    expect(updateIds).not.toContain(2);

    // A reconciliation follow-up was queued for the variance.
    expect(mocks.storage.createFollowUp).toHaveBeenCalledOnce();
    const fu = mocks.storage.createFollowUp.mock.calls[0][0];
    expect(fu).toMatchObject({
      patientId: 200,
      followUpType: "payment_variance",
      status: "pending",
      priority: "high",
      assignedTo: "ops-user",
    });
    expect(fu.nextAction).toMatch(/Posting #2/);
    expect(fu.nextAction).toMatch(/underpayment/);
    expect(fu.notes).toMatch(/Aetna/);
    expect(fu.dueDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("is idempotent — does NOT duplicate the variance follow-up if one already references the posting id", async () => {
    mocks.storage.getPaymentPostings.mockResolvedValue([
      { id: 7, patientId: 50, postingStatus: "pending", varianceFlag: true, varianceReason: "overpayment", paymentAmount: "1000.00" },
    ]);
    // The Work Queue already has a pending follow-up for this posting.
    mocks.storage.getFollowUps.mockResolvedValue([
      { id: 99, patientId: 50, status: "pending", nextAction: "Reconcile Posting #7 — overpayment" },
    ]);

    const res = await request(app).post("/api/era/auto-post-all").send({});

    expect(res.body.variancesQueued).toBe(0);
    expect(mocks.storage.createFollowUp).not.toHaveBeenCalled();
  });

  it("creates the follow-up when the marker appears in notes rather than nextAction", async () => {
    // Tolerate the dedup-marker living in either field — staff edits
    // shouldn't break the idempotency check.
    mocks.storage.getPaymentPostings.mockResolvedValue([
      { id: 12, patientId: 50, postingStatus: "pending", varianceFlag: true, varianceReason: "x", paymentAmount: "0" },
    ]);
    mocks.storage.getFollowUps.mockResolvedValue([
      { id: 99, patientId: 50, status: "pending", nextAction: "Other unrelated task", notes: "see Posting #12 for context" },
    ]);

    const res = await request(app).post("/api/era/auto-post-all").send({});

    expect(res.body.variancesQueued).toBe(0);
  });

  it("does not fail the endpoint if a follow-up insert throws", async () => {
    mocks.storage.getPaymentPostings.mockResolvedValue([
      { id: 8, patientId: 60, postingStatus: "pending", varianceFlag: true, varianceReason: "y", paymentAmount: "10" },
    ]);
    mocks.storage.getFollowUps.mockResolvedValue([]);
    mocks.storage.createFollowUp.mockRejectedValueOnce(new Error("queue down"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const res = await request(app).post("/api/era/auto-post-all").send({});

    expect(res.status).toBe(200);
    // The endpoint still returned cleanly; the failure was logged.
    expect(res.body.posted).toBe(0);
    expect(res.body.variancesQueued).toBe(0);
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});
