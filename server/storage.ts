import { db } from "./db";
import { eq, desc, and, gte, lte, sql } from "drizzle-orm";
import {
  patients,
  medicalHistory,
  dentalInfo,
  facialEvaluation,
  insurance,
  referringProviders,
  patientReferrals,
  clinicalNotes,
  patientDocuments,
  treatmentPlans,
  appointments,
  surgeryReports,
  billingClaims,
  cephalometrics,
  priorAuthorizations,
  medicalConsults,
  fullArchExams,
  followUps,
  careReports,
  users,
  type Patient,
  type InsertPatient,
  type MedicalHistory,
  type InsertMedicalHistory,
  type DentalInfo,
  type InsertDentalInfo,
  type FacialEvaluation,
  type InsertFacialEvaluation,
  type Insurance,
  type InsertInsurance,
  type ReferringProvider,
  type InsertReferringProvider,
  type ClinicalNote,
  type InsertClinicalNote,
  type PatientDocument,
  type InsertPatientDocument,
  type TreatmentPlan,
  type InsertTreatmentPlan,
  type Appointment,
  type InsertAppointment,
  type SurgeryReport,
  type InsertSurgeryReport,
  type BillingClaim,
  type InsertBillingClaim,
  type Cephalometric,
  type InsertCephalometric,
  type PriorAuthorization,
  type InsertPriorAuthorization,
  type MedicalConsult,
  type InsertMedicalConsult,
  type FullArchExam,
  type InsertFullArchExam,
  type FollowUp,
  type InsertFollowUp,
  type CareReport,
  type InsertCareReport,
  type User,
  type UpsertUser,
} from "@shared/schema";

export interface IStorage {
  // Users (Auth)
  getUser(id: string): Promise<User | undefined>;
  upsertUser(user: UpsertUser): Promise<User>;

  // Patients
  getPatients(): Promise<Patient[]>;
  getPatient(id: number): Promise<Patient | undefined>;
  getPatientWithDetails(id: number): Promise<any>;
  createPatient(data: InsertPatient): Promise<Patient>;
  updatePatient(id: number, data: Partial<InsertPatient>): Promise<Patient | undefined>;
  deletePatient(id: number): Promise<void>;

  // Medical History
  getMedicalHistory(patientId: number): Promise<MedicalHistory | undefined>;
  upsertMedicalHistory(data: InsertMedicalHistory): Promise<MedicalHistory>;

  // Dental Info
  getDentalInfo(patientId: number): Promise<DentalInfo | undefined>;
  upsertDentalInfo(data: InsertDentalInfo): Promise<DentalInfo>;

  // Facial Evaluation
  getFacialEvaluation(patientId: number): Promise<FacialEvaluation | undefined>;
  upsertFacialEvaluation(data: InsertFacialEvaluation): Promise<FacialEvaluation>;

  // Insurance
  getPatientInsurance(patientId: number): Promise<Insurance[]>;
  createInsurance(data: InsertInsurance): Promise<Insurance>;
  updateInsurance(id: number, data: Partial<InsertInsurance>): Promise<Insurance | undefined>;
  deleteInsurance(id: number): Promise<void>;

  // Treatment Plans
  getTreatmentPlans(filters?: { patientId?: number; status?: string; priorAuthStatus?: string }): Promise<TreatmentPlan[]>;
  getTreatmentPlan(id: number): Promise<TreatmentPlan | undefined>;
  createTreatmentPlan(data: InsertTreatmentPlan): Promise<TreatmentPlan>;
  updateTreatmentPlan(id: number, data: Partial<InsertTreatmentPlan>): Promise<TreatmentPlan | undefined>;

  // Appointments
  getAppointments(filters?: { patientId?: number; startDate?: Date; endDate?: Date }): Promise<Appointment[]>;
  getUpcomingAppointments(): Promise<Appointment[]>;
  getAppointment(id: number): Promise<Appointment | undefined>;
  createAppointment(data: InsertAppointment): Promise<Appointment>;
  updateAppointment(id: number, data: Partial<InsertAppointment>): Promise<Appointment | undefined>;

  // Clinical Notes
  getPatientNotes(patientId: number): Promise<ClinicalNote[]>;
  createNote(data: InsertClinicalNote): Promise<ClinicalNote>;

