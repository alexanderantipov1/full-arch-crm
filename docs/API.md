# ImplantBill AI — API Reference

All endpoints require authentication via Replit Auth session cookie unless noted.
Base URL: `/api`
Error format: `{ "message": "string" }`

---

## Authentication
Handled by Replit OIDC. Managed in `server/replit_integrations/auth/`.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/auth/user` | Returns current authenticated user |
| GET | `/api/login` | Initiates Replit OIDC login flow |
| GET | `/api/logout` | Ends session and redirects to landing |

---

## Dashboard
| Method | Endpoint | Response |
|---|---|---|
| GET | `/api/dashboard/stats` | `{ totalPatients, appointmentsToday, monthlyRevenue, outstandingClaims }` |

---

## Patients
| Method | Endpoint | Query / Body | Notes |
|---|---|---|---|
| GET | `/api/patients` | — | All patients |
| GET | `/api/patients/:id` | — | Patient with full details |
| POST | `/api/patients` | `InsertPatient` | |
| PATCH | `/api/patients/:id` | `Partial<InsertPatient>` | |
| DELETE | `/api/patients/:id` | — | |

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
| GET | `/api/patients/:patientId/cephalometrics` | Cephalometric records |
| GET | `/api/patients/:patientId/consults` | Medical consult records |
| GET | `/api/patients/:patientId/full-arch-exams` | Full arch exam records |
| GET | `/api/patients/:patientId/care-reports` | Care reports |
| GET | `/api/patients/:patientId/tooth-conditions` | Tooth conditions for charting |
| POST | `/api/patients/:patientId/tooth-conditions` | Add tooth condition |
| GET | `/api/patients/:patientId/procedures` | All procedures across treatment plans |

---

## Insurance
| Method | Endpoint | Body |
|---|---|---|
| PATCH | `/api/insurance/:id` | `Partial<InsertInsurance>` |
| DELETE | `/api/insurance/:id` | — |

---

## Treatment Plans
| Method | Endpoint | Query / Body |
|---|---|---|
| GET | `/api/treatment-plans` | `?patientId=&status=&priorAuthStatus=` |
| GET | `/api/treatment-plans/:id` | — |
| POST | `/api/treatment-plans` | `InsertTreatmentPlan` |
| PATCH | `/api/treatment-plans/:id` | `Partial<InsertTreatmentPlan>` |
| GET | `/api/treatment-plans/:planId/procedures` | Procedures within a plan |
| POST | `/api/treatment-plans/:planId/procedures` | Add procedure to plan |

### Procedures
| Method | Endpoint | Body |
|---|---|---|
| PATCH | `/api/procedures/:id` | `Partial<InsertTreatmentPlanProcedure>` |
| DELETE | `/api/procedures/:id` | — |

---

## Tooth Conditions
| Method | Endpoint | Body |
|---|---|---|
| PATCH | `/api/tooth-conditions/:id` | `Partial<InsertToothCondition>` |
| DELETE | `/api/tooth-conditions/:id` | — |

---

## Appointments
| Method | Endpoint | Query / Body |
|---|---|---|
| GET | `/api/appointments` | `?patientId=&startDate=&endDate=` |
| GET | `/api/appointments/upcoming` | — |
| POST | `/api/appointments` | `InsertAppointment` |
| PATCH | `/api/appointments/:id` | `Partial<InsertAppointment>` |

**Note:** Use `startTime` / `endTime` field names (not `date`).

---

## Billing & Claims
| Method | Endpoint | Query / Body |
|---|---|---|
| GET | `/api/billing/stats` | — → `{ total billed, collected, outstanding, denial rate }` |
| GET | `/api/billing/claims` | `?patientId=&status=` |
| POST | `/api/billing/claims` | `InsertBillingClaim` |
| PATCH | `/api/billing/claims/:id` | `Partial<InsertBillingClaim>` |
| GET | `/api/billing/claims/denied` | Denied claims with denial reason/code |

**Note:** Schema field is `claimStatus` (not `status`).

---

## Prior Authorizations
| Method | Endpoint | Query / Body |
|---|---|---|
| GET | `/api/prior-authorizations` | `?patientId=&status=` |
| GET | `/api/prior-authorizations/:id` | — |
| POST | `/api/prior-authorizations` | `InsertPriorAuthorization` |
| PATCH | `/api/prior-authorizations/:id` | `Partial<InsertPriorAuthorization>` |

---

## Appeals Engine
| Method | Endpoint | Body | Response |
|---|---|---|---|
| GET | `/api/appeals/stats` | — | `{ total, pending, submitted, won, lost, successRate, avgTurnaround, totalRecovered }` |
| GET | `/api/appeals` | — | All appeal records |
| POST | `/api/appeals/generate` | `{ claimId, patientId, denialReason, denialCode, additionalInfo? }` | `{ appealLetter, successProbability }` |
| POST | `/api/appeals` | `{ claimId, patientId, appealLetter, denialReason, denialCode }` | Created appeal record (201) |

---

## ERA Processing
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/era/stats` | `{ pendingCount, postedToday, totalPosted, varianceCount, autoPostRate, avgProcessingTime }` |
| GET | `/api/era/pending` | Pending payment postings |
| GET | `/api/era/recent` | Recently posted payments |
| GET | `/api/era/variances` | Postings with variance flags |
| POST | `/api/era/:id/post` | Post a single payment — `{ success: true }` |
| POST | `/api/era/auto-post-all` | Auto-post all pending non-variance payments — `{ posted: number }` |

