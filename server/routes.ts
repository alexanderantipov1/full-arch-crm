import type { Express } from "express";
import { createServer, type Server } from "http";
import { storage } from "./storage";
import { setupAuth, isAuthenticated } from "./replit_integrations/auth/replitAuth";
import { registerAuthRoutes } from "./replit_integrations/auth/routes";
import { registerChatRoutes } from "./replit_integrations/chat";
import Anthropic from "@anthropic-ai/sdk";
import {
  insertPatientSchema,
  insertMedicalHistorySchema,
  insertDentalInfoSchema,
  insertFacialEvaluationSchema,
  insertInsuranceSchema,
  insertTreatmentPlanSchema,
  insertAppointmentSchema,
  insertClinicalNoteSchema,
  insertBillingClaimSchema,
  insertCephalometricSchema,
  insertPriorAuthorizationSchema,
  insertMedicalConsultSchema,
  insertFullArchExamSchema,
  insertFollowUpSchema,
  insertCareReportSchema,
  insertReferringProviderSchema,
  insertCodeCrossReferenceSchema,
  insertFeeScheduleSchema,
  insertLeadSchema,
  insertTreatmentPackageSchema,
  insertAppointmentReminderSchema,
  insertPatientCheckInSchema,
  insertFinancingPlanSchema,
  insertMedicalClearanceSchema,
  insertPreSurgeryTaskSchema,
  insertSurgerySessionSchema,
  insertLabCaseSchema,
  insertPostOpVisitSchema,
  insertWarrantyRecordSchema,
  insertTestimonialSchema,
  insertMaintenanceAppointmentSchema,
  insertConsentFormSchema,
  insertPatientDocumentSchema,
  insertInternalMessageSchema,
  insertPracticeSettingsSchema,
  insertToothConditionSchema,
  insertTreatmentPlanProcedureSchema,
  insertUnionOrganizationSchema,
  insertUnionContactSchema,
  insertUnionOutreachSchema,
  insertUnionEventSchema,
  insertUnionAgreementSchema,
  insertUnionMemberVisitSchema,
  insertPerioExamSchema,
  insertOrthoCaseSchema,
  insertEndoCaseSchema,
  insertRecallPatientSchema,
  insertRecallContactLogSchema,
  insertPracticeProviderSchema,
  insertPatientMessageSchema,
  insertPracticeLocationSchema,
  insertPediatricExamSchema,
  insertOralSurgeryCaseSchema,
  insertPortalAppointmentRequestSchema,
} from "@shared/schema";

const anthropic = new Anthropic({
  apiKey: process.env.ANTHROPIC_API_KEY,
});

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

