/**
 * GET /api/integrations/carestack/patient/[id]/raw — single Patient, all fields, live.
 */
import { NextResponse, type NextRequest } from "next/server";
import { csGet, CSNotConnectedError } from "@/lib/cs/client";

export const dynamic = "force-dynamic";

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } },
) {
  try {
    const data = await csGet<unknown>(
      `api/v1.0/patients/${encodeURIComponent(params.id)}`,
    );
    return NextResponse.json(data);
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
