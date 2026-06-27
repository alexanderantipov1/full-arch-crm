/**
 * MockAdapter — dev/testing adapter
 * Uses the local PostgreSQL database (same as the existing storage layer).
 * Zero network calls — perfect for local dev and CI.
 * 
 * This is also the fallback when no ADAPTER_TYPE env var is set.
 */

import { db } from "../../db";
import { patients, appointments, treatmentPlans, clinicalNotes, insurance, billingClaims, medicalHistory, priorAuthorizations, financingPlans } from "../../../shared/schema";
import { eq } from "drizzle-orm/sql/expressions/conditions";
import type { DatabaseAdapter, CdtCodeResult, EobPosting } from "../interface";

// Row types inferred from schema — eliminates implicit-any in .map() lambdas
type PatientRow       = typeof patients.$inferSelect;
type AppointmentRow   = typeof appointments.$inferSelect;
type TreatmentPlanRow = typeof treatmentPlans.$inferSelect;
type ClinicalNoteRow  = typeof clinicalNotes.$inferSelect;
type InsuranceRow     = typeof insurance.$inferSelect;
type ClaimRow         = typeof billingClaims.$inferSelect;
type PriorAuthRow     = typeof priorAuthorizations.$inferSelect;
type FinancingPlanRow = typeof financingPlans.$inferSelect;
import type {
  PhiAccessContext, PhiAuditEntry, AdapterHealthStatus,
  CanonicalPatient, CanonicalPatientSummary, CanonicalMedicalHistory,
  CanonicalInsurance, CanonicalEligibilityResult, CanonicalAppointment,
  CanonicalTreatmentPlan, CanonicalClinicalNote, CanonicalClaim,
  CanonicalPriorAuth, CanonicalFinancingPlan, AnonymizedIntelligencePattern,
  PatientListOptions, PatientListResult, AppointmentListOptions, ClaimListOptions,
} from "../types";

export class MockAdapter implements DatabaseAdapter {
  readonly adapterType = "mock";
  readonly tenantId: string;

  constructor(tenantId: string) {
    this.tenantId = tenantId;
  }

  async healthCheck(): Promise<AdapterHealthStatus> {
    try {
      await db.execute("SELECT 1");
      return { adapterType: "mock", tenantId: this.tenantId, healthy: true, lastCheckedAt: new Date() };
    } catch (err) {
      return { adapterType: "mock", tenantId: this.tenantId, healthy: false, lastCheckedAt: new Date(), errorMessage: String(err) };
    }
  }

  // ── Patients ──────────────────────────────────────────────────────────────

  async listPatients(options?: PatientListOptions): Promise<PatientListResult> {
    const rows = await db.select().from(patients).limit(options?.limit ?? 50);
    const items: CanonicalPatientSummary[] = rows.map((p: PatientRow) => ({
      personUid: String(p.id),
      tenantId: this.tenantId,
      displayName: `${p.firstName} ${p.lastName.charAt(0)}.`,
      ageBand: this.toAgeBand(p.dateOfBirth),
      gender: (p.gender as CanonicalPatient["gender"]) ?? "Unknown",
      patientStage: "consultation_completed",
      activeTreatmentPlan: false,
      scenarioTags: [],
      sourceAdapter: "mock",
    }));
    return { items, total: items.length, hasMore: false };
  }

