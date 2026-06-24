import { z } from "zod";

/**
 * Messenger directory (ENG-564) — read-only mirror of the corporate Mattermost
 * server's teams & channels, shown on the staff Settings → Messenger tab.
 *
 * Mirrors `packages/integrations/chat/directory_schemas.py`
 * `MessengerTeamOut` / `MessengerChannelOut` EXACTLY (field names, types). The
 * backend builds these from the Mattermost REST API, so there are no datetime
 * fields (no `Datetime` alias needed).
 */

export const MessengerTeamSchema = z.object({
  id: z.string(),
  name: z.string(),
  display_name: z.string(),
  url: z.string(),
});
export type MessengerTeam = z.infer<typeof MessengerTeamSchema>;

export const MessengerTeamListSchema = z.array(MessengerTeamSchema);
export type MessengerTeamList = z.infer<typeof MessengerTeamListSchema>;

export const MessengerChannelSchema = z.object({
  id: z.string(),
  name: z.string(),
  display_name: z.string(),
  // Raw Mattermost channel type: "O" (open/public) or "P" (private).
  type: z.string(),
  purpose: z.string(),
});
export type MessengerChannel = z.infer<typeof MessengerChannelSchema>;

export const MessengerChannelListSchema = z.array(MessengerChannelSchema);
export type MessengerChannelList = z.infer<typeof MessengerChannelListSchema>;
