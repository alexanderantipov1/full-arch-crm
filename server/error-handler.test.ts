import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import express from "express";
import request from "supertest";
import { errorHandler } from "./app";

function appWithErrorHandler() {
  const app = express();
  app.get("/explode", () => {
    const err: any = new Error("database connection string leaked");
    err.status = 500;
    throw err;
  });
  app.get("/bad-input", () => {
    const err: any = new Error("Email is required");
    err.status = 400;
    throw err;
  });
  app.get("/no-status", () => {
    throw new Error("unhandled internals");
  });
  app.use(errorHandler);
  return app;
}

describe("global error handler", () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it("hides the message for 5xx errors", async () => {
    const res = await request(appWithErrorHandler()).get("/explode");
    expect(res.status).toBe(500);
    expect(res.body.message).toBe("Internal Server Error");
    expect(res.body.message).not.toMatch(/database/i);
  });

  it("defaults to 500 + generic message when no status is set", async () => {
    const res = await request(appWithErrorHandler()).get("/no-status");
    expect(res.status).toBe(500);
    expect(res.body.message).toBe("Internal Server Error");
    expect(res.body.message).not.toMatch(/unhandled/);
  });

  it("surfaces the message for 4xx client errors", async () => {
    const res = await request(appWithErrorHandler()).get("/bad-input");
    expect(res.status).toBe(400);
    expect(res.body.message).toBe("Email is required");
  });

  it("still logs the full error server-side regardless of response", async () => {
    await request(appWithErrorHandler()).get("/explode");
    expect(consoleErrorSpy).toHaveBeenCalled();
    const logged = consoleErrorSpy.mock.calls[0]?.[0];
    expect(String(logged)).toMatch(/GET \/explode/);
  });
});
