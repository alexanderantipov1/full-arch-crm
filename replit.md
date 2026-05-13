# ImplantBill AI — HIPAA-Compliant Dental Practice Management Platform

## Overview
ImplantBill AI is a comprehensive, all-specialty SaaS dental practice management system designed primarily for full-arch implant practices (All-on-4 / All-on-6). It combines CRM, patient management, AI-powered medical billing, revenue cycle management, virtual office infrastructure, and comprehensive practice analytics — evolving toward a CareStack-style all-inclusive system.

The platform maximizes practice revenue through intelligent CDT→CPT/ICD-10 cross-coding, AI-powered insurance appeals, automated medical necessity documentation, and predictive analytics.

## User Preferences
- Focus on medical billing workflow for full arch implants
- All-on-4 and All-on-6 are the primary procedures
- AI assistance for insurance approvals, appeals, and coding
- Medical necessity documentation is key to getting claims approved
- Professional, clinical appearance
- Consolidated hub architecture preferred over individual standalone pages

## System Architecture
**Frontend:** React 18 + TypeScript, Vite, TailwindCSS, Shadcn/UI, Wouter routing, TanStack Query v5
**Backend:** Express.js + TypeScript
**Database:** PostgreSQL + Drizzle ORM (30+ tables in `shared/schema.ts`)
**Auth:** Replit Auth (OIDC) — `isAuthenticated` middleware, `getSessionUserId(req)` for user ID
**AI:** Anthropic `claude-opus-4-5` via `ANTHROPIC_API_KEY` — `askClaude()` helper in `server/routes.ts`

### Consolidated Hub Architecture (Phase 2)
Three major hub pages consolidate formerly scattered standalone pages:

| Hub | Route | Tabs | Pages Consolidated |
|---|---|---|---|
| Analytics Hub | `/analytics` | Revenue Cycle, Reports, Business Intel, Provider Intel, Predictive AI | 5+ analytics pages |
| AI Command Center | `/ai-hub` | AI Assistant, Documentation, Phone Agent, DentBot, Voice-to-Code | 5 AI tool pages |
| Marketing Hub | `/marketing` | Channels, Content Engine, Reputation, NPS, Testimonials | 5 marketing pages |
| Virtual Office | `/virtual-office` | Floor Plan, HR/Staff, Telehealth, Training, Announcements | HR + ops pages |

Legacy standalone pages remain accessible at `-old` / `-classic` routes as fallbacks.

### Key Files
- `client/src/App.tsx` — All ~94 route registrations
- `client/src/components/app-sidebar.tsx` — Navigation sidebar
- `server/routes.ts` — All API endpoints (~3263 lines)
- `server/storage.ts` — IStorage interface + DatabaseStorage
- `shared/schema.ts` — Drizzle schema + Zod types (1525 lines)
- `claude.md` — Full agent guide with conventions, gotchas, and patterns
- `docs/ARCHITECTURE.md` — System design and data flow
- `docs/FEATURES.md` — All 94 pages catalogued with routes and data sources
- `docs/API.md` — Complete API endpoint reference

### HIPAA Compliance
- 15-minute inactivity session timeout (`components/session-timeout.tsx`)
- Audit logging for PHI access
- All API routes protected by `isAuthenticated`
- Secure OIDC session management

### Critical Schema Notes
- `billing_claims.claimStatus` — use `claimStatus` NOT `status`
- `appointments.startTime` / `appointments.endTime` — NOT `date`
- Owner bypass: user ID `47100532` auto-completes onboarding

## AI-Powered Features
- **Intelligent Coding Engine** — CDT→CPT/ICD-10 cross-coding
- **Smart Appeals Engine** — AI-generated insurance appeals and denial analysis
- **AI Documentation Engine** — Medical necessity letters, operative reports, SOAP notes, predetermination letters
- **Predictive Analytics** — Collection forecasting, at-risk claim identification
- **AI Phone Agent (ARIA)** — Virtual HIPAA-compliant receptionist
- **DentBot Advisor** — Practice intelligence with proactive insights
- **Voice-to-Code** — Voice dictation → procedure code mapping

## External Dependencies
- **Database**: PostgreSQL (Replit managed, `DATABASE_URL` auto-set)
- **ORM**: Drizzle ORM
- **Authentication**: Replit Auth (OIDC)
- **AI**: Anthropic Claude (`claude-opus-4-5`) via `ANTHROPIC_API_KEY`
- **UI**: Shadcn/UI + lucide-react + TailwindCSS
