import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest";
import type { Express } from "express";
import request from "supertest";

// These tests run with STRIPE_SECRET_KEY unset (default in vitest.config.ts),
// so routes.ts initializes `stripe` to null and we exercise the simulated /
// no-Stripe code paths. To test the real-Stripe branches (intent.status check,
// patientId metadata validation), a sibling file would set STRIPE_SECRET_KEY
// and vi.mock("stripe") before imports.

const mocks = vi.hoisted(() => ({
  storage: {
    getStripePaymentByIntentId: vi.fn(),
    createStripePayment: vi.fn(),
    createPaymentPosting: vi.fn(),
    getAllStripePayments: vi.fn(),
    getStripePaymentsByPatient: vi.fn(),
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
  mocks.storage.createAuditLog.mockResolvedValue(undefined);
});

describe("GET /api/payments/config", () => {
  it("reports stripe as not configured when no key is set", async () => {
    const res = await request(app).get("/api/payments/config");

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({
      configured: false,
      testMode: true,
    });
    // publishableKey may be null or string depending on env; just ensure the field exists.
    expect(res.body).toHaveProperty("publishableKey");
  });
});

describe("POST /api/payments/create-intent", () => {
  it("rejects missing amount with 400", async () => {
    const res = await request(app)
      .post("/api/payments/create-intent")
      .send({ patientId: 1 });

    expect(res.status).toBe(400);
    expect(res.body.message).toMatch(/amount/i);
  });

  it("rejects zero or negative amount with 400", async () => {
    const zero = await request(app)
      .post("/api/payments/create-intent")
      .send({ amount: 0, patientId: 1 });
    expect(zero.status).toBe(400);

    const negative = await request(app)
      .post("/api/payments/create-intent")
      .send({ amount: -50, patientId: 1 });
    expect(negative.status).toBe(400);
  });

  it("rejects missing patientId with 400", async () => {
    const res = await request(app)
      .post("/api/payments/create-intent")
      .send({ amount: 100 });

    expect(res.status).toBe(400);
    expect(res.body.message).toMatch(/patient/i);
  });

  it("returns a simulated intent when Stripe is not configured", async () => {
    const res = await request(app)
      .post("/api/payments/create-intent")
      .send({ amount: 250.5, patientId: 42 });

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({
      simulated: true,
      testMode: true,
    });
    expect(res.body.paymentIntentId).toMatch(/^pi_test_/);
    expect(res.body.clientSecret).toContain(res.body.paymentIntentId);
  });
});

describe("POST /api/payments/confirm — validation", () => {
  it("rejects missing paymentIntentId with 400", async () => {
    const res = await request(app)
      .post("/api/payments/confirm")
      .send({ patientId: 1 });

    expect(res.status).toBe(400);
    expect(res.body.message).toMatch(/required/i);
  });

  it("rejects missing patientId with 400", async () => {
    const res = await request(app)
      .post("/api/payments/confirm")
      .send({ paymentIntentId: "pi_test_x" });

    expect(res.status).toBe(400);
  });

  it("returns 500 when real (non-simulated) confirm is attempted without Stripe configured", async () => {
    mocks.storage.getStripePaymentByIntentId.mockResolvedValue(null);

    const res = await request(app)
      .post("/api/payments/confirm")
      .send({
        paymentIntentId: "pi_real_1",
        patientId: 1,
        simulated: false,
      });

    expect(res.status).toBe(500);
    expect(res.body.message).toMatch(/Stripe not configured/);
    // Critically, nothing was written to the books.
    expect(mocks.storage.createStripePayment).not.toHaveBeenCalled();
    expect(mocks.storage.createPaymentPosting).not.toHaveBeenCalled();
  });
});

describe("POST /api/payments/confirm — idempotency", () => {
  it("returns the existing record without re-recording when intent was already confirmed", async () => {
    const existing = {
      id: 7,
      patientId: 1,
      stripePaymentIntentId: "pi_test_dup",
      amount: 10000,
      currency: "usd",
      status: "succeeded",
    };
    mocks.storage.getStripePaymentByIntentId.mockResolvedValue(existing);

    const res = await request(app)
      .post("/api/payments/confirm")
      .send({
        paymentIntentId: "pi_test_dup",
        patientId: 1,
        amount: 100,
        simulated: true,
      });

    expect(res.status).toBe(200);
    expect(res.body).toEqual(existing);
    // The whole point of the idempotency guard — no double-write.
    expect(mocks.storage.createStripePayment).not.toHaveBeenCalled();
    expect(mocks.storage.createPaymentPosting).not.toHaveBeenCalled();
  });

  it("records the payment when the intent is new", async () => {
    mocks.storage.getStripePaymentByIntentId.mockResolvedValue(null);
    const created = { id: 99, patientId: 1, amount: 25000, currency: "usd" };
    mocks.storage.createStripePayment.mockResolvedValue(created);
    mocks.storage.createPaymentPosting.mockResolvedValue({ id: 88 });

    const res = await request(app)
      .post("/api/payments/confirm")
      .send({
        paymentIntentId: "pi_test_new",
        patientId: 1,
        amount: 250,
        patientName: "Jane Doe",
        simulated: true,
      });

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ id: 99, isSimulated: true });
    expect(mocks.storage.createStripePayment).toHaveBeenCalledOnce();
    expect(mocks.storage.createPaymentPosting).toHaveBeenCalledOnce();
  });
});

