import crypto from "node:crypto";
import { NextResponse } from "next/server";
import { csGet, CSNotConnectedError } from "@/lib/cs/client";
import type { CSLocation } from "@/lib/cs/normalize";
import { recordCSLastSync } from "@/lib/cs/tokens";

export const dynamic = "force-dynamic";

export async function POST() {
  const syncRunId = crypto.randomUUID();
  try {
    const locations = await csGet<CSLocation[]>("api/v1.0/locations");
    await recordCSLastSync({
      id: syncRunId,
      status: "success",
      records_pulled: locations.length,
      finished_at: new Date().toISOString(),
    });
    return NextResponse.json({
      sync_run_id: syncRunId,
      records_pulled: locations.length,
    });
  } catch (e) {
    if (e instanceof CSNotConnectedError) {
      return NextResponse.json(
        {
          error: { code: "NOT_CONNECTED", message: e.message, details: {} },
        },
        { status: 409 },
      );
    }
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json(
      { error: { code: "CS_ERROR", message, details: {} } },
      { status: 500 },
    );
  }
}
