import { describe, it, expect } from "vitest";
import express from "express";
import request from "supertest";
import { authLimiter, aiLimiter } from "./rate-limit";

// Helper: build a throwaway Express app that only mounts the limiter under test.
function appWith(limiter: express.RequestHandler, path = "/test") {
  const app = express();
  app.use(path, limiter, (_req, res) => res.json({ ok: true }));
  return app;
}

describe("rate limiters", () => {
  describe("authLimiter", () => {
    it("allows requests under the limit", async () => {
      const app = appWith(authLimiter, "/login");
      const res = await request(app).get("/login");
      expect(res.status).toBe(200);
      expect(res.body).toEqual({ ok: true });
    });

    it("emits standard rate-limit headers", async () => {
      const app = appWith(authLimiter, "/login");
      const res = await request(app).get("/login");
      // express-rate-limit with standardHeaders: 'draft-7' uses RateLimit-* (no X-).
      expect(res.headers["ratelimit"]).toBeDefined();
      expect(res.headers["ratelimit-policy"]).toBeDefined();
    });

    it("blocks after exceeding the dev limit (100/min)", async () => {
      const app = appWith(authLimiter, "/login");
      // Dev limit is 100. Fire 101 requests sequentially; the last should 429.
      let lastStatus = 0;
      let lastBody: any = null;
      for (let i = 0; i < 101; i++) {
        const res = await request(app).get("/login");
        lastStatus = res.status;
        lastBody = res.body;
      }
      expect(lastStatus).toBe(429);
      expect(lastBody.message).toMatch(/login attempts/i);
    });
  });

  describe("aiLimiter", () => {
    it("returns the expected message shape on throttle", async () => {
      const app = appWith(aiLimiter, "/ai");
      // Dev limit is 200. Fire one over.
      let lastStatus = 0;
      let lastBody: any = null;
      for (let i = 0; i < 201; i++) {
        const res = await request(app).get("/ai");
        lastStatus = res.status;
        lastBody = res.body;
      }
      expect(lastStatus).toBe(429);
      expect(lastBody.message).toMatch(/AI request limit/i);
    });
  });
});