  async getPatient(personUid: string, phiContext: PhiAccessContext): Promise<CanonicalPatient | null> {
    await this.logPhiAccess({ tenantId: this.tenantId, patientId: personUid, accessedBy: phiContext.requestedBy, purpose: phiContext.purpose, fieldsAccessed: ["all"], sourceAdapter: "mock", traceId: phiContext.traceId });
    const rows = await db.select().from(patients).where(eq(patients.id, parseInt(personUid)));
    const p = rows[0];
    if (!p) return null;
    return {
      personUid: String(p.id),
      tenantId: this.tenantId,
      externalIds: [],
      firstName: p.firstName,
      lastName: p.lastName,
      dateOfBirth: new Date(p.dateOfBirth),
      gender: (p.gender as CanonicalPatient["gender"]) ?? "Unknown",
      email: p.email ?? undefined,
      phone: p.phone ?? undefined,
      address: p.address ? { line1: p.address, city: p.city ?? "", state: p.state ?? "", zip: p.zipCode ?? "", country: "US" } : undefined,
      emergencyContact: p.emergencyContact ? { name: p.emergencyContact, phone: p.emergencyPhone ?? "", relationship: "Other" } : undefined,
      patientStage: "consultation_completed",
      activeTreatmentPlan: false,
      createdAt: p.createdAt,
      updatedAt: p.updatedAt,
      sourceAdapter: "mock",
      dataFreshness: new Date(),
    };
  }

  async searchPatients(query: string, limit = 20): Promise<CanonicalPatientSummary[]> {
    const rows = await db.select().from(patients).limit(limit);
    const q = query.toLowerCase();
    return rows
      .filter((p: PatientRow) => `${p.firstName} ${p.lastName}`.toLowerCase().includes(q) || p.email?.includes(q))
      .map((p: PatientRow) => ({
        personUid: String(p.id),
        tenantId: this.tenantId,
        displayName: `${p.firstName} ${p.lastName.charAt(0)}.`,
        ageBand: this.toAgeBand(p.dateOfBirth),
        gender: (p.gender as CanonicalPatient["gender"]) ?? "Unknown",
        patientStage: "consultation_completed" as const,
        activeTreatmentPlan: false,
        scenarioTags: [],
        sourceAdapter: "mock" as const,
      }));
  }

  async createPatient(data: Omit<CanonicalPatient, "personUid" | "createdAt" | "updatedAt" | "sourceAdapter" | "dataFreshness">, phiContext: PhiAccessContext): Promise<CanonicalPatient> {
    const [row] = await db.insert(patients).values({
      firstName: data.firstName,
      lastName: data.lastName,
      dateOfBirth: data.dateOfBirth.toISOString().split("T")[0],
      gender: data.gender,
      email: data.email,
      phone: data.phone,
      address: data.address?.line1,
      city: data.address?.city,
      state: data.address?.state,
      zipCode: data.address?.zip,
    }).returning();
    return this.getPatient(String(row.id), phiContext) as Promise<CanonicalPatient>;
  }

  async updatePatient(personUid: string, updates: Partial<CanonicalPatient>, phiContext: PhiAccessContext): Promise<CanonicalPatient> {
    await db.update(patients).set({ email: updates.email, phone: updates.phone }).where(eq(patients.id, parseInt(personUid)));
    return this.getPatient(personUid, phiContext) as Promise<CanonicalPatient>;
  }

  // ── Medical History ───────────────────────────────────────────────────────

  async getMedicalHistory(personUid: string, _ctx: PhiAccessContext): Promise<CanonicalMedicalHistory | null> {
    const rows = await db.select().from(medicalHistory).where(eq(medicalHistory.patientId, parseInt(personUid)));
    const m = rows[0];
    if (!m) return null;
    return {
      personUid,
      tenantId: this.tenantId,
      conditions: (m.conditions as string[]) ?? [],
      allergies: (m.allergies as string[]) ?? [],
      medications: (m.medications as string[]) ?? [],
      surgeries: (m.surgeries as string[]) ?? [],
      notes: m.notes ?? undefined,
      updatedAt: m.updatedAt,
    };
  }

  async upsertMedicalHistory(data: CanonicalMedicalHistory, _ctx: PhiAccessContext): Promise<CanonicalMedicalHistory> {
    await db.insert(medicalHistory).values({ patientId: parseInt(data.personUid), conditions: data.conditions, allergies: data.allergies, medications: data.medications }).onConflictDoNothing();
    return data;
  }