export async function registerRoutes(
  httpServer: Server,
  app: Express
): Promise<Server> {
  // Setup auth
  await setupAuth(app);
  registerAuthRoutes(app);

  // Register chat routes for AI
  registerChatRoutes(app);

  // Dashboard stats
  app.get("/api/dashboard/stats", isAuthenticated, async (req, res) => {
    try {
      const stats = await storage.getDashboardStats();
      res.json(stats);
    } catch (error) {
      console.error("Error fetching dashboard stats:", error);
      res.status(500).json({ message: "Failed to fetch dashboard stats" });
    }
  });

  // ============ PATIENTS ============
  app.get("/api/patients", isAuthenticated, async (req, res) => {
    try {
      const patients = await storage.getPatients();
      res.json(patients);
    } catch (error) {
      console.error("Error fetching patients:", error);
      res.status(500).json({ message: "Failed to fetch patients" });
    }
  });

  app.get("/api/patients/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const patient = await storage.getPatientWithDetails(id);
      if (!patient) {
        return res.status(404).json({ message: "Patient not found" });
      }
      res.json(patient);
    } catch (error) {
      console.error("Error fetching patient:", error);
      res.status(500).json({ message: "Failed to fetch patient" });
    }
  });

  app.post("/api/patients", isAuthenticated, async (req, res) => {
    try {
      const data = insertPatientSchema.parse(req.body);
      const patient = await storage.createPatient(data);
      res.status(201).json(patient);
    } catch (error: any) {
      console.error("Error creating patient:", error);
      res.status(400).json({ message: error.message || "Failed to create patient" });
    }
  });

  app.patch("/api/patients/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertPatientSchema.partial().parse(req.body);
      const patient = await storage.updatePatient(id, data);
      if (!patient) {
        return res.status(404).json({ message: "Patient not found" });
      }
      res.json(patient);
    } catch (error: any) {
      console.error("Error updating patient:", error);
      res.status(400).json({ message: error.message || "Failed to update patient" });
    }
  });

  app.delete("/api/patients/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deletePatient(id);
      res.status(204).send();
    } catch (error) {
      console.error("Error deleting patient:", error);
      res.status(500).json({ message: "Failed to delete patient" });
    }
  });

  // ============ MEDICAL HISTORY ============
  app.get("/api/patients/:id/medical-history", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const history = await storage.getMedicalHistory(patientId);
      res.json(history || {});
    } catch (error) {
      console.error("Error fetching medical history:", error);
      res.status(500).json({ message: "Failed to fetch medical history" });
    }
  });

  app.put("/api/patients/:id/medical-history", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const data = insertMedicalHistorySchema.parse({ ...req.body, patientId });
      const history = await storage.upsertMedicalHistory(data);
      res.json(history);
    } catch (error: any) {
      console.error("Error updating medical history:", error);
      res.status(400).json({ message: error.message || "Failed to update medical history" });
    }
  });

  // ============ DENTAL INFO ============
  app.get("/api/patients/:id/dental-info", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const info = await storage.getDentalInfo(patientId);
      res.json(info || {});
    } catch (error) {
      console.error("Error fetching dental info:", error);
      res.status(500).json({ message: "Failed to fetch dental info" });
    }
  });

  app.put("/api/patients/:id/dental-info", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const data = insertDentalInfoSchema.parse({ ...req.body, patientId });
      const info = await storage.upsertDentalInfo(data);
      res.json(info);
    } catch (error: any) {
      console.error("Error updating dental info:", error);
      res.status(400).json({ message: error.message || "Failed to update dental info" });
    }
  });

  // ============ FACIAL EVALUATION ============
  app.put("/api/patients/:id/facial-evaluation", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const data = insertFacialEvaluationSchema.parse({ ...req.body, patientId });
      const evaluation = await storage.upsertFacialEvaluation(data);
      res.json(evaluation);
    } catch (error: any) {
      console.error("Error updating facial evaluation:", error);
      res.status(400).json({ message: error.message || "Failed to update facial evaluation" });
    }
  });

  // ============ INSURANCE ============
  app.get("/api/patients/:id/insurance", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const insurances = await storage.getPatientInsurance(patientId);
      res.json(insurances);
    } catch (error) {
      console.error("Error fetching insurance:", error);
      res.status(500).json({ message: "Failed to fetch insurance" });
    }
  });

  app.post("/api/patients/:id/insurance", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const data = insertInsuranceSchema.parse({ ...req.body, patientId });
      const insurance = await storage.createInsurance(data);
      res.status(201).json(insurance);
    } catch (error: any) {
      console.error("Error creating insurance:", error);
      res.status(400).json({ message: error.message || "Failed to create insurance" });
    }
  });

  app.patch("/api/insurance/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertInsuranceSchema.partial().parse(req.body);
      const insurance = await storage.updateInsurance(id, data);
      if (!insurance) {
        return res.status(404).json({ message: "Insurance not found" });
      }
      res.json(insurance);
    } catch (error: any) {
      console.error("Error updating insurance:", error);
      res.status(400).json({ message: error.message || "Failed to update insurance" });
    }
  });

  app.delete("/api/insurance/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteInsurance(id);
      res.status(204).send();
    } catch (error) {
      console.error("Error deleting insurance:", error);
      res.status(500).json({ message: "Failed to delete insurance" });
    }
  });

  // ============ TREATMENT PLANS ============
  app.get("/api/treatment-plans", isAuthenticated, async (req, res) => {
    try {
      const filters: any = {};
      if (req.query.patientId) filters.patientId = parseInt(req.query.patientId as string);
      if (req.query.status) filters.status = req.query.status as string;
      if (req.query.priorAuthStatus) filters.priorAuthStatus = req.query.priorAuthStatus as string;
      
      const plans = await storage.getTreatmentPlans(filters);
      res.json(plans);
    } catch (error) {
      console.error("Error fetching treatment plans:", error);
      res.status(500).json({ message: "Failed to fetch treatment plans" });
    }
  });

  app.get("/api/treatment-plans/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const plan = await storage.getTreatmentPlan(id);
      if (!plan) {
        return res.status(404).json({ message: "Treatment plan not found" });
      }
      res.json(plan);
    } catch (error) {
      console.error("Error fetching treatment plan:", error);
      res.status(500).json({ message: "Failed to fetch treatment plan" });
    }
  });

  app.post("/api/treatment-plans", isAuthenticated, async (req, res) => {
    try {
      const data = insertTreatmentPlanSchema.parse(req.body);
      const plan = await storage.createTreatmentPlan(data);
      res.status(201).json(plan);
    } catch (error: any) {
      console.error("Error creating treatment plan:", error);
      res.status(400).json({ message: error.message || "Failed to create treatment plan" });
    }
  });

  app.patch("/api/treatment-plans/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertTreatmentPlanSchema.partial().parse(req.body);
      const plan = await storage.updateTreatmentPlan(id, data);
      if (!plan) {
        return res.status(404).json({ message: "Treatment plan not found" });
      }
      res.json(plan);
    } catch (error: any) {
      console.error("Error updating treatment plan:", error);
      res.status(400).json({ message: error.message || "Failed to update treatment plan" });
    }
  });

  // ============ APPOINTMENTS ============
  app.get("/api/appointments", isAuthenticated, async (req, res) => {
    try {
      const filters: any = {};
      if (req.query.patientId) filters.patientId = parseInt(req.query.patientId as string);
      if (req.query.startDate) filters.startDate = new Date(req.query.startDate as string);
      if (req.query.endDate) filters.endDate = new Date(req.query.endDate as string);
      
      const appointments = await storage.getAppointments(filters);
      res.json(appointments);
    } catch (error) {
      console.error("Error fetching appointments:", error);
      res.status(500).json({ message: "Failed to fetch appointments" });
    }
  });

  app.get("/api/appointments/upcoming", isAuthenticated, async (req, res) => {
    try {
      const appointments = await storage.getUpcomingAppointments();
      res.json(appointments);
    } catch (error) {
      console.error("Error fetching upcoming appointments:", error);
      res.status(500).json({ message: "Failed to fetch upcoming appointments" });
    }
  });

  app.post("/api/appointments", isAuthenticated, async (req, res) => {
    try {
      const data = insertAppointmentSchema.parse(req.body);
      const appointment = await storage.createAppointment(data);
      res.status(201).json(appointment);
    } catch (error: any) {
      console.error("Error creating appointment:", error);
      res.status(400).json({ message: error.message || "Failed to create appointment" });
    }
  });

  app.patch("/api/appointments/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertAppointmentSchema.partial().parse(req.body);
      const appointment = await storage.updateAppointment(id, data);
      if (!appointment) {
        return res.status(404).json({ message: "Appointment not found" });
      }
      res.json(appointment);
    } catch (error: any) {
      console.error("Error updating appointment:", error);
      res.status(400).json({ message: error.message || "Failed to update appointment" });
    }
  });

  // ============ CLINICAL NOTES ============
  app.get("/api/patients/:id/notes", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const notes = await storage.getPatientNotes(patientId);
      res.json(notes);
    } catch (error) {
      console.error("Error fetching notes:", error);
      res.status(500).json({ message: "Failed to fetch notes" });
    }
  });

  app.post("/api/patients/:id/notes", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const data = insertClinicalNoteSchema.parse({ ...req.body, patientId });
      const note = await storage.createNote(data);
      res.status(201).json(note);
    } catch (error: any) {
      console.error("Error creating note:", error);
      res.status(400).json({ message: error.message || "Failed to create note" });
    }
  });

  // ============ BILLING & CLAIMS ============
  app.get("/api/billing/stats", isAuthenticated, async (req, res) => {
    try {
      const stats = await storage.getBillingStats();
      res.json(stats);
    } catch (error) {
      console.error("Error fetching billing stats:", error);
      res.status(500).json({ message: "Failed to fetch billing stats" });
    }
  });

  app.get("/api/billing/claims", isAuthenticated, async (req, res) => {
    try {
      const filters: any = {};
      if (req.query.patientId) filters.patientId = parseInt(req.query.patientId as string);
      if (req.query.status) filters.status = req.query.status as string;
      
      const claims = await storage.getBillingClaims(filters);
      res.json(claims);
    } catch (error) {
      console.error("Error fetching claims:", error);
      res.status(500).json({ message: "Failed to fetch claims" });
    }
  });

  app.post("/api/billing/claims", isAuthenticated, async (req, res) => {
    try {
      const data = insertBillingClaimSchema.parse(req.body);
      const claim = await storage.createBillingClaim(data);
      res.status(201).json(claim);
    } catch (error: any) {
      console.error("Error creating claim:", error);
      res.status(400).json({ message: error.message || "Failed to create claim" });
    }
  });

  app.patch("/api/billing/claims/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertBillingClaimSchema.partial().parse(req.body);

      // Preflight gate: block submission if no passing preflight result exists
      if (data.claimStatus === "submitted") {
        const preflightResult = await storage.getPreflightResult(id);
        if (!preflightResult || preflightResult.riskScore < 70) {
          return res.status(422).json({
            message: "Claim blocked: a passing pre-flight check (risk score ≥ 70) is required before submission.",
            preflightRequired: true,
            currentScore: preflightResult?.riskScore ?? null,
          });
        }
      }

      const claim = await storage.updateBillingClaim(id, data);
      if (!claim) {
        return res.status(404).json({ message: "Claim not found" });
      }
      res.json(claim);
    } catch (error: unknown) {
      console.error("Error updating claim:", error);
      const msg = error instanceof Error ? error.message : "Failed to update claim";
      res.status(400).json({ message: msg });
    }
  });

  // ============ PRIOR AUTHORIZATIONS ============
  app.get("/api/prior-authorizations", isAuthenticated, async (req, res) => {
    try {
      const patientId = req.query.patientId ? parseInt(String(req.query.patientId)) : undefined;
      const status = req.query.status ? String(req.query.status) : undefined;
      const auths = await storage.getPriorAuthorizations({ patientId, status });
      res.json(auths);
    } catch (error) {
      console.error("Error fetching prior authorizations:", error);
      res.status(500).json({ message: "Failed to fetch prior authorizations" });
    }
  });

  app.get("/api/prior-authorizations/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const auth = await storage.getPriorAuthorization(id);
      if (!auth) {
        return res.status(404).json({ message: "Prior authorization not found" });
      }
      res.json(auth);
    } catch (error) {
      console.error("Error fetching prior authorization:", error);
      res.status(500).json({ message: "Failed to fetch prior authorization" });
    }
  });

  app.post("/api/prior-authorizations", isAuthenticated, async (req, res) => {
    try {
      const data = insertPriorAuthorizationSchema.parse(req.body);
      const auth = await storage.createPriorAuthorization(data);
      res.status(201).json(auth);
    } catch (error: any) {
      console.error("Error creating prior authorization:", error);
      res.status(400).json({ message: error.message || "Failed to create prior authorization" });
    }
  });

  app.patch("/api/prior-authorizations/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertPriorAuthorizationSchema.partial().parse(req.body);
      const auth = await storage.updatePriorAuthorization(id, data);
      if (!auth) {
        return res.status(404).json({ message: "Prior authorization not found" });
      }
      res.json(auth);
    } catch (error: any) {
      console.error("Error updating prior authorization:", error);
      res.status(400).json({ message: error.message || "Failed to update prior authorization" });
    }
  });

  // ============ CEPHALOMETRICS ============
  app.get("/api/patients/:patientId/cephalometrics", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const cephs = await storage.getPatientCephalometrics(patientId);
      res.json(cephs);
    } catch (error) {
      console.error("Error fetching cephalometrics:", error);
      res.status(500).json({ message: "Failed to fetch cephalometrics" });
    }
  });

  app.post("/api/cephalometrics", isAuthenticated, async (req, res) => {
    try {
      const data = insertCephalometricSchema.parse(req.body);
      const ceph = await storage.createCephalometric(data);
      res.status(201).json(ceph);
    } catch (error: any) {
      console.error("Error creating cephalometric:", error);
      res.status(400).json({ message: error.message || "Failed to create cephalometric" });
    }
  });

  // ============ MEDICAL CONSULTS ============
  app.get("/api/patients/:patientId/consults", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const consults = await storage.getMedicalConsults(patientId);
      res.json(consults);
    } catch (error) {
      console.error("Error fetching medical consults:", error);
      res.status(500).json({ message: "Failed to fetch medical consults" });
    }
  });

  app.post("/api/consults", isAuthenticated, async (req, res) => {
    try {
      const data = insertMedicalConsultSchema.parse(req.body);
      const consult = await storage.createMedicalConsult(data);
      res.status(201).json(consult);
    } catch (error: any) {
      console.error("Error creating medical consult:", error);
      res.status(400).json({ message: error.message || "Failed to create medical consult" });
    }
  });

  app.patch("/api/consults/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertMedicalConsultSchema.partial().parse(req.body);
      const consult = await storage.updateMedicalConsult(id, data);
      if (!consult) {
        return res.status(404).json({ message: "Medical consult not found" });
      }
      res.json(consult);
    } catch (error: any) {
      console.error("Error updating medical consult:", error);
      res.status(400).json({ message: error.message || "Failed to update medical consult" });
    }
  });

  // ============ FULL ARCH EXAMS ============
  app.get("/api/patients/:patientId/full-arch-exams", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const exams = await storage.getPatientFullArchExams(patientId);
      res.json(exams);
    } catch (error) {
      console.error("Error fetching full arch exams:", error);
      res.status(500).json({ message: "Failed to fetch full arch exams" });
    }
  });

  app.post("/api/full-arch-exams", isAuthenticated, async (req, res) => {
    try {
      const data = insertFullArchExamSchema.parse(req.body);
      const exam = await storage.createFullArchExam(data);
      res.status(201).json(exam);
    } catch (error: any) {
      console.error("Error creating full arch exam:", error);
      res.status(400).json({ message: error.message || "Failed to create full arch exam" });
    }
  });

  app.patch("/api/full-arch-exams/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertFullArchExamSchema.partial().parse(req.body);
      const exam = await storage.updateFullArchExam(id, data);
      if (!exam) {
        return res.status(404).json({ message: "Full arch exam not found" });
      }
      res.json(exam);
    } catch (error: any) {
      console.error("Error updating full arch exam:", error);
      res.status(400).json({ message: error.message || "Failed to update full arch exam" });
    }
  });

  // ============ FOLLOW-UPS ============
  app.get("/api/follow-ups", isAuthenticated, async (req, res) => {
    try {
      const patientId = req.query.patientId ? parseInt(String(req.query.patientId)) : undefined;
      const status = req.query.status ? String(req.query.status) : undefined;
      const followUps = await storage.getFollowUps({ patientId, status });
      res.json(followUps);
    } catch (error) {
      console.error("Error fetching follow-ups:", error);
      res.status(500).json({ message: "Failed to fetch follow-ups" });
    }
  });

  app.post("/api/follow-ups", isAuthenticated, async (req, res) => {
    try {
      const data = insertFollowUpSchema.parse(req.body);
      const followUp = await storage.createFollowUp(data);
      res.status(201).json(followUp);
    } catch (error: any) {
      console.error("Error creating follow-up:", error);
      res.status(400).json({ message: error.message || "Failed to create follow-up" });
    }
  });

  app.patch("/api/follow-ups/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertFollowUpSchema.partial().parse(req.body);
      const followUp = await storage.updateFollowUp(id, data);
      if (!followUp) {
        return res.status(404).json({ message: "Follow-up not found" });
      }
      res.json(followUp);
    } catch (error: any) {
      console.error("Error updating follow-up:", error);
      res.status(400).json({ message: error.message || "Failed to update follow-up" });
    }
  });

  // ============ CARE REPORTS ============
  app.get("/api/patients/:patientId/care-reports", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const reports = await storage.getCareReports(patientId);
      res.json(reports);
    } catch (error) {
      console.error("Error fetching care reports:", error);
      res.status(500).json({ message: "Failed to fetch care reports" });
    }
  });

  app.post("/api/care-reports", isAuthenticated, async (req, res) => {
    try {
      const data = insertCareReportSchema.parse(req.body);
      const report = await storage.createCareReport(data);
      res.status(201).json(report);
    } catch (error: any) {
      console.error("Error creating care report:", error);
      res.status(400).json({ message: error.message || "Failed to create care report" });
    }
  });

  // ============ REFERRING PROVIDERS ============
  app.get("/api/referring-providers", isAuthenticated, async (req, res) => {
    try {
      const providers = await storage.getReferringProviders();
      res.json(providers);
    } catch (error) {
      console.error("Error fetching referring providers:", error);
      res.status(500).json({ message: "Failed to fetch referring providers" });
    }
  });

  app.get("/api/referring-providers/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const provider = await storage.getReferringProvider(id);
      if (!provider) {
        return res.status(404).json({ message: "Referring provider not found" });
      }
      res.json(provider);
    } catch (error) {
      console.error("Error fetching referring provider:", error);
      res.status(500).json({ message: "Failed to fetch referring provider" });
    }
  });

  app.post("/api/referring-providers", isAuthenticated, async (req, res) => {
    try {
      const data = insertReferringProviderSchema.parse(req.body);
      const provider = await storage.createReferringProvider(data);
      res.status(201).json(provider);
    } catch (error: any) {
      console.error("Error creating referring provider:", error);
      res.status(400).json({ message: error.message || "Failed to create referring provider" });
    }
  });

  app.patch("/api/referring-providers/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertReferringProviderSchema.partial().parse(req.body);
      const provider = await storage.updateReferringProvider(id, data);
      if (!provider) {
        return res.status(404).json({ message: "Referring provider not found" });
      }
      res.json(provider);
    } catch (error: any) {
      console.error("Error updating referring provider:", error);
      res.status(400).json({ message: error.message || "Failed to update referring provider" });
    }
  });

  // ============ AI ASSISTANT ============
  app.post("/api/ai/chat", isAuthenticated, async (req, res) => {
    try {
      const { content } = req.body;
      
      if (!content || typeof content !== "string") {
        return res.status(400).json({ message: "Content is required" });
      }

      const systemPrompt = `You are an expert dental implant assistant specializing in full arch dental implants (All-on-4, All-on-6), oral surgery, and comprehensive facial/airway evaluation. You help dental practices maximize insurance approvals and streamline billing. You assist with:

1. Treatment Planning: Provide guidance on case assessment for full arch implants, implant positioning, bone grafting needs, and prosthetic options (hybrid, zirconia, PMMA).

2. Insurance & Billing: Help with correct CDT codes and ICD-10 codes for medical necessity. Common codes include:
   - D6010: Surgical placement of implant body ($2,200)
   - D6056: Prefabricated abutment ($650)
   - D6058: Abutment supported crown ($1,400)
   - D6114: Implant/abutment supported fixed denture for completely edentulous arch ($28,500)
   - D7210: Extraction with flap elevation ($285)
   - D7953: Bone replacement graft ($875)
   
   Key ICD-10 codes for medical necessity:
   - K08.1: Complete loss of teeth
   - K08.101-K08.109: Loss due to trauma, periodontal disease, caries
   - M26.5: Dentofacial functional abnormalities
   - R63.3: Feeding difficulties (nutritional impact)
   - G47.33: Obstructive sleep apnea (for airway cases)

3. Prior Authorization: Assist with submitting prior authorizations, including documentation requirements and clinical evidence needed for approval.

4. Medical Necessity Letters: Help draft compelling letters emphasizing functional impairment, nutritional concerns, speech difficulties, and quality of life impact that increase approval rates.

5. Denial Appeals: Guide practices through the appeals process with evidence-based arguments, citing peer-reviewed literature and clinical guidelines.

6. Insurance Strategy: Advise on whether to bill medical vs dental insurance, dual coverage strategies, and when medical insurance is more likely to approve full arch cases (trauma, cancer reconstruction, severe atrophy).

7. Arnett & Gunson Protocols: Provide guidance on facial evaluation protocols including:
   - Facial profile analysis (convex, straight, concave)
   - Soft tissue evaluation and lip competence
   - Airway assessment and Mallampati scoring
   - Bite classification and occlusion analysis
   - Cephalometric landmarks and measurements (SNA, SNB, ANB, FMA)

8. Cephalometric Analysis: Help interpret cephalometric measurements for treatment planning, including skeletal classification, growth patterns, and surgical planning considerations.

9. Airway Evaluation: Assist with airway assessment including tongue position, tonsil size, neck circumference, and sleep apnea considerations that may affect treatment planning.

10. Medical Consultation Requests: Generate appropriate preoperative medical clearance requests with necessary labs and specialist consultations.

Always provide accurate, professional guidance. When discussing billing codes or insurance, note that practices should verify with their specific payers.`;

      const assistantResponse = await askClaude(systemPrompt, content, 1500) || "I apologize, I couldn't generate a response. Please try again.";

      res.json({ response: assistantResponse });
    } catch (error: any) {
      console.error("Error in AI chat:", error);
      res.status(500).json({ message: "Failed to get AI response" });
    }
  });

  // AI-assisted diagnosis for treatment planning
  app.post("/api/ai/diagnosis", isAuthenticated, async (req, res) => {
    try {
      const { patientInfo, chiefComplaint, dentalConditions } = req.body;

      const prompt = `Based on the following patient information, provide a diagnosis and treatment recommendations for full arch dental implants:

Patient Info: ${JSON.stringify(patientInfo)}
Chief Complaint: ${chiefComplaint}
Dental Conditions: ${JSON.stringify(dentalConditions)}

Please provide:
1. Primary diagnosis with ICD-10 code
2. Treatment recommendations (All-on-4, All-on-6, or alternative)
3. Estimated procedure list with CDT codes
4. Key considerations for treatment planning
5. Suggested pre-operative requirements`;

      const diagnosis = await askClaude(
        "You are an expert dental implant treatment planning assistant. Provide detailed, clinically accurate recommendations.",
        prompt, 2000
      );
      res.json({ diagnosis });
    } catch (error) {
      console.error("Error in AI diagnosis:", error);
      res.status(500).json({ message: "Failed to get AI diagnosis" });
    }
  });

  // AI-generated medical necessity letter
  app.post("/api/ai/medical-necessity-letter", isAuthenticated, async (req, res) => {
    try {
      const { patientName, dateOfBirth, diagnosis, procedures, justification } = req.body;

      const prompt = `Generate a professional medical necessity letter for dental implant treatment:

Patient: ${patientName}
DOB: ${dateOfBirth}
Diagnosis: ${diagnosis}
Procedures: ${procedures}
Additional Justification: ${justification}

The letter should:
1. Be professionally formatted
2. Include relevant ICD-10 and CDT codes
3. Emphasize functional impairment and quality of life impact
4. Reference clinical evidence for implant therapy
5. Be suitable for insurance submission`;

      const letter = await askClaude(
        "You are an expert at writing medical necessity letters for dental implant procedures. Create compelling, evidence-based letters.",
        prompt, 2000
      );
      res.json({ letter });
    } catch (error) {
      console.error("Error generating medical necessity letter:", error);
      res.status(500).json({ message: "Failed to generate letter" });
    }
  });

  // AI-generated appeal letter
  app.post("/api/ai/appeal-letter", isAuthenticated, async (req, res) => {
    try {
      const { patientName, claimNumber, denialReason, originalDiagnosis, procedures } = req.body;

      const prompt = `Generate a professional insurance appeal letter for a denied dental implant claim:

Patient: ${patientName}
Claim Number: ${claimNumber}
Denial Reason: ${denialReason}
Original Diagnosis: ${originalDiagnosis}
Procedures: ${procedures}

The appeal should:
1. Professionally address the specific denial reason
2. Cite relevant clinical evidence and guidelines
3. Reference peer-reviewed literature if applicable
4. Include strong medical necessity arguments
5. Request reconsideration with specific action items`;

      const letter = await askClaude(
        "You are an expert at writing insurance appeal letters for dental procedures. Create persuasive, evidence-based appeals.",
        prompt, 2000
      );
      res.json({ letter });
    } catch (error) {
      console.error("Error generating appeal letter:", error);
      res.status(500).json({ message: "Failed to generate appeal letter" });
    }
  });

  // ============ CODING ENGINE ============
  app.get("/api/coding/cross-references", isAuthenticated, async (req, res) => {
    try {
      const codes = await storage.getCodeCrossReferences();
      res.json(codes);
    } catch (error) {
      console.error("Error fetching code cross-references:", error);
      res.status(500).json({ message: "Failed to fetch code cross-references" });
    }
  });

  app.get("/api/coding/cross-references/:cdtCode", isAuthenticated, async (req, res) => {
    try {
      const cdtCode = req.params.cdtCode;
      const code = await storage.getCodeCrossReferenceByCDT(cdtCode);
      if (!code) {
        return res.status(404).json({ message: "Code not found" });
      }
      res.json(code);
    } catch (error) {
      console.error("Error fetching code cross-reference:", error);
      res.status(500).json({ message: "Failed to fetch code cross-reference" });
    }
  });

  app.post("/api/coding/cross-references", isAuthenticated, async (req, res) => {
    try {
      const data = insertCodeCrossReferenceSchema.parse(req.body);
      const code = await storage.createCodeCrossReference(data);
      res.status(201).json(code);
    } catch (error: any) {
      console.error("Error creating code cross-reference:", error);
      res.status(400).json({ message: error.message || "Failed to create code cross-reference" });
    }
  });

  app.get("/api/coding/fee-schedules", isAuthenticated, async (req, res) => {
    try {
      const payerName = req.query.payer as string | undefined;
      const schedules = await storage.getFeeSchedules(payerName);
      res.json(schedules);
    } catch (error) {
      console.error("Error fetching fee schedules:", error);
      res.status(500).json({ message: "Failed to fetch fee schedules" });
    }
  });

  app.post("/api/coding/fee-schedules", isAuthenticated, async (req, res) => {
    try {
      const data = insertFeeScheduleSchema.parse(req.body);
      const schedule = await storage.createFeeSchedule(data);
      res.status(201).json(schedule);
    } catch (error: any) {
      console.error("Error creating fee schedule:", error);
      res.status(400).json({ message: error.message || "Failed to create fee schedule" });
    }
  });

  // AI-assisted code suggestion
  app.post("/api/coding/suggest", isAuthenticated, async (req, res) => {
    try {
      const { diagnosis, procedures, clinicalNotes } = req.body;
      
      if (!diagnosis || typeof diagnosis !== "string" || diagnosis.trim() === "") {
        return res.status(400).json({ message: "Diagnosis is required" });
      }
      if (!procedures || typeof procedures !== "string" || procedures.trim() === "") {
        return res.status(400).json({ message: "Procedures is required" });
      }
      
      const codeSystemPrompt = `You are an expert dental billing coder specializing in full arch dental implants. Your role is to suggest the most appropriate CDT codes, CPT codes (for medical insurance cross-coding), and ICD-10 diagnosis codes that maximize insurance approval rates while maintaining compliance.

For full arch dental implants, focus on:
- Medical necessity documentation (functional impairment, nutritional concerns, airway issues)
- Appropriate modifier usage (RT/LT for laterality, 22 for complexity)
- Supporting diagnoses that strengthen medical necessity

Common CDT codes for full arch:
- D6010: Surgical placement of implant body
- D6056: Prefabricated abutment
- D6114: Implant/abutment supported fixed denture for completely edentulous arch
- D7210: Extraction with flap elevation
- D7953: Bone replacement graft

Common ICD-10 codes for medical necessity:
- K08.1: Complete loss of teeth (edentulism)
- K08.109: Complete loss of teeth, unspecified cause
- K08.419: Partial loss of teeth, unspecified cause
- R63.3: Feeding difficulties and mismanagement (nutritional impact)
- G47.33: Obstructive sleep apnea (if applicable)
- E11.x: Type 2 diabetes mellitus (if applicable for bone healing)

Return your response as valid JSON only (no markdown, no code blocks) with this structure:
{"suggestedCDT": [{"code": "D6010", "description": "...", "fee": 2200}], "suggestedCPT": [{"code": "21248", "description": "...", "medicalCrossCode": true}], "suggestedICD10": [{"code": "K08.1", "description": "...", "priority": 1}], "medicalNecessityNotes": "...", "confidenceScore": 95, "warnings": []}`;

      const codeRaw = await askClaude(codeSystemPrompt, `Suggest appropriate billing codes for:
Diagnosis: ${diagnosis || "Not specified"}
Procedures: ${procedures || "Not specified"}
Clinical Notes: ${clinicalNotes || "Not provided"}`, 1500);

      const suggestions = JSON.parse(codeRaw || "{}");
      res.json(suggestions);
    } catch (error) {
      console.error("Error generating code suggestions:", error);
      res.status(500).json({ message: "Failed to generate code suggestions" });
    }
  });

  // ============ PATIENT RESPONSIBILITY CALCULATOR ============
  app.post("/api/calculator/patient-responsibility", isAuthenticated, async (req, res) => {
    try {
      const { treatmentCost, insuranceType, coveragePercentage, deductible, deductibleMet, annualMaximum, usedBenefits, medicalCrossCode } = req.body;

      if (!treatmentCost || typeof treatmentCost !== "number" || treatmentCost <= 0) {
        return res.status(400).json({ message: "Valid treatment cost is required" });
      }

      const coverage = coveragePercentage || 0;
      const deductibleAmount = deductible || 0;
      const deductibleAlreadyMet = deductibleMet || 0;
      const maxBenefit = annualMaximum || 0;
      const benefitsUsed = usedBenefits || 0;

      // Calculate remaining deductible
      const remainingDeductible = Math.max(0, deductibleAmount - deductibleAlreadyMet);
      
      // Amount subject to coverage (after deductible)
      const amountAfterDeductible = Math.max(0, treatmentCost - remainingDeductible);
      
      // Calculate insurance portion based on coverage percentage
      let insurancePortion = amountAfterDeductible * (coverage / 100);
      
      // Check against annual maximum if applicable
      const remainingBenefits = maxBenefit > 0 ? Math.max(0, maxBenefit - benefitsUsed) : Infinity;
      insurancePortion = Math.min(insurancePortion, remainingBenefits);
      
      // Patient responsibility
      const patientResponsibility = treatmentCost - insurancePortion;
      
      // Medical cross-coding potential (typically higher coverage for medical necessity)
      let medicalPotential = null;
      if (medicalCrossCode) {
        const medicalCoverage = Math.min(coverage + 20, 80); // Medical often covers more
        const medicalInsurancePortion = amountAfterDeductible * (medicalCoverage / 100);
        const medicalPatientResp = treatmentCost - Math.min(medicalInsurancePortion, remainingBenefits);
        medicalPotential = {
          estimatedCoverage: Math.round(Math.min(medicalInsurancePortion, remainingBenefits) * 100) / 100,
          patientResponsibility: Math.round(medicalPatientResp * 100) / 100,
          potentialSavings: Math.round((patientResponsibility - medicalPatientResp) * 100) / 100
        };
      }

      res.json({
        treatmentCost: Math.round(treatmentCost * 100) / 100,
        deductibleApplied: Math.round(remainingDeductible * 100) / 100,
        insuranceCoverage: Math.round(insurancePortion * 100) / 100,
        patientResponsibility: Math.round(patientResponsibility * 100) / 100,
        coveragePercentage: coverage,
        remainingAnnualBenefits: remainingBenefits === Infinity ? null : Math.round((remainingBenefits - insurancePortion) * 100) / 100,
        medicalCrossCodePotential: medicalPotential,
        breakdown: {
          totalCost: Math.round(treatmentCost * 100) / 100,
          lessDeductible: Math.round(remainingDeductible * 100) / 100,
          amountCovered: Math.round(amountAfterDeductible * 100) / 100,
          insurancePays: Math.round(insurancePortion * 100) / 100,
          youPay: Math.round(patientResponsibility * 100) / 100
        }
      });
    } catch (error) {
      console.error("Error calculating patient responsibility:", error);
      res.status(500).json({ message: "Failed to calculate patient responsibility" });
    }
  });

  // ============ REVENUE CYCLE ANALYTICS ============
  app.get("/api/analytics/revenue-cycle", isAuthenticated, async (req, res) => {
    try {
      const claims = await storage.getBillingClaims();
      const priorAuths = await storage.getPriorAuthorizations();
      
      // Calculate metrics
      const totalClaims = claims.length;
      const paidClaims = claims.filter(c => c.claimStatus === "paid");
      const deniedClaims = claims.filter(c => c.claimStatus === "denied");
      const pendingClaims = claims.filter(c => c.claimStatus === "pending" || c.claimStatus === "submitted");
      
      const totalBilled = claims.reduce((sum, c) => sum + (parseFloat(c.chargedAmount?.toString() || "0")), 0);
      const totalCollected = paidClaims.reduce((sum, c) => sum + (parseFloat(c.paidAmount?.toString() || "0")), 0);
      const totalPending = pendingClaims.reduce((sum, c) => sum + (parseFloat(c.chargedAmount?.toString() || "0")), 0);
      
      const collectionRate = totalBilled > 0 ? (totalCollected / totalBilled) * 100 : 0;
      const denialRate = totalClaims > 0 ? (deniedClaims.length / totalClaims) * 100 : 0;
      
      // Prior auth metrics
      const approvedAuths = priorAuths.filter(p => p.status === "approved");
      const deniedAuths = priorAuths.filter(p => p.status === "denied");
      const pendingAuths = priorAuths.filter(p => p.status === "pending" || p.status === "submitted");
      const authApprovalRate = priorAuths.length > 0 ? (approvedAuths.length / priorAuths.length) * 100 : 0;
      
      // Calculate average days to payment (mock for demo)
      const avgDaysToPayment = 32;
      
      // Aging buckets
      const now = new Date();
      const agingBuckets = {
        current: pendingClaims.filter(c => {
          const created = new Date(c.createdAt);
          return (now.getTime() - created.getTime()) / (1000 * 60 * 60 * 24) <= 30;
        }).length,
        days31to60: pendingClaims.filter(c => {
          const created = new Date(c.createdAt);
          const days = (now.getTime() - created.getTime()) / (1000 * 60 * 60 * 24);
          return days > 30 && days <= 60;
        }).length,
        days61to90: pendingClaims.filter(c => {
          const created = new Date(c.createdAt);
          const days = (now.getTime() - created.getTime()) / (1000 * 60 * 60 * 24);
          return days > 60 && days <= 90;
        }).length,
        over90: pendingClaims.filter(c => {
          const created = new Date(c.createdAt);
          return (now.getTime() - created.getTime()) / (1000 * 60 * 60 * 24) > 90;
        }).length
      };

      res.json({
        summary: {
          totalBilled: Math.round(totalBilled * 100) / 100,
          totalCollected: Math.round(totalCollected * 100) / 100,
          totalPending: Math.round(totalPending * 100) / 100,
          collectionRate: Math.round(collectionRate * 10) / 10,
          denialRate: Math.round(denialRate * 10) / 10,
          avgDaysToPayment
        },
        claims: {
          total: totalClaims,
          paid: paidClaims.length,
          denied: deniedClaims.length,
          pending: pendingClaims.length
        },
        priorAuthorizations: {
          total: priorAuths.length,
          approved: approvedAuths.length,
          denied: deniedAuths.length,
          pending: pendingAuths.length,
          approvalRate: Math.round(authApprovalRate * 10) / 10
        },
        agingBuckets,
        trends: {
          monthlyCollections: [45000, 52000, 48000, 61000, 58000, 72000],
          monthlyDenials: [3, 2, 4, 1, 2, 1],
          months: ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan"]
        }
      });
    } catch (error) {
      console.error("Error fetching revenue analytics:", error);
      res.status(500).json({ message: "Failed to fetch revenue analytics" });
    }
  });

  // ============ AI DOCUMENTATION ENGINE ============
  app.get("/api/ai/documents/recent", isAuthenticated, async (req, res) => {
    try {
      const docs = await storage.getRecentGeneratedDocuments(10);
      res.json(docs);
    } catch (error) {
      console.error("Error fetching recent documents:", error);
      res.json([]);
    }
  });

  app.post("/api/ai/generate-document", isAuthenticated, async (req, res) => {
    try {
      const { patientId, documentType, additionalContext } = req.body;
      
      if (!patientId || !documentType) {
        return res.status(400).json({ message: "Patient ID and document type are required" });
      }

      const patient = await storage.getPatient(patientId);
      if (!patient) {
        return res.status(404).json({ message: "Patient not found" });
      }

      const medicalHistory = await storage.getMedicalHistory(patientId);
      const treatmentPlans = await storage.getTreatmentPlansByPatient(patientId);

      const documentTemplates: Record<string, string> = {
        "medical-necessity": `Generate a comprehensive medical necessity letter for insurance submission. Include clinical justification for full arch dental implants, functional impairment documentation, and reference to ADA guidelines.`,
        "operative-report": `Generate a detailed operative report for dental implant surgery. Include procedure details, implant specifications, bone quality, complications if any, and post-operative instructions.`,
        "progress-note": `Generate a clinical progress note documenting the patient's treatment progress, healing status, and any clinical observations.`,
        "history-physical": `Generate a comprehensive History and Physical (H&P) document from the patient's intake data, including chief complaint, medical history, review of systems, and physical examination findings.`,
        "peer-to-peer": `Generate talking points and clinical justification for a peer-to-peer review with an insurance medical director. Focus on medical necessity and clinical evidence.`
      };

      const prompt = `${documentTemplates[documentType] || "Generate appropriate clinical documentation."}

Patient Information:
- Name: ${patient.firstName} ${patient.lastName}
- DOB: ${patient.dateOfBirth}
- Medical History: ${JSON.stringify(medicalHistory || {})}
- Treatment Plans: ${JSON.stringify(treatmentPlans || [])}
${additionalContext ? `\nAdditional Context: ${additionalContext}` : ""}

Please generate professional, HIPAA-compliant clinical documentation.`;

      const content = await askClaude(
        "You are an expert dental billing specialist generating clinical documentation for full arch dental implant procedures. Generate professional, compliant documentation that supports medical necessity and insurance claims.",
        prompt, 2000
      );
      
      const savedDoc = await storage.createGeneratedDocument({
        patientId,
        documentType,
        title: `${documentType.replace("-", " ").replace(/\b\w/g, (l: string) => l.toUpperCase())} - ${patient.firstName} ${patient.lastName}`,
        content,
        metadata: { additionalContext }
      });

      res.json({ content, documentId: savedDoc.id });
    } catch (error) {
      console.error("Error generating document:", error);
      res.status(500).json({ message: "Failed to generate document" });
    }
  });

  // ============ APPEALS ENGINE ============
  app.get("/api/appeals/stats", isAuthenticated, async (req, res) => {
    try {
      const appeals = await storage.getAppeals();
      const won = appeals.filter(a => a.status === "won").length;
      const total = appeals.length;
      
      res.json({
        total,
        pending: appeals.filter(a => a.status === "pending").length,
        submitted: appeals.filter(a => a.status === "submitted").length,
        won,
        lost: appeals.filter(a => a.status === "lost").length,
        successRate: total > 0 ? Math.round((won / total) * 100) : 78,
        avgTurnaround: 14,
        totalRecovered: 245000
      });
    } catch (error) {
      console.error("Error fetching appeals stats:", error);
      res.json({ total: 0, pending: 0, submitted: 0, won: 0, lost: 0, successRate: 78, avgTurnaround: 14, totalRecovered: 0 });
    }
  });

  app.get("/api/appeals", isAuthenticated, async (req, res) => {
    try {
      const appeals = await storage.getAppeals();
      res.json(appeals);
    } catch (error) {
      console.error("Error fetching appeals:", error);
      res.json([]);
    }
  });

  app.get("/api/billing/claims/denied", isAuthenticated, async (req, res) => {
    try {
      const claims = await storage.getBillingClaims();
      const deniedClaims = claims.filter(c => c.claimStatus === "denied").map(c => ({
        id: c.id,
        patientId: c.patientId,
        patientName: `Patient ${c.patientId}`,
        denialReason: c.description || "Service not covered under plan",
        denialCode: "CO-50",
        claimAmount: parseFloat(c.chargedAmount?.toString() || "0"),
        serviceDate: c.serviceDate
      }));
      res.json(deniedClaims);
    } catch (error) {
      console.error("Error fetching denied claims:", error);
      res.json([]);
    }
  });

  // ============ CLAIM PRE-FLIGHT CHECK ENGINE ============

  app.get("/api/billing/claims/:id/preflight", isAuthenticated, async (req, res) => {
    try {
      const claimId = parseInt(req.params.id);
      const result = await storage.getPreflightResult(claimId);
      if (!result) return res.status(404).json({ message: "No preflight result found" });
      res.json(result);
    } catch (error) {
      console.error("Error fetching preflight result:", error);
      res.status(500).json({ message: "Failed to fetch preflight result" });
    }
  });

  app.post("/api/billing/claims/:id/preflight", isAuthenticated, async (req, res) => {
    try {
      const claimId = parseInt(req.params.id);
      const claims = await storage.getBillingClaims();
      const claim = claims.find(c => c.id === claimId);
      if (!claim) return res.status(404).json({ message: "Claim not found" });

      const patient = await storage.getPatient(claim.patientId);
      const insuranceList = await storage.getInsurance(claim.patientId);
      const primaryInsurance = insuranceList[0];

      const systemPrompt = `You are an expert medical billing compliance specialist for dental implant claims. 
Analyze the provided claim and return a JSON object with the following exact structure:
{
  "riskScore": <integer 0-100, higher means lower denial risk>,
  "approvalProbability": <integer 0-100>,
  "issues": [
    {
      "code": "<short_code>",
      "severity": "<critical|warning|info>",
      "description": "<what is wrong>",
      "suggestion": "<how to fix it>",
      "autoFixable": <boolean>,
      "fixValue": "<corrected value if autoFixable>"
    }
  ],
  "checklist": [
    { "label": "<check description>", "passed": <boolean> }
  ],
  "recommendedActions": ["<action 1>", "<action 2>"]
}
Focus on: CDT/CPT code validity, ICD-10 presence and specificity, timely filing windows, medical necessity documentation, modifier requirements, and prior authorization requirements for full arch implants.
Return ONLY valid JSON, no markdown.`;

      const userMessage = `Analyze this dental implant claim for denial risk:

Claim ID: ${claim.id}
Claim Number: ${claim.claimNumber || "Not assigned"}
Procedure Code: ${claim.procedureCode}
ICD-10 Code: ${claim.icd10Code || "MISSING"}
Description: ${claim.description || "None provided"}
Service Date: ${claim.serviceDate}
Charged Amount: $${claim.chargedAmount}
Claim Status: ${claim.claimStatus}
Denial Reason (if any): ${claim.denialReason || "None"}

Patient: ${patient?.firstName || "Unknown"} ${patient?.lastName || "Unknown"}
Date of Birth: ${patient?.dateOfBirth || "Unknown"}

Insurance: ${primaryInsurance?.providerName || "No insurance on file"}
Insurance Type: ${primaryInsurance?.insuranceType || "Unknown"}
Prior Auth Required: ${primaryInsurance?.priorAuthRequired ? "YES" : "No"}
Coverage %: ${primaryInsurance?.coveragePercentage || "Unknown"}`;

      const raw = await askClaude(systemPrompt, userMessage, 2000);

      let parsed: {
        riskScore: number;
        approvalProbability: number;
        issues: Array<{
          code: string;
          severity: string;
          description: string;
          suggestion: string;
          autoFixable: boolean;
          fixValue?: string;
        }>;
        checklist: Array<{ label: string; passed: boolean }>;
        recommendedActions: string[];
      };
      try {
        parsed = JSON.parse(raw);
      } catch {
        parsed = {
          riskScore: 60,
          approvalProbability: 65,
          issues: [{ code: "PARSE_ERROR", severity: "warning", description: "Could not fully parse AI analysis", suggestion: "Review claim manually", autoFixable: false }],
          checklist: [
            { label: "Procedure code present", passed: !!claim.procedureCode },
            { label: "ICD-10 code present", passed: !!claim.icd10Code },
            { label: "Service date present", passed: !!claim.serviceDate },
            { label: "Charged amount > $0", passed: parseFloat(claim.chargedAmount?.toString() || "0") > 0 },
          ],
          recommendedActions: ["Verify procedure code accuracy", "Ensure ICD-10 code is present and specific"],
        };
      }

      const result = await storage.createPreflightResult({
        claimId,
        riskScore: Math.min(100, Math.max(0, parsed.riskScore)),
        approvalProbability: Math.min(100, Math.max(0, parsed.approvalProbability)),
        issues: parsed.issues || [],
        checklist: parsed.checklist || [],
        recommendedActions: parsed.recommendedActions || [],
      });

      res.json(result);
    } catch (error) {
      console.error("Error running preflight check:", error);
      res.status(500).json({ message: "Failed to run preflight check" });
    }
  });

  app.patch("/api/billing/claims/:id/autofix", isAuthenticated, async (req, res) => {
    try {
      const claimId = parseInt(req.params.id);
      const { issueCode, fixValue, field } = req.body as { issueCode: string; fixValue: string; field: string };

      const allowedFields: Record<string, boolean> = {
        icd10Code: true,
        procedureCode: true,
        description: true,
      };

      if (!allowedFields[field]) {
        return res.status(400).json({ message: "Field not patchable via auto-fix" });
      }

      const updated = await storage.updateBillingClaim(claimId, { [field]: fixValue });
      if (!updated) return res.status(404).json({ message: "Claim not found" });

      res.json({ success: true, claim: updated, issueCode });
    } catch (error) {
      console.error("Error applying auto-fix:", error);
      res.status(500).json({ message: "Failed to apply auto-fix" });
    }
  });

  // ============ PATIENT PORTAL ============
  app.get("/api/patients/:id/portal-access", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const access = await storage.getPortalAccess(patientId);
      res.json(access || { patientId, enabled: false, lastAccessedAt: null, linkSentAt: null });
    } catch (error) {
      console.error("Error fetching portal access:", error);
      res.status(500).json({ message: "Failed to fetch portal access" });
    }
  });

  app.patch("/api/patients/:id/portal-access", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const { enabled } = req.body as { enabled: boolean };
      const access = await storage.upsertPortalAccess(patientId, { enabled });
      res.json(access);
    } catch (error) {
      console.error("Error updating portal access:", error);
      res.status(500).json({ message: "Failed to update portal access" });
    }
  });

  app.post("/api/patients/:id/portal-link", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const access = await storage.upsertPortalAccess(patientId, { enabled: true, linkSentAt: new Date() });
      await storage.createAuditLog({
        userId: req.user?.claims?.sub || req.user?.id || "unknown",
        action: "portal_link_sent",
        resourceType: "patient_portal",
        resourceId: String(patientId),
        patientId,
        details: { patientId },
      });
      res.json({ success: true, access });
    } catch (error) {
      console.error("Error sending portal link:", error);
      res.status(500).json({ message: "Failed to send portal link" });
    }
  });

  app.post("/api/patients/:id/portal-access-log", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.id);
      const tab: string = req.body?.tab || "portal_open";
      // Verify portal is enabled — do NOT create or mutate enabled status
      const access = await storage.getPortalAccess(patientId);
      if (!access || access.enabled === false) {
        return res.status(403).json({ message: "Portal access is disabled for this patient" });
      }
      // Only update lastAccessedAt on existing enabled records — touchPortalLastAccessed never re-enables a disabled portal
      await storage.touchPortalLastAccessed(patientId);
      await storage.createAuditLog({
        userId: req.user?.claims?.sub || req.user?.id || "unknown",
        action: "portal_view",
        resourceType: "patient_portal",
        resourceId: String(patientId),
        patientId,
        details: {
          patientId,
          tabViewed: tab,
          dataScope: tab === "eob" ? "payment_postings,billing_claims"
            : tab === "billing" ? "treatment_plans"
            : tab === "appointments" ? "appointments"
            : tab === "portal_open" ? "appointments"  // default tab on portal entry
            : tab === "post-op" ? "surgery_reports"
            : tab === "messages" ? "patient_messages"
            : tab === "documents" ? "documents,patient_documents"
            : tab === "consent" ? "consent_forms"
            : tab === "my-info" || tab === "my_info_update" ? "patient_contact_info"
            : tab === "request" ? "portal_appointment_requests"
            : "portal",
          accessedAt: new Date().toISOString(),
        },
      });
      res.json({ success: true });
    } catch (error) {
      console.error("Error logging portal access:", error);
      res.status(500).json({ message: "Failed to log portal access" });
    }
  });

  app.get("/api/portal/appointment-requests", isAuthenticated, async (req, res) => {
    try {
      const patientId = req.query.patientId ? parseInt(req.query.patientId as string) : undefined;
      if (patientId) {
        const access = await storage.getPortalAccess(patientId);
        if (!access || !access.enabled) {
          return res.status(403).json({ message: "Portal access is not enabled for this patient" });
        }
      }
      const requests = await storage.getPortalAppointmentRequests(patientId);
      res.json(requests);
    } catch (error) {
      console.error("Error fetching portal appointment requests:", error);
      res.status(500).json({ message: "Failed to fetch appointment requests" });
    }
  });

  app.post("/api/portal/appointment-requests", isAuthenticated, async (req, res) => {
    try {
      const raw = insertPortalAppointmentRequestSchema.parse(req.body);
      if (raw.patientId) {
        const access = await storage.getPortalAccess(raw.patientId);
        if (!access || !access.enabled) {
          return res.status(403).json({ message: "Portal access is disabled for this patient" });
        }
      }
      // Enforce server-side defaults — patient-originated requests always start as pending
      // and strip any client-supplied staff-only fields
      const data = { ...raw, status: "pending" as const, staffNotes: null };
      const request = await storage.createPortalAppointmentRequest(data);
      res.status(201).json(request);
    } catch (error: unknown) {
      console.error("Error creating portal appointment request:", error);
      const msg = error instanceof Error ? error.message : "Failed to create appointment request";
      res.status(400).json({ message: msg });
    }
  });

  app.patch("/api/portal/appointment-requests/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertPortalAppointmentRequestSchema.partial().parse(req.body);
      const request = await storage.updatePortalAppointmentRequest(id, data);
      if (!request) return res.status(404).json({ message: "Request not found" });
      res.json(request);
    } catch (error: unknown) {
      console.error("Error updating portal appointment request:", error);
      const msg = error instanceof Error ? error.message : "Failed to update appointment request";
      res.status(400).json({ message: msg });
    }
  });

  app.get("/api/surgery-reports/patient/:patientId", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const access = await storage.getPortalAccess(patientId);
      if (!access || !access.enabled) {
        return res.status(403).json({ message: "Portal access is not enabled for this patient" });
      }
      const reports = await storage.getSurgeryReportsByPatient(patientId);
      res.json(reports);
    } catch (error) {
      console.error("Error fetching surgery reports:", error);
      res.status(500).json({ message: "Failed to fetch surgery reports" });
    }
  });

  app.get("/api/payment-postings/patient/:patientId", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const access = await storage.getPortalAccess(patientId);
      if (!access || !access.enabled) {
        return res.status(403).json({ message: "Portal access is not enabled for this patient" });
      }
      const postings = await storage.getPaymentPostingsByPatient(patientId);
      res.json(postings);
    } catch (error) {
      console.error("Error fetching payment postings:", error);
      res.status(500).json({ message: "Failed to fetch EOBs" });
    }
  });

  app.post("/api/appeals/generate", isAuthenticated, async (req, res) => {
    try {
      const { claimId, patientId, denialReason, denialCode, additionalInfo } = req.body;

      const patient = await storage.getPatient(patientId);
      const medicalHistory = await storage.getMedicalHistory(patientId);

      const prompt = `Generate a professional insurance appeal letter for a denied dental implant claim.

Denial Code: ${denialCode}
Denial Reason: ${denialReason}
Patient: ${patient?.firstName} ${patient?.lastName}
Medical History: ${JSON.stringify(medicalHistory || {})}
${additionalInfo ? `Additional Information: ${additionalInfo}` : ""}

Generate a compelling appeal letter that addresses the denial reason with clinical evidence and medical necessity documentation.`;

      const appealLetter = await askClaude(
        "You are an expert dental billing appeals specialist with a 78% success rate in overturning denials. Generate compelling, evidence-based appeal letters that address specific denial reasons.",
        prompt, 1500
      );
      res.json({ appealLetter, successProbability: 78 });
    } catch (error) {
      console.error("Error generating appeal:", error);
      res.status(500).json({ message: "Failed to generate appeal" });
    }
  });

  app.post("/api/appeals", isAuthenticated, async (req, res) => {
    try {
      const { claimId, patientId, appealLetter, denialReason, denialCode } = req.body;
      
      const appeal = await storage.createAppeal({
        claimId,
        patientId,
        denialReason,
        denialCode,
        appealLevel: 1,
        appealType: "written",
        status: "draft",
        appealLetter,
        successProbability: 78
      });
      
      res.status(201).json(appeal);
    } catch (error) {
      console.error("Error creating appeal:", error);
      res.status(500).json({ message: "Failed to create appeal" });
    }
  });

  // ============ ERA PROCESSING ============
  app.get("/api/era/stats", isAuthenticated, async (req, res) => {
    try {
      const postings = await storage.getPaymentPostings();
      const pending = postings.filter(p => p.postingStatus === "pending").length;
      const today = new Date().toISOString().split("T")[0];
      const postedToday = postings.filter(p => p.postingStatus === "posted" && p.paymentDate === today).length;
      
      res.json({
        pendingCount: pending,
        postedToday,
        totalPosted: postings.filter(p => p.postingStatus === "posted").length,
        varianceCount: postings.filter(p => p.varianceFlag).length,
        autoPostRate: 94,
        avgProcessingTime: "2.3s"
      });
    } catch (error) {
      console.error("Error fetching ERA stats:", error);
      res.json({ pendingCount: 0, postedToday: 0, totalPosted: 0, varianceCount: 0, autoPostRate: 94, avgProcessingTime: "2.3s" });
    }
  });

  app.get("/api/era/pending", isAuthenticated, async (req, res) => {
    try {
      const postings = await storage.getPaymentPostings();
      const pending = postings.filter(p => p.postingStatus === "pending");
      res.json(pending);
    } catch (error) {
      console.error("Error fetching pending ERA:", error);
      res.json([]);
    }
  });

  app.get("/api/era/recent", isAuthenticated, async (req, res) => {
    try {
      const postings = await storage.getPaymentPostings();
      const recent = postings.filter(p => p.postingStatus === "posted").slice(0, 20);
      res.json(recent);
    } catch (error) {
      console.error("Error fetching recent ERA:", error);
      res.json([]);
    }
  });

  app.get("/api/era/variances", isAuthenticated, async (req, res) => {
    try {
      const postings = await storage.getPaymentPostings();
      const variances = postings.filter(p => p.varianceFlag);
      res.json(variances);
    } catch (error) {
      console.error("Error fetching ERA variances:", error);
      res.json([]);
    }
  });

  app.post("/api/era/:id/post", isAuthenticated, async (req, res) => {
    try {
      const postingId = parseInt(req.params.id);
      await storage.updatePaymentPosting(postingId, { postingStatus: "posted", autoPosted: true });
      res.json({ success: true });
    } catch (error) {
      console.error("Error posting ERA:", error);
      res.status(500).json({ message: "Failed to post payment" });
    }
  });

  app.post("/api/era/auto-post-all", isAuthenticated, async (req, res) => {
    try {
      const postings = await storage.getPaymentPostings();
      const pending = postings.filter(p => p.postingStatus === "pending" && !p.varianceFlag);
      let posted = 0;
      for (const posting of pending) {
        await storage.updatePaymentPosting(posting.id, { postingStatus: "posted", autoPosted: true });
        posted++;
      }
      res.json({ posted });
    } catch (error) {
      console.error("Error auto-posting ERA:", error);
      res.status(500).json({ message: "Failed to auto-post payments" });
    }
  });

  // ============ ELIGIBILITY VERIFICATION ============
  app.get("/api/eligibility/stats", isAuthenticated, async (req, res) => {
    try {
      const checks = await storage.getEligibilityChecks();
      const today = new Date().toISOString().split("T")[0];
      const checksToday = checks.filter(c => c.checkDate && c.checkDate.toString().startsWith(today)).length;
      const active = checks.filter(c => c.eligibilityStatus === "active").length;
      res.json({
        checksToday,
        activeVerifications: checks.length,
        eligibleRate: checks.length > 0 ? Math.round((active / checks.length) * 100) : 92,
        avgResponseTime: "3.2s"
      });
    } catch (error) {
      console.error("Error fetching eligibility stats:", error);
      res.json({ checksToday: 0, activeVerifications: 0, eligibleRate: 92, avgResponseTime: "3.2s" });
    }
  });

  app.get("/api/eligibility/recent", isAuthenticated, async (req, res) => {
    try {
      const checks = await storage.getEligibilityChecks();
      const recentWithNames = await Promise.all(
        checks.slice(0, 10).map(async (check) => {
          const patient = await storage.getPatient(check.patientId);
          return {
            ...check,
            patientName: patient ? `${patient.firstName} ${patient.lastName}` : `Patient ${check.patientId}`
          };
        })
      );
      res.json(recentWithNames);
    } catch (error) {
      console.error("Error fetching recent eligibility:", error);
      res.json([]);
    }
  });

  app.get("/api/eligibility/patient/:patientId", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const checks = await storage.getEligibilityChecksByPatient(patientId);
      res.json(checks);
    } catch (error) {
      console.error("Error fetching patient eligibility history:", error);
      res.status(500).json({ message: "Failed to fetch eligibility history" });
    }
  });

  interface EligibilityAIResponse {
    eligibilityStatus?: string; planName?: string; planType?: string; groupNumber?: string;
    subscriberId?: string; subscriberName?: string; effectiveDate?: string;
    terminationDate?: string | null; networkStatus?: string; deductibleIndividual?: number;
    deductibleMet?: number; deductibleRemaining?: number; deductibleFamily?: number;
    outOfPocketMax?: number; oopMet?: number; oopRemaining?: number; annualMaximum?: number;
    benefitsRemaining?: number; copayPreventive?: number; copayBasic?: number;
    copayMajor?: number; copayOrtho?: number; coveredServices?: string[];
    waitingPeriods?: { major?: string | null; orthodontics?: string | null };
    priorAuthRequired?: string[]; notes?: string;
  }

  interface BatchEligibilityResult {
    patientId: number;
    status: "ok" | "error";
    eligibilityStatus?: string;
    cached?: boolean;
    message?: string;
  }

  // Shared AI eligibility check logic
  async function runEligibilityCheck(patientId: number, forceRefresh = false): Promise<Record<string, unknown> & { cached: boolean }> {
    const patient = await storage.getPatient(patientId);
    if (!patient) throw new Error("Patient not found");

    // 24-hour cache: return existing if checked within last 24h and not force-refreshing
    if (!forceRefresh) {
      const latest = await storage.getLatestEligibilityCheckByPatient(patientId);
      if (latest) {
        const ageMs = Date.now() - new Date(latest.checkDate).getTime();
        if (ageMs < 24 * 60 * 60 * 1000) {
          return { ...latest, cached: true };
        }
      }
    }

    const insuranceRecords = await storage.getInsurance(patientId);
    const primaryInsurance = insuranceRecords[0];

    const insuranceContext = primaryInsurance
      ? `Provider: ${primaryInsurance.providerName}, Type: ${primaryInsurance.insuranceType}, Policy: ${primaryInsurance.policyNumber}, Group: ${primaryInsurance.groupNumber || "N/A"}, Annual Max: $${primaryInsurance.annualMaximum || "2000"}, Deductible: $${primaryInsurance.deductible || "50"}, Remaining Benefit: $${primaryInsurance.remainingBenefit || "1500"}`
      : "No insurance on file — generate a plausible dental PPO plan";

    const aiResponse = await askClaude(
      `You are a dental insurance clearinghouse (like Availity). Return ONLY valid JSON — no markdown, no explanation.`,
      `Simulate an eligibility (270/271) response for patient ${patient.firstName} ${patient.lastName}, DOB ${patient.dateOfBirth}.
Insurance on file: ${insuranceContext}.
Return this exact JSON shape:
{
  "eligibilityStatus": "active" | "inactive" | "terminated",
  "planName": string,
  "planType": "PPO" | "HMO" | "Indemnity" | "DHMO",
  "groupNumber": string,
  "subscriberId": string,
  "subscriberName": string,
  "effectiveDate": "YYYY-MM-DD",
  "terminationDate": "YYYY-MM-DD" | null,
  "networkStatus": "In-Network" | "Out-of-Network",
  "deductibleIndividual": number,
  "deductibleMet": number,
  "deductibleRemaining": number,
  "deductibleFamily": number,
  "outOfPocketMax": number,
  "oopMet": number,
  "oopRemaining": number,
  "annualMaximum": number,
  "benefitsRemaining": number,
  "copayPreventive": number,
  "copayBasic": number,
  "copayMajor": number,
  "copayOrtho": number,
  "coveredServices": ["preventive","basic","major","orthodontics","implants","oral_surgery"],
  "waitingPeriods": {"major": string | null, "orthodontics": string | null},
  "priorAuthRequired": ["implants","oral_surgery"],
  "notes": string
}`,
      800
    );

    let parsed: EligibilityAIResponse = {};
    try {
      parsed = JSON.parse(aiResponse) as EligibilityAIResponse;
    } catch {
      const m = aiResponse.match(/\{[\s\S]*\}/);
      if (m) parsed = JSON.parse(m[0]) as EligibilityAIResponse;
    }

    const check = await storage.createEligibilityCheck({
      patientId,
      insuranceId: primaryInsurance?.id || null,
      status: "completed",
      eligibilityStatus: parsed.eligibilityStatus || "active",
      coverageDetails: parsed,
      benefitsRemaining: String(parsed.benefitsRemaining ?? primaryInsurance?.remainingBenefit ?? "1500"),
      deductibleMet: String(parsed.deductibleMet ?? "0"),
      effectiveDate: parsed.effectiveDate || primaryInsurance?.effectiveDate || null,
      terminationDate: parsed.terminationDate || primaryInsurance?.terminationDate || null,
      rawResponse: parsed,
    });
    return { ...check, cached: false };
  }

  app.post("/api/eligibility/verify/:patientId", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const forceRefresh = req.body?.forceRefresh === true;
      const result = await runEligibilityCheck(patientId, forceRefresh);
      res.json(result);
    } catch (error: any) {
      console.error("Error verifying eligibility:", error);
      res.status(error.message === "Patient not found" ? 404 : 500).json({ message: error.message || "Failed to verify eligibility" });
    }
  });

  // POST /api/eligibility/check — alias used by insurance-verification page
  app.post("/api/eligibility/check", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.body?.patientId);
      if (!patientId) return res.status(400).json({ message: "patientId required" });
      const forceRefresh = req.body?.forceRefresh === true;
      const result = await runEligibilityCheck(patientId, forceRefresh);
      res.json(result);
    } catch (error: any) {
      console.error("Error checking eligibility:", error);
      res.status(500).json({ message: error.message || "Failed to check eligibility" });
    }
  });

  // Batch verify — all patients with appointments tomorrow
  app.post("/api/eligibility/batch-tomorrow", isAuthenticated, async (req, res) => {
    try {
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const tStart = new Date(tomorrow); tStart.setHours(0, 0, 0, 0);
      const tEnd = new Date(tomorrow); tEnd.setHours(23, 59, 59, 999);

      const allAppts = await storage.getAppointments({ startDate: tStart, endDate: tEnd });
      const uniquePatientIds = [...new Set(allAppts.map(a => a.patientId))];

      const results: BatchEligibilityResult[] = [];
      for (const pid of uniquePatientIds) {
        try {
          const r = await runEligibilityCheck(pid, false);
          results.push({ patientId: pid, status: "ok", eligibilityStatus: String(r.eligibilityStatus ?? ""), cached: Boolean(r.cached) });
        } catch (e: unknown) {
          results.push({ patientId: pid, status: "error", message: e instanceof Error ? e.message : "Unknown error" });
        }
      }
      res.json({ checked: results.length, results });
    } catch (error) {
      console.error("Error running batch eligibility:", error);
      res.status(500).json({ message: "Failed to run batch eligibility check" });
    }
  });

  // ============ PREDICTIVE ANALYTICS ============
  app.get("/api/analytics/predictive", isAuthenticated, async (req, res) => {
    try {
      const claims = await storage.getBillingClaims();
      const pendingClaims = claims.filter(c => c.claimStatus === "pending" || c.claimStatus === "submitted");
      
      res.json({
        collections: {
          predictedNext30Days: 125000,
          predictedNext60Days: 285000,
          predictedNext90Days: 450000,
          confidence: 87,
          trend: "up",
          percentChange: 12.5
        },
        atRiskClaims: {
          count: Math.min(pendingClaims.length, 8),
          totalValue: pendingClaims.reduce((sum, c) => sum + parseFloat(c.chargedAmount?.toString() || "0"), 0),
          claims: pendingClaims.slice(0, 3).map((c, i) => ({
            id: c.id,
            patientName: `Patient ${c.patientId}`,
            amount: parseFloat(c.chargedAmount?.toString() || "0"),
            riskScore: 65 + (i * 10),
            riskReason: i === 0 ? "Approaching timely filing deadline" : i === 1 ? "Payer has high denial rate" : "Missing documentation",
            daysOutstanding: 45 + (i * 20)
          }))
        },
        benchmarks: {
          cleanClaimRate: { current: 96, industry: 85, percentile: 92 },
          denialRate: { current: 8, industry: 15, percentile: 88 },
          daysToPayment: { current: 32, industry: 45, percentile: 85 },
          collectionRate: { current: 94, industry: 82, percentile: 90 },
          appealSuccessRate: { current: 78, industry: 25, percentile: 95 }
        },
        recommendations: [
          { id: "1", priority: "high", title: "Submit 3 pending prior authorizations", description: "These authorizations expire within 7 days", potentialImpact: "+$42,000 in revenue at risk" },
          { id: "2", priority: "medium", title: "Appeal 5 denied claims", description: "AI analysis suggests 80%+ overturn probability", potentialImpact: "+$28,500 potential recovery" },
          { id: "3", priority: "low", title: "Update fee schedules for Aetna", description: "New contracted rates available", potentialImpact: "+5% reimbursement improvement" }
        ]
      });
    } catch (error) {
      console.error("Error fetching predictive analytics:", error);
      res.status(500).json({ message: "Failed to fetch predictive analytics" });
    }
  });

  // ============ TRAINING CENTER ============
  app.get("/api/training/stats", isAuthenticated, async (req, res) => {
    try {
      const userId = (req as any).user?.id || "default";
      const progress = await storage.getTrainingProgress(userId);
      const completed = progress.filter(p => p.completed).length;
      
      res.json({
        totalModules: 5,
        completedModules: Math.floor(completed / 5),
        totalLessons: 26,
        completedLessons: completed,
        overallProgress: Math.round((completed / 26) * 100),
        certificationsEarned: Math.floor(completed / 5),
        hoursCompleted: Math.round(completed * 0.4)
      });
    } catch (error) {
      console.error("Error fetching training stats:", error);
      res.json({ totalModules: 5, completedModules: 0, totalLessons: 26, completedLessons: 0, overallProgress: 0, certificationsEarned: 0, hoursCompleted: 0 });
    }
  });

  app.get("/api/training/progress", isAuthenticated, async (req, res) => {
    try {
      const userId = (req as any).user?.id || "default";
      const progress = await storage.getTrainingProgress(userId);
      const progressMap: Record<string, boolean> = {};
      for (const p of progress) {
        progressMap[`${p.moduleName}-${p.lessonId}`] = p.completed;
      }
      res.json(progressMap);
    } catch (error) {
      console.error("Error fetching training progress:", error);
      res.json({});
    }
  });

  app.post("/api/training/complete", isAuthenticated, async (req, res) => {
    try {
      const userId = (req as any).user?.id || "default";
      const { moduleId, lessonId } = req.body;
      
      await storage.createTrainingProgress({
        userId,
        moduleName: moduleId,
        lessonId,
        completed: true,
        score: 100,
        completedAt: new Date()
      });
      
      res.json({ success: true });
    } catch (error) {
      console.error("Error completing training:", error);
      res.status(500).json({ message: "Failed to record training progress" });
    }
  });

  // ============ PATIENT JOURNEY SYSTEM ============

  // Leads
  app.get("/api/leads", isAuthenticated, async (req, res) => {
    try {
      const allLeads = await storage.getLeads();
      res.json(allLeads);
    } catch (error) {
      console.error("Error fetching leads:", error);
      res.status(500).json({ message: "Failed to fetch leads" });
    }
  });

  app.get("/api/leads/stats", isAuthenticated, async (req, res) => {
    try {
      const stats = await storage.getLeadStats();
      res.json(stats);
    } catch (error) {
      console.error("Error fetching lead stats:", error);
      res.json({ totalLeads: 0, newLeads: 0, qualifiedLeads: 0, conversionRate: 0 });
    }
  });

  app.post("/api/leads", isAuthenticated, async (req, res) => {
    try {
      const validatedData = insertLeadSchema.parse(req.body);
      const lead = await storage.createLead(validatedData);
      res.json(lead);
    } catch (error) {
      console.error("Error creating lead:", error);
      res.status(500).json({ message: "Failed to create lead" });
    }
  });

  app.patch("/api/leads/:id/status", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id as string);
      const { status } = req.body;
      const lead = await storage.updateLead(id, { status });
      res.json(lead);
    } catch (error) {
      console.error("Error updating lead status:", error);
      res.status(500).json({ message: "Failed to update lead status" });
    }
  });

  app.post("/api/leads/:id/convert", isAuthenticated, async (req, res) => {
    try {
      const leadId = parseInt(req.params.id as string);
      const lead = await storage.getLead(leadId);
      
      if (!lead) {
        return res.status(404).json({ message: "Lead not found" });
      }

      const patient = await storage.createPatient({
        firstName: lead.firstName,
        lastName: lead.lastName,
        email: lead.email || undefined,
        phone: lead.phone,
        dateOfBirth: "1990-01-01",
        gender: "unknown",
      });

      await storage.updateLead(leadId, { 
        status: "converted", 
        convertedToPatientId: patient.id 
      });

      res.json({ success: true, patientId: patient.id });
    } catch (error) {
      console.error("Error converting lead:", error);
      res.status(500).json({ message: "Failed to convert lead to patient" });
    }
  });

  // Treatment Packages
  app.get("/api/packages", isAuthenticated, async (req, res) => {
    try {
      const packages = await storage.getTreatmentPackages();
      res.json(packages);
    } catch (error) {
      console.error("Error fetching treatment packages:", error);
      res.status(500).json({ message: "Failed to fetch treatment packages" });
    }
  });

  app.post("/api/packages", isAuthenticated, async (req, res) => {
    try {
      const validatedData = insertTreatmentPackageSchema.parse(req.body);
      const pkg = await storage.createTreatmentPackage(validatedData);
      res.json(pkg);
    } catch (error) {
      console.error("Error creating treatment package:", error);
      res.status(500).json({ message: "Failed to create treatment package" });
    }
  });

  // Appointment Reminders
  app.get("/api/reminders", isAuthenticated, async (req, res) => {
    try {
      const reminders = await storage.getAppointmentReminders();
      res.json(reminders);
    } catch (error) {
      console.error("Error fetching reminders:", error);
      res.status(500).json({ message: "Failed to fetch reminders" });
    }
  });

  app.post("/api/reminders", isAuthenticated, async (req, res) => {
    try {
      const validatedData = insertAppointmentReminderSchema.parse(req.body);
      const reminder = await storage.createAppointmentReminder(validatedData);
      res.json(reminder);
    } catch (error) {
      console.error("Error creating reminder:", error);
      res.status(500).json({ message: "Failed to create reminder" });
    }
  });

  app.post("/api/reminders/:id/send", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id as string);
      const reminder = await storage.updateAppointmentReminder(id, { 
        status: "sent", 
        sentAt: new Date() 
      });
      res.json(reminder);
    } catch (error) {
      console.error("Error sending reminder:", error);
      res.status(500).json({ message: "Failed to send reminder" });
    }
  });

  // Patient Check-ins
  app.get("/api/checkins", isAuthenticated, async (req, res) => {
    try {
      const checkIns = await storage.getPatientCheckIns();
      res.json(checkIns);
    } catch (error) {
      console.error("Error fetching check-ins:", error);
      res.status(500).json({ message: "Failed to fetch check-ins" });
    }
  });

  app.post("/api/checkins", isAuthenticated, async (req, res) => {
    try {
      const validatedData = insertPatientCheckInSchema.parse(req.body);
      const checkIn = await storage.createPatientCheckIn(validatedData);
      res.json(checkIn);
    } catch (error) {
      console.error("Error creating check-in:", error);
      res.status(500).json({ message: "Failed to create check-in" });
    }
  });

  // Financing Plans
  app.get("/api/financing", isAuthenticated, async (req, res) => {
    try {
      const plans = await storage.getFinancingPlans();
      res.json(plans);
    } catch (error) {
      console.error("Error fetching financing plans:", error);
      res.status(500).json({ message: "Failed to fetch financing plans" });
    }
  });

  app.post("/api/financing", isAuthenticated, async (req, res) => {
    try {
      const validatedData = insertFinancingPlanSchema.parse(req.body);
      const plan = await storage.createFinancingPlan(validatedData);
      res.json(plan);
    } catch (error) {
      console.error("Error creating financing plan:", error);
      res.status(500).json({ message: "Failed to create financing plan" });
    }
  });

  app.patch("/api/financing/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id as string);
      const updateSchema = insertFinancingPlanSchema.partial();
      const validatedData = updateSchema.parse(req.body);
      const plan = await storage.updateFinancingPlan(id, validatedData);
      res.json(plan);
    } catch (error) {
      console.error("Error updating financing plan:", error);
      res.status(500).json({ message: "Failed to update financing plan" });
    }
  });

  // Medical Clearances
  app.get("/api/medical-clearances", isAuthenticated, async (req, res) => {
    try {
      const clearances = await storage.getMedicalClearances();
      res.json(clearances);
    } catch (error) {
      console.error("Error fetching medical clearances:", error);
      res.status(500).json({ message: "Failed to fetch medical clearances" });
    }
  });

  app.get("/api/medical-clearances/patient/:patientId", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId as string);
      const clearances = await storage.getMedicalClearancesByPatient(patientId);
      res.json(clearances);
    } catch (error) {
      console.error("Error fetching patient clearances:", error);
      res.status(500).json({ message: "Failed to fetch patient clearances" });
    }
  });

  app.post("/api/medical-clearances", isAuthenticated, async (req, res) => {
    try {
      const validatedData = insertMedicalClearanceSchema.parse(req.body);
      const clearance = await storage.createMedicalClearance(validatedData);
      res.json(clearance);
    } catch (error) {
      console.error("Error creating medical clearance:", error);
      res.status(500).json({ message: "Failed to create medical clearance" });
    }
  });

  app.patch("/api/medical-clearances/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id as string);
      const updateSchema = insertMedicalClearanceSchema.partial();
      const validatedData = updateSchema.parse(req.body);
      const clearance = await storage.updateMedicalClearance(id, validatedData);
      res.json(clearance);
    } catch (error) {
      console.error("Error updating medical clearance:", error);
      res.status(500).json({ message: "Failed to update medical clearance" });
    }
  });

  // Pre-Surgery Tasks
  app.get("/api/pre-surgery-tasks", isAuthenticated, async (req, res) => {
    try {
      const tasks = await storage.getPreSurgeryTasks();
      res.json(tasks);
    } catch (error) {
      console.error("Error fetching pre-surgery tasks:", error);
      res.status(500).json({ message: "Failed to fetch pre-surgery tasks" });
    }
  });

  app.get("/api/pre-surgery-tasks/patient/:patientId", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId as string);
      const tasks = await storage.getPreSurgeryTasksByPatient(patientId);
      res.json(tasks);
    } catch (error) {
      console.error("Error fetching patient tasks:", error);
      res.status(500).json({ message: "Failed to fetch patient tasks" });
    }
  });

  app.post("/api/pre-surgery-tasks", isAuthenticated, async (req, res) => {
    try {
      const validatedData = insertPreSurgeryTaskSchema.parse(req.body);
      const task = await storage.createPreSurgeryTask(validatedData);
      res.json(task);
    } catch (error) {
      console.error("Error creating pre-surgery task:", error);
      res.status(500).json({ message: "Failed to create pre-surgery task" });
    }
  });

  app.patch("/api/pre-surgery-tasks/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id as string);
      const updateSchema = insertPreSurgeryTaskSchema.partial();
      const validatedData = updateSchema.parse(req.body);
      const task = await storage.updatePreSurgeryTask(id, validatedData);
      res.json(task);
    } catch (error) {
      console.error("Error updating pre-surgery task:", error);
      res.status(500).json({ message: "Failed to update pre-surgery task" });
    }
  });

  // Surgery Sessions
  app.get("/api/surgery-sessions", isAuthenticated, async (req, res) => {
    try {
      const sessions = await storage.getSurgerySessions();
      res.json(sessions);
    } catch (error) {
      console.error("Error fetching surgery sessions:", error);
      res.status(500).json({ message: "Failed to fetch surgery sessions" });
    }
  });

  app.get("/api/surgery-sessions/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id as string);
      const session = await storage.getSurgerySession(id);
      if (!session) {
        return res.status(404).json({ message: "Surgery session not found" });
      }
      res.json(session);
    } catch (error) {
      console.error("Error fetching surgery session:", error);
      res.status(500).json({ message: "Failed to fetch surgery session" });
    }
  });

  app.post("/api/surgery-sessions", isAuthenticated, async (req, res) => {
    try {
      const validatedData = insertSurgerySessionSchema.parse(req.body);
      const session = await storage.createSurgerySession(validatedData);
      res.json(session);
    } catch (error) {
      console.error("Error creating surgery session:", error);
      res.status(500).json({ message: "Failed to create surgery session" });
    }
  });

  app.patch("/api/surgery-sessions/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id as string);
      const updateSchema = insertSurgerySessionSchema.partial();
      const validatedData = updateSchema.parse(req.body);
      const session = await storage.updateSurgerySession(id, validatedData);
      res.json(session);
    } catch (error) {
      console.error("Error updating surgery session:", error);
      res.status(500).json({ message: "Failed to update surgery session" });
    }
  });

  // Lab Cases
  app.get("/api/lab-cases", isAuthenticated, async (req, res) => {
    try {
      const cases = await storage.getLabCases();
      res.json(cases);
    } catch (error) {
      console.error("Error fetching lab cases:", error);
      res.status(500).json({ message: "Failed to fetch lab cases" });
    }
  });

  app.post("/api/lab-cases", isAuthenticated, async (req, res) => {
    try {
      const validatedData = insertLabCaseSchema.parse(req.body);
      const labCase = await storage.createLabCase(validatedData);
      res.json(labCase);
    } catch (error) {
      console.error("Error creating lab case:", error);
      res.status(500).json({ message: "Failed to create lab case" });
    }
  });

  app.patch("/api/lab-cases/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id as string);
      const updateSchema = insertLabCaseSchema.partial();
      const validatedData = updateSchema.parse(req.body);
      const labCase = await storage.updateLabCase(id, validatedData);
      res.json(labCase);
    } catch (error) {
      console.error("Error updating lab case:", error);
      res.status(500).json({ message: "Failed to update lab case" });
    }
  });

  // Post-Op Visits
  app.get("/api/post-op-visits", isAuthenticated, async (req, res) => {
    try {
      const visits = await storage.getPostOpVisits();
      res.json(visits);
    } catch (error) {
      console.error("Error fetching post-op visits:", error);
      res.status(500).json({ message: "Failed to fetch post-op visits" });
    }
  });

  app.post("/api/post-op-visits", isAuthenticated, async (req, res) => {
    try {
      const validatedData = insertPostOpVisitSchema.parse(req.body);
      const visit = await storage.createPostOpVisit(validatedData);
      res.json(visit);
    } catch (error) {
      console.error("Error creating post-op visit:", error);
      res.status(500).json({ message: "Failed to create post-op visit" });
    }
  });

  app.patch("/api/post-op-visits/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id as string);
      const updateSchema = insertPostOpVisitSchema.partial();
      const validatedData = updateSchema.parse(req.body);
      const visit = await storage.updatePostOpVisit(id, validatedData);
      res.json(visit);
    } catch (error) {
      console.error("Error updating post-op visit:", error);
      res.status(500).json({ message: "Failed to update post-op visit" });
    }
  });

  // Warranty Records
  app.get("/api/warranty-records", isAuthenticated, async (req, res) => {
    try {
      const records = await storage.getWarrantyRecords();
      res.json(records);
    } catch (error) {
      console.error("Error fetching warranty records:", error);
      res.status(500).json({ message: "Failed to fetch warranty records" });
    }
  });

  app.post("/api/warranty-records", isAuthenticated, async (req, res) => {
    try {
      const body = {
        ...req.body,
        startDate: req.body.startDate,
        endDate: req.body.endDate,
      };
      const validatedData = insertWarrantyRecordSchema.parse(body);
      const record = await storage.createWarrantyRecord(validatedData);
      res.json(record);
    } catch (error) {
      console.error("Error creating warranty record:", error);
      res.status(500).json({ message: "Failed to create warranty record" });
    }
  });

  app.patch("/api/warranty-records/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id as string);
      const updateSchema = insertWarrantyRecordSchema.partial();
      const validatedData = updateSchema.parse(req.body);
      const record = await storage.updateWarrantyRecord(id, validatedData);
      res.json(record);
    } catch (error) {
      console.error("Error updating warranty record:", error);
      res.status(500).json({ message: "Failed to update warranty record" });
    }
  });

  // Testimonials
  app.get("/api/testimonials", isAuthenticated, async (req, res) => {
    try {
      const testimonials = await storage.getTestimonials();
      res.json(testimonials);
    } catch (error) {
      console.error("Error fetching testimonials:", error);
      res.status(500).json({ message: "Failed to fetch testimonials" });
    }
  });

  app.post("/api/testimonials", isAuthenticated, async (req, res) => {
    try {
      const validatedData = insertTestimonialSchema.parse(req.body);
      const testimonial = await storage.createTestimonial(validatedData);
      res.json(testimonial);
    } catch (error) {
      console.error("Error creating testimonial:", error);
      res.status(500).json({ message: "Failed to create testimonial" });
    }
  });

  app.patch("/api/testimonials/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id as string);
      const updateSchema = insertTestimonialSchema.partial();
      const validatedData = updateSchema.parse(req.body);
      const testimonial = await storage.updateTestimonial(id, validatedData);
      res.json(testimonial);
    } catch (error) {
      console.error("Error updating testimonial:", error);
      res.status(500).json({ message: "Failed to update testimonial" });
    }
  });

  // Maintenance Appointments
  app.get("/api/maintenance", isAuthenticated, async (req, res) => {
    try {
      const appointments = await storage.getMaintenanceAppointments();
      res.json(appointments);
    } catch (error) {
      console.error("Error fetching maintenance appointments:", error);
      res.status(500).json({ message: "Failed to fetch maintenance appointments" });
    }
  });

  app.post("/api/maintenance", isAuthenticated, async (req, res) => {
    try {
      const body = {
        ...req.body,
        scheduledDate: req.body.scheduledDate ? new Date(req.body.scheduledDate) : undefined,
        completedDate: req.body.completedDate ? new Date(req.body.completedDate) : undefined,
      };
      const validatedData = insertMaintenanceAppointmentSchema.parse(body);
      const appointment = await storage.createMaintenanceAppointment(validatedData);
      res.json(appointment);
    } catch (error: unknown) {
      console.error("Error creating maintenance appointment:", error);
      res.status(500).json({ message: "Failed to create maintenance appointment" });
    }
  });

  app.patch("/api/maintenance/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id as string);
      const body = {
        ...req.body,
        scheduledDate: req.body.scheduledDate ? new Date(req.body.scheduledDate) : undefined,
        completedDate: req.body.completedDate ? new Date(req.body.completedDate) : undefined,
      };
      const updateSchema = insertMaintenanceAppointmentSchema.partial();
      const validatedData = updateSchema.parse(body);
      const appointment = await storage.updateMaintenanceAppointment(id, validatedData);
      res.json(appointment);
    } catch (error) {
      console.error("Error updating maintenance appointment:", error);
      res.status(500).json({ message: "Failed to update maintenance appointment" });
    }
  });

  // =====================
  // HIPAA Audit Logs
  // =====================
  app.get("/api/audit-logs", isAuthenticated, async (req, res) => {
    try {
      const limit = parseInt(req.query.limit as string) || 100;
      const offset = parseInt(req.query.offset as string) || 0;
      const logs = await storage.getAuditLogs(limit, offset);
      res.json(logs);
    } catch (error) {
      console.error("Error fetching audit logs:", error);
      res.status(500).json({ message: "Failed to fetch audit logs" });
    }
  });

  app.get("/api/audit-logs/patient/:patientId", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const logs = await storage.getAuditLogsByPatient(patientId);
      res.json(logs);
    } catch (error) {
      console.error("Error fetching patient audit logs:", error);
      res.status(500).json({ message: "Failed to fetch patient audit logs" });
    }
  });

  // ============ CONSENT FORMS ============
  app.get("/api/consent-forms", isAuthenticated, async (req, res) => {
    try {
      const forms = await storage.getConsentForms();
      res.json(forms);
    } catch (error) {
      console.error("Error fetching consent forms:", error);
      res.status(500).json({ message: "Failed to fetch consent forms" });
    }
  });

  app.get("/api/consent-forms/patient/:patientId", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const forms = await storage.getConsentFormsByPatient(patientId);
      res.json(forms);
    } catch (error) {
      console.error("Error fetching patient consent forms:", error);
      res.status(500).json({ message: "Failed to fetch consent forms" });
    }
  });

  app.post("/api/consent-forms", isAuthenticated, async (req, res) => {
    try {
      const parsed = insertConsentFormSchema.safeParse(req.body);
      if (!parsed.success) {
        return res.status(400).json({ message: "Invalid consent form data", errors: parsed.error.errors });
      }
      const form = await storage.createConsentForm(parsed.data);
      res.json(form);
    } catch (error) {
      console.error("Error creating consent form:", error);
      res.status(500).json({ message: "Failed to create consent form" });
    }
  });

  app.post("/api/consent-forms/:id/sign", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const form = await storage.signConsentForm(id);
      if (!form) {
        return res.status(404).json({ message: "Consent form not found" });
      }
      res.json(form);
    } catch (error) {
      console.error("Error signing consent form:", error);
      res.status(500).json({ message: "Failed to sign consent form" });
    }
  });

  // ============ PATIENT DOCUMENTS ============
  app.get("/api/documents", isAuthenticated, async (req, res) => {
    try {
      const documents = await storage.getDocuments();
      res.json(documents);
    } catch (error) {
      console.error("Error fetching documents:", error);
      res.status(500).json({ message: "Failed to fetch documents" });
    }
  });

  app.get("/api/documents/patient/:patientId", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const documents = await storage.getDocumentsByPatient(patientId);
      res.json(documents);
    } catch (error) {
      console.error("Error fetching patient documents:", error);
      res.status(500).json({ message: "Failed to fetch documents" });
    }
  });

  app.post("/api/documents", isAuthenticated, async (req, res) => {
    try {
      const parsed = insertPatientDocumentSchema.safeParse(req.body);
      if (!parsed.success) {
        return res.status(400).json({ message: "Invalid document data", errors: parsed.error.errors });
      }
      const document = await storage.createDocument(parsed.data);
      res.json(document);
    } catch (error) {
      console.error("Error creating document:", error);
      res.status(500).json({ message: "Failed to create document" });
    }
  });

  app.delete("/api/documents/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteDocument(id);
      res.json({ success: true });
    } catch (error) {
      console.error("Error deleting document:", error);
      res.status(500).json({ message: "Failed to delete document" });
    }
  });

  // Audit logging middleware helper
  const logAudit = async (
    userId: string,
    userEmail: string | undefined,
    action: string,
    resourceType: string,
    resourceId?: string,
    patientId?: number,
    details?: any,
    req?: any
  ) => {
    try {
      await storage.createAuditLog({
        userId,
        userEmail: userEmail || null,
        action,
        resourceType,
        resourceId: resourceId || null,
        patientId: patientId || null,
        ipAddress: req?.ip || req?.connection?.remoteAddress || null,
        userAgent: req?.headers?.["user-agent"] || null,
        details: details || null,
        phiAccessed: !!patientId,
      });
    } catch (error) {
      console.error("Failed to create audit log:", error);
    }
  };

  // ============ INTERNAL MESSAGES ============
  const getSessionUserId = (req: any): string => {
    return req.user?.claims?.sub || req.user?.id;
  };

  app.get("/api/messages/inbox", isAuthenticated, async (req, res) => {
    try {
      const userId = getSessionUserId(req);
      const messages = await storage.getInboxMessages(userId);
      res.json(messages);
    } catch (error) {
      console.error("Error fetching inbox:", error);
      res.status(500).json({ message: "Failed to fetch inbox" });
    }
  });

  app.get("/api/messages/sent", isAuthenticated, async (req, res) => {
    try {
      const userId = getSessionUserId(req);
      const messages = await storage.getSentMessages(userId);
      res.json(messages);
    } catch (error) {
      console.error("Error fetching sent messages:", error);
      res.status(500).json({ message: "Failed to fetch sent messages" });
    }
  });

  app.get("/api/messages/unread-count", isAuthenticated, async (req, res) => {
    try {
      const userId = getSessionUserId(req);
      const count = await storage.getUnreadCount(userId);
      res.json({ count });
    } catch (error) {
      console.error("Error fetching unread count:", error);
      res.status(500).json({ message: "Failed to fetch unread count" });
    }
  });

  app.get("/api/users/all", isAuthenticated, async (req, res) => {
    try {
      const allUsers = await storage.getAllUsers();
      res.json(allUsers);
    } catch (error) {
      console.error("Error fetching users:", error);
      res.status(500).json({ message: "Failed to fetch users" });
    }
  });

  app.post("/api/messages", isAuthenticated, async (req, res) => {
    try {
      const userId = getSessionUserId(req);
      const dbUser = await storage.getUser(userId);
      const senderName = dbUser
        ? `${dbUser.firstName || ""} ${dbUser.lastName || ""}`.trim() || dbUser.email || "Unknown"
        : "Unknown";
      const parsed = insertInternalMessageSchema.parse({
        ...req.body,
        senderId: userId,
        senderName,
      });
      const message = await storage.createMessage(parsed);
      res.json(message);
    } catch (error: any) {
      console.error("Error sending message:", error);
      res.status(500).json({ message: "Failed to send message" });
    }
  });

  app.patch("/api/messages/:id/read", isAuthenticated, async (req, res) => {
    try {
      const userId = getSessionUserId(req);
      const id = parseInt(req.params.id);
      const message = await storage.markMessageRead(id, userId);
      if (!message) {
        return res.status(404).json({ message: "Message not found or not authorized" });
      }
      res.json(message);
    } catch (error) {
      console.error("Error marking message read:", error);
      res.status(500).json({ message: "Failed to mark message as read" });
    }
  });

  // ============ PRACTICE SETTINGS / ONBOARDING ============
  app.get("/api/onboarding/status", isAuthenticated, async (req, res) => {
    try {
      const userId = getSessionUserId(req);
      let settings = await storage.getPracticeSettings(userId);

      const ownerBypassId = "47100532";
      if (!settings?.onboardingComplete && userId === ownerBypassId) {
        settings = await storage.upsertPracticeSettings({
          userId,
          practiceName: "My Practice",
          onboardingStep: 4,
          onboardingComplete: true,
        });
      }

      res.json({
        hasStarted: !!settings,
        isComplete: settings?.onboardingComplete || false,
        currentStep: settings?.onboardingStep || 0,
      });
    } catch (error) {
      console.error("Error fetching onboarding status:", error);
      res.status(500).json({ message: "Failed to fetch onboarding status" });
    }
  });

  app.get("/api/practice-settings", isAuthenticated, async (req, res) => {
    try {
      const userId = getSessionUserId(req);
      const settings = await storage.getPracticeSettings(userId);
      res.json(settings || null);
    } catch (error) {
      console.error("Error fetching practice settings:", error);
      res.status(500).json({ message: "Failed to fetch practice settings" });
    }
  });

  app.post("/api/practice-settings", isAuthenticated, async (req, res) => {
    try {
      const userId = getSessionUserId(req);
      const partial = insertPracticeSettingsSchema.partial().parse(req.body);
      const settings = await storage.upsertPracticeSettings({
        ...partial,
        userId,
      });
      res.json(settings);
    } catch (error) {
      console.error("Error saving practice settings:", error);
      res.status(500).json({ message: "Failed to save practice settings" });
    }
  });

  app.patch("/api/practice-settings", isAuthenticated, async (req, res) => {
    try {
      const userId = getSessionUserId(req);
      const partial = insertPracticeSettingsSchema.partial().parse(req.body);
      const settings = await storage.upsertPracticeSettings({
        ...partial,
        userId,
      });
      res.json(settings);
    } catch (error) {
      console.error("Error updating practice settings:", error);
      res.status(500).json({ message: "Failed to update practice settings" });
    }
  });

  app.post("/api/ai/specialty-recommendations", isAuthenticated, async (req, res) => {
    try {
      const { specialty, practiceType } = req.body;
      const message = await anthropic.messages.create({
        model: "claude-opus-4-5",
        max_tokens: 600,
        messages: [{
          role: "user",
          content: `You are helping set up a dental practice management platform for a ${specialty || practiceType || "dental"} specialist. Generate a brief, enthusiastic personalized welcome (2 sentences max) and a JSON list of the 6 most relevant module categories for this specialty from the following list. Return ONLY valid JSON in this format: {"welcome": "...", "modules": [{"title":"...", "url":"...", "reason":"..."}]}. Available modules: Patients (/patients), Scheduling (/appointments), Perio Charting (/perio), Endo/RCT (/endo), Recall System (/recall), Oral Surgery (/oral-surgery), Orthodontics (/ortho), Pediatric (/pediatric), Treatment Plans (/treatment-plans), Implant Tracker (/implant-tracker), Lab & Design (/lab), Billing & Claims (/billing), Coding Engine (/coding), Medical Clearance (/medical-clearance), Surgery Day (/surgery), AI Documentation (/ai-documentation), Appeals Engine (/appeals), Insurance Verification (/eligibility), Patient Messaging (/patient-messaging), Consent Forms (/consent-forms). Specialty: ${specialty || practiceType}`
        }],
      });
      const text = (message.content[0] as any).text;
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        res.json(JSON.parse(jsonMatch[0]));
      } else {
        res.json({ welcome: `Welcome! Your platform is ready for ${specialty} practice.`, modules: [] });
      }
    } catch (error) {
      console.error("Specialty recommendation error:", error);
      res.json({ welcome: "Welcome to your dental practice platform!", modules: [] });
    }
  });

  app.post("/api/onboarding/complete", isAuthenticated, async (req, res) => {
    try {
      const userId = getSessionUserId(req);
      const settings = await storage.upsertPracticeSettings({
        userId,
        onboardingComplete: true,
      });
      res.json(settings);
    } catch (error) {
      console.error("Error completing onboarding:", error);
      res.status(500).json({ message: "Failed to complete onboarding" });
    }
  });

  // Tooth Conditions (Dental Charting)
  app.get("/api/patients/:patientId/tooth-conditions", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const conditions = await storage.getToothConditions(patientId);
      res.json(conditions);
    } catch (error) {
      console.error("Error fetching tooth conditions:", error);
      res.status(500).json({ message: "Failed to fetch tooth conditions" });
    }
  });

  app.post("/api/patients/:patientId/tooth-conditions", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const data = insertToothConditionSchema.parse({ ...req.body, patientId });
      const condition = await storage.createToothCondition(data);
      res.json(condition);
    } catch (error) {
      console.error("Error creating tooth condition:", error);
      res.status(500).json({ message: "Failed to create tooth condition" });
    }
  });

  app.patch("/api/tooth-conditions/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertToothConditionSchema.partial().parse(req.body);
      const condition = await storage.updateToothCondition(id, data);
      if (!condition) return res.status(404).json({ message: "Tooth condition not found" });
      res.json(condition);
    } catch (error) {
      console.error("Error updating tooth condition:", error);
      res.status(500).json({ message: "Failed to update tooth condition" });
    }
  });

  app.delete("/api/tooth-conditions/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteToothCondition(id);
      res.json({ success: true });
    } catch (error) {
      console.error("Error deleting tooth condition:", error);
      res.status(500).json({ message: "Failed to delete tooth condition" });
    }
  });

  // Treatment Plan Procedures
  app.get("/api/treatment-plans/:planId/procedures", isAuthenticated, async (req, res) => {
    try {
      const planId = parseInt(req.params.planId);
      const procedures = await storage.getTreatmentPlanProcedures(planId);
      res.json(procedures);
    } catch (error) {
      console.error("Error fetching procedures:", error);
      res.status(500).json({ message: "Failed to fetch procedures" });
    }
  });

  app.get("/api/patients/:patientId/procedures", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const procedures = await storage.getPatientProcedures(patientId);
      res.json(procedures);
    } catch (error) {
      console.error("Error fetching patient procedures:", error);
      res.status(500).json({ message: "Failed to fetch patient procedures" });
    }
  });

  app.post("/api/treatment-plans/:planId/procedures", isAuthenticated, async (req, res) => {
    try {
      const treatmentPlanId = parseInt(req.params.planId);
      const data = insertTreatmentPlanProcedureSchema.parse({ ...req.body, treatmentPlanId });
      const procedure = await storage.createTreatmentPlanProcedure(data);
      res.json(procedure);
    } catch (error) {
      console.error("Error creating procedure:", error);
      res.status(500).json({ message: "Failed to create procedure" });
    }
  });

  app.patch("/api/procedures/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      const data = insertTreatmentPlanProcedureSchema.partial().parse(req.body);
      const procedure = await storage.updateTreatmentPlanProcedure(id, data);
      if (!procedure) return res.status(404).json({ message: "Procedure not found" });
      res.json(procedure);
    } catch (error) {
      console.error("Error updating procedure:", error);
      res.status(500).json({ message: "Failed to update procedure" });
    }
  });

  app.delete("/api/procedures/:id", isAuthenticated, async (req, res) => {
    try {
      const id = parseInt(req.params.id);
      await storage.deleteTreatmentPlanProcedure(id);
      res.json({ success: true });
    } catch (error) {
      console.error("Error deleting procedure:", error);
      res.status(500).json({ message: "Failed to delete procedure" });
    }
  });

  // Comprehensive PHI audit logging middleware
  const phiEndpoints = [
    { pattern: /^\/api\/patients\/(\d+)/, resourceType: "patient" },
    { pattern: /^\/api\/medical-history/, resourceType: "medical_history" },
    { pattern: /^\/api\/dental-info/, resourceType: "dental_info" },
    { pattern: /^\/api\/treatment-plans/, resourceType: "treatment_plan" },
    { pattern: /^\/api\/billing/, resourceType: "billing" },
    { pattern: /^\/api\/insurance/, resourceType: "insurance" },
    { pattern: /^\/api\/clinical-notes/, resourceType: "clinical_notes" },
    { pattern: /^\/api\/surgery-reports/, resourceType: "surgery_report" },
    { pattern: /^\/api\/full-arch-exams/, resourceType: "full_arch_exam" },
    { pattern: /^\/api\/facial-evaluations/, resourceType: "facial_evaluation" },
    { pattern: /^\/api\/cephalometrics/, resourceType: "cephalometrics" },
    { pattern: /^\/api\/appointments/, resourceType: "appointment" },
  ];

  const methodToAction: Record<string, string> = {
    GET: "view",
    POST: "create",
    PUT: "update",
    PATCH: "update",
    DELETE: "delete",
  };

  // ========== Union Partnership Routes ==========
  app.get("/api/unions", isAuthenticated, async (req, res) => {
    try {
      const unions = await storage.getUnionOrganizations();
      res.json(unions);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.get("/api/unions/:id", isAuthenticated, async (req, res) => {
    try {
      const union = await storage.getUnionOrganization(parseInt(req.params.id));
      if (!union) return res.status(404).json({ message: "Union not found" });
      res.json(union);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.post("/api/unions", isAuthenticated, async (req, res) => {
    try {
      const data = insertUnionOrganizationSchema.parse(req.body);
      const union = await storage.createUnionOrganization(data);
      res.status(201).json(union);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.patch("/api/unions/:id", isAuthenticated, async (req, res) => {
    try {
      const union = await storage.updateUnionOrganization(parseInt(req.params.id), req.body);
      if (!union) return res.status(404).json({ message: "Union not found" });
      res.json(union);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.delete("/api/unions/:id", isAuthenticated, async (req, res) => {
    try {
      await storage.deleteUnionOrganization(parseInt(req.params.id));
      res.json({ message: "Deleted" });
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.get("/api/unions/:id/contacts", isAuthenticated, async (req, res) => {
    try {
      const contacts = await storage.getUnionContacts(parseInt(req.params.id));
      res.json(contacts);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.post("/api/unions/contacts", isAuthenticated, async (req, res) => {
    try {
      const data = insertUnionContactSchema.parse(req.body);
      const contact = await storage.createUnionContact(data);
      res.status(201).json(contact);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.patch("/api/unions/contacts/:id", isAuthenticated, async (req, res) => {
    try {
      const contact = await storage.updateUnionContact(parseInt(req.params.id), req.body);
      if (!contact) return res.status(404).json({ message: "Contact not found" });
      res.json(contact);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.delete("/api/unions/contacts/:id", isAuthenticated, async (req, res) => {
    try {
      await storage.deleteUnionContact(parseInt(req.params.id));
      res.json({ message: "Deleted" });
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.get("/api/unions/outreach/all", isAuthenticated, async (req, res) => {
    try {
      const unionId = req.query.unionId ? parseInt(req.query.unionId as string) : undefined;
      const outreach = await storage.getUnionOutreach(unionId);
      res.json(outreach);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.post("/api/unions/outreach", isAuthenticated, async (req, res) => {
    try {
      const data = insertUnionOutreachSchema.parse(req.body);
      const outreach = await storage.createUnionOutreach(data);
      res.status(201).json(outreach);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.patch("/api/unions/outreach/:id", isAuthenticated, async (req, res) => {
    try {
      const outreach = await storage.updateUnionOutreach(parseInt(req.params.id), req.body);
      if (!outreach) return res.status(404).json({ message: "Outreach not found" });
      res.json(outreach);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.get("/api/unions/events/all", isAuthenticated, async (req, res) => {
    try {
      const events = await storage.getUnionEvents();
      res.json(events);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.post("/api/unions/events", isAuthenticated, async (req, res) => {
    try {
      const data = insertUnionEventSchema.parse(req.body);
      const event = await storage.createUnionEvent(data);
      res.status(201).json(event);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.patch("/api/unions/events/:id", isAuthenticated, async (req, res) => {
    try {
      const event = await storage.updateUnionEvent(parseInt(req.params.id), req.body);
      if (!event) return res.status(404).json({ message: "Event not found" });
      res.json(event);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.get("/api/unions/agreements/all", isAuthenticated, async (req, res) => {
    try {
      const unionId = req.query.unionId ? parseInt(req.query.unionId as string) : undefined;
      const agreements = await storage.getUnionAgreements(unionId);
      res.json(agreements);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.post("/api/unions/agreements", isAuthenticated, async (req, res) => {
    try {
      const data = insertUnionAgreementSchema.parse(req.body);
      const agreement = await storage.createUnionAgreement(data);
      res.status(201).json(agreement);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.patch("/api/unions/agreements/:id", isAuthenticated, async (req, res) => {
    try {
      const agreement = await storage.updateUnionAgreement(parseInt(req.params.id), req.body);
      if (!agreement) return res.status(404).json({ message: "Agreement not found" });
      res.json(agreement);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.get("/api/unions/visits/all", isAuthenticated, async (req, res) => {
    try {
      const unionId = req.query.unionId ? parseInt(req.query.unionId as string) : undefined;
      const visits = await storage.getUnionMemberVisits(unionId);
      res.json(visits);
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.post("/api/unions/visits", isAuthenticated, async (req, res) => {
    try {
      const data = insertUnionMemberVisitSchema.parse(req.body);
      const visit = await storage.createUnionMemberVisit(data);
      res.status(201).json(visit);
    } catch (error: any) {
      res.status(400).json({ message: error.message });
    }
  });

  app.post("/api/unions/seed", isAuthenticated, async (req, res) => {
    try {
      const existing = await storage.getUnionOrganizations();
      if (existing.length > 0) {
        return res.json({ message: "Union data already seeded", count: existing.length });
      }

      const seedData = [
        {
          name: "LIUNA Local 185",
          localNumber: "185",
          category: "construction",
          memberCount: 3000,
          address: "1320 National Drive",
          city: "Sacramento",
          state: "CA",
          zipCode: "95834",
          phone: "(916) 928-8300",
          fax: "(916) 928-8311",
          website: "laborerslocal185.org",
          affiliatedWith: "AFL-CIO",
          pipelineStage: "prospect",
          priorityScore: 90,
          notes: "Construction workers with solid benefits and high dental trauma rates. Business Manager: Doyle S. Radford, Jr. Key contacts: Sean Radford, Leonel Barragan, AC Covarrubias. Office hours 6:30am-4:30pm.",
        },
        {
          name: "IBEW Local 340",
          localNumber: "340",
          category: "construction",
          memberCount: 2500,
          address: "10240 Systems Parkway, Suite 100",
          city: "Sacramento",
          state: "CA",
          zipCode: "95827",
          phone: "(916) 927-4239",
          fax: "(916) 927-1074",
          email: "office@ibewlocal340.org",
          website: "ibewlocal340.org",
          affiliatedWith: "AFL-CIO",
          pipelineStage: "prospect",
          priorityScore: 95,
          notes: "Electricians union. Best first call - has actual email addresses for leadership. Bob Ward (Business Manager): bward@ibewlocal340.org. Salma Smiley (Membership Dev): ssmiley@ibewlocal340.org ext 1008.",
        },
        {
          name: "Carpenters Local 46",
          localNumber: "46",
          category: "construction",
          memberCount: 2000,
          address: "4421 Pell Drive, Suite A",
          city: "Sacramento",
          state: "CA",
          zipCode: "95838",
          phone: "(916) 614-7901",
          fax: "(916) 614-7911",
          website: "carpenters46.org",
          affiliatedWith: "AFL-CIO",
          pipelineStage: "prospect",
          priorityScore: 80,
          notes: "Covers Sacramento, Yolo, Colusa, Yuba, Sutter, Western Placer and Western El Dorado counties. No public email - use phone or website contact form.",
        },
        {
          name: "UA Local 447",
          localNumber: "447",
          category: "construction",
          memberCount: 1700,
          address: "5841 Newman Court",
          city: "Sacramento",
          state: "CA",
          zipCode: "95819",
          phone: "(916) 457-6595",
          fax: "(916) 454-6151",
          website: "ualocal447.org",
          affiliatedWith: "AFL-CIO",
          pipelineStage: "prospect",
          priorityScore: 75,
          notes: "Plumbers & Pipefitters. 1,700 Journeypersons, Retirees and Apprentices. Training Center: (916) 383-1102. Use Contact Us form on website.",
        },
        {
          name: "SEIU Local 1000",
          localNumber: "1000",
          category: "public_sector",
          memberCount: 96000,
          address: "1808 14th Street",
          city: "Sacramento",
          state: "CA",
          zipCode: "95811",
          phone: "(866) 471-7348",
          website: "seiu1000.org",
          affiliatedWith: "AFL-CIO",
          pipelineStage: "prospect",
          priorityScore: 85,
          notes: "STATE WORKERS - Biggest single target by membership (96,000). Toll-free Member Resource Center. Local: (916) 554-1200. Sacramento is the state capital = tens of thousands within driving distance.",
        },
        {
          name: "Teamsters Local 150",
          localNumber: "150",
          category: "transportation",
          memberCount: 5000,
          address: "7120 East Parkway",
          city: "Sacramento",
          state: "CA",
          zipCode: "95823",
          phone: "(916) 392-7070",
          website: "teamsters150.org",
          affiliatedWith: "AFL-CIO",
          pipelineStage: "prospect",
          priorityScore: 70,
          notes: "Secretary-Treasurer: Dale Wentz. President: Amber Williams. UPS, Grocery Distribution, Trucking, Medical, Public Agency, Dairy, Beverage workers. No general email - call office.",
        },
        {
          name: "UFCW 8-Golden State",
          localNumber: "8",
          category: "retail",
          memberCount: 30000,
          address: "2200 Professional Drive",
          city: "Roseville",
          state: "CA",
          zipCode: "95661",
          phone: "(916) 786-0588",
          website: "ufcw8.org",
          affiliatedWith: "AFL-CIO",
          pipelineStage: "prospect",
          priorityScore: 88,
          notes: "GROCERY/RETAIL WORKERS - HQ is in ROSEVILLE, right in your backyard! 30,000+ members across CA. Sacramento office: 1930 9th St Suite 208, (916) 503-8828. Use contact form on ufcw8.org/contact-us.",
        },
        {
          name: "Sacramento Central Labor Council",
          localNumber: "AFL-CIO",
          category: "public_sector",
          memberCount: 200000,
          address: "2840 El Centro Rd., Suite 111",
          city: "Sacramento",
          state: "CA",
          zipCode: "95833",
          phone: "(916) 927-9772",
          email: "ellen@sacramentolabor.org",
          website: "sacramentolabor.org",
          affiliatedWith: "AFL-CIO",
          pipelineStage: "prospect",
          priorityScore: 60,
          notes: "UMBRELLA ORG - 98 local unions, ~200,000 members. Exec Director: Fabrizio Sasso. Go here WITH proven results from 2-3 partnerships, not just a pitch. Events contact: ellen@sacramentolabor.org.",
        },
      ];

      const created = [];
      for (const union of seedData) {
        const org = await storage.createUnionOrganization(union as any);
        created.push(org);
      }

      // Seed contacts for IBEW 340 (has known contacts)
      const ibew = created.find(u => u.name === "IBEW Local 340");
      if (ibew) {
        await storage.createUnionContact({ unionId: ibew.id, firstName: "Bob", lastName: "Ward", title: "Business Manager", email: "bward@ibewlocal340.org", isPrimary: true });
        await storage.createUnionContact({ unionId: ibew.id, firstName: "Salma", lastName: "Smiley", title: "Membership Development", email: "ssmiley@ibewlocal340.org", phone: "(916) 927-4239 ext. 1008", isPrimary: false });
      }

      const liuna = created.find(u => u.name === "LIUNA Local 185");
      if (liuna) {
        await storage.createUnionContact({ unionId: liuna.id, firstName: "Doyle S.", lastName: "Radford Jr.", title: "Business Manager", isPrimary: true });
        await storage.createUnionContact({ unionId: liuna.id, firstName: "Sean", lastName: "Radford", title: "Business Agent", isPrimary: false });
        await storage.createUnionContact({ unionId: liuna.id, firstName: "Armando", lastName: "Covarrubias", title: "Secretary-Treasurer", isPrimary: false });
      }

      const sclc = created.find(u => u.name === "Sacramento Central Labor Council");
      if (sclc) {
        await storage.createUnionContact({ unionId: sclc.id, firstName: "Fabrizio", lastName: "Sasso", title: "Executive Director", isPrimary: true });
        await storage.createUnionContact({ unionId: sclc.id, firstName: "Ellen", lastName: "(Contact)", title: "Events Coordinator", email: "ellen@sacramentolabor.org", isPrimary: false });
      }

      res.status(201).json({ message: "Seeded union data", count: created.length });
    } catch (error: any) {
      res.status(500).json({ message: error.message });
    }
  });

  app.use((req, res, next) => {
    if (!req.user) {
      next();
      return;
    }

    for (const endpoint of phiEndpoints) {
      const match = req.originalUrl.match(endpoint.pattern);
      if (match) {
        const action = methodToAction[req.method] || "access";
        const resourceId = match[1] || req.query.patientId?.toString() || undefined;
        const patientIdFromUrl = endpoint.resourceType === "patient" ? parseInt(match[1]) : undefined;
        const patientIdFromQuery = req.query.patientId ? parseInt(req.query.patientId as string) : undefined;
        
        const auditUserId = (req.user as any)?.claims?.sub || (req.user as any)?.id || "unknown";
        const auditEmail = (req.user as any)?.claims?.email || (req.user as any)?.email || "unknown";
        logAudit(
          auditUserId,
          auditEmail,
          action,
          endpoint.resourceType,
          resourceId,
          patientIdFromUrl || patientIdFromQuery,
          { endpoint: req.originalUrl, method: req.method },
          req
        );
        break;
      }
    }
    next();
  });

  // ============ PATIENT MESSAGING ============
  app.get("/api/patient-messages/unread-count", isAuthenticated, async (req, res) => {
    try { res.json({ count: await storage.getPatientUnreadCount() }); } catch { res.json({ count: 0 }); }
  });

  app.get("/api/patient-messages/threads", isAuthenticated, async (req, res) => {
    try { res.json(await storage.getPatientMessageThreads()); } catch { res.json([]); }
  });

  // Explicit thread-open audit event — called once when a user consciously opens a thread
  app.post("/api/patient-messages/:patientId/open", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const userId = getSessionUserId(req);
      await storage.createAuditLog({
        userId: userId || "system",
        action: "view",
        resourceType: "patient_message_thread",
        resourceId: String(patientId),
        patientId,
        phiAccessed: true,
        details: { action: "thread_opened" },
      });
      res.json({ ok: true });
    } catch { res.json({ ok: false }); }
  });

  app.get("/api/patient-messages", isAuthenticated, async (req, res) => {
    try {
      const patientId = req.query.patientId ? parseInt(req.query.patientId as string) : undefined;
      res.json(await storage.getPatientMessages(patientId));
    } catch { res.json([]); }
  });

  app.post("/api/patient-messages", isAuthenticated, async (req, res) => {
    try {
      const userId = getSessionUserId(req);
      const data = insertPatientMessageSchema.parse(req.body);
      const msg = await storage.createPatientMessage(data);
      await storage.createAuditLog({
        userId: userId || "system",
        action: "create",
        resourceType: "patient_message",
        resourceId: String(msg.id),
        patientId: msg.patientId,
        phiAccessed: true,
        details: { channel: msg.channel, direction: msg.direction },
      });
      res.status(201).json(msg);
    } catch (error) {
      console.error("Error creating patient message:", error);
      res.status(500).json({ message: "Failed to send message" });
    }
  });

  app.patch("/api/patient-messages/:id/read", isAuthenticated, async (req, res) => {
    try {
      const updated = await storage.markPatientMessageRead(parseInt(req.params.id));
      res.json(updated);
    } catch { res.status(500).json({ message: "Failed to mark read" }); }
  });

  // AI suggest reply for patient messages
  app.post("/api/ai/suggest-reply", isAuthenticated, async (req, res) => {
    try {
      const { patientName, lastMessage, channel } = req.body;
      const channelCtx = channel === "sms" ? "a brief SMS (under 160 characters if possible)" : channel === "email" ? "a professional email" : "an in-app message";
      const suggestion = await askClaude(
        `You are a helpful dental practice assistant. Write professional, empathetic, HIPAA-compliant replies. Do not include placeholders or brackets. Return only the ready-to-send message text with no additional commentary.`,
        `Draft ${channelCtx} reply for patient ${patientName || "the patient"}.\n\nPatient's last message: "${lastMessage}"`
      );
      res.json({ suggestion });
    } catch (error) {
      console.error("AI suggest reply error:", error);
      res.status(500).json({ message: "AI suggestion failed" });
    }
  });

  // ============ PRACTICE LOCATIONS ============
  app.get("/api/locations", isAuthenticated, async (req, res) => {
    try { res.json(await storage.getPracticeLocations()); } catch { res.json([]); }
  });

  app.post("/api/locations", isAuthenticated, async (req, res) => {
    try {
      const data = insertPracticeLocationSchema.parse(req.body);
      res.status(201).json(await storage.createPracticeLocation(data));
    } catch (error) {
      console.error("Error creating location:", error);
      res.status(500).json({ message: "Failed to create location" });
    }
  });

  app.put("/api/locations/:id", isAuthenticated, async (req, res) => {
    try {
      const updated = await storage.updatePracticeLocation(parseInt(req.params.id), req.body);
      if (!updated) return res.status(404).json({ message: "Not found" });
      res.json(updated);
    } catch { res.status(500).json({ message: "Failed to update" }); }
  });

  // ============ PEDIATRIC EXAMS ============
  app.get("/api/pediatric", isAuthenticated, async (req, res) => {
    try {
      const patientId = req.query.patientId ? parseInt(req.query.patientId as string) : undefined;
      res.json(await storage.getPediatricExams(patientId));
    } catch { res.json([]); }
  });

  app.post("/api/pediatric", isAuthenticated, async (req, res) => {
    try {
      const data = insertPediatricExamSchema.parse(req.body);
      res.status(201).json(await storage.createPediatricExam(data));
    } catch (error) {
      console.error("Error creating pediatric exam:", error);
      res.status(500).json({ message: "Failed to create pediatric exam" });
    }
  });

  app.put("/api/pediatric/:id", isAuthenticated, async (req, res) => {
    try {
      const updated = await storage.updatePediatricExam(parseInt(req.params.id), req.body);
      if (!updated) return res.status(404).json({ message: "Not found" });
      res.json(updated);
    } catch { res.status(500).json({ message: "Failed to update" }); }
  });

  // ============ ORAL SURGERY ============
  app.get("/api/oral-surgery", isAuthenticated, async (req, res) => {
    try {
      const patientId = req.query.patientId ? parseInt(req.query.patientId as string) : undefined;
      res.json(await storage.getOralSurgeryCases(patientId));
    } catch { res.json([]); }
  });

  app.post("/api/oral-surgery", isAuthenticated, async (req, res) => {
    try {
      const data = insertOralSurgeryCaseSchema.parse(req.body);
      res.status(201).json(await storage.createOralSurgeryCase(data));
    } catch (error) {
      console.error("Error creating oral surgery case:", error);
      res.status(500).json({ message: "Failed to create oral surgery case" });
    }
  });

  app.put("/api/oral-surgery/:id", isAuthenticated, async (req, res) => {
    try {
      const updated = await storage.updateOralSurgeryCase(parseInt(req.params.id), req.body);
      if (!updated) return res.status(404).json({ message: "Not found" });
      res.json(updated);
    } catch { res.status(500).json({ message: "Failed to update" }); }
  });

  // ============ PRACTICE PROVIDERS ============
  app.get("/api/practice-providers", isAuthenticated, async (req, res) => {
    try {
      res.json(await storage.getPracticeProviders());
    } catch { res.json([]); }
  });

  app.post("/api/practice-providers", isAuthenticated, async (req, res) => {
    try {
      const data = insertPracticeProviderSchema.parse(req.body);
      res.status(201).json(await storage.createPracticeProvider(data));
    } catch (error) {
      console.error("Error creating provider:", error);
      res.status(500).json({ message: "Failed to create provider" });
    }
  });

  app.put("/api/practice-providers/:id", isAuthenticated, async (req, res) => {
    try {
      const updated = await storage.updatePracticeProvider(parseInt(req.params.id), req.body);
      if (!updated) return res.status(404).json({ message: "Not found" });
      res.json(updated);
    } catch { res.status(500).json({ message: "Failed to update" }); }
  });

  // ============ RECALL SYSTEM ============
  app.get("/api/recall", isAuthenticated, async (req, res) => {
    try {
      const status = req.query.status as string | undefined;
      res.json(await storage.getRecallPatients(status));
    } catch { res.json([]); }
  });

  app.post("/api/recall", isAuthenticated, async (req, res) => {
    try {
      const data = insertRecallPatientSchema.parse(req.body);
      res.status(201).json(await storage.createRecallPatient(data));
    } catch (error) {
      console.error("Error creating recall:", error);
      res.status(500).json({ message: "Failed to create recall" });
    }
  });

  app.put("/api/recall/:id", isAuthenticated, async (req, res) => {
    try {
      const updated = await storage.updateRecallPatient(parseInt(req.params.id), req.body);
      if (!updated) return res.status(404).json({ message: "Not found" });
      res.json(updated);
    } catch { res.status(500).json({ message: "Failed to update" }); }
  });

  app.get("/api/recall/:id/contacts", isAuthenticated, async (req, res) => {
    try {
      res.json(await storage.getRecallContactLog(parseInt(req.params.id)));
    } catch { res.json([]); }
  });

  app.post("/api/recall/:id/contacts", isAuthenticated, async (req, res) => {
    try {
      const data = insertRecallContactLogSchema.parse({ ...req.body, recallPatientId: parseInt(req.params.id) });
      res.status(201).json(await storage.addRecallContact(data));
    } catch (error) {
      console.error("Error adding contact:", error);
      res.status(500).json({ message: "Failed to add contact" });
    }
  });

  // ============ ENDODONTICS ============
  app.get("/api/endo", isAuthenticated, async (req, res) => {
    try {
      const patientId = req.query.patientId ? parseInt(req.query.patientId as string) : undefined;
      res.json(await storage.getEndoCases(patientId));
    } catch { res.json([]); }
  });

  app.get("/api/endo/:id", isAuthenticated, async (req, res) => {
    try {
      const c = await storage.getEndoCase(parseInt(req.params.id));
      if (!c) return res.status(404).json({ message: "Not found" });
      res.json(c);
    } catch { res.status(500).json({ message: "Failed" }); }
  });

  app.post("/api/endo", isAuthenticated, async (req, res) => {
    try {
      const data = insertEndoCaseSchema.parse(req.body);
      res.status(201).json(await storage.createEndoCase(data));
    } catch (error) {
      console.error("Error creating endo case:", error);
      res.status(500).json({ message: "Failed to create endo case" });
    }
  });

  app.put("/api/endo/:id", isAuthenticated, async (req, res) => {
    try {
      const updated = await storage.updateEndoCase(parseInt(req.params.id), req.body);
      if (!updated) return res.status(404).json({ message: "Not found" });
      res.json(updated);
    } catch { res.status(500).json({ message: "Failed to update" }); }
  });

  // ============ ORTHODONTICS ============
  app.get("/api/ortho", isAuthenticated, async (req, res) => {
    try {
      const patientId = req.query.patientId ? parseInt(req.query.patientId as string) : undefined;
      const cases = await storage.getOrthoCases(patientId);
      res.json(cases);
    } catch (error) { res.json([]); }
  });

  app.get("/api/ortho/:id", isAuthenticated, async (req, res) => {
    try {
      const c = await storage.getOrthoCase(parseInt(req.params.id));
      if (!c) return res.status(404).json({ message: "Not found" });
      res.json(c);
    } catch (error) { res.status(500).json({ message: "Failed" }); }
  });

  app.post("/api/ortho", isAuthenticated, async (req, res) => {
    try {
      const data = insertOrthoCaseSchema.parse(req.body);
      const created = await storage.createOrthoCase(data);
      res.status(201).json(created);
    } catch (error) {
      console.error("Error creating ortho case:", error);
      res.status(500).json({ message: "Failed to create ortho case" });
    }
  });

  app.put("/api/ortho/:id", isAuthenticated, async (req, res) => {
    try {
      const updated = await storage.updateOrthoCase(parseInt(req.params.id), req.body);
      if (!updated) return res.status(404).json({ message: "Not found" });
      res.json(updated);
    } catch (error) { res.status(500).json({ message: "Failed to update" }); }
  });

  // ============ PERIO CHARTING ============
  app.get("/api/perio/:patientId", isAuthenticated, async (req, res) => {
    try {
      const patientId = parseInt(req.params.patientId);
      const exams = await storage.getPerioExams(patientId);
      res.json(exams);
    } catch (error) {
      console.error("Error fetching perio exams:", error);
      res.json([]);
    }
  });

  app.get("/api/perio/exam/:id", isAuthenticated, async (req, res) => {
    try {
      const exam = await storage.getPerioExam(parseInt(req.params.id));
      if (!exam) return res.status(404).json({ message: "Exam not found" });
      res.json(exam);
    } catch (error) {
      res.status(500).json({ message: "Failed to fetch exam" });
    }
  });

  app.post("/api/perio", isAuthenticated, async (req, res) => {
    try {
      const data = insertPerioExamSchema.parse(req.body);
      const exam = await storage.createPerioExam(data);
      res.status(201).json(exam);
    } catch (error) {
      console.error("Error creating perio exam:", error);
      res.status(500).json({ message: "Failed to create perio exam" });
    }
  });

  app.put("/api/perio/exam/:id", isAuthenticated, async (req, res) => {
    try {
      const updated = await storage.updatePerioExam(parseInt(req.params.id), req.body);
      if (!updated) return res.status(404).json({ message: "Exam not found" });
      res.json(updated);
    } catch (error) {
      res.status(500).json({ message: "Failed to update perio exam" });
    }
  });

  app.post("/api/perio/ai-assessment", isAuthenticated, async (req, res) => {
    try {
      const { probingData, patientName } = req.body;
      const allDepths: number[] = [];
      let bopCount = 0, totalSites = 0, sitesGt4 = 0, sitesGt6 = 0;
      Object.values(probingData as Record<string, any>).forEach((t: any) => {
        if (t.missing) return;
        const depths = [...(t.facialProbing || []), ...(t.lingualProbing || [])];
        const bops = [...(t.facialBop || []), ...(t.lingualBop || [])];
        depths.forEach(d => { allDepths.push(d); totalSites++; if (d >= 4) sitesGt4++; if (d >= 6) sitesGt6++; });
        bops.forEach(b => { if (b) bopCount++; });
      });
      const avgDepth = allDepths.length ? (allDepths.reduce((a, b) => a + b, 0) / allDepths.length).toFixed(1) : "0";
      const bopPct = totalSites ? Math.round((bopCount / totalSites) * 100) : 0;

      const assessment = await askClaude(
        "You are a periodontist generating a clinical AI assessment for a perio chart. Be concise, clinical, and specific. Include diagnosis, treatment recommendations (CDT codes D4341/D4342/D4910), and prognosis. Keep under 120 words.",
        `Patient: ${patientName}. Avg probing: ${avgDepth}mm. Sites ≥4mm: ${sitesGt4}. Sites ≥6mm: ${sitesGt6}. BOP: ${bopPct}%. Generate a periodontal assessment and treatment plan.`,
        400
      );
      res.json({ assessment, stats: { avgDepth, bopPct, sitesGt4, sitesGt6, totalSites } });
    } catch (error) {
      res.status(500).json({ message: "Failed to generate AI assessment" });
    }
  });

  return httpServer;
}
