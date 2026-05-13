# ImplantBill AI — System Architecture

## Overview
ImplantBill AI runs as a single Express server that serves both the Vite-built frontend (static files in production, dev proxy in development) and the REST API backend. Both share port 5000.

## Frontend Architecture

### Framework & Build
- **React 18** with TypeScript, built by **Vite**
- JSX transformer is pre-configured — do NOT import React explicitly
- Path aliases: `@/` → `client/src/`, `@assets/` → `attached_assets/`, `@shared/` → `shared/`

### Routing
- **Wouter** handles client-side routing
- All routes registered in `client/src/App.tsx` inside a `<Switch>`
- Public routes (SEO pages, landing) are at the top level of `<App>`
- Authenticated routes wrapped in `<AuthenticatedLayout>` (sidebar + header)
- Onboarding check: if user exists but `onboardingStatus.isComplete === false`, redirect to `/onboarding`

### State Management
- **TanStack Query v5** for all server state (data fetching, caching, mutations)
- Default fetcher in `queryClient.ts` handles auth headers automatically
- `apiRequest(method, url, body)` helper in `client/src/lib/queryClient.ts` for mutations
- Local UI state uses React `useState` / `useReducer`

### Component Library
- **Shadcn/UI** components in `client/src/components/ui/`
- **lucide-react** for icons
- **react-icons/si** for brand/company logos
- Custom components: `AppSidebar`, `SessionTimeout`, `ThemeProvider`, `ThemeToggle`

### Styling
- **TailwindCSS** with `darkMode: ["class"]`
- CSS variables defined in `client/src/index.css` using `H S% L%` format (no `hsl()` wrapper)
- Dark mode toggled by adding/removing `dark` class on `document.documentElement`
- Theme persisted in `localStorage` under key `implantcrm-theme`

## Backend Architecture

### Server Setup
```
server/
├── index.ts          # Entry point — creates Express + HTTP server
├── routes.ts         # All API route handlers (~3263 lines)
├── storage.ts        # IStorage interface + DatabaseStorage implementation
├── vite.ts           # Vite dev middleware integration (do not modify)
└── replit_integrations/
    ├── auth/
    │   ├── replitAuth.ts   # OIDC setup, isAuthenticated middleware, getSessionUserId
    │   └── routes.ts       # /api/auth/user, /api/login, /api/logout
    └── chat/               # Registered chat routes
```

### Authentication
- **Replit Auth (OIDC)** — `setupAuth(app)` configures passport with OIDC strategy
- `isAuthenticated` middleware: checks `req.isAuthenticated()` and session validity
- User ID extraction: `getSessionUserId(req)` returns `req.user.claims.sub` (string)
- Owner bypass: user ID `"47100532"` auto-completes onboarding flow
- Session: `express-session` with `SESSION_SECRET` env var, 15-minute HIPAA timeout enforced on frontend

### API Design
- RESTful resource-based endpoints
- All routes require `isAuthenticated` except public auth endpoints
- Request bodies validated with Zod schemas from `shared/schema.ts`
- All handlers delegate to `storage` interface — routes stay thin
- Error responses: `{ message: string }` with appropriate HTTP status codes

### Storage Interface
```typescript
// server/storage.ts
interface IStorage {
  // Patients
  getPatients(): Promise<Patient[]>;
  getPatientWithDetails(id: number): Promise<PatientWithDetails | null>;
  createPatient(data: InsertPatient): Promise<Patient>;
  updatePatient(id: number, data: Partial<InsertPatient>): Promise<Patient | null>;
  deletePatient(id: number): Promise<void>;
  // ... 100+ methods covering all tables
}
```
`DatabaseStorage` implements `IStorage` using Drizzle ORM queries.

## Database

### ORM
- **Drizzle ORM** with PostgreSQL driver
- Schema defined in `shared/schema.ts` — single source of truth for types
- Migrations: `drizzle.config.ts` points to `./migrations/` directory
- Insert schemas auto-generated via `createInsertSchema` from `drizzle-zod`

### Connection
- `DATABASE_URL` environment variable (auto-set by Replit PostgreSQL integration)
- Connection pool managed by Drizzle's postgres.js adapter

### Schema Pattern
```typescript
// Table definition
export const patients = pgTable("patients", { ... });

// Insert schema (excludes auto-generated fields)
export const insertPatientSchema = createInsertSchema(patients).omit({ id: true, createdAt: true, updatedAt: true });

// Types
export type InsertPatient = z.infer<typeof insertPatientSchema>;
export type Patient = typeof patients.$inferSelect;
```

## AI Integration

### Anthropic Claude
```typescript
const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

async function askClaude(systemPrompt: string, userMessage: string, maxTokens = 1500): Promise<string> {
  const response = await anthropic.messages.create({
    model: "claude-opus-4-5",
    max_tokens: maxTokens,
    system: systemPrompt,
    messages: [{ role: "user", content: userMessage }],
  });
  return response.content[0].type === "text" ? response.content[0].text : "";
}
```

### AI Endpoints
> Source of truth: `server/routes.ts`. Complete reference: `docs/API.md`.

| Endpoint | Purpose |
|---|---|
| `POST /api/ai/chat` | General billing & clinical assistant chat |
| `POST /api/ai/generate-document` | Generate medical necessity letters, operative reports, SOAP notes |
| `POST /api/ai/appeal-letter` | AI-powered appeal letter text generation |
| `POST /api/ai/medical-necessity-letter` | Medical necessity letter generation |
| `POST /api/ai/diagnosis` | AI diagnosis assistance |
| `POST /api/ai/specialty-recommendations` | Onboarding specialty recommendations |
| `POST /api/appeals/generate` | Full appeal record: AI letter + DB persist (NOT `/api/ai/appeals`) |
| `POST /api/coding/suggest` | CDT→CPT/ICD-10 cross-coding suggestions (NOT `/api/ai/coding`) |
| `POST /api/perio/ai-assessment` | Periodontal AI clinical assessment |

## Data Flow
```
User Action
  → React component
    → TanStack Query / apiRequest
      → Express route handler
        → Zod validation
          → IStorage method
            → Drizzle ORM query
              → PostgreSQL
                → Response JSON
                  → TanStack Query cache update
                    → React re-render
```

## HIPAA Compliance Architecture
1. **Authentication**: All API routes gated by `isAuthenticated` middleware
2. **Session timeout**: `SessionTimeout` component monitors activity, forces logout after 15 minutes of inactivity
3. **Audit logging**: PHI access events logged to `audit_logs` table
4. **Transport security**: HTTPS enforced in Replit deployment environment
5. **Data isolation**: Multi-tenant ready — all queries can be scoped by practice/user ID

## Deployment
- Replit handles hosting, TLS, and health checks
- `npm run dev` starts both Vite dev server and Express in development
- Production build: Vite compiles frontend to `dist/public/`, Express serves static files
