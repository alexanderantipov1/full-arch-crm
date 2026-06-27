"use client";

import { useEffect, useState } from "react";

let started: Promise<void> | null = null;

async function startMockWorker() {
  if (typeof window === "undefined") return;
  if (process.env.NEXT_PUBLIC_API_MOCKING !== "enabled") return;
  const { worker } = await import("./browser");
  await worker.start({
    onUnhandledRequest: "bypass",
    serviceWorker: { url: "/mockServiceWorker.js" },
  });
}

export const _RELOAD_GUARD_KEY = "__msw_unregister_reloaded";

export async function stopMockWorker() {
  if (typeof window === "undefined") return;
  if (!("serviceWorker" in navigator)) return;
  const registrations = await navigator.serviceWorker.getRegistrations();
  // ENG-342: match the worker in ANY lifecycle state (active / waiting /
  // installing). The previous ``active?.scriptURL`` check missed a worker
  // that was waiting, installing, or whose ``active`` had gone null
  // (errored / redundant) — leaving a stale ``mockServiceWorker`` that kept
  // intercepting ``/api/*`` and showing mock data after mocking was disabled.
  const stale = registrations.filter((registration) => {
    const scriptURL = (
      registration.active ??
      registration.waiting ??
      registration.installing
    )?.scriptURL;
    return scriptURL?.endsWith("/mockServiceWorker.js") ?? false;
  });
  if (stale.length === 0) return;
  await Promise.all(stale.map((registration) => registration.unregister()));
  // Unregistering does NOT detach the worker that already controls THIS
  // page — it keeps intercepting until the page reloads. Reload once so the
  // live page drops the mock layer; the sessionStorage guard prevents a loop.
  if (
    navigator.serviceWorker.controller &&
    !window.sessionStorage.getItem(_RELOAD_GUARD_KEY)
  ) {
    window.sessionStorage.setItem(_RELOAD_GUARD_KEY, "1");
    window.location.reload();
  }
}

export function MockProvider({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setMounted(true);
    if (process.env.NEXT_PUBLIC_API_MOCKING !== "enabled") {
      void stopMockWorker();
      setReady(true);
      return;
    }
    if (ready) return;
    if (!started) {
      started = startMockWorker();
    }
    started.then(() => setReady(true));
  }, [ready]);

  if (!mounted) {
    return null;
  }

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">
        Booting mock backend...
      </div>
    );
  }
  return <>{children}</>;
}