---

## Eligibility Verification
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/eligibility/stats` | `{ checksToday, activeVerifications, eligibleRate, avgResponseTime }` |
| GET | `/api/eligibility/recent` | Recent checks with patient names (last 10) |
| POST | `/api/eligibility/verify/:patientId` | Run eligibility check for patient |

---

## Coding Engine
| Method | Endpoint | Query / Body |
|---|---|---|
| GET | `/api/coding/cross-references` | All CDT→CPT/ICD-10 mappings |
| GET | `/api/coding/cross-references/:cdtCode` | Lookup by CDT code |
| POST | `/api/coding/cross-references` | `InsertCodeCrossReference` |
| GET | `/api/coding/fee-schedules` | `?payer=` — fee schedules by payer |
| POST | `/api/coding/fee-schedules` | `InsertFeeSchedule` |
| POST | `/api/coding/suggest` | AI code suggestion — `{ diagnosis, procedures, clinicalNotes? }` → JSON with `suggestedCDT`, `suggestedCPT`, `suggestedICD10`, `medicalNecessityNotes`, `confidenceScore` |

---

## AI Endpoints
| Method | Endpoint | Body | Response |
|---|---|---|---|
| POST | `/api/ai/chat` | `{ content: string }` | `{ response: string }` |
| POST | `/api/ai/diagnosis` | `{ patientInfo, chiefComplaint, dentalConditions }` | `{ diagnosis: string }` |
| POST | `/api/ai/medical-necessity-letter` | `{ patientName, dateOfBirth, diagnosis, procedures, justification }` | `{ letter: string }` |
| POST | `/api/ai/appeal-letter` | `{ patientName, claimNumber, denialReason, originalDiagnosis, procedures }` | `{ letter: string }` |
| POST | `/api/ai/generate-document` | `{ patientId, documentType, additionalContext? }` | `{ content: string, documentId: number }` |
| GET | `/api/ai/documents/recent` | — | Last 10 generated documents |
| POST | `/api/ai/specialty-recommendations` | `{ specialty, practiceType }` | `{ welcome: string, modules: [] }` |

**`documentType` values:** `medical-necessity`, `operative-report`, `progress-note`, `history-physical`, `peer-to-peer`

**Note on `/api/ai/chat`:** Request body key is `content` (not `message`).

---

## Calculator
| Method | Endpoint | Body | Response |
|---|---|---|---|
| POST | `/api/calculator/patient-responsibility` | `{ treatmentCost, insuranceType, coveragePercentage, deductible, deductibleMet, annualMaximum, usedBenefits, medicalCrossCode? }` | `{ patientResponsibility, insuranceCoverage, deductibleApplied, breakdown, medicalCrossCodePotential? }` |

---

## Analytics
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/analytics/revenue-cycle` | Claims/prior auth KPIs, aging buckets, 6-month trends |
| GET | `/api/analytics/predictive` | Collection forecast, at-risk claims, industry benchmarks, recommendations |

---

## Training Center
| Method | Endpoint | Body | Description |
|---|---|---|---|
| GET | `/api/training/stats` | — | `{ totalModules, completedModules, totalLessons, completedLessons, overallProgress }` |
| GET | `/api/training/progress` | — | Map of `moduleId-lessonId → boolean` |
| POST | `/api/training/complete` | `{ moduleId, lessonId }` | Mark lesson complete |

---

## Leads (CRM)
| Method | Endpoint | Body | Description |
|---|---|---|---|
| GET | `/api/leads` | — | All leads |
| GET | `/api/leads/stats` | — | `{ totalLeads, newLeads, qualifiedLeads, conversionRate }` |
| POST | `/api/leads` | `InsertLead` | |
| PATCH | `/api/leads/:id/status` | `{ status }` | Update lead status only |
| POST | `/api/leads/:id/convert` | — | Convert lead to patient → `{ success, patientId }` |

---