describe("POST /api/payments/confirm — simulated mode bookkeeping", () => {
  it("converts a dollar amount to cents and records authoritative fields", async () => {
    mocks.storage.getStripePaymentByIntentId.mockResolvedValue(null);
    mocks.storage.createStripePayment.mockResolvedValue({ id: 1 });
    mocks.storage.createPaymentPosting.mockResolvedValue({ id: 1 });

    await request(app)
      .post("/api/payments/confirm")
      .send({
        paymentIntentId: "pi_test_amt",
        patientId: 42,
        amount: 199.95,
        patientName: "Cash Patient",
        simulated: true,
      });

    const paymentArgs = mocks.storage.createStripePayment.mock.calls[0][0];
    expect(paymentArgs).toMatchObject({
      patientId: 42,
      stripePaymentIntentId: "pi_test_amt",
      amount: 19995, // dollars → cents
      currency: "usd",
      status: "succeeded",
      collectedBy: "test-user", // from the authenticated session
      testMode: true,
    });
  });

  it("posts the matching AR entry with payerName derived from patientName", async () => {
    mocks.storage.getStripePaymentByIntentId.mockResolvedValue(null);
    mocks.storage.createStripePayment.mockResolvedValue({ id: 12 });
    mocks.storage.createPaymentPosting.mockResolvedValue({ id: 88 });

    await request(app)
      .post("/api/payments/confirm")
      .send({
        paymentIntentId: "pi_test_ar",
        patientId: 7,
        amount: 500,
        patientName: "John Smith",
        claimId: "33",
        simulated: true,
      });

    const postingArgs = mocks.storage.createPaymentPosting.mock.calls[0][0];
    expect(postingArgs).toMatchObject({
      patientId: 7,
      claimId: 33,
      checkNumber: "pi_test_ar",
      paymentAmount: "500.00",
      patientResponsibility: "500.00",
      postingStatus: "posted",
      autoPosted: true,
      payerName: "Patient — John Smith",
    });
  });

  it("falls back to a generic payerName when no patientName is provided", async () => {
    mocks.storage.getStripePaymentByIntentId.mockResolvedValue(null);
    mocks.storage.createStripePayment.mockResolvedValue({ id: 13 });
    mocks.storage.createPaymentPosting.mockResolvedValue({ id: 89 });

    await request(app)
      .post("/api/payments/confirm")
      .send({
        paymentIntentId: "pi_test_anon",
        patientId: 7,
        amount: 100,
        simulated: true,
      });

    const postingArgs = mocks.storage.createPaymentPosting.mock.calls[0][0];
    expect(postingArgs.payerName).toBe("Patient — Card");
  });
});

describe("GET /api/payments/history", () => {
  it("returns the payment activity feed with a 200-row cap", async () => {
    const rows = [{ id: 1 }, { id: 2 }];
    mocks.storage.getAllStripePayments.mockResolvedValue(rows);

    const res = await request(app).get("/api/payments/history");

    expect(res.status).toBe(200);
    expect(res.body).toEqual(rows);
    expect(mocks.storage.getAllStripePayments).toHaveBeenCalledWith(200);
  });

  it("returns 500 with a generic message on storage failure", async () => {
    mocks.storage.getAllStripePayments.mockRejectedValue(new Error("db down — connection string visible"));

    const res = await request(app).get("/api/payments/history");

    expect(res.status).toBe(500);
    expect(res.body.message).toBe("Failed to fetch payment history");
    expect(res.body.message).not.toMatch(/connection string/);
  });
});

describe("GET /api/payments/history/:patientId", () => {
  it("forwards the patient id to storage", async () => {
    mocks.storage.getStripePaymentsByPatient.mockResolvedValue([]);

    const res = await request(app).get("/api/payments/history/42");

    expect(res.status).toBe(200);
    expect(mocks.storage.getStripePaymentsByPatient).toHaveBeenCalledWith(42);
  });
});
