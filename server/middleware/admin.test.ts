import { describe, it, expect, beforeEach, afterEach } from "vitest";
import express from "express";
import request from "supertest";
import { isAdmin } from "./admin";

function buildApp(userId: string) {
  const app = express();
  app.use((req: any, _res, next) => {
    req.user = { claims: { sub: userId, email: "u@test" } };
    next();
  });
  app.get("/admin-only", isAdmin, (_req, res) => res.json({ ok: true }));
  return app;
}

const originalOwner = process.env.OWNER_USER_ID;
const originalAdmins = process.env.ADMIN_USER_IDS;

beforeEach(() => {
  delete process.env.OWNER_USER_ID;
  delete process.env.ADMIN_USER_IDS;
});

afterEach(() => {
  if (originalOwner !== undefined) process.env.OWNER_USER_ID = originalOwner;
  else delete process.env.OWNER_USER_ID;
  if (originalAdmins !== undefined) process.env.ADMIN_USER_IDS = originalAdmins;
  else delete process.env.ADMIN_USER_IDS;
});

describe("isAdmin middleware", () => {
  it("rejects users not in the admin set", async () => {
    process.env.OWNER_USER_ID = "owner-1";
    const res = await request(buildApp("random-user")).get("/admin-only");
    expect(res.status).toBe(403);
    expect(res.body.message).toMatch(/admin/i);
  });

  it("admits OWNER_USER_ID", async () => {
    process.env.OWNER_USER_ID = "owner-1";
    const res = await request(buildApp("owner-1")).get("/admin-only");
    expect(res.status).toBe(200);
  });

  it("admits any user listed in ADMIN_USER_IDS (comma-separated, whitespace-tolerant)", async () => {
    process.env.ADMIN_USER_IDS = " u1 , u2 , u3 ";
    const res = await request(buildApp("u3")).get("/admin-only");
    expect(res.status).toBe(200);
  });

  it("rejects when no admin envs are set at all", async () => {
    const res = await request(buildApp("anyone")).get("/admin-only");
    expect(res.status).toBe(403);
  });

  it("rejects when the principal has no userId on the request", async () => {
    const app = express();
    app.get("/admin-only", isAdmin, (_req, res) => res.json({ ok: true }));
    process.env.OWNER_USER_ID = "owner-1";
    const res = await request(app).get("/admin-only");
    expect(res.status).toBe(401);
  });
});
