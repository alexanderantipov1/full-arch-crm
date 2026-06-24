import { NextResponse, type NextRequest } from "next/server";

export const dynamic = "force-dynamic";

/**
 * GET /api/auth/session — return current session info.
 *
 * In production behind Cloud IAP, IAP injects the
 * `X-Goog-Authenticated-User-Email` header with the verified Google
 * identity. We return that as the session. The frontend doesn't carry
 * a `staff_session` cookie in this mode — IAP is the auth.
 *
 * When the header is missing (e.g. local dev with MSW disabled but no
 * IAP in front), return 401 — the frontend treats this the same as
 * "no active session".
 */
export async function GET(req: NextRequest) {
  const iapEmail = req.headers.get("x-goog-authenticated-user-email");
  if (!iapEmail) {
    return NextResponse.json(
      { error: { code: "UNAUTHENTICATED", message: "No active session", details: {} } },
      { status: 401 },
    );
  }
  // Header value is `accounts.google.com:<email>` — strip the prefix.
  const email = iapEmail.replace(/^accounts\.google\.com:/, "");
  const displayName = email.split("@")[0] ?? email;

  return NextResponse.json({
    session: {
      // Synthetic staff_id derived from the IAP identity. The real
      // staff row lookup will live in apps/api once `auth.staff` ships.
      staff_id: `iap-${displayName}`,
      email,
      display_name: displayName,
      // IAP sessions don't expose their own expiry to the backend;
      // emit a long-ish placeholder so the frontend doesn't churn.
      expires_at: new Date(Date.now() + 8 * 3600_000).toISOString(),
    },
  });
}
