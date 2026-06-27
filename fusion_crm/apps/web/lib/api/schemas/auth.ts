import { z } from "zod";
import { Datetime, Uuid } from "./common";

export const StaffSessionSchema = z.object({
  staff_id: Uuid,
  email: z.string().email(),
  display_name: z.string(),
  expires_at: Datetime,
});
export type StaffSession = z.infer<typeof StaffSessionSchema>;

export const LoginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});
export type LoginRequest = z.infer<typeof LoginRequestSchema>;

export const LoginResponseSchema = z.object({
  session: StaffSessionSchema,
});
export type LoginResponse = z.infer<typeof LoginResponseSchema>;

export const AccessMemberKindSchema = z.enum([
  "user",
  "domain",
  "serviceAccount",
  "group",
  "other",
]);
export type AccessMemberKind = z.infer<typeof AccessMemberKindSchema>;

export const AccessSurfaceSchema = z.enum(["web", "api"]);
export type AccessSurface = z.infer<typeof AccessSurfaceSchema>;

export const AccessMemberSchema = z.object({
  kind: AccessMemberKindSchema,
  value: z.string(),
  role: z.string(),
  surfaces: z.array(AccessSurfaceSchema),
});
export type AccessMember = z.infer<typeof AccessMemberSchema>;

export const AccessListSchema = z.object({
  live: z.boolean(),
  members: z.array(AccessMemberSchema),
  reason: z.string().nullable().optional(),
});
export type AccessList = z.infer<typeof AccessListSchema>;
