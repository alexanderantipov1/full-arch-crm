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
  codeCrossReference,
  feeSchedules,
  generatedDocuments,
  appeals,
  eligibilityChecks,
  paymentPostings,
  trainingProgress,
  leads,
  leadActivities,
  treatmentPackages,
  appointmentReminders,
  patientCheckIns,
  financingPlans,
  medicalClearances,
  preSurgeryTasks,
  surgerySessions,
  labCases,
  postOpVisits,
  warrantyRecords,
  testimonials,
  maintenanceAppointments,
  auditLogs,
  consentForms,
  internalMessages,
  practiceSettings,
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
  type CodeCrossReference,
  type InsertCodeCrossReference,
  type FeeSchedule,
  type InsertFeeSchedule,
  type GeneratedDocument,
  type InsertGeneratedDocument,
  type Appeal,
  type InsertAppeal,
  type EligibilityCheck,
  type InsertEligibilityCheck,
  type PaymentPosting,
  type InsertPaymentPosting,
  type TrainingProgress,
  type InsertTrainingProgress,
  type Lead,
  type InsertLead,
  type LeadActivity,
  type InsertLeadActivity,
  type TreatmentPackage,
  type InsertTreatmentPackage,
  type AppointmentReminder,
  type InsertAppointmentReminder,
  type PatientCheckIn,
  type InsertPatientCheckIn,
  type FinancingPlan,
  type InsertFinancingPlan,
  type MedicalClearance,
  type InsertMedicalClearance,
  type PreSurgeryTask,
  type InsertPreSurgeryTask,
  type SurgerySession,
  type InsertSurgerySession,
  type LabCase,
  type InsertLabCase,
  type PostOpVisit,
  type InsertPostOpVisit,
  type WarrantyRecord,
  type InsertWarrantyRecord,
  type Testimonial,
  type InsertTestimonial,
  type MaintenanceAppointment,
  type InsertMaintenanceAppointment,
  type AuditLog,
  type InsertAuditLog,
  type ConsentForm,
  type InsertConsentForm,
  type InternalMessage,
  type InsertInternalMessage,
  type PracticeSettings,
  type InsertPracticeSettings,
  toothConditions,
  treatmentPlanProcedures,
  type ToothCondition,
  type InsertToothCondition,
  type TreatmentPlanProcedure,
  type InsertTreatmentPlanProcedure,
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
  
  // Coding Engine
  getCodeCrossReferences(): Promise<CodeCrossReference[]>;
  getCodeCrossReferenceByCDT(cdtCode: string): Promise<CodeCrossReference | undefined>;
  createCodeCrossReference(data: InsertCodeCrossReference): Promise<CodeCrossReference>;
  getFeeSchedules(payerName?: string): Promise<FeeSchedule[]>;
  createFeeSchedule(data: InsertFeeSchedule): Promise<FeeSchedule>;

  // Generated Documents
  getRecentGeneratedDocuments(limit: number): Promise<GeneratedDocument[]>;
  createGeneratedDocument(data: InsertGeneratedDocument): Promise<GeneratedDocument>;

  // Appeals
  getAppeals(): Promise<Appeal[]>;
  createAppeal(data: InsertAppeal): Promise<Appeal>;
  updateAppeal(id: number, data: Partial<InsertAppeal>): Promise<Appeal | undefined>;

  // Eligibility Checks
  getEligibilityChecks(): Promise<EligibilityCheck[]>;
  createEligibilityCheck(data: InsertEligibilityCheck): Promise<EligibilityCheck>;

  // Payment Postings
  getPaymentPostings(): Promise<PaymentPosting[]>;
  createPaymentPosting(data: InsertPaymentPosting): Promise<PaymentPosting>;
  updatePaymentPosting(id: number, data: Partial<InsertPaymentPosting>): Promise<PaymentPosting | undefined>;

  // Training Progress
  getTrainingProgress(userId: string): Promise<TrainingProgress[]>;
  createTrainingProgress(data: InsertTrainingProgress): Promise<TrainingProgress>;

  // Additional helpers
  getInsurance(patientId: number): Promise<Insurance[]>;
  getTreatmentPlansByPatient(patientId: number): Promise<TreatmentPlan[]>;

  // Patient Journey - Leads
  getLeads(): Promise<Lead[]>;
  getLead(id: number): Promise<Lead | undefined>;
  createLead(data: InsertLead): Promise<Lead>;
  updateLead(id: number, data: Partial<InsertLead>): Promise<Lead | undefined>;
  getLeadStats(): Promise<{ totalLeads: number; newLeads: number; qualifiedLeads: number; conversionRate: number }>;
  createLeadActivity(data: InsertLeadActivity): Promise<LeadActivity>;

  // Patient Journey - Treatment Packages
  getTreatmentPackages(): Promise<TreatmentPackage[]>;
  getTreatmentPackage(id: number): Promise<TreatmentPackage | undefined>;
  createTreatmentPackage(data: InsertTreatmentPackage): Promise<TreatmentPackage>;
  updateTreatmentPackage(id: number, data: Partial<InsertTreatmentPackage>): Promise<TreatmentPackage | undefined>;

  // Patient Journey - Appointment Reminders
  getAppointmentReminders(): Promise<AppointmentReminder[]>;
  createAppointmentReminder(data: InsertAppointmentReminder): Promise<AppointmentReminder>;
  updateAppointmentReminder(id: number, data: Partial<InsertAppointmentReminder>): Promise<AppointmentReminder | undefined>;

  // Patient Journey - Check-ins
  getPatientCheckIns(): Promise<PatientCheckIn[]>;
  createPatientCheckIn(data: InsertPatientCheckIn): Promise<PatientCheckIn>;
  updatePatientCheckIn(id: number, data: Partial<InsertPatientCheckIn>): Promise<PatientCheckIn | undefined>;

  // Patient Journey - Financing Plans
  getFinancingPlans(): Promise<FinancingPlan[]>;
  createFinancingPlan(data: InsertFinancingPlan): Promise<FinancingPlan>;
  updateFinancingPlan(id: number, data: Partial<InsertFinancingPlan>): Promise<FinancingPlan | undefined>;
  
  // Medical Clearances
  getMedicalClearances(): Promise<MedicalClearance[]>;
  getMedicalClearancesByPatient(patientId: number): Promise<MedicalClearance[]>;
  createMedicalClearance(data: InsertMedicalClearance): Promise<MedicalClearance>;
  updateMedicalClearance(id: number, data: Partial<InsertMedicalClearance>): Promise<MedicalClearance | undefined>;
  
  // Pre-Surgery Tasks
  getPreSurgeryTasks(): Promise<PreSurgeryTask[]>;
  getPreSurgeryTasksByPatient(patientId: number): Promise<PreSurgeryTask[]>;
  createPreSurgeryTask(data: InsertPreSurgeryTask): Promise<PreSurgeryTask>;
  updatePreSurgeryTask(id: number, data: Partial<InsertPreSurgeryTask>): Promise<PreSurgeryTask | undefined>;
  
  // Surgery Sessions
  getSurgerySessions(): Promise<SurgerySession[]>;
  getSurgerySession(id: number): Promise<SurgerySession | undefined>;
  createSurgerySession(data: InsertSurgerySession): Promise<SurgerySession>;
  updateSurgerySession(id: number, data: Partial<InsertSurgerySession>): Promise<SurgerySession | undefined>;
  
  // Lab Cases
  getLabCases(): Promise<LabCase[]>;
  createLabCase(data: InsertLabCase): Promise<LabCase>;
  updateLabCase(id: number, data: Partial<InsertLabCase>): Promise<LabCase | undefined>;
  
  // Post-Op Visits
  getPostOpVisits(): Promise<PostOpVisit[]>;
  createPostOpVisit(data: InsertPostOpVisit): Promise<PostOpVisit>;
  updatePostOpVisit(id: number, data: Partial<InsertPostOpVisit>): Promise<PostOpVisit | undefined>;
  
  // Warranty Records
  getWarrantyRecords(): Promise<WarrantyRecord[]>;
  createWarrantyRecord(data: InsertWarrantyRecord): Promise<WarrantyRecord>;
  updateWarrantyRecord(id: number, data: Partial<InsertWarrantyRecord>): Promise<WarrantyRecord | undefined>;
  
  // Testimonials
  getTestimonials(): Promise<Testimonial[]>;
  createTestimonial(data: InsertTestimonial): Promise<Testimonial>;
  updateTestimonial(id: number, data: Partial<InsertTestimonial>): Promise<Testimonial | undefined>;
  
  // Maintenance Appointments
  getMaintenanceAppointments(): Promise<MaintenanceAppointment[]>;
  createMaintenanceAppointment(data: InsertMaintenanceAppointment): Promise<MaintenanceAppointment>;
  updateMaintenanceAppointment(id: number, data: Partial<InsertMaintenanceAppointment>): Promise<MaintenanceAppointment | undefined>;
  
  // Consent Forms
  getConsentForms(): Promise<ConsentForm[]>;
  getConsentFormsByPatient(patientId: number): Promise<ConsentForm[]>;
  createConsentForm(data: InsertConsentForm): Promise<ConsentForm>;
  signConsentForm(id: number): Promise<ConsentForm | undefined>;

  // Patient Documents
  getDocuments(): Promise<PatientDocument[]>;
  getDocumentsByPatient(patientId: number): Promise<PatientDocument[]>;
  createDocument(data: InsertPatientDocument): Promise<PatientDocument>;
  deleteDocument(id: number): Promise<void>;

  // Internal Messages
  getInboxMessages(userId: string): Promise<InternalMessage[]>;
  getSentMessages(userId: string): Promise<InternalMessage[]>;
  createMessage(data: InsertInternalMessage): Promise<InternalMessage>;
  markMessageRead(id: number, userId: string): Promise<InternalMessage | undefined>;
  getUnreadCount(userId: string): Promise<number>;
  getAllUsers(): Promise<User[]>;

  // Practice Settings (Onboarding)
  getPracticeSettings(userId: string): Promise<PracticeSettings | undefined>;
  upsertPracticeSettings(data: Partial<InsertPracticeSettings> & { userId: string }): Promise<PracticeSettings>;

  // Tooth Conditions
  getToothConditions(patientId: number): Promise<ToothCondition[]>;
  createToothCondition(data: InsertToothCondition): Promise<ToothCondition>;
  updateToothCondition(id: number, data: Partial<InsertToothCondition>): Promise<ToothCondition | undefined>;
  deleteToothCondition(id: number): Promise<void>;

  // Treatment Plan Procedures
  getTreatmentPlanProcedures(treatmentPlanId: number): Promise<TreatmentPlanProcedure[]>;
  getPatientProcedures(patientId: number): Promise<TreatmentPlanProcedure[]>;
  createTreatmentPlanProcedure(data: InsertTreatmentPlanProcedure): Promise<TreatmentPlanProcedure>;
  updateTreatmentPlanProcedure(id: number, data: Partial<InsertTreatmentPlanProcedure>): Promise<TreatmentPlanProcedure | undefined>;
  deleteTreatmentPlanProcedure(id: number): Promise<void>;
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

  // Coding Engine
  async getCodeCrossReferences(): Promise<CodeCrossReference[]> {
    return db.select().from(codeCrossReference).orderBy(codeCrossReference.cdtCode);
  }

  async getCodeCrossReferenceByCDT(cdtCode: string): Promise<CodeCrossReference | undefined> {
    const [code] = await db.select().from(codeCrossReference).where(eq(codeCrossReference.cdtCode, cdtCode));
    return code;
  }

  async createCodeCrossReference(data: InsertCodeCrossReference): Promise<CodeCrossReference> {
    const [code] = await db.insert(codeCrossReference).values(data).returning();
    return code;
  }

  async getFeeSchedules(payerName?: string): Promise<FeeSchedule[]> {
    if (payerName) {
      return db.select().from(feeSchedules).where(eq(feeSchedules.payerName, payerName));
    }
    return db.select().from(feeSchedules).orderBy(feeSchedules.payerName);
  }

  async createFeeSchedule(data: InsertFeeSchedule): Promise<FeeSchedule> {
    const [schedule] = await db.insert(feeSchedules).values(data).returning();
    return schedule;
  }

  // Generated Documents
  async getRecentGeneratedDocuments(limit: number): Promise<GeneratedDocument[]> {
    return db.select().from(generatedDocuments).orderBy(desc(generatedDocuments.createdAt)).limit(limit);
  }

  async createGeneratedDocument(data: InsertGeneratedDocument): Promise<GeneratedDocument> {
    const [doc] = await db.insert(generatedDocuments).values(data).returning();
    return doc;
  }

  // Appeals
  async getAppeals(): Promise<Appeal[]> {
    return db.select().from(appeals).orderBy(desc(appeals.createdAt));
  }

  async createAppeal(data: InsertAppeal): Promise<Appeal> {
    const [appeal] = await db.insert(appeals).values(data).returning();
    return appeal;
  }

  async updateAppeal(id: number, data: Partial<InsertAppeal>): Promise<Appeal | undefined> {
    const [appeal] = await db.update(appeals).set({ ...data, updatedAt: new Date() }).where(eq(appeals.id, id)).returning();
    return appeal;
  }

  // Eligibility Checks
  async getEligibilityChecks(): Promise<EligibilityCheck[]> {
    return db.select().from(eligibilityChecks).orderBy(desc(eligibilityChecks.checkDate));
  }

  async createEligibilityCheck(data: InsertEligibilityCheck): Promise<EligibilityCheck> {
    const [check] = await db.insert(eligibilityChecks).values(data).returning();
    return check;
  }

  // Payment Postings
  async getPaymentPostings(): Promise<PaymentPosting[]> {
    return db.select().from(paymentPostings).orderBy(desc(paymentPostings.createdAt));
  }

  async createPaymentPosting(data: InsertPaymentPosting): Promise<PaymentPosting> {
    const [posting] = await db.insert(paymentPostings).values(data).returning();
    return posting;
  }

  async updatePaymentPosting(id: number, data: Partial<InsertPaymentPosting>): Promise<PaymentPosting | undefined> {
    const [posting] = await db.update(paymentPostings).set(data).where(eq(paymentPostings.id, id)).returning();
    return posting;
  }

  // Training Progress
  async getTrainingProgress(userId: string): Promise<TrainingProgress[]> {
    return db.select().from(trainingProgress).where(eq(trainingProgress.userId, userId));
  }

  async createTrainingProgress(data: InsertTrainingProgress): Promise<TrainingProgress> {
    const [progress] = await db.insert(trainingProgress).values(data).returning();
    return progress;
  }

  // Additional helpers
  async getInsurance(patientId: number): Promise<Insurance[]> {
    return db.select().from(insurance).where(eq(insurance.patientId, patientId));
  }

  async getTreatmentPlansByPatient(patientId: number): Promise<TreatmentPlan[]> {
    return db.select().from(treatmentPlans).where(eq(treatmentPlans.patientId, patientId));
  }

  // ============ PATIENT JOURNEY SYSTEM ============

  // Leads
  async getLeads(): Promise<Lead[]> {
    return db.select().from(leads).orderBy(desc(leads.createdAt));
  }

  async getLead(id: number): Promise<Lead | undefined> {
    const [lead] = await db.select().from(leads).where(eq(leads.id, id));
    return lead;
  }

  async createLead(data: InsertLead): Promise<Lead> {
    const [lead] = await db.insert(leads).values(data).returning();
    return lead;
  }

  async updateLead(id: number, data: Partial<InsertLead>): Promise<Lead | undefined> {
    const [lead] = await db.update(leads).set({ ...data, updatedAt: new Date() }).where(eq(leads.id, id)).returning();
    return lead;
  }

  async getLeadStats(): Promise<{ totalLeads: number; newLeads: number; qualifiedLeads: number; conversionRate: number }> {
    const allLeads = await db.select().from(leads);
    const totalLeads = allLeads.length;
    const newLeads = allLeads.filter(l => l.status === "new").length;
    const qualifiedLeads = allLeads.filter(l => l.status === "qualified").length;
    const convertedLeads = allLeads.filter(l => l.status === "converted" || l.convertedToPatientId).length;
    const conversionRate = totalLeads > 0 ? Math.round((convertedLeads / totalLeads) * 100) : 0;
    return { totalLeads, newLeads, qualifiedLeads, conversionRate };
  }

  // Lead Activities
  async getLeadActivities(leadId: number): Promise<LeadActivity[]> {
    return db.select().from(leadActivities).where(eq(leadActivities.leadId, leadId)).orderBy(desc(leadActivities.createdAt));
  }

  async createLeadActivity(data: InsertLeadActivity): Promise<LeadActivity> {
    const [activity] = await db.insert(leadActivities).values(data).returning();
    return activity;
  }

  // Treatment Packages
  async getTreatmentPackages(): Promise<TreatmentPackage[]> {
    return db.select().from(treatmentPackages).orderBy(treatmentPackages.displayOrder);
  }

  async getTreatmentPackage(id: number): Promise<TreatmentPackage | undefined> {
    const [pkg] = await db.select().from(treatmentPackages).where(eq(treatmentPackages.id, id));
    return pkg;
  }

  async createTreatmentPackage(data: InsertTreatmentPackage): Promise<TreatmentPackage> {
    const [pkg] = await db.insert(treatmentPackages).values(data).returning();
    return pkg;
  }

  async updateTreatmentPackage(id: number, data: Partial<InsertTreatmentPackage>): Promise<TreatmentPackage | undefined> {
    const [pkg] = await db.update(treatmentPackages).set(data).where(eq(treatmentPackages.id, id)).returning();
    return pkg;
  }

  // Appointment Reminders
  async getAppointmentReminders(): Promise<AppointmentReminder[]> {
    return db.select().from(appointmentReminders).orderBy(desc(appointmentReminders.createdAt));
  }

  async createAppointmentReminder(data: InsertAppointmentReminder): Promise<AppointmentReminder> {
    const [reminder] = await db.insert(appointmentReminders).values(data).returning();
    return reminder;
  }

  async updateAppointmentReminder(id: number, data: Partial<InsertAppointmentReminder>): Promise<AppointmentReminder | undefined> {
    const [reminder] = await db.update(appointmentReminders).set(data).where(eq(appointmentReminders.id, id)).returning();
    return reminder;
  }

  // Patient Check-ins
  async getPatientCheckIns(): Promise<PatientCheckIn[]> {
    return db.select().from(patientCheckIns).orderBy(desc(patientCheckIns.createdAt));
  }

  async createPatientCheckIn(data: InsertPatientCheckIn): Promise<PatientCheckIn> {
    const [checkIn] = await db.insert(patientCheckIns).values(data).returning();
    return checkIn;
  }

  async updatePatientCheckIn(id: number, data: Partial<InsertPatientCheckIn>): Promise<PatientCheckIn | undefined> {
    const [checkIn] = await db.update(patientCheckIns).set(data).where(eq(patientCheckIns.id, id)).returning();
    return checkIn;
  }

  // Financing Plans
  async getFinancingPlans(): Promise<FinancingPlan[]> {
    return db.select().from(financingPlans).orderBy(desc(financingPlans.createdAt));
  }

  async createFinancingPlan(data: InsertFinancingPlan): Promise<FinancingPlan> {
    const [plan] = await db.insert(financingPlans).values(data).returning();
    return plan;
  }

  async updateFinancingPlan(id: number, data: Partial<InsertFinancingPlan>): Promise<FinancingPlan | undefined> {
    const [plan] = await db.update(financingPlans).set(data).where(eq(financingPlans.id, id)).returning();
    return plan;
  }

  // Medical Clearances
  async getMedicalClearances(): Promise<MedicalClearance[]> {
    return db.select().from(medicalClearances).orderBy(desc(medicalClearances.requestedDate));
  }

  async getMedicalClearancesByPatient(patientId: number): Promise<MedicalClearance[]> {
    return db.select().from(medicalClearances).where(eq(medicalClearances.patientId, patientId)).orderBy(desc(medicalClearances.requestedDate));
  }

  async createMedicalClearance(data: InsertMedicalClearance): Promise<MedicalClearance> {
    const [clearance] = await db.insert(medicalClearances).values(data).returning();
    return clearance;
  }

  async updateMedicalClearance(id: number, data: Partial<InsertMedicalClearance>): Promise<MedicalClearance | undefined> {
    const [clearance] = await db.update(medicalClearances).set(data).where(eq(medicalClearances.id, id)).returning();
    return clearance;
  }

  // Pre-Surgery Tasks
  async getPreSurgeryTasks(): Promise<PreSurgeryTask[]> {
    return db.select().from(preSurgeryTasks).orderBy(desc(preSurgeryTasks.createdAt));
  }

  async getPreSurgeryTasksByPatient(patientId: number): Promise<PreSurgeryTask[]> {
    return db.select().from(preSurgeryTasks).where(eq(preSurgeryTasks.patientId, patientId)).orderBy(desc(preSurgeryTasks.createdAt));
  }

  async createPreSurgeryTask(data: InsertPreSurgeryTask): Promise<PreSurgeryTask> {
    const [task] = await db.insert(preSurgeryTasks).values(data).returning();
    return task;
  }

  async updatePreSurgeryTask(id: number, data: Partial<InsertPreSurgeryTask>): Promise<PreSurgeryTask | undefined> {
    const [task] = await db.update(preSurgeryTasks).set(data).where(eq(preSurgeryTasks.id, id)).returning();
    return task;
  }

  // Surgery Sessions
  async getSurgerySessions(): Promise<SurgerySession[]> {
    return db.select().from(surgerySessions).orderBy(desc(surgerySessions.surgeryDate));
  }

  async getSurgerySession(id: number): Promise<SurgerySession | undefined> {
    const [session] = await db.select().from(surgerySessions).where(eq(surgerySessions.id, id));
    return session;
  }

  async createSurgerySession(data: InsertSurgerySession): Promise<SurgerySession> {
    const [session] = await db.insert(surgerySessions).values(data).returning();
    return session;
  }

  async updateSurgerySession(id: number, data: Partial<InsertSurgerySession>): Promise<SurgerySession | undefined> {
    const [session] = await db.update(surgerySessions).set(data).where(eq(surgerySessions.id, id)).returning();
    return session;
  }

  // Lab Cases
  async getLabCases(): Promise<LabCase[]> {
    return db.select().from(labCases).orderBy(desc(labCases.createdAt));
  }

  async createLabCase(data: InsertLabCase): Promise<LabCase> {
    const [labCase] = await db.insert(labCases).values(data).returning();
    return labCase;
  }

  async updateLabCase(id: number, data: Partial<InsertLabCase>): Promise<LabCase | undefined> {
    const [labCase] = await db.update(labCases).set(data).where(eq(labCases.id, id)).returning();
    return labCase;
  }

  // Post-Op Visits
  async getPostOpVisits(): Promise<PostOpVisit[]> {
    return db.select().from(postOpVisits).orderBy(desc(postOpVisits.visitDate));
  }

  async createPostOpVisit(data: InsertPostOpVisit): Promise<PostOpVisit> {
    const [visit] = await db.insert(postOpVisits).values(data).returning();
    return visit;
  }

  async updatePostOpVisit(id: number, data: Partial<InsertPostOpVisit>): Promise<PostOpVisit | undefined> {
    const [visit] = await db.update(postOpVisits).set(data).where(eq(postOpVisits.id, id)).returning();
    return visit;
  }

  // Warranty Records
  async getWarrantyRecords(): Promise<WarrantyRecord[]> {
    return db.select().from(warrantyRecords).orderBy(desc(warrantyRecords.createdAt));
  }

  async createWarrantyRecord(data: InsertWarrantyRecord): Promise<WarrantyRecord> {
    const [record] = await db.insert(warrantyRecords).values(data).returning();
    return record;
  }

  async updateWarrantyRecord(id: number, data: Partial<InsertWarrantyRecord>): Promise<WarrantyRecord | undefined> {
    const [record] = await db.update(warrantyRecords).set(data).where(eq(warrantyRecords.id, id)).returning();
    return record;
  }

  // Testimonials
  async getTestimonials(): Promise<Testimonial[]> {
    return db.select().from(testimonials).orderBy(desc(testimonials.createdAt));
  }

  async createTestimonial(data: InsertTestimonial): Promise<Testimonial> {
    const [testimonial] = await db.insert(testimonials).values(data).returning();
    return testimonial;
  }

  async updateTestimonial(id: number, data: Partial<InsertTestimonial>): Promise<Testimonial | undefined> {
    const [testimonial] = await db.update(testimonials).set(data).where(eq(testimonials.id, id)).returning();
    return testimonial;
  }

  // Maintenance Appointments
  async getMaintenanceAppointments(): Promise<MaintenanceAppointment[]> {
    return db.select().from(maintenanceAppointments).orderBy(desc(maintenanceAppointments.scheduledDate));
  }

  async createMaintenanceAppointment(data: InsertMaintenanceAppointment): Promise<MaintenanceAppointment> {
    const [appointment] = await db.insert(maintenanceAppointments).values(data).returning();
    return appointment;
  }

  async updateMaintenanceAppointment(id: number, data: Partial<InsertMaintenanceAppointment>): Promise<MaintenanceAppointment | undefined> {
    const [appointment] = await db.update(maintenanceAppointments).set(data).where(eq(maintenanceAppointments.id, id)).returning();
    return appointment;
  }

  // Audit Logs
  async createAuditLog(data: InsertAuditLog): Promise<AuditLog> {
    const [log] = await db.insert(auditLogs).values(data).returning();
    return log;
  }

  async getAuditLogs(limit: number = 100, offset: number = 0): Promise<AuditLog[]> {
    return db.select().from(auditLogs).orderBy(desc(auditLogs.createdAt)).limit(limit).offset(offset);
  }

  async getAuditLogsByPatient(patientId: number): Promise<AuditLog[]> {
    return db.select().from(auditLogs).where(eq(auditLogs.patientId, patientId)).orderBy(desc(auditLogs.createdAt));
  }

  async getAuditLogsByUser(userId: string): Promise<AuditLog[]> {
    return db.select().from(auditLogs).where(eq(auditLogs.userId, userId)).orderBy(desc(auditLogs.createdAt));
  }

  // Consent Forms
  async getConsentForms(): Promise<ConsentForm[]> {
    return db.select().from(consentForms).orderBy(desc(consentForms.createdAt));
  }

  async getConsentFormsByPatient(patientId: number): Promise<ConsentForm[]> {
    return db.select().from(consentForms).where(eq(consentForms.patientId, patientId)).orderBy(desc(consentForms.createdAt));
  }

  async createConsentForm(data: InsertConsentForm): Promise<ConsentForm> {
    const [form] = await db.insert(consentForms).values(data).returning();
    return form;
  }

  async signConsentForm(id: number): Promise<ConsentForm | undefined> {
    const [form] = await db.update(consentForms).set({
      status: "signed",
      signedAt: new Date(),
    }).where(eq(consentForms.id, id)).returning();
    return form;
  }

  // Patient Documents
  async getDocuments(): Promise<PatientDocument[]> {
    return db.select().from(patientDocuments).orderBy(desc(patientDocuments.createdAt));
  }

  async getDocumentsByPatient(patientId: number): Promise<PatientDocument[]> {
    return db.select().from(patientDocuments).where(eq(patientDocuments.patientId, patientId)).orderBy(desc(patientDocuments.createdAt));
  }

  async createDocument(data: InsertPatientDocument): Promise<PatientDocument> {
    const [doc] = await db.insert(patientDocuments).values(data).returning();
    return doc;
  }

  async deleteDocument(id: number): Promise<void> {
    await db.delete(patientDocuments).where(eq(patientDocuments.id, id));
  }

  // Internal Messages
  async getInboxMessages(userId: string): Promise<InternalMessage[]> {
    return db.select().from(internalMessages).where(eq(internalMessages.recipientId, userId)).orderBy(desc(internalMessages.createdAt));
  }

  async getSentMessages(userId: string): Promise<InternalMessage[]> {
    return db.select().from(internalMessages).where(eq(internalMessages.senderId, userId)).orderBy(desc(internalMessages.createdAt));
  }

  async createMessage(data: InsertInternalMessage): Promise<InternalMessage> {
    const [message] = await db.insert(internalMessages).values(data).returning();
    return message;
  }

  async markMessageRead(id: number, userId: string): Promise<InternalMessage | undefined> {
    const [message] = await db.update(internalMessages).set({ isRead: true }).where(and(eq(internalMessages.id, id), eq(internalMessages.recipientId, userId))).returning();
    return message;
  }

  async getUnreadCount(userId: string): Promise<number> {
    const result = await db.select({ count: sql<number>`count(*)` }).from(internalMessages).where(and(eq(internalMessages.recipientId, userId), eq(internalMessages.isRead, false)));
    return result[0]?.count || 0;
  }

  async getAllUsers(): Promise<User[]> {
    return db.select().from(users).orderBy(users.firstName);
  }

  async getPracticeSettings(userId: string): Promise<PracticeSettings | undefined> {
    const [settings] = await db.select().from(practiceSettings).where(eq(practiceSettings.userId, userId));
    return settings;
  }

  async upsertPracticeSettings(data: Partial<InsertPracticeSettings> & { userId: string }): Promise<PracticeSettings> {
    const existing = await this.getPracticeSettings(data.userId);
    if (existing) {
      const [updated] = await db.update(practiceSettings)
        .set({ ...data, updatedAt: new Date() })
        .where(eq(practiceSettings.userId, data.userId))
        .returning();
      return updated;
    }
    const [created] = await db.insert(practiceSettings)
      .values({ practiceName: "My Practice", ...data } as InsertPracticeSettings)
      .returning();
    return created;
  }

  async getToothConditions(patientId: number): Promise<ToothCondition[]> {
    return db.select().from(toothConditions).where(eq(toothConditions.patientId, patientId)).orderBy(toothConditions.toothNumber);
  }

  async createToothCondition(data: InsertToothCondition): Promise<ToothCondition> {
    const [created] = await db.insert(toothConditions).values(data).returning();
    return created;
  }

  async updateToothCondition(id: number, data: Partial<InsertToothCondition>): Promise<ToothCondition | undefined> {
    const [updated] = await db.update(toothConditions).set(data).where(eq(toothConditions.id, id)).returning();
    return updated;
  }

  async deleteToothCondition(id: number): Promise<void> {
    await db.delete(toothConditions).where(eq(toothConditions.id, id));
  }

  async getTreatmentPlanProcedures(treatmentPlanId: number): Promise<TreatmentPlanProcedure[]> {
    return db.select().from(treatmentPlanProcedures).where(eq(treatmentPlanProcedures.treatmentPlanId, treatmentPlanId)).orderBy(treatmentPlanProcedures.priority);
  }

  async getPatientProcedures(patientId: number): Promise<TreatmentPlanProcedure[]> {
    return db.select().from(treatmentPlanProcedures).where(eq(treatmentPlanProcedures.patientId, patientId)).orderBy(treatmentPlanProcedures.priority);
  }

  async createTreatmentPlanProcedure(data: InsertTreatmentPlanProcedure): Promise<TreatmentPlanProcedure> {
    const [created] = await db.insert(treatmentPlanProcedures).values(data).returning();
    return created;
  }

  async updateTreatmentPlanProcedure(id: number, data: Partial<InsertTreatmentPlanProcedure>): Promise<TreatmentPlanProcedure | undefined> {
    const [updated] = await db.update(treatmentPlanProcedures).set(data).where(eq(treatmentPlanProcedures.id, id)).returning();
    return updated;
  }

  async deleteTreatmentPlanProcedure(id: number): Promise<void> {
    await db.delete(treatmentPlanProcedures).where(eq(treatmentPlanProcedures.id, id));
  }
}

export const storage = new DatabaseStorage();