  // ── Insurance ─────────────────────────────────────────────────────────────

  async getInsurance(personUid: string, _ctx: PhiAccessContext): Promise<CanonicalInsurance[]> {
    const rows = await db.select().from(insurance).where(eq(insurance.patientId, parseInt(personUid)));
    return rows.map((i: InsuranceRow) => ({
      personUid,
      tenantId: this.tenantId,
      insuranceType: (i.insuranceType as CanonicalInsurance["insuranceType"]) ?? "primary",
      providerName: i.providerName,
      policyNumber: i.policyNumber,
      groupNumber: i.groupNumber ?? undefined,
      subscriberName: i.subscriberName ?? undefined,
      relationship: (i.relationship as CanonicalInsurance["relationship"]) ?? "self",
      coveragePercentage: i.coveragePercentage ?? undefined,
      annualMaximum: i.annualMaximum ? Number(i.annualMaximum) : undefined,
      deductible: i.deductible ? Number(i.deductible) : undefined,
      remainingBenefit: i.remainingBenefit ? Number(i.remainingBenefit) : undefined,
      priorAuthRequired: i.priorAuthRequired ?? false,
    }));
  }

  async checkEligibility(personUid: string, procedureCodes: string[], _ctx: PhiAccessContext): Promise<CanonicalEligibilityResult> {
    const ins = await this.getInsurance(personUid, _ctx);
    const primary = ins[0];
    return {
      personUid,
      tenantId: this.tenantId,
      checkedAt: new Date(),
      status: "active",
      remainingBenefit: primary?.remainingBenefit ?? 0,
      deductibleMet: 0,
      coverageDetails: {},
      procedureCoverageMap: Object.fromEntries(procedureCodes.map(code => [code, {
        cdtCode: code,
        covered: true,
        coveragePercent: primary?.coveragePercentage ?? 50,
        requiresPriorAuth: primary?.priorAuthRequired ?? false,
      }])),
    };
  }

  // ── Appointments ──────────────────────────────────────────────────────────

  async listAppointments(options: AppointmentListOptions): Promise<CanonicalAppointment[]> {
    const rows = await db.select().from(appointments).limit(options.limit ?? 50);
    return rows.map((a: AppointmentRow) => ({
      appointmentId: String(a.id),
      tenantId: this.tenantId,
      personUid: String(a.patientId),
      treatmentPlanId: a.treatmentPlanId ? String(a.treatmentPlanId) : undefined,
      title: a.title,
      appointmentType: (a.appointmentType as CanonicalAppointment["appointmentType"]) ?? "other",
      startTime: new Date(a.startTime),
      endTime: new Date(a.endTime),
      durationMinutes: Math.round((new Date(a.endTime).getTime() - new Date(a.startTime).getTime()) / 60000),
      status: (a.status as CanonicalAppointment["status"]) ?? "scheduled",
      providerName: a.providerName ?? undefined,
      procedureCodes: [],
      insuranceVerified: false,
      notes: a.notes ?? undefined,
      createdAt: a.createdAt,
      updatedAt: a.updatedAt,
      sourceAdapter: "mock",
    }));
  }

  async getAppointment(appointmentId: string): Promise<CanonicalAppointment | null> {
    const rows = await this.listAppointments({});
    return rows.find(a => a.appointmentId === appointmentId) ?? null;
  }

  async createAppointment(data: Omit<CanonicalAppointment, "appointmentId" | "createdAt" | "updatedAt" | "sourceAdapter">): Promise<CanonicalAppointment> {
    const [row] = await db.insert(appointments).values({
      patientId: parseInt(data.personUid),
      appointmentType: data.appointmentType,
      title: data.title,
      startTime: data.startTime,
      endTime: data.endTime,
      status: data.status,
      providerName: data.providerName,
      notes: data.notes,
    }).returning();
    return this.getAppointment(String(row.id)) as Promise<CanonicalAppointment>;
  }

