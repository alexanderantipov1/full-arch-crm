# ImplantBill AI — API Reference

All endpoints require authentication via Replit Auth session cookie unless noted.
Base URL: `/api`
Error format: `{ "message": "string" }`

---

## Authentication
Handled by Replit OIDC. Managed in `server/replit_integrations/auth/`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/auth/user` | Returns current authenticated user `{ id, email, name, ... }` |
| GET | `/api/login` | Initiates Replit OIDC login flow |
| GET | `/api/logout` | Ends session and redirects to landing |

---

## Dashboard
| Method | Endpoint | Description | Response |
|---|---|---|---|
| GET | `/api/dashboard/stats` | KPIs: total patients, appointments today, monthly revenue, outstanding claims | `{ totalPatients, appointmentsToday, monthlyRevenue, outstandingClaims }` |

---

## Patients

| Method | Endpoint | Description | Body / Query |
|---|---|---|---|
| GET | `/api/patients` | List all patients | — |
| GET | `/api/patients/:id` | Get patient with full details (insurance, history, etc.) | — |
| POST | `/api/patients` | Create patient | `InsertPatient` |
| PATCH | `/api/patients/:id` | Update patient fields | `Partial<InsertPatient>` |
| DELETE | `/api/patients/:id` | Delete patient | — |

### Patient Sub-Resources
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/patients/:id/medical-history` | Get medical history |
| PUT | `/api/patients/:id/medical-history` | Upsert medical history |
| GET | `/api/patients/:id/dental-info` | Get dental info |
| PUT | `/api/patients/:id/dental-info` | Upsert dental info |
| PUT | `/api/patients/:id/facial-evaluation` | Upsert Arnett-Gunson facial evaluation |
| GET | `/api/patients/:id/insurance` | List insurance records |
| POST | `/api/patients/:id/insurance` | Add insurance record |
| GET | `/api/patients/:id/notes` | List clinical notes (SOAP) |
| POST | `/api/patients/:id/notes` | Create clinical note |

---

## Insurance
| Method | Endpoint | Description | Body |
|---|---|---|---|
| PATCH | `/api/insurance/:id` | Update insurance record | `Partial<InsertInsurance>` |
| DELETE | `/api/insurance/:id` | Delete insurance record | — |

---

## Treatment Plans
| Method | Endpoint | Query Params | Body |
|---|---|---|---|
| GET | `/api/treatment-plans` | `?patientId=&status=&priorAuthStatus=` | — |
| GET | `/api/treatment-plans/:id` | — | — |
| POST | `/api/treatment-plans` | — | `InsertTreatmentPlan` |
| PATCH | `/api/treatment-plans/:id` | — | `Partial<InsertTreatmentPlan>` |

---

## Appointments
| Method | Endpoint | Query / Body | Notes |
|---|---|---|---|
| GET | `/api/appointments` | `?patientId=&startDate=&endDate=` | Filtered list |
| GET | `/api/appointments/upcoming` | — | Next appointments sorted by startTime |
| POST | `/api/appointments` | `InsertAppointment` | |
| PATCH | `/api/appointments/:id` | `Partial<InsertAppointment>` | Update status, time, etc. |

---

## Billing & Claims
| Method | Endpoint | Description | Body / Query |
|---|---|---|---|
| GET | `/api/billing/stats` | Billing KPIs: total billed, collected, outstanding, denial rate | — |
| GET | `/api/billing/claims` | List claims | `?patientId=&status=` |
| POST | `/api/billing/claims` | Create claim | `InsertBillingClaim` |
| PATCH | `/api/billing/claims/:id` | Update claim (status, amounts) | `Partial<InsertBillingClaim>` |

**Note:** Filter by `claimStatus` field (not `status`) in the schema.

---

## Prior Authorizations
| Method | Endpoint | Description | Body / Query |
|---|---|---|---|
| GET | `/api/prior-authorizations` | List prior auths | `?patientId=&status=` |
| GET | `/api/prior-authorizations/:id` | Get single prior auth | — |
| POST | `/api/prior-authorizations` | Create prior auth request | `InsertPriorAuthorization` |
| PATCH | `/api/prior-authorizations/:id` | Update auth status/details | `Partial<InsertPriorAuthorization>` |

---

