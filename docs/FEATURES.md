# ImplantBill AI — Feature & Page Inventory

All 94 pages in `client/src/pages/`. Organized by sidebar section.

**Data source key:**
- 🟢 Live DB — queries real PostgreSQL data via API
- 🟡 Mixed — some live data, some static demo
- ⚪ Static — demo/mock data only

---

## Public / Auth Pages
| File | Route | Description | Data |
|---|---|---|---|
| `landing.tsx` | `/` (unauthenticated) | Marketing landing page with login CTA | ⚪ |
| `onboarding.tsx` | Shown before dashboard | Multi-step specialty onboarding flow, AI personalization | 🟢 |
| `not-found.tsx` | `*` | 404 page | ⚪ |
| `about.tsx` | `/about` | Public about/marketing page | ⚪ |
| `seo-all-on-4.tsx` | `/all-on-4-billing` | SEO landing: All-on-4 billing guide | ⚪ |
| `seo-all-on-6.tsx` | `/all-on-6-billing` | SEO landing: All-on-6 billing guide | ⚪ |
| `seo-dental-billing.tsx` | `/dental-implant-billing` | SEO landing: dental implant billing | ⚪ |

---

## Home / Dashboard
| File | Route | Description | Data |
|---|---|---|---|
| `dashboard.tsx` | `/` | Main dashboard with KPIs, today's schedule, alerts | 🟢 |
| `command-center.tsx` | `/command-center` | Practice command center overview | 🟡 |

---

## Patients & Scheduling
| File | Route | Description | Data |
|---|---|---|---|
| `patients.tsx` | `/patients` | Patient list with search and filters | 🟢 |
| `patient-form.tsx` | `/patients/new` | New patient intake form | 🟢 |
| `patient-detail.tsx` | `/patients/:id` | Full patient record with tabbed detail view | 🟢 |
| `appointments.tsx` | `/appointments` | Appointment calendar and list | 🟢 |
| `multi-provider-scheduling.tsx` | `/multi-scheduling` | Multi-provider schedule view | 🟡 |
| `appointment-reminders.tsx` | `/reminders` | Automated appointment reminder management | 🟢 |
| `patient-checkin.tsx` | `/check-in` | Digital patient check-in flow | 🟢 |
| `recall-system.tsx` | `/recall` | Patient recall and re-engagement system | 🟢 |
| `leads.tsx` | `/leads` | CRM lead management and pipeline | 🟢 |
| `practice-crm.tsx` | `/practice-crm` | Full CRM with contact management | 🟡 |

---

## Clinical Care
| File | Route | Description | Data |
|---|---|---|---|
| `clinical-notes.tsx` | `/notes` | SOAP notes and clinical documentation | 🟢 |
| `evaluations.tsx` | `/evaluations` | Patient evaluation forms | 🟢 |
| `intake-form.tsx` | `/intake` | Patient intake forms | 🟢 |
| `consent-forms.tsx` | `/consent-forms` | Digital consent form management | 🟢 |
| `treatment-plans.tsx` | `/treatment-plans` | Treatment plan creation and management | 🟢 |
| `treatment-progress.tsx` | `/treatment-progress` | Track treatment milestones | 🟢 |
| `dental-charting.tsx` | `/dental-charting/:id?` | Interactive tooth chart (FDI/ADA) | 🟢 |
| `perio-charting.tsx` | `/perio` | Periodontal chart with pocket depths | 🟢 |
| `decision-support.tsx` | `/decision-support` | AI-assisted clinical decision support | 🟡 |
| `ai-diagnostics.tsx` | `/ai-diagnostics` | AI diagnostic analysis tools | 🟡 |
| `e-prescribing.tsx` | `/e-prescribing` | Electronic prescribing module | 🟡 |
| `patient-documents.tsx` | `/documents` | Patient document management (X-rays, photos) | 🟢 |
| `medical-clearance.tsx` | `/medical-clearance` | Medical clearance workflow | 🟢 |

---

