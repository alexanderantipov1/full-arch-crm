# ImplantBill AI — Claude Agent Guide

## Project Overview
ImplantBill AI is a HIPAA-compliant SaaS dental practice management platform built for full-arch implant practices (All-on-4 / All-on-6). It combines CRM, patient management, AI-powered medical billing, virtual office infrastructure, and comprehensive practice analytics into a single system.

## Tech Stack
| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript, Vite, TailwindCSS, Shadcn/UI |
| Routing | Wouter (client-side) |
| State/Data | TanStack Query v5 |
| Backend | Express.js + TypeScript |
| Database | PostgreSQL via Drizzle ORM |
| Auth | Replit Auth (OIDC) |
| AI | Anthropic `claude-opus-4-5` via `ANTHROPIC_API_KEY` |
| Icons | lucide-react + react-icons/si |

## File Structure
```
/
├── client/src/
│   ├── App.tsx                  # Root router — all 90+ page routes registered here
│   ├── pages/                   # ~94 page components
│   ├── components/
│   │   ├── app-sidebar.tsx      # Main navigation sidebar
│   │   ├── session-timeout.tsx  # HIPAA 15-min inactivity timeout
│   │   └── ui/                  # Shadcn components
│   ├── hooks/
│   │   ├── use-auth.ts          # Auth hook (wraps /api/auth/user)
│   │   └── use-toast.ts
│   └── lib/
│       └── queryClient.ts       # TanStack Query client + apiRequest helper
├── server/
│   ├── routes.ts                # All API endpoints (~3263 lines)
│   ├── storage.ts               # IStorage interface + DatabaseStorage impl
│   └── replit_integrations/
│       └── auth/                # Replit OIDC auth setup
├── shared/
│   └── schema.ts                # Drizzle schema + Zod insert schemas (1525 lines, 30+ tables)
├── replit.md                    # Project overview + user preferences
└── claude.md                    # This file
```

## Auth Pattern
```typescript
// Backend: get user ID from session
import { getSessionUserId } from "./replit_integrations/auth/replitAuth";
const userId = getSessionUserId(req); // returns req.user.claims.sub

// Owner bypass: user ID "47100532" auto-completes onboarding
// Middleware: isAuthenticated from "./replit_integrations/auth/replitAuth"

// Frontend: use auth hook
const { user, isLoading } = useAuth();
// user.id, user.email, user.name available
```

## AI Integration
```typescript
// Anthropic client is initialized in server/routes.ts
const anthropic = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

async function askClaude(systemPrompt: string, userMessage: string, maxTokens = 1500): Promise<string> {
  const response = await anthropic.messages.create({
    model: "claude-opus-4-5",
    max_tokens: maxTokens,
    system: systemPrompt,
    messages: [{ role: "user", content: userMessage }],
  });
  const block = response.content[0];
  return block.type === "text" ? block.text : "";
}
```
AI endpoints: `POST /api/ai/chat`, `POST /api/ai/generate-document`, `POST /api/ai/appeals`, `POST /api/ai/coding`

## Database Schema — Key Tables
| Table | Purpose | Key Fields |
|---|---|---|
| `patients` | Core patient record | id, firstName, lastName, dateOfBirth, email, phone |
| `medical_history` | Health history per patient | patientId, conditions[], allergies[], medications[] |
| `dental_info` | Dental-specific info | patientId, chiefComplaint, missingTeeth[], implants[] |
| `insurance` | Insurance per patient | patientId, insuranceType, providerName, policyNumber |
| `treatment_plans` | Treatment plans | patientId, procedureType, status, totalFee |
| `appointments` | Scheduling | patientId, startTime, endTime, appointmentType, status |
| `billing_claims` | Insurance claims | patientId, claimStatus (NOT `status`), totalFee, cdtCodes[] |
| `prior_authorizations` | Pre-auth requests | patientId, procedureCode, authStatus |
| `clinical_notes` | SOAP notes | patientId, noteType, content |
| `code_cross_references` | CDT→CPT/ICD-10 | cdtCode, cptCodes[], icd10Codes[] |
| `fee_schedules` | Insurance fee schedules | insuranceName, cdtCode, allowedAmount |
| `leads` | CRM leads | firstName, lastName, source, status |
| `perio_exams` | Periodontal charting | patientId, examDate, pocketDepths[] |
| `ortho_cases` | Orthodontic tracking | patientId, bracesType, startDate |
| `endo_cases` | Endodontic tracking | patientId, toothNumber, canalCount |
| `oral_surgery_cases` | Oral surgery | patientId, procedureType, surgeryDate |
| `union_organizations` | Union outreach CRM | name, industry, memberCount |
| `practice_locations` | Multi-location | name, address, phone |

