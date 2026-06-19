import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest";
import type { Express } from "express";
import request from "supertest";

// Mocks at the boundaries — same shape as billing.test.ts.
const mocks = vi.hoisted(() => ({
  storage: {
    getPatient: vi.fn(),
    getInsurance: vi.fn(),
    getPatientInsurance: vi.fn(),
    getMedicalHistory: vi.fn(),
    getTreatmentPlansByPatient: vi.fn(),
    getLatestEligibilityCheckByPatient: vi.fn(),
    createEligibilityCheck: vi.fn(),
    createFollowUp: vi.fn().mockResolvedValue({ id: 1 }),
    createAuditLog: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock("./replit_integrations/auth/replitAuth", () => ({
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
vi.mock("./replit_integrations/auth/routes", () => ({ registerAuthRoutes: vi.fn() }));
vi.mock("./replit_integrations/chat", () => ({ registerChatRoutes: vi.fn() }));

// Force askClaude to return a predictable eligibility-AI JSON shape so the
// runEligibilityCheck path is deterministic.
vi.mock("./services/ai", () => ({
  askClaude: vi.fn(),
  anthropic: {} as any,
  hasSignedAnthropicBaa: vi.fn(() => true),
}));

vi.mock("./storage", () => ({ storage: mocks.storage }));

import { askClaude } from "./services/ai";
const askClaudeMock = vi.mocked(askClaude);

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
  // The PhiService chain reads patient by id; provide one in the same
  // (default null) tenant as the principal so the gate passes.
  mocks.storage.getPatient.mockResolvedValue({
    id: 7,
    tenantId: null,
    firstName: "Jane",
    lastName: "Doe",
    dateOfBirth: "1960-01-01",
  });
  mocks.storage.getInsurance.mockResolvedValue([]);
  mocks.storage.getPatientInsurance.mockResolvedValue([]);
});

describe("POST /api/eligibility/verify/:patientId — coverage-gap → Work Queue", () => {
  it("creates a high-priority follow-up when eligibility transitions into 'inactive'", async () => {
    mocks.storage.getLatestEligibilityCheckByPatient.mockResolvedValue(null); // no prior check
    askClaudeMock.mockResolvedValue(
      JSON.stringify({
        eligibilityStatus: "inactive",
        planName: "Old Plan",
        benefitsRemaining: 0,
        deductibleMet: 0,
      }),
    );
    mocks.storage.createEligibilityCheck.mockImplementation(async (data: any) => ({
      id: 1,
      ...data,
    }));

    const res = await request(app).post("/api/eligibility/verify/7").send({});

    expect(res.status).toBe(200);
    expect(mocks.storage.createFollowUp).toHaveBeenCalledOnce();
    const fu = mocks.storage.createFollowUp.mock.calls[0][0];
    expect(fu).toMatchObject({
      patientId: 7,
      followUpType: "eligibility_gap",
      status: "pending",
      priority: "high",
      assignedTo: "test-user",
    });
    expect(fu.nextAction).toMatch(/inactive/);
    expect(fu.notes).toMatch(/inactive/);
    expect(fu.dueDate).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("does NOT create a follow-up when the patient is already in a gap (idempotent on re-check)", async () => {
    // Prior check was 'inactive'; new check is still 'inactive'. No new task.
    mocks.storage.getLatestEligibilityCheckByPatient.mockResolvedValue({
      id: 99,
      eligibilityStatus: "inactive",
      checkDate: new Date().toISOString(),
    });
    askClaudeMock.mockResolvedValue(JSON.stringify({ eligibilityStatus: "inactive" }));
    mocks.storage.createEligibilityCheck.mockImplementation(async (data: any) => ({
      id: 2,
      ...data,
    }));

    const res = await request(app)
      .post("/api/eligibility/verify/7")
      .send({ forceRefresh: true });

    expect(res.status).toBe(200);
    expect(mocks.storage.createFollowUp).not.toHaveBeenCalled();
  });

  it("does NOT create a follow-up when eligibility is 'active'", async () => {
    mocks.storage.getLatestEligibilityCheckByPatient.mockResolvedValue(null);
    askClaudeMock.mockResolvedValue(JSON.stringify({ eligibilityStatus: "active" }));
    mocks.storage.createEligibilityCheck.mockImplementation(async (data: any) => ({
      id: 3,
      ...data,
    }));

    await request(app).post("/api/eligibility/verify/7").send({});

    expect(mocks.storage.createFollowUp).not.toHaveBeenCalled();
  });

  it("does not fail the eligibility check if the follow-up insert throws", async () => {
    mocks.storage.getLatestEligibilityCheckByPatient.mockResolvedValue(null);
    askClaudeMock.mockResolvedValue(JSON.stringify({ eligibilityStatus: "terminated" }));
    mocks.storage.createEligibilityCheck.mockImplementation(async (data: any) => ({
      id: 4,
      ...data,
    }));
    mocks.storage.createFollowUp.mockRejectedValueOnce(new Error("queue down"));
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    const res = await request(app).post("/api/eligibility/verify/7").send({});

    expect(res.status).toBe(200);
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});