  // Billing Claims
  getBillingClaims(filters?: { patientId?: number; status?: string }): Promise<BillingClaim[]>;
  createBillingClaim(data: InsertBillingClaim): Promise<BillingClaim>;
  updateBillingClaim(id: number, data: Partial<InsertBillingClaim>): Promise<BillingClaim | undefined>;

  // Dashboard Stats
  getDashboardStats(): Promise<{
    totalPatients: number;
    todayAppointments: number;
    pendingTreatmentPlans: number;
    pendingClaims: number;
  }>;

  // Billing Stats
  getBillingStats(): Promise<{
    totalBilled: number;
    totalCollected: number;
    pendingClaims: number;
    deniedClaims: number;
    averageReimbursement: number;
  }>;

  // Cephalometrics
  getPatientCephalometrics(patientId: number): Promise<Cephalometric[]>;
  createCephalometric(data: InsertCephalometric): Promise<Cephalometric>;

  // Prior Authorizations
  getPriorAuthorizations(filters?: { patientId?: number; status?: string }): Promise<PriorAuthorization[]>;
  getPriorAuthorization(id: number): Promise<PriorAuthorization | undefined>;
  createPriorAuthorization(data: InsertPriorAuthorization): Promise<PriorAuthorization>;
  updatePriorAuthorization(id: number, data: Partial<InsertPriorAuthorization>): Promise<PriorAuthorization | undefined>;

  // Medical Consults
  getMedicalConsults(patientId: number): Promise<MedicalConsult[]>;
  createMedicalConsult(data: InsertMedicalConsult): Promise<MedicalConsult>;
  updateMedicalConsult(id: number, data: Partial<InsertMedicalConsult>): Promise<MedicalConsult | undefined>;

  // Full Arch Exams
  getPatientFullArchExams(patientId: number): Promise<FullArchExam[]>;
  createFullArchExam(data: InsertFullArchExam): Promise<FullArchExam>;
  updateFullArchExam(id: number, data: Partial<InsertFullArchExam>): Promise<FullArchExam | undefined>;

  // Follow-ups
  getFollowUps(filters?: { patientId?: number; status?: string }): Promise<FollowUp[]>;
  createFollowUp(data: InsertFollowUp): Promise<FollowUp>;
  updateFollowUp(id: number, data: Partial<InsertFollowUp>): Promise<FollowUp | undefined>;

  // Care Reports
  getCareReports(patientId: number): Promise<CareReport[]>;
  createCareReport(data: InsertCareReport): Promise<CareReport>;

  // Referring Providers
  getReferringProviders(): Promise<ReferringProvider[]>;
  getReferringProvider(id: number): Promise<ReferringProvider | undefined>;
  createReferringProvider(data: InsertReferringProvider): Promise<ReferringProvider>;
  updateReferringProvider(id: number, data: Partial<InsertReferringProvider>): Promise<ReferringProvider | undefined>;
}

export class DatabaseStorage implements IStorage {
  // Users
  async getUser(id: string): Promise<User | undefined> {
    const [user] = await db.select().from(users).where(eq(users.id, id));
    return user;
  }

  async upsertUser(userData: UpsertUser): Promise<User> {
    const [user] = await db
      .insert(users)
      .values(userData)
      .onConflictDoUpdate({
        target: users.id,
        set: {
          ...userData,
          updatedAt: new Date(),
        },
      })
      .returning();
    return user;
  }

  // Patients
  async getPatients(): Promise<Patient[]> {
    return db.select().from(patients).orderBy(desc(patients.createdAt));
  }

  async getPatient(id: number): Promise<Patient | undefined> {
    const [patient] = await db.select().from(patients).where(eq(patients.id, id));
    return patient;
  }