## Surgery Center
| File | Route | Description | Data |
|---|---|---|---|
| `pre-surgery.tsx` | `/pre-surgery` | Pre-surgical checklist and prep | 🟢 |
| `surgery-day.tsx` | `/surgery` | Day-of-surgery workflow and tracking | 🟢 |
| `post-op.tsx` | `/post-op` | Post-operative visit management | 🟢 |
| `lab.tsx` | `/lab` | Lab case tracking and prosthetics | 🟢 |
| `implant-tracker.tsx` | `/implant-tracker` | Implant component tracking by patient | 🟢 |
| `sterilization.tsx` | `/sterilization` | Sterilization log and compliance | 🟡 |
| `oral-surgery-module.tsx` | `/oral-surgery` | Full oral surgery case management | 🟢 |

---

## Specialty Modules
| File | Route | Description | Data |
|---|---|---|---|
| `ortho-tracker.tsx` | `/ortho` | Orthodontic case management | 🟢 |
| `endo-tracker.tsx` | `/endo` | Endodontic case tracking | 🟢 |
| `pediatric-module.tsx` | `/pediatric` | Pediatric dental module | 🟢 |
| `perio-charting.tsx` | `/perio` | Periodontal charting | 🟢 |

---

## Billing & Revenue Cycle
| File | Route | Description | Data |
|---|---|---|---|
| `billing.tsx` | `/billing` | Billing claims list and management | 🟢 |
| `coding-engine.tsx` | `/coding` | CDT→CPT/ICD-10 intelligent cross-coding | 🟢 |
| `appeals-engine.tsx` | `/appeals` | AI-powered insurance appeal management | 🟢 |
| `era-processing.tsx` | `/era-processing` | ERA (835) remittance processing | 🟢 |
| `insurance-verification.tsx` | `/eligibility` | Real-time insurance eligibility verification | 🟡 |
| `payments.tsx` | `/payments` | Patient payment processing and history | 🟢 |
| `prior-authorizations` (in billing) | via billing | Pre-authorization request management | 🟢 |
| `calculator.tsx` | `/calculator` | Implant fee and patient cost calculator | ⚪ |
| `treatment-packages.tsx` | `/packages` | All-on-4/6 treatment package builder | 🟢 |
| `financing.tsx` | `/financing` | Patient financing plans (CareCredit etc.) | 🟢 |
| `fee-optimizer.tsx` | `/fee-optimizer` | AI fee schedule optimization | 🟡 |
| `rcm.tsx` | `/rcm` | Revenue cycle management dashboard | 🟡 |
| `financial.tsx` | `/financial` | Financial reporting and AR aging | 🟢 |
| `warranty.tsx` | `/warranty` | Implant warranty management | 🟢 |
| `case-acceptance.tsx` | `/case-acceptance` | Case acceptance rate tracking | 🟡 |

---

## AI Command Center (Hub: `/ai-hub`)
| File | Route | Tab / Description | Data |
|---|---|---|---|
| `ai-hub.tsx` | `/ai-hub` | **Hub** — 5 tabs below | 🟡 |
| → AI Assistant tab | — | General billing/clinical AI chat | 🟢 Live API |
| → Documentation tab | — | AI document generation (letters, SOAP, appeals) | 🟢 Live API |
| → Phone Agent tab | — | ARIA AI receptionist call log | ⚪ |
| → DentBot tab | — | Practice intelligence advisor | ⚪ |
| → Voice-to-Code tab | — | Voice dictation → procedure codes | ⚪ Simulated |
| `ai-assistant.tsx` | `/ai-assistant` | Standalone AI chat (legacy) | 🟢 |
| `ai-documentation.tsx` | `/ai-documentation` | Standalone doc generation (legacy) | 🟢 |
| `ai-phone.tsx` | `/ai-phone` | Standalone AI phone (legacy) | ⚪ |
| `dentbot.tsx` | `/dentbot` | Standalone DentBot (legacy) | ⚪ |
| `voice-to-code.tsx` | `/voice-to-code` | Standalone voice-to-code (legacy) | ⚪ |

---

