import { db } from "../server/db";
import {
  patients,
  medicalHistory,
  dentalInfo,
  insurance,
  treatmentPlans,
  appointments,
  billingClaims,
  consentForms,
  patientDocuments,
} from "../shared/schema";

async function seedThomasZ() {
  console.log("Creating simulation patient: Thomas Z...");

  // 1. Create patient Thomas Zimmerman
  const [thomas] = await db
    .insert(patients)
    .values({
      firstName: "Thomas",
      lastName: "Zimmerman",
      dateOfBirth: "1965-03-15",
      gender: "male",
      email: "thomas.zimmerman@email.com",
      phone: "(555) 234-5678",
      address: "1425 Oak Valley Drive",
      city: "Denver",
      state: "CO",
      zipCode: "80202",
      emergencyContact: "Sarah Zimmerman",
      emergencyPhone: "(555) 234-9999",
      preferredContact: "phone",
      notes: "Full arch implant candidate - All-on-4 upper arch. Referred by Dr. Martinez.",
    })
    .returning();

  console.log(`✓ Created patient: Thomas Z (ID: ${thomas.id})`);

  // 2. Add medical history
  await db.insert(medicalHistory).values({
    patientId: thomas.id,
    conditions: ["Controlled Hypertension", "Mild Sleep Apnea"],
    allergies: ["Latex"],
    medications: ["Lisinopril 10mg daily", "CPAP at night"],
    smokingStatus: "Former smoker - quit 15 years ago",
    bloodPressure: "128/82",
    heartRate: "70 bpm",
    weight: "185 lbs",
    height: "5'11\"",
  });
  console.log("✓ Added medical history");

  // 3. Add dental info
  await db.insert(dentalInfo).values({
    patientId: thomas.id,
    chiefComplaint: "Failing upper dentition with multiple loose teeth. Difficulty eating and embarrassed to smile.",
    dentalHistory: "Multiple failed root canals, periodontal disease, wearing upper partial denture",
    missingTeeth: ["3", "5", "12", "14", "15"],
    existingImplants: [],
    previousDentalWork: "Crown on #7, RCT #8 and #9, upper partial denture",
    oralHygieneHabits: "Brush 2x daily, struggles with flossing due to partial",
    lastDentalVisit: "2025-09-15",
  });
  console.log("✓ Added dental info");

  // 4. Add insurance (medical and dental)
  await db.insert(insurance).values({
    patientId: thomas.id,
    insuranceType: "medical",
    providerName: "Aetna PPO",
    policyNumber: "AET-789456123",
    groupNumber: "GRP-5500",
    subscriberName: "Thomas Zimmerman",
    subscriberDob: "1965-03-15",
    relationship: "Self",
    coveragePercentage: 80,
    annualMaximum: "50000",
    deductible: "500",
    remainingBenefit: "49500",
    priorAuthRequired: true,
  });
  await db.insert(insurance).values({
    patientId: thomas.id,
    insuranceType: "dental",
    providerName: "Delta Dental Premier",
    policyNumber: "DDI-456789",
    groupNumber: "DDG-2200",
    subscriberName: "Thomas Zimmerman",
    subscriberDob: "1965-03-15",
    relationship: "Self",
    coveragePercentage: 50,
    annualMaximum: "2500",
    deductible: "100",
    remainingBenefit: "2400",
    priorAuthRequired: false,
  });
  console.log("✓ Added insurance info (medical + dental)");

  // 5. Create All-on-4 Treatment Plan
  const [treatmentPlan] = await db
    .insert(treatmentPlans)
    .values({
      patientId: thomas.id,
      planName: "Full Arch Upper - All-on-4 Implant Reconstruction",
      status: "approved",
      diagnosis: "K08.1 - Complete loss of teeth due to periodontal disease, upper arch",
      diagnosisCode: "K08.1",
      procedures: [
        { code: "D7210", description: "Extraction surgical - 8 teeth", quantity: 8, fee: 285 },
        { code: "D6010", description: "Surgical implant placement", quantity: 4, fee: 2200 },
        { code: "D7953", description: "Bone graft - socket preservation", quantity: 4, fee: 875 },
        { code: "D6114", description: "Implant supported fixed denture", quantity: 1, fee: 28500 },
        { code: "D6056", description: "Prefabricated abutment", quantity: 4, fee: 650 },
        { code: "D9243", description: "IV sedation", quantity: 1, fee: 850 },
      ],
      totalCost: "47330",
      insuranceCoverage: "8500",
      patientResponsibility: "38830",
      notes: "All-on-4 upper arch. Patient motivated and medically cleared. Excellent bone density on CBCT. Proceeding with immediate load protocol.",
      priorAuthStatus: "approved",
      priorAuthNumber: "PA-2026-TZ-001",
    })
    .returning();
  console.log(`✓ Created treatment plan: ${treatmentPlan.planName}`);

  // 6. Create consent forms
  const consentTypes = [
    { type: "general_treatment", title: "General Treatment Consent" },
    { type: "implant_surgery", title: "Dental Implant Surgery Consent" },
    { type: "sedation", title: "IV Sedation/Anesthesia Consent" },
    { type: "financial", title: "Financial Agreement & Payment Plan" },
    { type: "hipaa", title: "HIPAA Privacy Authorization" },
  ];

  for (const consent of consentTypes) {
    await db.insert(consentForms).values({
      patientId: thomas.id,
      formType: consent.type,
      title: consent.title,
      content: `Standard ${consent.title} form content for Thomas Zimmerman...`,
      status: "signed",
      signedAt: new Date(),
      signatureData: "Thomas Zimmerman - Digital Signature",
    });
  }
  console.log("✓ Created 5 consent forms (all signed)");

  // 7. Create appointments
  const today = new Date();
  
  const createApptTime = (daysOffset: number, hour: number, durationMins: number) => {
    const start = new Date(today.getTime() + daysOffset * 24 * 60 * 60 * 1000);
    start.setHours(hour, 0, 0, 0);
    const end = new Date(start.getTime() + durationMins * 60 * 1000);
    return { start, end };
  };

  const appointments_data = [
    {
      patientId: thomas.id,
      treatmentPlanId: treatmentPlan.id,
      appointmentType: "consultation",
      title: "Initial Consultation - All-on-4",
      description: "Initial consultation. Discussed All-on-4 options. Patient very interested.",
      ...createApptTime(-14, 10, 60),
      providerName: "Dr. Sarah Mitchell",
      status: "completed",
      location: "Operatory 1",
      notes: "Patient motivated, good candidate for All-on-4.",
    },
    {
      patientId: thomas.id,
      treatmentPlanId: treatmentPlan.id,
      appointmentType: "imaging",
      title: "CBCT Scan",
      description: "CBCT scan completed. Excellent bone volume for All-on-4.",
      ...createApptTime(-10, 9, 30),
      providerName: "Dr. Sarah Mitchell",
      status: "completed",
      location: "Imaging Suite",
      notes: "Excellent bone density observed.",
    },
    {
      patientId: thomas.id,
      treatmentPlanId: treatmentPlan.id,
      appointmentType: "planning",
      title: "Treatment Planning Session",
      description: "Finalized treatment plan. Patient signed all consents. Surgery scheduled.",
      ...createApptTime(-7, 14, 45),
      providerName: "Dr. Sarah Mitchell",
      status: "completed",
      location: "Consultation Room",
      notes: "All consents signed. Ready for surgery.",
    },
    {
      patientId: thomas.id,
      treatmentPlanId: treatmentPlan.id,
      appointmentType: "surgery",
      title: "All-on-4 Surgery - Upper Arch",
      description: "All-on-4 upper arch surgery with immediate provisional. NPO after midnight.",
      ...createApptTime(3, 8, 300),
      providerName: "Dr. Sarah Mitchell",
      status: "scheduled",
      location: "Surgery Suite A",
      notes: "IV sedation. NPO after midnight. Arrive 7:30 AM.",
    },
    {
      patientId: thomas.id,
      treatmentPlanId: treatmentPlan.id,
      appointmentType: "follow-up",
      title: "24-Hour Post-Op Check",
      description: "24-hour post-op check. Suture evaluation.",
      ...createApptTime(4, 10, 30),
      providerName: "Dr. Sarah Mitchell",
      status: "scheduled",
      location: "Operatory 1",
      notes: "Check healing, remove any loose sutures if needed.",
    },
  ];

  for (const appt of appointments_data) {
    await db.insert(appointments).values({
      ...appt,
      startTime: appt.start,
      endTime: appt.end,
    });
  }
  console.log("✓ Created 5 appointments (3 completed, 2 scheduled)");

  // 8. Create billing claims
  const claims = [
    { code: "D6010", desc: "Implant placement x4", charged: 8800, allowed: 4000, paid: 4000 },
    { code: "D6114", desc: "Fixed denture", charged: 28500, allowed: 3500, paid: 3500 },
    { code: "D7953", desc: "Bone graft x4", charged: 3500, allowed: 1000, paid: 1000 },
  ];
  
  for (const claim of claims) {
    await db.insert(billingClaims).values({
      patientId: thomas.id,
      treatmentPlanId: treatmentPlan.id,
      claimNumber: `CLM-2026-TZ-${claim.code}`,
      claimStatus: "paid",
      serviceDate: new Date(today.getTime() - 5 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      procedureCode: claim.code,
      icd10Code: "K08.1",
      description: claim.desc,
      chargedAmount: String(claim.charged),
      allowedAmount: String(claim.allowed),
      paidAmount: String(claim.paid),
      patientPortion: String(claim.charged - claim.paid),
      submittedDate: new Date(today.getTime() - 5 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      paidDate: new Date(today.getTime() - 2 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    });
  }
  console.log("✓ Created 3 billing claims (paid)");

  // 9. Add patient documents
  const documents = [
    { documentType: "cbct", category: "diagnostic", fileName: "thomas_cbct_scan.dcm", description: "CBCT 3D scan - Full upper arch" },
    { documentType: "xray", category: "diagnostic", fileName: "thomas_panoramic.jpg", description: "Panoramic X-ray" },
    { documentType: "photo", category: "pre-treatment", fileName: "thomas_smile_photo.jpg", description: "Pre-op smile photo" },
    { documentType: "photo", category: "pre-treatment", fileName: "thomas_intraoral.jpg", description: "Intraoral photos - upper arch" },
    { documentType: "treatment_plan", category: "treatment-plan", fileName: "thomas_digital_plan.pdf", description: "Digital treatment planning file" },
  ];

  for (const doc of documents) {
    await db.insert(patientDocuments).values({
      patientId: thomas.id,
      documentType: doc.documentType,
      category: doc.category,
      fileName: doc.fileName,
      fileUrl: `/uploads/${doc.fileName}`,
      mimeType: doc.fileName.endsWith('.pdf') ? 'application/pdf' : 
                doc.fileName.endsWith('.dcm') ? 'application/dicom' : 'image/jpeg',
      description: doc.description,
    });
  }
  console.log("✓ Added 5 patient documents");

  console.log("\n========================================");
  console.log("🦷 Thomas Z Pipeline Summary");
  console.log("========================================");
  console.log(`Patient ID: ${thomas.id}`);
  console.log(`Treatment: All-on-4 Upper Arch ($47,330)`);
  console.log(`Insurance Approved: $8,500`);
  console.log(`Patient Responsibility: $38,830`);
  console.log(`Status: Pre-surgery - Ready for All-on-4`);
  console.log(`Next Appointment: Surgery in 3 days`);
  console.log("========================================\n");

  console.log("✅ Thomas Z simulation complete!");
}

seedThomasZ()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("Error seeding Thomas Z:", err);
    process.exit(1);
  });