## Critical Schema Gotchas
- `billing_claims.claimStatus` — use `claimStatus` NOT `status`
- `appointments.startTime` / `appointments.endTime` — use `startTime` NOT `date`
- Array columns use `.array()` method: `text("field").array()` NOT `array(text("field"))`

## Key Architectural Decisions — Hub Consolidation
The app has ~94 pages. To reduce sidebar clutter, 3 consolidated hubs were built:

| Hub | Route | Tabs | Replaces |
|---|---|---|---|
| Analytics Hub | `/analytics` | Revenue Cycle, Reports, Business Intel, Provider Intel, Predictive AI | `/analytics-old`, standalone pages |
| AI Command Center | `/ai-hub` | AI Assistant, Documentation, Phone Agent, DentBot, Voice-to-Code | `/ai-assistant`, `/ai-documentation`, `/dentbot`, `/ai-phone`, `/voice-to-code` |
| Marketing Hub | `/marketing` | Channels, Content Engine, Reputation, NPS, Testimonials | `/marketing-classic`, `/content-engine`, `/reputation`, `/nps`, `/testimonials` |
| Virtual Office | `/virtual-office` | Floor Plan, HR/Staff, Telehealth, Training, Announcements | `/hr`, standalone pages |

Old standalone routes are retained as fallbacks (redirected to `-old` or `-classic` variants).

## HIPAA Compliance
- 15-minute inactivity session timeout (`components/session-timeout.tsx`)
- Audit logging for PHI access
- All routes protected by `isAuthenticated` middleware
- Secure session management via Replit Auth OIDC

## Frontend Conventions
```typescript
// Data fetching — always use TanStack Query
const { data: patients = [], isLoading } = useQuery<Patient[]>({ queryKey: ["/api/patients"] });

// Mutations — use apiRequest then invalidate cache
const mutation = useMutation({
  mutationFn: async (data) => {
    const res = await apiRequest("POST", "/api/patients", data);
    return res.json();
  },
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["/api/patients"] }),
});

// Forms — always use react-hook-form + zodResolver
const form = useForm<InsertPatient>({
  resolver: zodResolver(insertPatientSchema),
  defaultValues: { firstName: "", lastName: "" },
});

// Toast notifications
const { toast } = useToast(); // import from "@/hooks/use-toast"

// Routing
import { Link, useLocation } from "wouter";
// Never use window.location for navigation
```

## Backend Conventions
```typescript
// All routes: validate with Zod, use storage interface, keep thin
app.post("/api/resource", isAuthenticated, async (req, res) => {
  try {
    const data = insertResourceSchema.parse(req.body);
    const result = await storage.createResource(data);
    res.status(201).json(result);
  } catch (error: any) {
    res.status(400).json({ message: error.message });
  }
});
```

## Pre-existing TypeScript Errors (Ignore These)
These files have pre-existing TS errors that are not regressions — do not fix them unless specifically asked:
- `client/src/pages/audit-logs.tsx`
- `client/src/pages/consent-forms.tsx`
- `client/src/pages/intake-form.tsx`
- `client/src/pages/patient-documents.tsx`
- `client/src/pages/payments.tsx`
- `client/src/pages/reports.tsx`
- `client/src/pages/treatment-progress.tsx`
- `server/routes.ts` (minor type issues in some handlers)
- `server/replit_integrations/` (integration scaffolding)

## Environment Variables
| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude AI model access |
| `SESSION_SECRET` | Express session signing |
| `DATABASE_URL` | PostgreSQL connection (auto-set by Replit) |

## Running the App
- Workflow: `Start application` → runs `npm run dev`
- Port 5000 serves both Vite frontend and Express backend
- Frontend: `http://localhost:5000/`
- Do NOT modify `vite.config.ts` or `server/vite.ts`
- Do NOT modify `drizzle.config.ts`
- Do NOT edit `package.json` (use packager tool to add deps)
