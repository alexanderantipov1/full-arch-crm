import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MessengerDirectoryCard } from "@/components/settings/MessengerDirectoryCard";
import { ApiError } from "@/lib/api/client";
import {
  useMessengerChannels,
  useMessengerTeams,
} from "@/lib/api/hooks/useMessengerDirectory";

vi.mock("@/lib/api/hooks/useMessengerDirectory", () => ({
  useMessengerTeams: vi.fn(),
  useMessengerChannels: vi.fn(),
  TEAMS_QUERY_KEY: ["messenger-teams"],
  CHANNELS_QUERY_KEY: ["messenger-channels"],
}));

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

function teamsResult(
  overrides: Record<string, unknown>,
): ReturnType<typeof useMessengerTeams> {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    error: null,
    isFetching: false,
    ...overrides,
  } as unknown as ReturnType<typeof useMessengerTeams>;
}

function channelsResult(
  overrides: Record<string, unknown>,
): ReturnType<typeof useMessengerChannels> {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    ...overrides,
  } as unknown as ReturnType<typeof useMessengerChannels>;
}

function renderCard() {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <MessengerDirectoryCard />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("MessengerDirectoryCard", () => {
  it("shows an actionable hint when no credential / admin token is configured", () => {
    vi.mocked(useMessengerTeams).mockReturnValue(
      teamsResult({
        isError: true,
        error: new ApiError("no_credential", "no mattermost credential", 404),
      }),
    );
    vi.mocked(useMessengerChannels).mockReturnValue(channelsResult({}));

    renderCard();

    expect(
      screen.getByRole("button", { name: /go to integrations/i }),
    ).toBeInTheDocument();
  });

  it("shows the actionable hint when the admin token is rejected (invalid_chat_credential)", () => {
    vi.mocked(useMessengerTeams).mockReturnValue(
      teamsResult({
        isError: true,
        error: new ApiError(
          "invalid_chat_credential",
          "mattermost admin_token rejected",
          422,
        ),
      }),
    );
    vi.mocked(useMessengerChannels).mockReturnValue(channelsResult({}));

    renderCard();

    expect(
      screen.getByRole("button", { name: /go to integrations/i }),
    ).toBeInTheDocument();
  });

  it("shows a generic error for an unreachable server", () => {
    vi.mocked(useMessengerTeams).mockReturnValue(
      teamsResult({
        isError: true,
        error: new ApiError(
          "integration_error",
          "Mattermost directory unavailable",
          502,
        ),
      }),
    );
    vi.mocked(useMessengerChannels).mockReturnValue(channelsResult({}));

    renderCard();

    expect(
      screen.getByText(/could not load the mattermost directory/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /go to integrations/i }),
    ).not.toBeInTheDocument();
  });

  it("shows the empty state when the server has no teams", () => {
    vi.mocked(useMessengerTeams).mockReturnValue(teamsResult({ data: [] }));
    vi.mocked(useMessengerChannels).mockReturnValue(channelsResult({}));

    renderCard();

    expect(screen.getByText(/no teams found/i)).toBeInTheDocument();
  });

  it("lists teams and lazy-loads channels on expand", () => {
    vi.mocked(useMessengerTeams).mockReturnValue(
      teamsResult({
        data: [
          {
            id: "team-1",
            name: "marketing",
            display_name: "Marketing",
            url: "https://chat.fusioncrm.app/marketing",
          },
        ],
      }),
    );
    vi.mocked(useMessengerChannels).mockReturnValue(
      channelsResult({
        data: [
          {
            id: "chan-1",
            name: "leads",
            display_name: "Leads channel",
            type: "P",
            purpose: "incoming",
          },
        ],
      }),
    );

    renderCard();

    // Team is rendered; channels are NOT in the DOM until expanded.
    expect(screen.getByText("Marketing")).toBeInTheDocument();
    expect(screen.queryByText("Leads channel")).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /expand channels/i }),
    );

    // After expand the channel and its private-type label appear.
    expect(screen.getByText("Leads channel")).toBeInTheDocument();
    expect(screen.getByText("Private")).toBeInTheDocument();
  });
});