## Analytics & Intelligence (Hub: `/analytics`)
| File | Route | Tab / Description | Data |
|---|---|---|---|
| `analytics-hub.tsx` | `/analytics` | **Hub** — 5 tabs below | 🟡 |
| → Revenue Cycle tab | — | Claims, ERA, payments KPIs | 🟢 Live DB |
| → Reports tab | — | Monthly/quarterly financial reports | 🟢 Live DB |
| → Business Intel tab | — | Market intelligence, benchmarks | ⚪ |
| → Provider Intel tab | — | Per-provider production analytics | ⚪ |
| → Predictive AI tab | — | Collection forecasting, at-risk claims | 🟡 |
| `analytics.tsx` | `/analytics-old` | Legacy analytics page | 🟢 |
| `predictive-analytics.tsx` | `/predictive` | Standalone predictive analytics | 🟡 |
| `provider-intel.tsx` | `/provider-intel` | Standalone provider intel | 🟡 |
| `payer-intel.tsx` | `/payer-intel` | Payer performance and contract analysis | 🟡 |
| `business-intelligence.tsx` | `/business-intelligence` | Standalone BI dashboard | 🟡 |
| `reports.tsx` | `/reports` | Standalone reports page | 🟢 |
| `compliance.tsx` | `/compliance` | Compliance tracking and audit prep | 🟡 |

---

## Marketing & Growth (Hub: `/marketing`)
| File | Route | Tab / Description | Data |
|---|---|---|---|
| `marketing-hub.tsx` | `/marketing` | **Hub** — 5 tabs below | ⚪ |
| → Channels tab | — | Marketing channel ROI and spend | ⚪ |
| → Content Engine tab | — | AI content generation and pipeline | ⚪ |
| → Reputation tab | — | Review management (Google, Yelp) | ⚪ |
| → NPS tab | — | Patient satisfaction and NPS scoring | ⚪ |
| → Testimonials tab | — | Featured patient testimonials | ⚪ |
| `marketing.tsx` | `/marketing-classic` | Legacy marketing suite (legacy) | ⚪ |
| `content-engine.tsx` | `/content-engine` | Standalone content engine (legacy) | ⚪ |
| `reputation-manager.tsx` | `/reputation` | Standalone reputation (legacy) | ⚪ |
| `nps.tsx` | `/nps` | Standalone NPS (legacy) | ⚪ |
| `testimonials.tsx` | `/testimonials` | Standalone testimonials (legacy) | ⚪ |

---

## Virtual Office & Operations
| File | Route | Description | Data |
|---|---|---|---|
| `virtual-office.tsx` | `/virtual-office` | **Hub** — Floor plan, HR, Telehealth, Training, Huddle | ⚪ |
| `hr-payroll.tsx` | `/hr` | HR and payroll management | ⚪ |
| `team-kpis.tsx` | `/team-kpis` | Team performance KPIs | 🟡 |
| `telehealth.tsx` | `/telehealth` | Telehealth session management | ⚪ |
| `inventory.tsx` | `/inventory` | Supply and inventory management | 🟡 |
| `maintenance.tsx` | `/maintenance` | Equipment maintenance tracking | 🟢 |
| `providers.tsx` | `/providers` | Provider directory and management | 🟢 |
| `multi-location.tsx` | `/multi-location` | Multi-location practice management | 🟡 |
| `settings.tsx` | `/settings` | Practice settings and configuration | 🟢 |
| `audit-logs.tsx` | `/audit-logs` | HIPAA audit log viewer | 🟢 |

---

## Communication
| File | Route | Description | Data |
|---|---|---|---|
| `messages.tsx` | `/messages` | Internal staff messaging | 🟡 |
| `patient-messaging.tsx` | `/patient-messaging` | Two-way patient SMS/messaging | 🟡 |
| `patient-portal.tsx` | `/patient-portal` | Patient self-service portal | 🟡 |

---

## Growth & Strategy
| File | Route | Description | Data |
|---|---|---|---|
| `practice-launchpad.tsx` | `/practice-launchpad` | Practice growth launchpad | ⚪ |
| `union-flow.tsx` | `/union-flow` | Union outreach CRM workflow | 🟢 |
| `advanced-modules.tsx` | `/advanced-modules` | Module marketplace and activation | ⚪ |
| `saas-admin.tsx` | `/saas-admin` | SaaS platform admin panel | ⚪ |
| `training.tsx` | `/training` | Staff training and CE management | ⚪ |
