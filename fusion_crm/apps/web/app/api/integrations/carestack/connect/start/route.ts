/**
 * POST /api/integrations/carestack/connect/start
 *
 * No browser redirect: server runs the password grant against CareStack's
 * IdP using credentials in the repo-root .env. On success, returns
 * `instant_connected` so the UI just refetches the list.
 */
import { NextResponse } from "next/server";
import { fetchAccessToken } from "@/lib/cs/auth";
import { csGet } from "@/lib/cs/client";
import type { CSLocation } from "@/lib/cs/normalize";

export const dynamic = "force-dynamic";

export async function POST() {
  try {
    await fetchAccessToken();
    // Sanity-check the token by hitting the locations endpoint.
    const locations = await csGet<CSLocation[]>("api/v1.0/locations");
    const primary = locations[0]?.name ?? "CareStack";
    return NextResponse.json({
      kind: "instant_connected",
      display_name: primary,
    });
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return NextResponse.json(
      {
        error: {
          code: "CS_CONNECT_FAILED",
          message,
          details: {},
        },
      },
      { status: 502 },
    );
  }
}
