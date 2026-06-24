import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  useMessengerChannels,
  useMessengerTeams,
} from "@/lib/api/hooks/useMessengerDirectory";

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("useMessengerTeams", () => {
  it("GETs /messenger/teams and parses the array", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify([
          {
            id: "team-1",
            name: "marketing",
            display_name: "Marketing",
            url: "https://chat.fusioncrm.app/marketing",
          },
        ]),
        { status: 200 },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useMessengerTeams(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/messenger/teams",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0]?.name).toBe("marketing");
  });
});

describe("useMessengerChannels", () => {
  it("is disabled (no fetch) while teamId is null", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useMessengerChannels(null), {
      wrapper,
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("GETs the team's channels once a teamId is provided", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify([
          {
            id: "chan-1",
            name: "leads",
            display_name: "Leads",
            type: "O",
            purpose: "incoming",
          },
        ]),
        { status: 200 },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useMessengerChannels("team-1"), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/messenger/teams/team-1/channels",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.current.data?.[0]?.type).toBe("O");
  });
});
