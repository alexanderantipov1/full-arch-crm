import { NextResponse } from "next/server";
import { clearCSTokens } from "@/lib/cs/tokens";

export const dynamic = "force-dynamic";

export async function DELETE() {
  await clearCSTokens();
  return NextResponse.json({
    id: "22222222-0000-0000-0000-000000000002",
    provider: "carestack",
    status: "disconnected",
    display_name: null,
    last_sync_at: null,
    last_sync_summary: null,
    error_message: null,
  });
}