  async updateAppointment(appointmentId: string, updates: Partial<CanonicalAppointment>): Promise<CanonicalAppointment> {
    await db.update(appointments).set({ status: updates.status, notes: updates.notes }).where(eq(appointments.id, parseInt(appointmentId)));
    return this.getAppointment(appointmentId) as Promise<CanonicalAppointment>;
  }

  async cancelAppointment(appointmentId: string): Promise<void> {
    await db.update(appointments).set({ status: "cancelled" }).where(eq(appointments.id, parseInt(appointmentId)));
  }

  // ── Treatment Plans ───────────────────────────────────────────────────────

  async getTreatmentPlans(personUid: string, _ctx: PhiAccessContext): Promise<CanonicalTreatmentPlan[]> {
    const rows = await db.select().from(treatmentPlans).where(eq(treatmentPlans.patientId, parseInt(personUid)));
    return rows.map((t: TreatmentPlanRow) => ({
      planId: String(t.id),
      tenantId: this.tenantId,
      personUid,
      planName: t.planName,
      status: (t.status as CanonicalTreatmentPlan["status"]) ?? "draft",
      diagnosis: t.diagnosis ?? undefined,
      diagnosisCode: t.diagnosisCode ?? undefined,
      aiDiagnosis: t.aiDiagnosis ?? undefined,
      procedures: (t.procedures as CanonicalTreatmentPlan["procedures"]) ?? [],
      totalCost: Number(t.totalCost ?? 0),
      insuranceCoverage: Number(t.insuranceCoverage ?? 0),
      patientResponsibility: Number(t.patientResponsibility ?? 0),
      createdAt: t.createdAt,
      updatedAt: t.updatedAt,
      sourceAdapter: "mock",
    }));
  }

  async getTreatmentPlan(planId: string, ctx: PhiAccessContext): Promise<CanonicalTreatmentPlan | null> {
    const rows = await db.select().from(treatmentPlans).where(eq(treatmentPlans.id, parseInt(planId)));
    if (!rows[0]) return null;
    const plans = await this.getTreatmentPlans(String(rows[0].patientId), ctx);
    return plans.find(p => p.planId === planId) ?? null;
  }

  async createTreatmentPlan(data: Omit<CanonicalTreatmentPlan, "planId" | "createdAt" | "updatedAt" | "sourceAdapter">, _ctx: PhiAccessContext): Promise<CanonicalTreatmentPlan> {
    const [row] = await db.insert(treatmentPlans).values({
      patientId: parseInt(data.personUid),
      planName: data.planName,
      status: data.status,
      totalCost: String(data.totalCost),
      insuranceCoverage: String(data.insuranceCoverage),
      patientResponsibility: String(data.patientResponsibility),
    }).returning();
    return this.getTreatmentPlan(String(row.id), _ctx) as Promise<CanonicalTreatmentPlan>;
  }

  async updateTreatmentPlan(planId: string, updates: Partial<CanonicalTreatmentPlan>, ctx: PhiAccessContext): Promise<CanonicalTreatmentPlan> {
    await db.update(treatmentPlans).set({ status: updates.status }).where(eq(treatmentPlans.id, parseInt(planId)));
    return this.getTreatmentPlan(planId, ctx) as Promise<CanonicalTreatmentPlan>;
  }

  // ── Clinical Notes ────────────────────────────────────────────────────────

  async getClinicalNotes(personUid: string, _ctx: PhiAccessContext): Promise<CanonicalClinicalNote[]> {
    const rows = await db.select().from(clinicalNotes).where(eq(clinicalNotes.patientId, parseInt(personUid)));
    return rows.map((n: ClinicalNoteRow) => ({
      noteId: String(n.id),
      tenantId: this.tenantId,
      personUid,
      noteType: (n.noteType as CanonicalClinicalNote["noteType"]) ?? "other",
      title: n.title,
      soapSubjective: undefined,
      soapObjective: undefined,
      soapAssessment: undefined,
      soapPlan: undefined,
      authorName: n.authorName ?? undefined,
      aiGenerated: false,
      createdAt: n.createdAt,
      updatedAt: n.updatedAt,
      sourceAdapter: "mock",
    }));
  }

