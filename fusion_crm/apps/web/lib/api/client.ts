import { ApiErrorSchema } from "./schemas/common";

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const BASE = "/api";

type Json = Record<string, unknown> | unknown[];

async function request<T>(
  method: string,
  path: string,
  body?: Json,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    credentials: "include",
  });

  const text = await res.text();
  const parsed: unknown = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const errParse = ApiErrorSchema.safeParse(parsed);
    if (errParse.success) {
      const e = errParse.data.error;
      throw new ApiError(e.code, e.message, res.status, e.details);
    }
    throw new ApiError(
      "UNKNOWN",
      `Request failed with status ${res.status}`,
      res.status,
    );
  }

  return parsed as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: Json) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: Json) => request<T>("PATCH", path, body),
  put: <T>(path: string, body?: Json) => request<T>("PUT", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
};
