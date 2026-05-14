import { describe, it, expect, vi, beforeAll, beforeEach } from "vitest";
import type { Express } from "express";
import request from "supertest";

// Exercises the real-Stripe branches of /api/payments/* — the security-critical
// code that pulls authoritative amount/status/patientId from Stripe (instead
// of trusting client input) and rejects status mismatches.
//
// Setup requires:
//   1. STRIPE_SECRET_KEY set before routes.ts loads (so `stripe` is non-null)
//   2. The `stripe` module mocked so `new Stripe(...)` returns our stub
//
// Both happen via vi.hoisted + vi.mock at the top of this file — they run
// before the dynamic `import("./app")` inside beforeAll.

const stripeStub = vi.hoisted(() => {
  // Setting STRIPE_SECRET_KEY here (in hoisted scope) is what flips routes.ts
  // out of simulated mode for this test file. Vitest isolates workers per
  // file so this doesn't leak to other test files.
  process.env.STRIPE_SECRET_KEY = "sk_test_mock_stripe_secret";
  return {
    paymentIntents: {
      create: vi.fn(),
      retrieve: vi.fn(),
    },
  };
});

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

// The Stripe SDK is imported as a default export and used as a constructor:
//   `import Stripe from "stripe"; const stripe = new Stripe(key, opts);`
// The mock must be a `function` (not an arrow) so it's constructable, and it
// explicitly returns our stub so `new MockStripe(...)` resolves to stripeStub.
vi.mock("stripe", () => ({
  default: function MockStripe() {
    return stripeStub;
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

describe("POST /api/payments/create-intent — real Stripe", () => {
  it("calls Stripe.paymentIntents.create with the right shape", async () => {
    stripeStub.paymentIntents.create.mockResolvedValue({
      id: "pi_real_1",
      client_secret: "pi_real_1_secret_xyz",
    });

    const res = await request(app)
      .post("/api/payments/create-intent")
      .send({
        amount: 250.5,
        patientId: 42,
        patientName: "Jane Doe",
        description: "Implant retainer",
        receiptEmail: "jane@example.com",
      });

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({
      paymentIntentId: "pi_real_1",
      clientSecret: "pi_real_1_secret_xyz",
      simulated: false,
      testMode: true, // sk_test_ prefix
    });

    expect(stripeStub.paymentIntents.create).toHaveBeenCalledOnce();
    const args = stripeStub.paymentIntents.create.mock.calls[0][0];
    expect(args).toMatchObject({
      amount: 25050, // dollars → cents, no float drift
      currency: "usd",
      description: "Implant retainer",
      receipt_email: "jane@example.com",
      metadata: { patientId: "42", patientName: "Jane Doe" },
      // No redirects allowed — limits payment methods to cards, which is why
      // no webhook is needed for this flow.
      automatic_payment_methods: { enabled: true, allow_redirects: "never" },
    });
  });

  it("returns 500 with the Stripe error message when create fails", async () => {
    stripeStub.paymentIntents.create.mockRejectedValue(new Error("Your card was declined"));

    const res = await request(app)
      .post("/api/payments/create-intent")
      .send({ amount: 100, patientId: 1 });

    expect(res.status).toBe(500);
  });
});

describe("POST /api/payments/confirm — Stripe verification", () => {
  it("rejects with 400 when the intent status is not 'succeeded'", async () => {
    mocks.storage.getStripePaymentByIntentId.mockResolvedValue(null);
    stripeStub.paymentIntents.retrieve.mockResolvedValue({
      id: "pi_real_pending",
      status: "requires_payment_method",
      amount: 10000,
      currency: "usd",
      metadata: { patientId: "1" },
    });

    const res = await request(app)
      .post("/api/payments/confirm")
      .send({
        paymentIntentId: "pi_real_pending",
        patientId: 1,
        simulated: false,
      });

    expect(res.status).toBe(400);
    expect(res.body.message).toMatch(/requires_payment_method/);
    // No money written to the books for an unsuccessful intent.
    expect(mocks.storage.createStripePayment).not.toHaveBeenCalled();
    expect(mocks.storage.createPaymentPosting).not.toHaveBeenCalled();
  });

  it("rejects with 400 when intent metadata patientId doesn't match the request", async () => {
    mocks.storage.getStripePaymentByIntentId.mockResolvedValue(null);
    stripeStub.paymentIntents.retrieve.mockResolvedValue({
      id: "pi_real_wrong",
      status: "succeeded",
      amount: 10000,
      currency: "usd",
      metadata: { patientId: "999" }, // intent belongs to patient 999
    });

    const res = await request(app)
      .post("/api/payments/confirm")
      .send({
        paymentIntentId: "pi_real_wrong",
        patientId: 1, // but caller claims patient 1
        simulated: false,
      });

    expect(res.status).toBe(400);
    expect(res.body.message).toMatch(/Patient ID mismatch/);
    expect(mocks.storage.createStripePayment).not.toHaveBeenCalled();
    expect(mocks.storage.createPaymentPosting).not.toHaveBeenCalled();
  });

  it("uses the authoritative amount from Stripe, not the request body", async () => {
    mocks.storage.getStripePaymentByIntentId.mockResolvedValue(null);
    // Stripe reports the real charged amount: $50.00 (5000 cents).
    stripeStub.paymentIntents.retrieve.mockResolvedValue({
      id: "pi_real_amt",
      status: "succeeded",
      amount: 5000,
      currency: "usd",
      receipt_email: "real@example.com",
      metadata: { patientId: "1" },
    });
    mocks.storage.createStripePayment.mockResolvedValue({ id: 42 });
    mocks.storage.createPaymentPosting.mockResolvedValue({ id: 43 });

    // Caller sends amount: 99999 (an attempt to inflate the recorded payment).
    await request(app)
      .post("/api/payments/confirm")
      .send({
        paymentIntentId: "pi_real_amt",
        patientId: 1,
        amount: 99999,
        simulated: false,
      });

    const paymentArgs = mocks.storage.createStripePayment.mock.calls[0][0];
    expect(paymentArgs.amount).toBe(5000); // Stripe wins, body ignored
    expect(paymentArgs.currency).toBe("usd");
    expect(paymentArgs.receiptEmail).toBe("real@example.com"); // also from Stripe

    const postingArgs = mocks.storage.createPaymentPosting.mock.calls[0][0];
    expect(postingArgs.paymentAmount).toBe("50.00"); // 5000 cents formatted, NOT 999.99
  });

  it("accepts the request when patientId is matched", async () => {
    mocks.storage.getStripePaymentByIntentId.mockResolvedValue(null);
    stripeStub.paymentIntents.retrieve.mockResolvedValue({
      id: "pi_real_ok",
      status: "succeeded",
      amount: 12345,
      currency: "usd",
      metadata: { patientId: "7" },
    });
    mocks.storage.createStripePayment.mockResolvedValue({ id: 1, patientId: 7 });
    mocks.storage.createPaymentPosting.mockResolvedValue({ id: 2 });

    const res = await request(app)
      .post("/api/payments/confirm")
      .send({
        paymentIntentId: "pi_real_ok",
        patientId: 7,
        simulated: false,
      });

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({ id: 1, isSimulated: false });
  });

  it("short-circuits on idempotent replay without calling Stripe", async () => {
    const existing = { id: 99, stripePaymentIntentId: "pi_real_dup" };
    mocks.storage.getStripePaymentByIntentId.mockResolvedValue(existing);

    const res = await request(app)
      .post("/api/payments/confirm")
      .send({
        paymentIntentId: "pi_real_dup",
        patientId: 1,
        simulated: false,
      });

    expect(res.status).toBe(200);
    expect(res.body).toEqual(existing);
    // Idempotency check is BEFORE Stripe retrieval — verify we never even
    // hit Stripe for a known intent.
    expect(stripeStub.paymentIntents.retrieve).not.toHaveBeenCalled();
    expect(mocks.storage.createStripePayment).not.toHaveBeenCalled();
  });
});

describe("GET /api/payments/config — real Stripe", () => {
  it("reports configured: true when STRIPE_SECRET_KEY is set", async () => {
    const res = await request(app).get("/api/payments/config");

    expect(res.status).toBe(200);
    expect(res.body).toMatchObject({
      configured: true,
      testMode: true, // sk_test_ prefix
    });
  });
});
