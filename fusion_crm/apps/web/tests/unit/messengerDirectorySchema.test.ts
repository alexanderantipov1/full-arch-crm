import { describe, expect, it } from "vitest";
import {
  MessengerChannelListSchema,
  MessengerChannelSchema,
  MessengerTeamListSchema,
  MessengerTeamSchema,
} from "@/lib/api/schemas/messenger";

describe("MessengerTeamSchema", () => {
  it("parses a well-formed team", () => {
    const team = MessengerTeamSchema.parse({
      id: "team-1",
      name: "marketing",
      display_name: "Marketing",
      url: "https://chat.fusioncrm.app/marketing",
    });
    expect(team.name).toBe("marketing");
  });

  it("rejects a team missing display_name", () => {
    const result = MessengerTeamSchema.safeParse({
      id: "team-1",
      name: "marketing",
      url: "https://chat.fusioncrm.app/marketing",
    });
    expect(result.success).toBe(false);
  });

  it("parses a list of teams", () => {
    const teams = MessengerTeamListSchema.parse([
      {
        id: "team-1",
        name: "marketing",
        display_name: "Marketing",
        url: "https://chat.fusioncrm.app/marketing",
      },
    ]);
    expect(teams).toHaveLength(1);
  });
});

describe("MessengerChannelSchema", () => {
  it("parses a channel and preserves the raw type code", () => {
    const channel = MessengerChannelSchema.parse({
      id: "chan-1",
      name: "leads",
      display_name: "Leads",
      type: "P",
      purpose: "incoming leads",
    });
    expect(channel.type).toBe("P");
    expect(channel.purpose).toBe("incoming leads");
  });

  it("rejects a channel missing type", () => {
    const result = MessengerChannelSchema.safeParse({
      id: "chan-1",
      name: "leads",
      display_name: "Leads",
      purpose: "",
    });
    expect(result.success).toBe(false);
  });

  it("parses an empty channel list", () => {
    expect(MessengerChannelListSchema.parse([])).toEqual([]);
  });
});