  async saveClinicalNote(data: Omit<CanonicalClinicalNote, "noteId" | "createdAt" | "updatedAt" | "sourceAdapter">, _ctx: PhiAccessContext): Promise<CanonicalClinicalNote> {
    const content = [data.soapSubjective, data.soapObjective, data.soapAssessment, data.soapPlan].filter(Boolean).join("\n\n");
    const [row] = await db.insert(clinicalNotes).values({
      patientId: parseInt(data.personUid),
      noteType: data.noteType,
      title: data.title,
      content: content || data.title,
      authorName: data.authorName,
    }).returning();
    return { ...data, noteId: String(row.id), createdAt: row.createdAt, updatedAt: row.updatedAt, sourceAdapter: "mock" };
  }

  async searchCdtCodes(query: string, limit = 10): Promise<CdtCodeResult[]> {
    const cdtCodes: CdtCodeResult[] = [
      { code: "D6010", description: "Surgical placement of implant body: endosteal implant", category: "Implant Services" },
      { code: "D6056", description: "Prefabricated abutment — includes placement", category: "Implant Services" },
      { code: "D6057", description: "Custom fabricated abutment — includes placement", category: "Implant Services" },
      { code: "D6114", description: "Implant-supported fixed denture (edentulous arch)", category: "Implant Services" },
      { code: "D0330", description: "Panoramic radiographic image", category: "Diagnostic" },
      { code: "D0150", description: "Comprehensive oral evaluation — new or established patient", category: "Diagnostic" },
      { code: "D4341", description: "Periodontal scaling and root planing — four or more teeth per quadrant", category: "Periodontics" },
      { code: "D7140", description: "Extraction, erupted tooth or exposed root", category: "Oral Surgery" },
      { code: "D7310", description: "Alveoloplasty in conjunction with extractions — four or more teeth", category: "Oral Surgery" },
      { code: "D9930", description: "Treatment of complications (post-surgical)", category: "Other" },
    ];
    const q = query.toLowerCase();
    return cdtCodes.filter(c => c.code.toLowerCase().includes(q) || c.description.toLowerCase().includes(q)).slice(0, limit);
  }

  // ── Claims ────────────────────────────────────────────────────────────────

  async listClaims(options: ClaimListOptions): Promise<CanonicalClaim[]> {
    let query = db.select().from(billingClaims);
    if (options.personUid) {
      query = query.where(eq(billingClaims.patientId, parseInt(options.personUid))) as typeof query;
    }
    const rows = await query.limit(options.limit ?? 50);
    return rows.map((c: ClaimRow) => ({
      claimId: String(c.id),
      tenantId: this.tenantId,
      personUid: String(c.patientId),
      claimNumber: c.claimNumber ?? `CLM-${c.id}`,
      claimStatus: (c.claimStatus as CanonicalClaim["claimStatus"]) ?? "pending",
      serviceDate: new Date(c.serviceDate),
      cdtCode: c.procedureCode,
      icd10Code: c.icd10Code ?? undefined,
      description: c.description ?? "",
      chargedAmount: Number(c.chargedAmount),
      allowedAmount: c.allowedAmount ? Number(c.allowedAmount) : undefined,
      paidAmount: c.paidAmount ? Number(c.paidAmount) : undefined,
      patientPortion: c.patientPortion ? Number(c.patientPortion) : undefined,
      denialReason: c.denialReason ?? undefined,
      sourceAdapter: "mock",
      createdAt: c.createdAt,
      updatedAt: c.createdAt,
    }));
  }