  async getPatientWithDetails(id: number): Promise<any> {
    const [patient] = await db.select().from(patients).where(eq(patients.id, id));
    if (!patient) return undefined;

    const [medical] = await db.select().from(medicalHistory).where(eq(medicalHistory.patientId, id));
    const [dental] = await db.select().from(dentalInfo).where(eq(dentalInfo.patientId, id));
    const [facial] = await db.select().from(facialEvaluation).where(eq(facialEvaluation.patientId, id));
    const patientInsurance = await db.select().from(insurance).where(eq(insurance.patientId, id));
    const patientPlans = await db.select().from(treatmentPlans).where(eq(treatmentPlans.patientId, id)).orderBy(desc(treatmentPlans.createdAt));
    const patientAppointments = await db.select().from(appointments).where(eq(appointments.patientId, id)).orderBy(desc(appointments.startTime));
    const patientCephalometrics = await db.select().from(cephalometrics).where(eq(cephalometrics.patientId, id)).orderBy(desc(cephalometrics.createdAt));
    const patientConsults = await db.select().from(medicalConsults).where(eq(medicalConsults.patientId, id)).orderBy(desc(medicalConsults.createdAt));
    const patientFullArchExams = await db.select().from(fullArchExams).where(eq(fullArchExams.patientId, id)).orderBy(desc(fullArchExams.createdAt));

    return {
      ...patient,
      medicalHistory: medical,
      dentalInfo: dental,
      facialEvaluation: facial,
      insurance: patientInsurance,
      treatmentPlans: patientPlans,
      appointments: patientAppointments,
      cephalometrics: patientCephalometrics,
      medicalConsults: patientConsults,
      fullArchExams: patientFullArchExams,
    };
  }

  async createPatient(data: InsertPatient): Promise<Patient> {
    const [patient] = await db.insert(patients).values(data).returning();
    return patient;
  }

  async updatePatient(id: number, data: Partial<InsertPatient>): Promise<Patient | undefined> {
    const [patient] = await db
      .update(patients)
      .set({ ...data, updatedAt: new Date() })
      .where(eq(patients.id, id))
      .returning();
    return patient;
  }

  async deletePatient(id: number): Promise<void> {
    await db.delete(patients).where(eq(patients.id, id));
  }

  // Medical History
  async getMedicalHistory(patientId: number): Promise<MedicalHistory | undefined> {
    const [history] = await db.select().from(medicalHistory).where(eq(medicalHistory.patientId, patientId));
    return history;
  }

  async upsertMedicalHistory(data: InsertMedicalHistory): Promise<MedicalHistory> {
    const existing = await this.getMedicalHistory(data.patientId);
    if (existing) {
      const [updated] = await db
        .update(medicalHistory)
        .set({ ...data, updatedAt: new Date() })
        .where(eq(medicalHistory.patientId, data.patientId))
        .returning();
      return updated;
    }
    const [created] = await db.insert(medicalHistory).values(data).returning();
    return created;
  }

  // Dental Info
  async getDentalInfo(patientId: number): Promise<DentalInfo | undefined> {
    const [info] = await db.select().from(dentalInfo).where(eq(dentalInfo.patientId, patientId));
    return info;
  }

  async upsertDentalInfo(data: InsertDentalInfo): Promise<DentalInfo> {
    const existing = await this.getDentalInfo(data.patientId);
    if (existing) {
      const [updated] = await db
        .update(dentalInfo)
        .set({ ...data, updatedAt: new Date() })
        .where(eq(dentalInfo.patientId, data.patientId))
        .returning();
      return updated;
    }
    const [created] = await db.insert(dentalInfo).values(data).returning();
    return created;
  }

  // Facial Evaluation
  async getFacialEvaluation(patientId: number): Promise<FacialEvaluation | undefined> {
    const [evaluation] = await db.select().from(facialEvaluation).where(eq(facialEvaluation.patientId, patientId));
    return evaluation;
  }

  async upsertFacialEvaluation(data: InsertFacialEvaluation): Promise<FacialEvaluation> {
    const existing = await this.getFacialEvaluation(data.patientId);
    if (existing) {
      const [updated] = await db
        .update(facialEvaluation)
        .set({ ...data, updatedAt: new Date() })
        .where(eq(facialEvaluation.patientId, data.patientId))
        .returning();
      return updated;
    }
    const [created] = await db.insert(facialEvaluation).values(data).returning();
    return created;
  }

  // Insurance
  async getPatientInsurance(patientId: number): Promise<Insurance[]> {
    return db.select().from(insurance).where(eq(insurance.patientId, patientId));
  }

  async createInsurance(data: InsertInsurance): Promise<Insurance> {
    const [ins] = await db.insert(insurance).values(data).returning();
    return ins;
  }

