import type { Express } from "express";
import { createServer, type Server } from "http";
import { storage } from "./storage";
import { setupAuth, isAuthenticated } from "./replit_integrations/auth/replitAuth";
import { registerAuthRoutes } from "./replit_integrations/auth/routes";
import { registerChatRoutes } from "./replit_integrations/chat";
import OpenAI from "openai";
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
} from "@shared/schema";

const openai = new OpenAI({
  apiKey: process.env.AI_INTEGRATIONS_OPENAI_API_KEY,
  baseURL: process.env.AI_INTEGRATIONS_OPENAI_BASE_URL,
});

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
      const claim = await storage.updateBillingClaim(id, data);
      if (!claim) {
        return res.status(404).json({ message: "Claim not found" });
      }
      res.json(claim);
    } catch (error: any) {
      console.error("Error updating claim:", error);
      res.status(400).json({ message: error.message || "Failed to update claim" });
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

      const response = await openai.chat.completions.create({
        model: "gpt-5.2",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content },
        ],
        max_completion_tokens: 1500,
      });

      const assistantResponse = response.choices[0]?.message?.content || "I apologize, I couldn't generate a response. Please try again.";

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

      const response = await openai.chat.completions.create({
        model: "gpt-5.2",
        messages: [
          {
            role: "system",
            content: "You are an expert dental implant treatment planning assistant. Provide detailed, clinically accurate recommendations.",
          },
          { role: "user", content: prompt },
        ],
        max_completion_tokens: 2000,
      });

      const diagnosis = response.choices[0]?.message?.content || "";
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

      const response = await openai.chat.completions.create({
        model: "gpt-5.2",
        messages: [
          {
            role: "system",
            content: "You are an expert at writing medical necessity letters for dental implant procedures. Create compelling, evidence-based letters.",
          },
          { role: "user", content: prompt },
        ],
        max_completion_tokens: 2000,
      });

      const letter = response.choices[0]?.message?.content || "";
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

      const response = await openai.chat.completions.create({
        model: "gpt-5.2",
        messages: [
          {
            role: "system",
            content: "You are an expert at writing insurance appeal letters for dental procedures. Create persuasive, evidence-based appeals.",
          },
          { role: "user", content: prompt },
        ],
        max_completion_tokens: 2000,
      });

      const letter = response.choices[0]?.message?.content || "";
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
      
      const response = await openai.chat.completions.create({
        model: "gpt-5.2",
        messages: [
          {
            role: "system",
            content: `You are an expert dental billing coder specializing in full arch dental implants. Your role is to suggest the most appropriate CDT codes, CPT codes (for medical insurance cross-coding), and ICD-10 diagnosis codes that maximize insurance approval rates while maintaining compliance.

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

Return your response as JSON with this structure:
{
  "suggestedCDT": [{"code": "D6010", "description": "...", "fee": 2200}],
  "suggestedCPT": [{"code": "21248", "description": "...", "medicalCrossCode": true}],
  "suggestedICD10": [{"code": "K08.1", "description": "...", "priority": 1}],
  "medicalNecessityNotes": "...",
  "confidenceScore": 95,
  "warnings": []
}`
          },
          {
            role: "user",
            content: `Suggest appropriate billing codes for:
Diagnosis: ${diagnosis || "Not specified"}
Procedures: ${procedures || "Not specified"}
Clinical Notes: ${clinicalNotes || "Not provided"}`
          }
        ],
        response_format: { type: "json_object" },
        max_tokens: 1500
      });

      const suggestions = JSON.parse(response.choices[0]?.message?.content || "{}");
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

  return httpServer;
}
