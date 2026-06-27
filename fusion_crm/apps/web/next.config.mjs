import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

// Load Salesforce / CareStack credentials from the repo-root `.env`
// so server-side route handlers have them without us duplicating
// secrets into apps/web/.env.local. Whitelisted prefixes only.
function loadRootEnv() {
  const rootEnvPath = resolve(process.cwd(), "..", "..", ".env");
  if (!existsSync(rootEnvPath)) return;
  const text = readFileSync(rootEnvPath, "utf8");
  const allow = (k) =>
    k.startsWith("SALESFORCE_") || k.startsWith("CARESTACK_");
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    if (!allow(key)) continue;
    if (process.env[key]) continue; // local override wins
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    process.env[key] = value;
  }
}
loadRootEnv();

// Surface the build's git SHA into the client bundle so the
// VersionWatcher can detect a backend update and prompt the operator
// to reload (ENG-150). Set via Docker build-arg in deploy-prod.yml;
// falls back to "dev" when running `next dev` locally.
const COMMIT_SHA = process.env.COMMIT_SHA ?? "dev";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_COMMIT_SHA: COMMIT_SHA,
  },
  poweredByHeader: false,
  // Standalone output is what makes apps/web/Dockerfile cheap: the
  // build step emits `.next/standalone/` + `.next/static/` containing
  // only the files needed at runtime (no node_modules tree, no source).
  // Required by the Cloud Run image; harmless during local `npm run dev`.
  output: "standalone",
  experimental: {
    typedRoutes: false,
  },
  async rewrites() {
    // ``fallback`` mode runs ONLY when no Next.js handler (static OR dynamic
    // route, page, or public file) matched. Default array form is
    // ``afterFiles`` which runs BEFORE dynamic routes — that swallows our
    // ``[id]/raw`` handlers and forwards them to FastAPI prematurely.
    return {
      beforeFiles: [
        // Google Workspace / Microsoft 365 OAuth callbacks come back to
        // ``/integrations/{provider}/callback`` (no ``/api/`` prefix) per
        // the URL registered with the provider's OAuth app. We rewrite to
        // ``/api/integrations/{provider}/callback`` so the fallback proxy
        // forwards to FastAPI (which serves the real handler in
        // ``integrations_oauth.py``). Salesforce uses the ``/api/`` form
        // natively (its Connected App was registered that way) and so
        // does not need this hop. ENG-156.
        {
          source: "/integrations/:provider(google_workspace|microsoft_365)/callback",
          destination: "/api/integrations/:provider/callback",
        },
      ],
      fallback: [
        {
          source: "/api/:path*",
          // ``INTERNAL_API_URL`` wins because it points DIRECTLY at the
          // fusion-api Cloud Run service URL, bypassing the public LB.
          // Using ``NEXT_PUBLIC_API_BASE_URL`` here causes an LB loop
          // (fusion-web → ``fusioncrm.app`` → fusion-web again) — that
          // bit prod after ENG-156 went live. Falls back to
          // ``NEXT_PUBLIC_API_BASE_URL`` for local dev where there is
          // no separate internal URL, then to localhost:8000 for the
          // bare ``next dev`` case. ENG-158.
          destination: (
            process.env.INTERNAL_API_URL?.replace(/\/$/, "") ||
            process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ||
            "http://localhost:8000"
          ) + "/:path*",
        },
      ],
    };
  },
};

export default nextConfig;
