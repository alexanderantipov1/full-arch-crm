import { z } from "zod";

/**
 * Provider → Mattermost username mapping (ENG-546, Step 2b).
 *
 * Mirrors `packages/actor/schemas.py` `ProviderMessengerMappingOut` /
 * `ProviderMessengerMappingListOut` EXACTLY (field names, optionality). Each
 * row is one CareStack provider (doctor) and the Mattermost username the
 * consult-reminder @mentions (ENG-543); `mattermost_username` is `null` until
 * an operator maps the doctor.
 */

export const ProviderMessengerMappingSchema = z.object({
  actor_id: z.string().uuid(),
  actor_name: z.string(),
  carestack_provider_id: z.string(),
  mattermost_username: z.string().nullable(),
});
export type ProviderMessengerMapping = z.infer<
  typeof ProviderMessengerMappingSchema
>;

export const ProviderMessengerMappingListSchema = z.object({
  items: z.array(ProviderMessengerMappingSchema),
});
export type ProviderMessengerMappingList = z.infer<
  typeof ProviderMessengerMappingListSchema
>;
