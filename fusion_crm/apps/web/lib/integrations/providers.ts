import {
  Activity,
  AudioLines,
  BarChart3,
  Brain,
  Cloud,
  CreditCard,
  Headphones,
  Heart,
  HeartHandshake,
  Inbox,
  LineChart,
  Magnet,
  Mail,
  MapPin,
  Megaphone,
  MessageCircle,
  MessageSquare,
  Mic,
  Music2,
  Plug,
  Search,
  Smile,
  Sparkles,
  Square as SquareIcon,
  Star,
  Stethoscope,
  Sun,
  ThumbsUp,
  type LucideIcon,
} from "lucide-react";
import type { ProviderKind } from "@/lib/api/schemas";

/**
 * Provider registry for the Integrations tab. Categories are presentation
 * groupings only; the wire enum stays flat in `ProviderKindSchema`.
 *
 * Lucide doesn't ship vendor brand marks, so the icons below are semantic
 * stand-ins. Swap for real brand SVGs once we add an icon set.
 *
 * ENG-131 / ENG-135 add `email` category for Google Workspace + Microsoft 365.
 */
export const PROVIDER_CATEGORIES = {
  crm: ["salesforce", "hubspot"],
  pms: ["carestack", "open_dental"],
  email: ["google_workspace", "microsoft_365"],
  voice_ai: ["vapi", "openai", "anthropic", "elevenlabs", "deepgram"],
  sms_voice: ["twilio"],
  reviews: ["birdeye", "podium", "google_business"],
  payment: ["stripe", "square", "carecredit", "sunbit", "cherry"],
  analytics: ["google_analytics", "meta_pixel", "tiktok_pixel"],
  ad_spend: ["google_ads", "meta_ads", "google_search_console"],
  chat: ["mattermost"],
  other: ["other"],
} as const satisfies Record<string, readonly ProviderKind[]>;

export type ProviderCategory = keyof typeof PROVIDER_CATEGORIES;

export const CATEGORY_LABELS: Record<ProviderCategory, string> = {
  crm: "CRM",
  pms: "Practice Management (PMS)",
  email: "Email (operator mailboxes)",
  voice_ai: "Voice / AI",
  sms_voice: "SMS / Voice transport",
  reviews: "Reviews & Reputation",
  payment: "Payment & Financing",
  analytics: "Marketing Analytics",
  ad_spend: "Ad Spend & SEO",
  chat: "Team Chat",
  other: "Other",
};

/** Stable display order for category sections. */
export const CATEGORY_ORDER: readonly ProviderCategory[] = [
  "crm",
  "pms",
  "email",
  "voice_ai",
  "sms_voice",
  "reviews",
  "payment",
  "analytics",
  "ad_spend",
  "chat",
  "other",
];

export const PROVIDER_LABELS: Record<ProviderKind, string> = {
  salesforce: "Salesforce",
  hubspot: "HubSpot",
  carestack: "CareStack",
  open_dental: "Open Dental",
  vapi: "VAPI",
  openai: "OpenAI",
  anthropic: "Anthropic",
  elevenlabs: "ElevenLabs",
  deepgram: "Deepgram",
  twilio: "Twilio",
  google_workspace: "Google Workspace (Gmail)",
  microsoft_365: "Microsoft 365 (Outlook)",
  birdeye: "Birdeye",
  podium: "Podium",
  google_business: "Google Business Profile",
  stripe: "Stripe",
  square: "Square",
  carecredit: "CareCredit",
  sunbit: "Sunbit",
  cherry: "Cherry",
  google_analytics: "Google Analytics",
  meta_pixel: "Meta Pixel",
  tiktok_pixel: "TikTok Pixel",
  google_ads: "Google Ads",
  meta_ads: "Meta Ads",
  google_search_console: "Google Search Console",
  mattermost: "Mattermost",
  other: "Other",
};

export const PROVIDER_ICONS: Record<ProviderKind, LucideIcon> = {
  salesforce: Cloud,
  hubspot: Magnet,
  carestack: Stethoscope,
  open_dental: Smile,
  vapi: Mic,
  openai: Sparkles,
  anthropic: Brain,
  elevenlabs: AudioLines,
  deepgram: Headphones,
  twilio: MessageSquare,
  google_workspace: Mail,
  microsoft_365: Inbox,
  birdeye: Star,
  podium: ThumbsUp,
  google_business: MapPin,
  stripe: CreditCard,
  square: SquareIcon,
  carecredit: HeartHandshake,
  sunbit: Sun,
  cherry: Heart,
  google_analytics: BarChart3,
  meta_pixel: Activity,
  tiktok_pixel: Music2,
  google_ads: Megaphone,
  meta_ads: LineChart,
  google_search_console: Search,
  mattermost: MessageCircle,
  other: Plug,
};

/**
 * The set of providers that are operator-email mailboxes. Used by the
 * outreach UI to filter the mailbox-picker, and by the integrations tab to
 * decide which "Connect" buttons follow the OAuth-popup flow (ENG-131).
 */
export const MAILBOX_PROVIDER_KINDS = new Set<ProviderKind>([
  "google_workspace",
  "microsoft_365",
]);

export function isMailboxProvider(p: ProviderKind): boolean {
  return MAILBOX_PROVIDER_KINDS.has(p);
}