## Referring Providers
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/referring-providers` | — |
| GET | `/api/referring-providers/:id` | — |
| POST | `/api/referring-providers` | `InsertReferringProvider` |
| PATCH | `/api/referring-providers/:id` | `Partial<InsertReferringProvider>` |

---

## Follow-Ups
| Method | Endpoint | Query / Body |
|---|---|---|
| GET | `/api/follow-ups` | `?patientId=&status=` |
| POST | `/api/follow-ups` | `InsertFollowUp` |
| PATCH | `/api/follow-ups/:id` | `Partial<InsertFollowUp>` |

---

## Clinical Sub-Resources
| Method | Endpoint | Body |
|---|---|---|
| POST | `/api/cephalometrics` | `InsertCephalometric` |
| POST | `/api/consults` | `InsertMedicalConsult` |
| PATCH | `/api/consults/:id` | `Partial<InsertMedicalConsult>` |
| POST | `/api/full-arch-exams` | `InsertFullArchExam` |
| PATCH | `/api/full-arch-exams/:id` | `Partial<InsertFullArchExam>` |
| POST | `/api/care-reports` | `InsertCareReport` |

---

## Treatment Packages
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/packages` | — |
| POST | `/api/packages` | `InsertTreatmentPackage` |

---

## Appointment Reminders
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/reminders` | — |
| POST | `/api/reminders` | `InsertAppointmentReminder` |
| POST | `/api/reminders/:id/send` | — → marks reminder as `sent` |

---

## Patient Check-ins
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/checkins` | — |
| POST | `/api/checkins` | `InsertPatientCheckIn` |

---

## Financing Plans
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/financing` | — |
| POST | `/api/financing` | `InsertFinancingPlan` |
| PATCH | `/api/financing/:id` | `Partial<InsertFinancingPlan>` |

---

## Medical Clearances
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/medical-clearances` | — |
| GET | `/api/medical-clearances/patient/:patientId` | — |
| POST | `/api/medical-clearances` | `InsertMedicalClearance` |
| PATCH | `/api/medical-clearances/:id` | `Partial<InsertMedicalClearance>` |

---

## Surgery Workflow
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/pre-surgery-tasks` | — |
| GET | `/api/pre-surgery-tasks/patient/:patientId` | — |
| POST | `/api/pre-surgery-tasks` | `InsertPreSurgeryTask` |
| PATCH | `/api/pre-surgery-tasks/:id` | `Partial<InsertPreSurgeryTask>` |
| GET | `/api/surgery-sessions` | — |
| GET | `/api/surgery-sessions/:id` | — |
| POST | `/api/surgery-sessions` | `InsertSurgerySession` |
| PATCH | `/api/surgery-sessions/:id` | `Partial<InsertSurgerySession>` |
| GET | `/api/post-op-visits` | — |
| POST | `/api/post-op-visits` | `InsertPostOpVisit` |
| PATCH | `/api/post-op-visits/:id` | `Partial<InsertPostOpVisit>` |
| GET | `/api/lab-cases` | — |
| POST | `/api/lab-cases` | `InsertLabCase` |
| PATCH | `/api/lab-cases/:id` | `Partial<InsertLabCase>` |

---

## Warranty Records
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/warranty-records` | — |
| POST | `/api/warranty-records` | `InsertWarrantyRecord` |
| PATCH | `/api/warranty-records/:id` | `Partial<InsertWarrantyRecord>` |

---

## Testimonials
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/testimonials` | — |
| POST | `/api/testimonials` | `InsertTestimonial` |
| PATCH | `/api/testimonials/:id` | `Partial<InsertTestimonial>` |

---

## Maintenance Appointments
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/maintenance` | — |
| POST | `/api/maintenance` | `InsertMaintenanceAppointment` |
| PATCH | `/api/maintenance/:id` | `Partial<InsertMaintenanceAppointment>` |

---

## Consent Forms
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/consent-forms` | — |
| GET | `/api/consent-forms/patient/:patientId` | — |
| POST | `/api/consent-forms` | `InsertConsentForm` |
| POST | `/api/consent-forms/:id/sign` | — → sets signed status |

---

## Patient Documents
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/documents` | — |
| GET | `/api/documents/patient/:patientId` | — |
| POST | `/api/documents` | `InsertPatientDocument` |
| DELETE | `/api/documents/:id` | — |

---

## Internal Messages (Staff)
| Method | Endpoint | Body | Notes |
|---|---|---|---|
| GET | `/api/messages/inbox` | — | Current user's inbox |
| GET | `/api/messages/sent` | — | Current user's sent messages |
| GET | `/api/messages/unread-count` | — | `{ count }` |
| POST | `/api/messages` | `InsertInternalMessage` (senderId injected server-side) | |
| PATCH | `/api/messages/:id/read` | — | Mark message as read |
| GET | `/api/users/all` | — | All users in system |

