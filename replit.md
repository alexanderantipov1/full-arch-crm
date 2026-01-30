# Full Arch CRM - HIPAA-Compliant Patient CRM for Dental Implant Practices

## Overview
Full Arch CRM is a comprehensive practice management system designed specifically for dental implant practices, with a strong focus on **medical billing for full arch dental implants** (All-on-4, All-on-6) - the highest-ticket dental procedures.

## Core Features
- **Patient Management**: Complete demographics, medical history, dental info
- **Treatment Planning**: AI-assisted full arch implant planning (All-on-4, All-on-6) with cost estimation
- **Medical Billing**: CDT/ICD-10 coding, prior authorizations, claims management, denial tracking with AI appeals
- **Intelligent Coding Engine**: CDT→CPT/ICD-10 cross-coding with AI-powered suggestions (99.2% accuracy target)
- **AI Assistant**: Medical necessity letters, appeal letter drafting, insurance coding guidance
- **Scheduling**: Appointment calendar for surgeries, consultations, follow-ups
- **Insurance Strategy**: Medical vs dental billing guidance, approval optimization
- **Provider Portal**: Referring dentist/orthodontist management, care reports

## Technology Stack
- **Frontend**: React + TypeScript, Vite, TailwindCSS, Shadcn/UI
- **Backend**: Express.js, TypeScript
- **Database**: PostgreSQL with Drizzle ORM
- **Auth**: Replit Auth (OIDC)
- **AI**: OpenAI GPT-5.2 via Replit AI Integrations

## Project Structure
```
├── client/                    # Frontend React application
│   ├── src/
│   │   ├── components/        # UI components
│   │   │   ├── ui/           # Shadcn UI components
│   │   │   ├── app-sidebar.tsx
│   │   │   ├── theme-provider.tsx
│   │   │   └── theme-toggle.tsx
│   │   ├── pages/            # Page components
│   │   │   ├── landing.tsx   # Public landing page
│   │   │   ├── dashboard.tsx
│   │   │   ├── patients.tsx
│   │   │   ├── patient-form.tsx
│   │   │   ├── patient-detail.tsx
│   │   │   ├── treatment-plans.tsx
│   │   │   ├── appointments.tsx
│   │   │   ├── billing.tsx   # Claims & insurance management
│   │   │   ├── coding-engine.tsx  # CDT→CPT/ICD-10 cross-coding
│   │   │   ├── providers.tsx  # Referring providers management
│   │   │   └── ai-assistant.tsx
│   │   ├── hooks/            # Custom React hooks
│   │   ├── lib/              # Utilities
│   │   └── App.tsx           # Main app with routing
├── server/                    # Backend Express server
│   ├── routes.ts             # All API routes
│   ├── storage.ts            # Database operations
│   ├── db.ts                 # Database connection
│   └── replit_integrations/  # Auth, AI, chat integrations
├── shared/                   # Shared types and schemas
│   ├── schema.ts            # Drizzle schema definitions
│   └── models/              # Auth and chat models
└── scripts/
    └── seed.ts              # Database seeding script
```

## Database Schema
Key tables:
- `patients`: Core patient demographics
- `medical_history`: Medical conditions, allergies, medications
- `dental_info`: Dental history, missing teeth, existing implants
- `facial_evaluation`: Arnett & Gunson protocol data, airway assessment
- `cephalometrics`: Cephalometric measurements (SNA, SNB, ANB, FMA, etc.)
- `insurance`: Medical/dental coverage
- `treatment_plans`: Full arch treatment plans with procedures and costs
- `prior_authorizations`: Prior auth workflow with peer-to-peer tracking
- `full_arch_exams`: Comprehensive full arch implant evaluations
- `medical_consults`: Medical clearance and consultation requests
- `appointments`: Scheduling
- `billing_claims`: Insurance claims with CDT/ICD codes
- `clinical_notes`: Clinical documentation
- `surgery_reports`: Op reports
- `follow_ups`: Patient follow-up tracking
- `care_reports`: Continuity of care documentation for referring providers
- `referring_providers`: Referring dentists and orthodontists
- `code_cross_reference`: CDT→CPT/ICD-10 code mappings
- `fee_schedules`: Payer-specific fee schedules

## Key API Endpoints
- `GET/POST /api/patients` - Patient CRUD
- `GET /api/patients/:id` - Patient with full details
- `GET/POST /api/treatment-plans` - Treatment planning
- `GET /api/billing/stats` - Billing dashboard stats
- `GET/POST /api/billing/claims` - Claims management
- `POST /api/ai/chat` - AI assistant chat
- `POST /api/ai/diagnosis` - AI treatment recommendations
- `POST /api/ai/medical-necessity-letter` - Generate letters
- `POST /api/ai/appeal-letter` - Generate denial appeals
- `GET/POST /api/coding/cross-references` - Code cross-reference management
- `GET/POST /api/coding/fee-schedules` - Fee schedule management
- `POST /api/coding/suggest` - AI-powered code suggestions

## Design Theme
Medical professional theme with:
- Primary: Clinical blue (#0EA5E9)
- Accent: Teal/green for success states
- Clean, professional interface
- HIPAA compliance messaging
- Light/dark mode support

## Running the Application
- Development: `npm run dev`
- Database push: `npm run db:push`
- Seed data: `npx tsx scripts/seed.ts`

## CDT Codes Reference (Full Arch Implants)
- D6010: Surgical placement of implant body ($2,200)
- D6056: Prefabricated abutment ($650)
- D6058: Abutment supported crown ($1,400)
- D6114: Implant supported fixed denture per arch ($28,500)
- D7210: Extraction with flap elevation ($285)
- D7953: Bone replacement graft ($875)

## User Preferences
- Focus on medical billing workflow for full arch implants
- All-on-4 and All-on-6 are the primary procedures
- AI assistance for insurance approvals, appeals, and coding
- Medical necessity documentation is key to getting claims approved
- Professional, clinical appearance