  async updateInsurance(id: number, data: Partial<InsertInsurance>): Promise<Insurance | undefined> {
    const [ins] = await db.update(insurance).set(data).where(eq(insurance.id, id)).returning();
    return ins;
  }

  async deleteInsurance(id: number): Promise<void> {
    await db.delete(insurance).where(eq(insurance.id, id));
  }

  // Treatment Plans
  async getTreatmentPlans(filters?: { patientId?: number; status?: string; priorAuthStatus?: string }): Promise<TreatmentPlan[]> {
    let query = db.select().from(treatmentPlans);
    
    const conditions = [];
    if (filters?.patientId) {
      conditions.push(eq(treatmentPlans.patientId, filters.patientId));
    }
    if (filters?.status) {
      conditions.push(eq(treatmentPlans.status, filters.status));
    }
    if (filters?.priorAuthStatus) {
      conditions.push(eq(treatmentPlans.priorAuthStatus, filters.priorAuthStatus));
    }

    if (conditions.length > 0) {
      return db.select().from(treatmentPlans).where(and(...conditions)).orderBy(desc(treatmentPlans.createdAt));
    }
    
    return db.select().from(treatmentPlans).orderBy(desc(treatmentPlans.createdAt));
  }

  async getTreatmentPlan(id: number): Promise<TreatmentPlan | undefined> {
    const [plan] = await db.select().from(treatmentPlans).where(eq(treatmentPlans.id, id));
    return plan;
  }

  async createTreatmentPlan(data: InsertTreatmentPlan): Promise<TreatmentPlan> {
    const [plan] = await db.insert(treatmentPlans).values(data).returning();
    return plan;
  }

  async updateTreatmentPlan(id: number, data: Partial<InsertTreatmentPlan>): Promise<TreatmentPlan | undefined> {
    const [plan] = await db
      .update(treatmentPlans)
      .set({ ...data, updatedAt: new Date() })
      .where(eq(treatmentPlans.id, id))
      .returning();
    return plan;
  }

  // Appointments
  async getAppointments(filters?: { patientId?: number; startDate?: Date; endDate?: Date }): Promise<Appointment[]> {
    const conditions = [];
    if (filters?.patientId) {
      conditions.push(eq(appointments.patientId, filters.patientId));
    }
    if (filters?.startDate) {
      conditions.push(gte(appointments.startTime, filters.startDate));
    }
    if (filters?.endDate) {
      conditions.push(lte(appointments.startTime, filters.endDate));
    }

    if (conditions.length > 0) {
      return db.select().from(appointments).where(and(...conditions)).orderBy(appointments.startTime);
    }
    return db.select().from(appointments).orderBy(appointments.startTime);
  }

  async getUpcomingAppointments(): Promise<Appointment[]> {
    const now = new Date();
    return db
      .select()
      .from(appointments)
      .where(gte(appointments.startTime, now))
      .orderBy(appointments.startTime)
      .limit(10);
  }

  async getAppointment(id: number): Promise<Appointment | undefined> {
    const [apt] = await db.select().from(appointments).where(eq(appointments.id, id));
    return apt;
  }

  async createAppointment(data: InsertAppointment): Promise<Appointment> {
    const [apt] = await db.insert(appointments).values(data).returning();
    return apt;
  }

  async updateAppointment(id: number, data: Partial<InsertAppointment>): Promise<Appointment | undefined> {
    const [apt] = await db.update(appointments).set(data).where(eq(appointments.id, id)).returning();
    return apt;
  }

  // Clinical Notes
  async getPatientNotes(patientId: number): Promise<ClinicalNote[]> {
    return db.select().from(clinicalNotes).where(eq(clinicalNotes.patientId, patientId)).orderBy(desc(clinicalNotes.createdAt));
  }

  async createNote(data: InsertClinicalNote): Promise<ClinicalNote> {
    const [note] = await db.insert(clinicalNotes).values(data).returning();
    return note;
  }