---

## Patient Messages (2-Way SMS/Communication)
| Method | Endpoint | Query / Body |
|---|---|---|
| GET | `/api/messages` | `?patientId=` — patient messages (separate from internal messages above) |
| POST | `/api/messages` | `InsertPatientMessage` |

**Note:** Both internal and patient messages use `/api/messages` POST. The schema determines routing.

---

## Practice Settings & Onboarding
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/onboarding/status` | — → `{ hasStarted, isComplete, currentStep }` |
| POST | `/api/onboarding/complete` | — → marks onboarding complete |
| GET | `/api/practice-settings` | — → current user's settings or null |
| POST | `/api/practice-settings` | `Partial<InsertPracticeSettings>` (upsert) |
| PATCH | `/api/practice-settings` | `Partial<InsertPracticeSettings>` (upsert) |

**Owner bypass:** User ID `47100532` auto-completes onboarding if not already set.

---

## Practice Providers
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/practice-providers` | — |
| POST | `/api/practice-providers` | `InsertPracticeProvider` |
| PUT | `/api/practice-providers/:id` | Updated provider fields |

---

## Practice Locations
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/locations` | — |
| POST | `/api/locations` | `InsertPracticeLocation` |
| PUT | `/api/locations/:id` | Updated location fields |

---

## Audit Logs (HIPAA)
| Method | Endpoint | Query |
|---|---|---|
| GET | `/api/audit-logs` | `?limit=100&offset=0` |
| GET | `/api/audit-logs/patient/:patientId` | — |

---

## Specialty Modules

### Perio Charting
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/perio/:patientId` | — |
| GET | `/api/perio/exam/:id` | — |
| POST | `/api/perio` | `InsertPerioExam` |
| PUT | `/api/perio/exam/:id` | Updated perio exam |
| POST | `/api/perio/ai-assessment` | `{ probingData, patientName }` → `{ assessment, stats }` |

### Orthodontics
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/ortho` | `?patientId=` |
| GET | `/api/ortho/:id` | — |
| POST | `/api/ortho` | `InsertOrthoCase` |
| PUT | `/api/ortho/:id` | Updated ortho case |

### Endodontics
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/endo` | `?patientId=` |
| GET | `/api/endo/:id` | — |
| POST | `/api/endo` | `InsertEndoCase` |
| PUT | `/api/endo/:id` | Updated endo case |

### Oral Surgery
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/oral-surgery` | `?patientId=` |
| POST | `/api/oral-surgery` | `InsertOralSurgeryCase` |
| PUT | `/api/oral-surgery/:id` | Updated oral surgery case |

### Pediatric Exams
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/pediatric` | `?patientId=` |
| POST | `/api/pediatric` | `InsertPediatricExam` |
| PUT | `/api/pediatric/:id` | Updated pediatric exam |

### Recall System
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/recall` | `?status=` |
| POST | `/api/recall` | `InsertRecallPatient` |
| PUT | `/api/recall/:id` | Updated recall patient |
| GET | `/api/recall/:id/contacts` | Contact log for recall patient |
| POST | `/api/recall/:id/contacts` | `InsertRecallContactLog` |

---

## Union Outreach (CRM)
| Method | Endpoint | Body |
|---|---|---|
| GET | `/api/unions` | — |
| GET | `/api/unions/:id` | — |
| POST | `/api/unions` | `InsertUnionOrganization` |
| PATCH | `/api/unions/:id` | Updated fields |
| DELETE | `/api/unions/:id` | — |
| GET | `/api/unions/:id/contacts` | Contacts for a union |
| POST | `/api/unions/contacts` | `InsertUnionContact` |
| PATCH | `/api/unions/contacts/:id` | Updated contact |
| DELETE | `/api/unions/contacts/:id` | — |
| GET | `/api/unions/outreach/all` | `?unionId=` |
| POST | `/api/unions/outreach` | `InsertUnionOutreach` |
| PATCH | `/api/unions/outreach/:id` | Updated outreach |
| GET | `/api/unions/events/all` | — |
| POST | `/api/unions/events` | `InsertUnionEvent` |
| PATCH | `/api/unions/events/:id` | Updated event |
| GET | `/api/unions/agreements/all` | `?unionId=` |
| POST | `/api/unions/agreements` | `InsertUnionAgreement` |
| PATCH | `/api/unions/agreements/:id` | Updated agreement |
| GET | `/api/unions/visits/all` | `?unionId=` |
| POST | `/api/unions/visits` | `InsertUnionMemberVisit` |
| POST | `/api/unions/seed` | — → seeds 8 Sacramento-area unions (idempotent) |
