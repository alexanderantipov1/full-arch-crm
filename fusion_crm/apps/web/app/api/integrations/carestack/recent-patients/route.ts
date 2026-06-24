/**
 * GET /api/integrations/carestack/recent-patients
 *
 * Live read-only inspection of CareStack patients modified in the last N days.
 * NOT persisted. Uses the documented sync feed
 * (docs/integrations/carestack/sync/patients.md) — the only LIST endpoint
 * CareStack exposes for patients.
 */
import { NextResponse, type NextRequest } from "next/server";
import { csGet, CSNotConnectedError } from "@/lib/cs/client";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const days = Number(req.nextUrl.searchParams.get("days") ?? "7");
  const pageSize = Number(req.nextUrl.searchParams.get("pageSize") ?? "50");
  const modifiedSince = new Date(
    Date.now() - days * 24 * 60 * 60 * 1000,
  ).toISOString();

  try {
    const data = await csGet<unknown>("api/v1.0/sync/patients", {
      modifiedSince,
      pageSize,
    });
    return NextResponse.json({ modifiedSince, pageSize, data });
  } catch (e) {
    if (e instanceof CSNotConnectedError) {
      return NextResponse.json(
        { error: { code: "CS_NOT_CONNECTED", message: e.message } },
        { status: 409 },
      );
    }
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json(
      { error: { code: "CS_ERROR", message } },
      { status: 502 },
    );
  }
}