  async getClaim(claimId: string): Promise<CanonicalClaim | null> {
    const claims = await this.listClaims({});
    return claims.find(c => c.claimId === claimId) ?? null;
  }

  async createClaim(data: Omit<CanonicalClaim, "claimId" | "createdAt" | "updatedAt" | "sourceAdapter">, _ctx: PhiAccessContext): Promise<CanonicalClaim> {
    const [row] = await db.insert(billingClaims).values({
      patientId: parseInt(data.personUid),
      claimNumber: data.claimNumber,
      claimStatus: data.claimStatus,
      serviceDate: data.serviceDate.toISOString().split("T")[0],
      procedureCode: data.cdtCode,
      icd10Code: data.icd10Code,
      description: data.description,
      chargedAmount: String(data.chargedAmount),
      submittedDate: data.submittedDate?.toISOString().split("T")[0],
    }).returning();
    return this.getClaim(String(row.id)) as Promise<CanonicalClaim>;
  }

  async updateClaim(claimId: string, updates: Partial<CanonicalClaim>): Promise<CanonicalClaim> {
    await db.update(billingClaims).set({
      claimStatus: updates.claimStatus,
      allowedAmount: updates.allowedAmount ? String(updates.allowedAmount) : undefined,
      paidAmount: updates.paidAmount ? String(updates.paidAmount) : undefined,
      denialReason: updates.denialReason,
    }).where(eq(billingClaims.id, parseInt(claimId)));
    return this.getClaim(claimId) as Promise<CanonicalClaim>;
  }

  async postEob(claimId: string, eob: EobPosting, _ctx: PhiAccessContext): Promise<CanonicalClaim> {
    return this.updateClaim(claimId, {
      claimStatus: eob.paidAmount > 0 ? "paid" : "denied",
      allowedAmount: eob.allowedAmount,
      paidAmount: eob.paidAmount,
      patientPortion: eob.patientPortion,
      denialReason: eob.denialDescription,
      paidDate: eob.processedDate,
    });
  }

  // ── Prior Auth ────────────────────────────────────────────────────────────

  async getPriorAuths(personUid: string, _ctx: PhiAccessContext): Promise<CanonicalPriorAuth[]> {
    const rows = await db.select().from(priorAuthorizations).where(eq(priorAuthorizations.patientId, parseInt(personUid)));
    return rows.map((pa: PriorAuthRow) => ({
      authId: String(pa.id),
      tenantId: this.tenantId,
      personUid,
      treatmentPlanId: pa.treatmentPlanId ? String(pa.treatmentPlanId) : undefined,
      authType: pa.authType ?? "dental",
      status: (pa.status as CanonicalPriorAuth["status"]) ?? "submitted",
      submissionDate: pa.submissionDate ? new Date(pa.submissionDate) : undefined,
      responseDate: pa.responseDate ? new Date(pa.responseDate) : undefined,
      authNumber: pa.authNumber ?? undefined,
      requestedProcedures: (pa.requestedProcedures as Record<string, unknown>) ?? {},
      notes: pa.notes ?? undefined,
    }));
  }

  async createPriorAuth(data: Omit<CanonicalPriorAuth, "authId">, _ctx: PhiAccessContext): Promise<CanonicalPriorAuth> {
    const [row] = await db.insert(priorAuthorizations).values({
      patientId: parseInt(data.personUid),
      authType: data.authType,
      status: data.status,
      submissionDate: data.submissionDate?.toISOString().split("T")[0],
      requestedProcedures: data.requestedProcedures,
      notes: data.notes,
    }).returning();
    return { ...data, authId: String(row.id) };
  }

