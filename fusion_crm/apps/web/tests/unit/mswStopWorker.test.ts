/**
 * ENG-342: the disabled-mocking guard must unregister a stale
 * ``mockServiceWorker`` in ANY lifecycle state and reload once (guarded) so
 * the live page detaches from a worker that is still controlling it.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { _RELOAD_GUARD_KEY, stopMockWorker } from "@/lib/msw/init";

const MSW_URL = "http://localhost:3000/mockServiceWorker.js";

function makeRegistration(
  state: "active" | "waiting" | "installing",
  scriptURL: string,
): ServiceWorkerRegistration {
  const sw = { scriptURL } as ServiceWorker;
  return {
    active: state === "active" ? sw : null,
    waiting: state === "waiting" ? sw : null,
    installing: state === "installing" ? sw : null,
    unregister: vi.fn().mockResolvedValue(true),
  } as unknown as ServiceWorkerRegistration;
}

function installServiceWorker(
  registrations: ServiceWorkerRegistration[],
  { controlled = true }: { controlled?: boolean } = {},
) {
  const reload = vi.fn();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...window.location, reload },
  });
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true,
    value: {
      getRegistrations: vi.fn().mockResolvedValue(registrations),
      controller: controlled ? ({} as ServiceWorker) : null,
    },
  });
  return reload;
}

beforeEach(() => {
  window.sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("stopMockWorker", () => {
  it("unregisters an active stale mock worker and reloads once", async () => {
    const reg = makeRegistration("active", MSW_URL);
    const reload = installServiceWorker([reg]);

    await stopMockWorker();

    expect(reg.unregister).toHaveBeenCalledOnce();
    expect(reload).toHaveBeenCalledOnce();
    expect(window.sessionStorage.getItem(_RELOAD_GUARD_KEY)).toBe("1");
  });

  it("unregisters a worker that is only in the waiting state", async () => {
    const reg = makeRegistration("waiting", MSW_URL);
    const reload = installServiceWorker([reg]);

    await stopMockWorker();

    expect(reg.unregister).toHaveBeenCalledOnce();
    expect(reload).toHaveBeenCalledOnce();
  });

  it("does nothing when there is no mock worker", async () => {
    const reg = makeRegistration("active", "http://localhost:3000/sw.js");
    const reload = installServiceWorker([reg]);

    await stopMockWorker();

    expect(reg.unregister).not.toHaveBeenCalled();
    expect(reload).not.toHaveBeenCalled();
  });

  it("does not reload twice (guarded against a loop)", async () => {
    const reg = makeRegistration("active", MSW_URL);
    const reload = installServiceWorker([reg]);
    window.sessionStorage.setItem(_RELOAD_GUARD_KEY, "1");

    await stopMockWorker();

    expect(reg.unregister).toHaveBeenCalledOnce();
    expect(reload).not.toHaveBeenCalled();
  });

  it("unregisters but does not reload when the page is not controlled", async () => {
    const reg = makeRegistration("active", MSW_URL);
    const reload = installServiceWorker([reg], { controlled: false });

    await stopMockWorker();

    expect(reg.unregister).toHaveBeenCalledOnce();
    expect(reload).not.toHaveBeenCalled();
  });
});
