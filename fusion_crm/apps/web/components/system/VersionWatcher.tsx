"use client";

import * as React from "react";
import { useToast } from "@/components/ui/toast";

/**
 * Background poller that detects a backend version drift and prompts
 * the operator to reload — ENG-150 cache-busting hint.
 *
 * Pattern: at bundle build time Next.js bakes ``NEXT_PUBLIC_COMMIT_SHA``
 * (via ``next.config.mjs``). At runtime we poll ``/api/healthz`` and
 * compare its ``commit_sha`` against the bundled value. When they
 * diverge — typically because the operator's tab is still on an old
 * page bundle after a fresh ``deploy-prod`` — we surface a non-blocking
 * toast with a Reload button. The poll runs every 60s and also on
 * window focus, so a quick context-switch back to the tab triggers
 * the check without the operator waiting for the next interval.
 *
 * Local dev (``next dev``) sets ``COMMIT_SHA = "dev"`` and the API
 * emits ``"dev"`` too, so the values match and the watcher stays
 * silent. The component is a no-op when either side reports ``dev``,
 * or when the fetch fails (no network is preferable to a noisy toast).
 */

const POLL_INTERVAL_MS = 60_000;
const BUNDLED_SHA = process.env.NEXT_PUBLIC_COMMIT_SHA ?? "dev";

interface HealthzResponse {
  status: string;
  commit_sha?: string;
}

async function fetchServerSha(): Promise<string | null> {
  try {
    const res = await fetch("/api/healthz", { cache: "no-store" });
    if (!res.ok) return null;
    const body = (await res.json()) as HealthzResponse;
    return typeof body.commit_sha === "string" ? body.commit_sha : null;
  } catch {
    return null;
  }
}

export function VersionWatcher() {
  const { toast } = useToast();
  const notifiedRef = React.useRef(false);

  const check = React.useCallback(async () => {
    if (notifiedRef.current) return;
    if (!BUNDLED_SHA || BUNDLED_SHA === "dev") return;

    const serverSha = await fetchServerSha();
    if (!serverSha || serverSha === "dev") return;
    if (serverSha === BUNDLED_SHA) return;

    notifiedRef.current = true;
    toast({
      title: "New version available",
      description: "The backend is on a newer build. Reload to pick it up.",
      variant: "default",
      durationMs: 24 * 60 * 60 * 1000, // sticky until the operator acts
    });
  }, [toast]);

  React.useEffect(() => {
    void check();
    const interval = window.setInterval(() => {
      void check();
    }, POLL_INTERVAL_MS);
    const onFocus = () => {
      void check();
    };
    window.addEventListener("focus", onFocus);
    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, [check]);

  return null;
}
