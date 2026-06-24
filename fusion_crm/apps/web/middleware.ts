import { NextResponse } from "next/server";

/**
 * Stamp ``X-Service: fusion-web`` and ``X-Commit: <sha>`` on every
 * response so operators can curl any path and tell which Cloud Run
 * container served it. Mirrors the FastAPI ``RequestContextMiddleware``
 * — together the two headers make the LB routing visible at a glance.
 *
 * Routes that **fall through** to fusion-api via ``next.config.mjs``
 * rewrites carry the ``X-Service: fusion-api`` header from there; this
 * middleware does NOT overwrite headers that exist already, so the
 * proxied response keeps its own identity.
 *
 * Background: today's prod debug session burned hours discovering that
 * ``/api/*`` was being served by Next.js when we thought it was
 * fusion-api. With these headers ``curl -I https://fusioncrm.app/api/...``
 * answers "who responded" in one shot. See ENG-153.
 */

const COMMIT_SHA = process.env.NEXT_PUBLIC_COMMIT_SHA ?? "dev";

export function middleware() {
  const res = NextResponse.next();
  if (!res.headers.has("x-service")) {
    res.headers.set("x-service", "fusion-web");
  }
  if (!res.headers.has("x-commit")) {
    res.headers.set("x-commit", COMMIT_SHA);
  }
  return res;
}

// Match every path. Excludes ``_next/static`` (fingerprinted assets,
// already cache-stable) and the favicon to keep the middleware out of
// the hot path for static delivery.
//
// Do NOT add a matcher for ``_next/static/chunks`` here. A previous
// revision redirected ``(staff)`` chunk paths to their ``%28staff%29``
// percent-encoded form, but ``nextUrl.pathname`` is already decoded, so
// the redirect target decoded straight back to the source on the next
// request — an infinite 307 loop that surfaced as ERR_TOO_MANY_REDIRECTS
// / ChunkLoadError in prod. App-router route-group parens are valid URL
// characters and load fine without any rewrite.
export const config = {
  matcher: ["/((?!_next/static|favicon.ico).*)"],
};