## ERA / Payments
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/era-processing` | List ERA records and remittance data |
| POST | `/api/era-processing` | Post ERA / remittance |
| GET | `/api/payments` | List patient payments |
| POST | `/api/payments` | Record payment |

---

## Coding Engine
| Method | Endpoint | Description | Body |
|---|---|---|---|
| GET | `/api/code-references` | List CDT→CPT/ICD-10 cross references | — |
| POST | `/api/code-references` | Add code mapping | `InsertCodeCrossReference` |
| GET | `/api/fee-schedules` | List fee schedules by insurance | — |
| POST | `/api/fee-schedules` | Add fee schedule entry | `InsertFeeSchedule` |

---

## AI Endpoints
| Method | Endpoint | Description | Body | Response |
|---|---|---|---|---|
| POST | `/api/ai/chat` | General billing & clinical AI assistant | `{ message: string }` | `{ response: string }` |
| POST | `/api/ai/generate-document` | Generate clinical document | `{ docType: string, patientId?: number, context?: string }` | `{ document: string }` |
| POST | `/api/ai/appeals` | Generate insurance appeal letter | `{ claimId?: number, denialReason?: string, context?: string }` | `{ appeal: string }` |
| POST | `/api/ai/coding` | Get AI coding suggestions (CDT→CPT/ICD-10) | `{ description: string, cdtCodes?: string[] }` | `{ suggestions: string[] }` |

`docType` values: `medical_necessity`, `operative_report`, `progress_note`, `referral_letter`, `predetermination`, `appeal_letter`

---

## Leads (CRM)
| Method | Endpoint | Description | Body |
|---|---|---|---|
| GET | `/api/leads` | List all leads | — |
| POST | `/api/leads` | Create lead | `InsertLead` |
| PATCH | `/api/leads/:id` | Update lead status/notes | `Partial<InsertLead>` |
| DELETE | `/api/leads/:id` | Delete lead | — |

---

## Scheduling & Operations
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/reminders` | Appointment reminders list |
| POST | `/api/reminders` | Create reminder rule |
| GET | `/api/check-ins` | Patient check-in records |
| POST | `/api/check-ins` | Record patient check-in |

---

## Surgery Workflow
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/pre-surgery` | Pre-surgery task lists |
| POST | `/api/pre-surgery` | Create pre-surgery task |
| GET | `/api/surgery-sessions` | Surgery session records |
| POST | `/api/surgery-sessions` | Create surgery session |
| GET | `/api/post-op-visits` | Post-op visit records |
| POST | `/api/post-op-visits` | Record post-op visit |
| GET | `/api/lab-cases` | Lab case tracking |
| POST | `/api/lab-cases` | Create lab case |

---

## Specialty Modules
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/perio-exams` | Periodontal exam records |
| POST | `/api/perio-exams` | Create perio exam |
| GET | `/api/ortho-cases` | Orthodontic cases |
| POST | `/api/ortho-cases` | Create ortho case |
| GET | `/api/endo-cases` | Endodontic cases |
| POST | `/api/endo-cases` | Create endo case |
| GET | `/api/oral-surgery-cases` | Oral surgery cases |
| POST | `/api/oral-surgery-cases` | Create oral surgery case |
| GET | `/api/recall-patients` | Recall patient list |
| POST | `/api/recall-patients` | Add patient to recall |
| POST | `/api/recall-contact-logs` | Log recall contact attempt |

---

## Practice Management
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/providers` | Practice providers list |
| POST | `/api/providers` | Add provider |
| GET | `/api/locations` | Practice locations |
| POST | `/api/locations` | Add location |
| GET | `/api/settings` | Practice settings |
| PUT | `/api/settings` | Update settings |
| GET | `/api/inventory` | Inventory items |
| POST | `/api/inventory` | Add inventory item |

---

## Union Outreach (CRM)
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/union-organizations` | List union orgs |
| POST | `/api/union-organizations` | Add union org |
| GET | `/api/union-contacts` | List contacts |
| POST | `/api/union-contacts` | Add contact |
| GET | `/api/union-outreach` | Outreach activity log |
| POST | `/api/union-outreach` | Log outreach activity |
| GET | `/api/union-events` | Union events |
| GET | `/api/union-agreements` | Union agreements |

---

## Patient Communication
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/messages` | Internal staff messages |
| POST | `/api/messages` | Send internal message |
| GET | `/api/patient-messages` | Patient messages |
| POST | `/api/patient-messages` | Send patient message |

---

## Onboarding
| Method | Endpoint | Description | Body |
|---|---|---|---|
| GET | `/api/onboarding/status` | Check if onboarding complete | — |
| POST | `/api/onboarding/complete` | Mark onboarding complete | `{ specialty, modules, ... }` |

---

## Analytics
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/analytics/revenue` | Monthly revenue breakdown |
| GET | `/api/analytics/claims` | Claim status distribution |
| GET | `/api/analytics/appointments` | Appointment volume metrics |

---

## Misc
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/consent-forms` | Consent form templates and records |
| GET | `/api/documents` | Patient documents |
| POST | `/api/documents` | Upload/link patient document |
| GET | `/api/testimonials` | Patient testimonials |
| POST | `/api/testimonials` | Add testimonial |
| GET | `/api/warranties` | Implant warranties |
| GET | `/api/financing-plans` | Financing plans |
| GET | `/api/treatment-packages` | Treatment packages |
| GET | `/api/audit-logs` | HIPAA audit log (admin only) |
