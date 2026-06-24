"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import {
  ChevronDown,
  ChevronRight,
  ExternalLink,
  Hash,
  Lock,
  MessageSquare,
  RefreshCw,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiError } from "@/lib/api/client";
import {
  CHANNELS_QUERY_KEY,
  TEAMS_QUERY_KEY,
  useMessengerChannels,
  useMessengerTeams,
} from "@/lib/api/hooks/useMessengerDirectory";
import type { MessengerTeam } from "@/lib/api/schemas/messenger";
import { cn } from "@/lib/utils";

/** Fallback Mattermost server URL when no team rows carry a usable origin. */
const MESSENGER_SERVER_URL = "https://chat.fusioncrm.app";

/** Map a raw Mattermost channel type to a human label. */
export function channelTypeLabel(type: string): string {
  if (type === "O") return "Public";
  if (type === "P") return "Private";
  return type;
}

function MessengerChannelsList({ teamId }: { teamId: string }) {
  const { data, isLoading, isError } = useMessengerChannels(teamId);
  const channels = data ?? [];

  if (isLoading) {
    return (
      <div className="space-y-2 py-2 pl-6">
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-2/3" />
      </div>
    );
  }
  if (isError) {
    return (
      <p className="py-2 pl-6 text-sm text-destructive">
        Could not load channels for this team.
      </p>
    );
  }
  if (channels.length === 0) {
    return (
      <p className="py-2 pl-6 text-sm text-muted-foreground">
        No channels in this team.
      </p>
    );
  }

  return (
    <ul className="space-y-1 py-2 pl-6">
      {channels.map((channel) => {
        const isPrivate = channel.type === "P";
        return (
          <li
            key={channel.id}
            className="flex items-start gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted/50"
          >
            {isPrivate ? (
              <Lock className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            ) : (
              <Hash className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{channel.display_name}</span>
                <span className="font-mono text-xs text-muted-foreground">
                  {channel.name}
                </span>
                <Badge variant="secondary" className="text-[10px]">
                  {channelTypeLabel(channel.type)}
                </Badge>
              </div>
              {channel.purpose ? (
                <p className="truncate text-xs text-muted-foreground">
                  {channel.purpose}
                </p>
              ) : null}
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function MessengerTeamRow({ team }: { team: MessengerTeam }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-md border">
      <div className="flex items-center gap-2 px-3 py-2">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          aria-label={expanded ? "Collapse channels" : "Expand channels"}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
          )}
          <span className="truncate font-medium">{team.display_name}</span>
          <span className="font-mono text-xs text-muted-foreground">
            {team.name}
          </span>
        </button>
        <a
          href={team.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
        >
          Open
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
      {expanded ? (
        <div className="border-t">
          <MessengerChannelsList teamId={team.id} />
        </div>
      ) : null}
    </div>
  );
}

/**
 * Settings → Messenger tab (ENG-564): a read-only mirror of the corporate
 * Mattermost server's teams & channels. Lazy-loads each team's channels on
 * expand; Refresh invalidates the React Query cache for a live refetch. The
 * "not configured / no admin token" error is actionable, linking to the
 * Integrations tab where the Mattermost credential is managed.
 */
export function MessengerDirectoryCard() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error, isFetching } = useMessengerTeams();
  const teams = data ?? [];

  const serverUrl = (() => {
    const first = teams[0]?.url;
    if (first) {
      try {
        return new URL(first).origin;
      } catch {
        return MESSENGER_SERVER_URL;
      }
    }
    return MESSENGER_SERVER_URL;
  })();

  const notConfigured =
    error instanceof ApiError &&
    (error.code === "no_credential" ||
      error.code === "invalid_chat_credential");

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: TEAMS_QUERY_KEY });
    void queryClient.invalidateQueries({ queryKey: CHANNELS_QUERY_KEY });
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-4 w-4" />
              Mattermost directory
            </CardTitle>
            <CardDescription>
              A read-only mirror of the corporate Mattermost server&apos;s teams
              and channels.{" "}
              <a
                href={serverUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-primary hover:underline"
              >
                {serverUrl.replace(/^https?:\/\//, "")}
                <ExternalLink className="h-3 w-3" />
              </a>
            </CardDescription>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={refresh}
            disabled={isFetching}
          >
            <RefreshCw
              className={cn("mr-2 h-4 w-4", isFetching && "animate-spin")}
            />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-2/3" />
          </div>
        ) : notConfigured ? (
          <div className="rounded-md border border-dashed p-6 text-center text-sm">
            <p className="text-muted-foreground">
              Mattermost isn&apos;t connected yet, or its admin token is missing.
              The directory needs a Mattermost credential with a system-admin
              token to list every team on the server.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => router.replace("/settings/tenant?tab=integrations")}
            >
              Go to Integrations
            </Button>
          </div>
        ) : isError ? (
          <p className="text-sm text-destructive">
            Could not load the Mattermost directory. Try Refresh, or check that
            the server is reachable.
          </p>
        ) : teams.length === 0 ? (
          <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
            No teams found on the Mattermost server yet.
          </div>
        ) : (
          <div className="space-y-2">
            {teams.map((team) => (
              <MessengerTeamRow key={team.id} team={team} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