  async updatePriorAuth(authId: string, updates: Partial<CanonicalPriorAuth>): Promise<CanonicalPriorAuth> {
    await db.update(priorAuthorizations).set({ status: updates.status, authNumber: updates.authNumber }).where(eq(priorAuthorizations.id, parseInt(authId)));
    const rows = await db.select().from(priorAuthorizations).where(eq(priorAuthorizations.id, parseInt(authId)));
    return { ...rows[0], authId, tenantId: this.tenantId, personUid: String(rows[0].patientId), authType: rows[0].authType ?? "dental", status: (rows[0].status as CanonicalPriorAuth["status"]) ?? "submitted", requestedProcedures: (rows[0].requestedProcedures as Record<string, unknown>) ?? {} };
  }

  // ── Financing ─────────────────────────────────────────────────────────────

  async getFinancingPlans(personUid: string, _ctx: PhiAccessContext): Promise<CanonicalFinancingPlan[]> {
    const rows = await db.select().from(financingPlans).where(eq(financingPlans.patientId, parseInt(personUid)));
    return rows.map((f: FinancingPlanRow) => ({
      planId: String(f.id),
      tenantId: this.tenantId,
      personUid,
      provider: f.provider,
      applicationStatus: (f.applicationStatus as CanonicalFinancingPlan["applicationStatus"]) ?? "pending",
      approvedAmount: f.approvedAmount ? Number(f.approvedAmount) : undefined,
      interestRate: f.interestRate ? Number(f.interestRate) : undefined,
      termMonths: f.termMonths ?? undefined,
      monthlyPayment: f.monthlyPayment ? Number(f.monthlyPayment) : undefined,
      downPayment: f.downPayment ? Number(f.downPayment) : undefined,
      approvalDate: f.approvalDate ? new Date(f.approvalDate) : undefined,
    }));
  }

  async createFinancingPlan(data: Omit<CanonicalFinancingPlan, "planId">, _ctx: PhiAccessContext): Promise<CanonicalFinancingPlan> {
    const [row] = await db.insert(financingPlans).values({
      patientId: parseInt(data.personUid),
      provider: data.provider,
      applicationStatus: data.applicationStatus,
      approvedAmount: data.approvedAmount ? String(data.approvedAmount) : undefined,
      termMonths: data.termMonths,
      monthlyPayment: data.monthlyPayment ? String(data.monthlyPayment) : undefined,
    }).returning();
    return { ...data, planId: String(row.id) };
  }

  // ── Intelligence ──────────────────────────────────────────────────────────

  async pushIntelligence(pattern: AnonymizedIntelligencePattern): Promise<void> {
    // In mock mode, log the pattern — no remote network call
    console.log(`[MockAdapter] Intelligence pattern: ${pattern.patternType} → ${pattern.wikiTargetPath}`);
  }

  async queryIntelligence(_type: string, _query: Record<string, unknown>): Promise<AnonymizedIntelligencePattern[]> {
    return []; // Mock returns empty — real adapter queries fusion_crm's intelligence endpoint
  }

  // ── HIPAA Audit ───────────────────────────────────────────────────────────

  async logPhiAccess(entry: Omit<PhiAuditEntry, "id" | "timestamp">): Promise<void> {
    console.log(`[PHI-AUDIT] purpose=${entry.purpose} patient=${entry.patientId} by=${entry.accessedBy} trace=${entry.traceId}`);
    // TODO: persist to audit_logs table
  }

  async getAuditLog(_options: { tenantId: string; from: Date; to: Date }, _ctx: PhiAccessContext): Promise<PhiAuditEntry[]> {
    return [];
  }

  // ── Helpers ───────────────────────────────────────────────────────────────

  private toAgeBand(dob: string | Date): CanonicalPatientSummary["ageBand"] {
    const age = Math.floor((Date.now() - new Date(dob).getTime()) / (365.25 * 24 * 3600 * 1000));
    if (age < 25) return "18-24";
    if (age < 35) return "25-34";
    if (age < 45) return "35-44";
    if (age < 55) return "45-54";
    if (age < 65) return "55-64";
    if (age < 75) return "65-74";
    return "75+";
  }
}
