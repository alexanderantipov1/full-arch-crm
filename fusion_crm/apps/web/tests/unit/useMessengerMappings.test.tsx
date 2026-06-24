import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  useProviderMessengerMappings,
  useSetProviderMessengerUsername,
} from "@/lib/api/hooks/useMessengerMappings";

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("useProviderMessengerMappings", () => {
  it("parses the provider list, preserving null usernames", async () => {
    const fetchMock = vi.fn(async () => {
      return new Response(
        JSON.stringify({
          items: [
            {
              actor_id: "11111111-1111-1111-1111-111111111111",
              actor_name: "Dr Antipov",
              carestack_provider_id: "1",
              mattermost_username: "drantipov",
            },
            {
              actor_id: "22222222-2222-2222-2222-222222222222",
              actor_name: "Dr Ivanova",
              carestack_provider_id: "2",
              mattermost_username: null,
            },
          ],
        }),
        { status: 200 },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useProviderMessengerMappings(), {
      wrapper,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/actor/provider-messenger-mappings",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.current.data?.items).toHaveLength(2);
    expect(result.current.data?.items[1]?.mattermost_username).toBeNull();
  });
});

describe("useSetProviderMessengerUsername", () => {
  it("PUTs the username to the provider path and parses the result", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      const body = JSON.parse(String(init?.body));
      expect(body.mattermost_username).toBe("@drantipov");
      return new Response(
        JSON.stringify({
          actor_id: "11111111-1111-1111-1111-111111111111",
          actor_name: "Dr Antipov",
          carestack_provider_id: "1",
          mattermost_username: "drantipov",
        }),
        { status: 200 },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useSetProviderMessengerUsername(), {
      wrapper,
    });

    result.current.mutate({
      carestackProviderId: "1",
      mattermostUsername: "@drantipov",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/actor/provider-messenger-mappings/1",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(result.current.data?.mattermost_username).toBe("drantipov");
  });

  it("invalidates the list query so the card refetches after success", async () => {
    const listItem = (username: string | null) => ({
      actor_id: "11111111-1111-1111-1111-111111111111",
      actor_name: "Dr Antipov",
      carestack_provider_id: "1",
      mattermost_username: username,
    });

    // Count GETs to the list path: first load returns unmapped, the post-
    // mutation refetch returns the new handle.
    let listGets = 0;
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (url === "/api/actor/provider-messenger-mappings" && method === "GET") {
        listGets += 1;
        return new Response(
          JSON.stringify({ items: [listItem(listGets === 1 ? null : "drantipov")] }),
          { status: 200 },
        );
      }
      if (
        url === "/api/actor/provider-messenger-mappings/1" &&
        method === "PUT"
      ) {
        return new Response(JSON.stringify(listItem("drantipov")), {
          status: 200,
        });
      }
      throw new Error(`unexpected ${method} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    // ONE shared QueryClient so the mutation's invalidateQueries reaches the
    // list query mounted alongside it (the module-level `wrapper` mints a
    // fresh client per call, which would not share the cache).
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    function sharedWrapper({ children }: { children: React.ReactNode }) {
      return (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      );
    }

    const { result } = renderHook(
      () => ({
        list: useProviderMessengerMappings(),
        set: useSetProviderMessengerUsername(),
      }),
      { wrapper: sharedWrapper },
    );

    // Initial list load — one GET, doctor unmapped.
    await waitFor(() => expect(result.current.list.isSuccess).toBe(true));
    expect(listGets).toBe(1);
    expect(result.current.list.data?.items[0]?.mattermost_username).toBeNull();

    // Fire the mutation.
    result.current.set.mutate({
      carestackProviderId: "1",
      mattermostUsername: "@drantipov",
    });
    await waitFor(() => expect(result.current.set.isSuccess).toBe(true));

    // onSuccess → invalidateQueries → the list GET is re-issued.
    await waitFor(() => expect(listGets).toBe(2));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/actor/provider-messenger-mappings",
      expect.objectContaining({ method: "GET" }),
    );
    await waitFor(() =>
      expect(result.current.list.data?.items[0]?.mattermost_username).toBe(
        "drantipov",
      ),
    );
  });
});