  // Billing Claims
  async getBillingClaims(filters?: { patientId?: number; status?: string }): Promise<BillingClaim[]> {
    const conditions = [];
    if (filters?.patientId) {
      conditions.push(eq(billingClaims.patientId, filters.patientId));
    }
    if (filters?.status) {
      conditions.push(eq(billingClaims.claimStatus, filters.status));
    }

    if (conditions.length > 0) {
      return db.select().from(billingClaims).where(and(...conditions)).orderBy(desc(billingClaims.createdAt));
    }
    return db.select().from(billingClaims).orderBy(desc(billingClaims.createdAt));
  }

  async createBillingClaim(data: InsertBillingClaim): Promise<BillingClaim> {
    const [claim] = await db.insert(billingClaims).values(data).returning();
    return claim;
  }

  async updateBillingClaim(id: number, data: Partial<InsertBillingClaim>): Promise<BillingClaim | undefined> {
    const [claim] = await db.update(billingClaims).set(data).where(eq(billingClaims.id, id)).returning();
    return claim;
  }

  // Dashboard Stats
  async getDashboardStats() {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    const [patientCount] = await db.select({ count: sql<number>`count(*)` }).from(patients);
    const [todayApts] = await db
      .select({ count: sql<number>`count(*)` })
      .from(appointments)
      .where(and(gte(appointments.startTime, today), lte(appointments.startTime, tomorrow)));
    const [pendingPlans] = await db
      .select({ count: sql<number>`count(*)` })
      .from(treatmentPlans)
      .where(eq(treatmentPlans.status, "pending"));
    const [pendingClaimsCount] = await db
      .select({ count: sql<number>`count(*)` })
      .from(billingClaims)
      .where(eq(billingClaims.claimStatus, "pending"));

    return {
      totalPatients: Number(patientCount?.count) || 0,
      todayAppointments: Number(todayApts?.count) || 0,
      pendingTreatmentPlans: Number(pendingPlans?.count) || 0,
      pendingClaims: Number(pendingClaimsCount?.count) || 0,
    };
  }

  // Billing Stats
  async getBillingStats() {
    const [billedSum] = await db
      .select({ total: sql<number>`COALESCE(SUM(charged_amount), 0)` })
      .from(billingClaims);
    const [collectedSum] = await db
      .select({ total: sql<number>`COALESCE(SUM(paid_amount), 0)` })
      .from(billingClaims)
      .where(eq(billingClaims.claimStatus, "paid"));
    const [pendingCount] = await db
      .select({ count: sql<number>`count(*)` })
      .from(billingClaims)
      .where(eq(billingClaims.claimStatus, "pending"));
    const [deniedCount] = await db
      .select({ count: sql<number>`count(*)` })
      .from(billingClaims)
      .where(eq(billingClaims.claimStatus, "denied"));

    const totalBilled = Number(billedSum?.total) || 0;
    const totalCollected = Number(collectedSum?.total) || 0;
    const avgReimb = totalBilled > 0 ? Math.round((totalCollected / totalBilled) * 100) : 0;

    return {
      totalBilled,
      totalCollected,
      pendingClaims: Number(pendingCount?.count) || 0,
      deniedClaims: Number(deniedCount?.count) || 0,
      averageReimbursement: avgReimb,
    };
  }

  // Cephalometrics
  async getPatientCephalometrics(patientId: number): Promise<Cephalometric[]> {
    return db.select().from(cephalometrics).where(eq(cephalometrics.patientId, patientId)).orderBy(desc(cephalometrics.createdAt));
  }

  async createCephalometric(data: InsertCephalometric): Promise<Cephalometric> {
    const [ceph] = await db.insert(cephalometrics).values(data).returning();
    return ceph;
  }

  // Prior Authorizations
  async getPriorAuthorizations(filters?: { patientId?: number; status?: string }): Promise<PriorAuthorization[]> {
    const conditions = [];
    if (filters?.patientId) {
      conditions.push(eq(priorAuthorizations.patientId, filters.patientId));
    }
    if (filters?.status) {
      conditions.push(eq(priorAuthorizations.status, filters.status));
    }

    if (conditions.length > 0) {
      return db.select().from(priorAuthorizations).where(and(...conditions)).orderBy(desc(priorAuthorizations.createdAt));
    }
    return db.select().from(priorAuthorizations).orderBy(desc(priorAuthorizations.createdAt));
  }

  async getPriorAuthorization(id: number): Promise<PriorAuthorization | undefined> {
    const [auth] = await db.select().from(priorAuthorizations).where(eq(priorAuthorizations.id, id));
    return auth;
  }

