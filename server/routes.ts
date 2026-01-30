import type { Express } from "express";
import { createServer, type Server } from "http";
import { storage } from "./storage";
import { setupAuth, isAuthenticated } from "./replit_integrations/auth/replitAuth";
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

  return httpServer;
}