  async createPriorAuthorization(data: InsertPriorAuthorization): Promise<PriorAuthorization> {
    const [auth] = await db.insert(priorAuthorizations).values(data).returning();
    return auth;
  }

  async updatePriorAuthorization(id: number, data: Partial<InsertPriorAuthorization>): Promise<PriorAuthorization | undefined> {
    const [auth] = await db
      .update(priorAuthorizations)
      .set({ ...data, updatedAt: new Date() })
      .where(eq(priorAuthorizations.id, id))
      .returning();
    return auth;
  }

  // Medical Consults
  async getMedicalConsults(patientId: number): Promise<MedicalConsult[]> {
    return db.select().from(medicalConsults).where(eq(medicalConsults.patientId, patientId)).orderBy(desc(medicalConsults.createdAt));
  }

  async createMedicalConsult(data: InsertMedicalConsult): Promise<MedicalConsult> {
    const [consult] = await db.insert(medicalConsults).values(data).returning();
    return consult;
  }

  async updateMedicalConsult(id: number, data: Partial<InsertMedicalConsult>): Promise<MedicalConsult | undefined> {
    const [consult] = await db.update(medicalConsults).set(data).where(eq(medicalConsults.id, id)).returning();
    return consult;
  }

  // Full Arch Exams
  async getPatientFullArchExams(patientId: number): Promise<FullArchExam[]> {
    return db.select().from(fullArchExams).where(eq(fullArchExams.patientId, patientId)).orderBy(desc(fullArchExams.createdAt));
  }

  async createFullArchExam(data: InsertFullArchExam): Promise<FullArchExam> {
    const [exam] = await db.insert(fullArchExams).values(data).returning();
    return exam;
  }

  async updateFullArchExam(id: number, data: Partial<InsertFullArchExam>): Promise<FullArchExam | undefined> {
    const [exam] = await db.update(fullArchExams).set(data).where(eq(fullArchExams.id, id)).returning();
    return exam;
  }

  // Follow-ups
  async getFollowUps(filters?: { patientId?: number; status?: string }): Promise<FollowUp[]> {
    const conditions = [];
    if (filters?.patientId) {
      conditions.push(eq(followUps.patientId, filters.patientId));
    }
    if (filters?.status) {
      conditions.push(eq(followUps.status, filters.status));
    }

    if (conditions.length > 0) {
      return db.select().from(followUps).where(and(...conditions)).orderBy(desc(followUps.createdAt));
    }
    return db.select().from(followUps).orderBy(desc(followUps.createdAt));
  }

  async createFollowUp(data: InsertFollowUp): Promise<FollowUp> {
    const [fu] = await db.insert(followUps).values(data).returning();
    return fu;
  }

  async updateFollowUp(id: number, data: Partial<InsertFollowUp>): Promise<FollowUp | undefined> {
    const [fu] = await db.update(followUps).set(data).where(eq(followUps.id, id)).returning();
    return fu;
  }

  // Care Reports
  async getCareReports(patientId: number): Promise<CareReport[]> {
    return db.select().from(careReports).where(eq(careReports.patientId, patientId)).orderBy(desc(careReports.createdAt));
  }

  async createCareReport(data: InsertCareReport): Promise<CareReport> {
    const [report] = await db.insert(careReports).values(data).returning();
    return report;
  }

  // Referring Providers
  async getReferringProviders(): Promise<ReferringProvider[]> {
    return db.select().from(referringProviders).orderBy(referringProviders.lastName);
  }

  async getReferringProvider(id: number): Promise<ReferringProvider | undefined> {
    const [provider] = await db.select().from(referringProviders).where(eq(referringProviders.id, id));
    return provider;
  }

  async createReferringProvider(data: InsertReferringProvider): Promise<ReferringProvider> {
    const [provider] = await db.insert(referringProviders).values(data).returning();
    return provider;
  }

  async updateReferringProvider(id: number, data: Partial<InsertReferringProvider>): Promise<ReferringProvider | undefined> {
    const [provider] = await db.update(referringProviders).set(data).where(eq(referringProviders.id, id)).returning();
    return provider;
  }
}

export const storage = new DatabaseStorage();
