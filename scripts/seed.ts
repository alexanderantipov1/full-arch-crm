import { db } from "../server/db";
import {
  patients,
  medicalHistory,
  dentalInfo,
  insurance,
  treatmentPlans,
  appointments,
  billingClaims,
} from "../shared/schema";

async function seed() {
  console.log("Seeding database...");

  // Create sample patients
  const [patient1] = await db
    .insert(patients)
    .values({
      firstName: "Margaret",
      lastName: "Thompson",
      dateOfBirth: "1958-03-15",
      gender: "female",
      email: "margaret.thompson@email.com",
      phone: "(555) 234-5678",
      address: "456 Oak Street",
      city: "Austin",
      state: "TX",
      zipCode: "78701",
      emergencyContact: "Robert Thompson",
      emergencyPhone: "(555) 234-5679",
    })
    .returning();

  const [patient2] = await db
    .insert(patients)
    .values({
      firstName: "William",
      lastName: "Chen",
      dateOfBirth: "1962-08-22",
      gender: "male",
      email: "william.chen@email.com",
      phone: "(555) 345-6789",
      address: "789 Pine Avenue",
      city: "Austin",
      state: "TX",
      zipCode: "78702",
      emergencyContact: "Lisa Chen",
      emergencyPhone: "(555) 345-6780",
    })
    .returning();

  const [patient3] = await db
    .insert(patients)
    .values({
      firstName: "Patricia",
      lastName: "Rodriguez",
      dateOfBirth: "1965-11-08",
      gender: "female",
      email: "patricia.r@email.com",
      phone: "(555) 456-7890",
      address: "321 Maple Lane",
      city: "Austin",
      state: "TX",
      zipCode: "78703",
      emergencyContact: "Carlos Rodriguez",
      emergencyPhone: "(555) 456-7891",
    })
    .returning();

  console.log("Created patients:", patient1.id, patient2.id, patient3.id);

  // Add medical history
  await db.insert(medicalHistory).values([
    {
      patientId: patient1.id,
      conditions: ["Hypertension", "Type 2 Diabetes"],
      allergies: ["Penicillin"],
      medications: ["Metformin 500mg", "Lisinopril 10mg"],
      smokingStatus: "Former smoker - quit 10 years ago",
      bloodPressure: "138/88",
      heartRate: "72 bpm",
      weight: "165 lbs",
      height: "5'6\"",
    },
    {
      patientId: patient2.id,
      conditions: ["Sleep Apnea"],
      allergies: [],
      medications: ["CPAP therapy"],
      smokingStatus: "Never smoker",
      bloodPressure: "125/80",
      heartRate: "68 bpm",
      weight: "195 lbs",
      height: "5'10\"",
    },
    {
      patientId: patient3.id,
      conditions: ["Osteoporosis"],
      allergies: ["Sulfa drugs"],
      medications: ["Calcium + Vitamin D", "Alendronate 70mg weekly"],
      smokingStatus: "Never smoker",
      bloodPressure: "118/75",
      heartRate: "70 bpm",
      weight: "145 lbs",
      height: "5'4\"",
    },
  ]);

  // Add dental info
  await db.insert(dentalInfo).values([
    {
      patientId: patient1.id,
      chiefComplaint: "Unable to wear lower denture, difficulty eating",
      dentalHistory: "Edentulous maxilla and mandible for 8 years",
      missingTeeth: ["1-16", "17-32"],
      dentures: "Complete upper and lower dentures - poor retention",
      tmjIssues: false,
      grindingClenching: true,
    },
    {
      patientId: patient2.id,
      chiefComplaint: "Multiple failing teeth, wants fixed solution",
      dentalHistory: "History of periodontal disease, multiple extractions",
      missingTeeth: ["3", "14", "19", "30"],
      existingConditions: ["Severe periodontitis", "Mobile teeth 2,4,5,12,13"],
      tmjIssues: true,
      grindingClenching: true,
    },
    {
      patientId: patient3.id,
      chiefComplaint: "Loose upper denture affecting speech and eating",
      dentalHistory: "Edentulous maxilla for 5 years",
      missingTeeth: ["1-16"],
      dentures: "Complete upper denture - requires adhesive",
      tmjIssues: false,
      grindingClenching: false,
    },
  ]);

  // Add insurance
  await db.insert(insurance).values([
    {
      patientId: patient1.id,
      insuranceType: "Medical",
      providerName: "Blue Cross Blue Shield",
      policyNumber: "BCX123456789",
      groupNumber: "GRP-54321",
      subscriberName: "Margaret Thompson",
      coveragePercentage: 80,
      annualMaximum: "50000",
      deductible: "500",
      remainingBenefit: "48500",
      priorAuthRequired: true,
    },
    {
      patientId: patient2.id,
      insuranceType: "Medical",
      providerName: "Aetna",
      policyNumber: "AET987654321",
      groupNumber: "GRP-12345",
      subscriberName: "William Chen",
      coveragePercentage: 70,
      annualMaximum: "30000",
      deductible: "1000",
      remainingBenefit: "29000",
      priorAuthRequired: true,
    },
    {
      patientId: patient3.id,
      insuranceType: "Dental",
      providerName: "Delta Dental",
      policyNumber: "DD555666777",
      groupNumber: "GRP-99999",
      subscriberName: "Patricia Rodriguez",
      coveragePercentage: 50,
      annualMaximum: "2000",
      deductible: "100",
      remainingBenefit: "1900",
      priorAuthRequired: false,
    },
  ]);

  // Add treatment plans
  const [plan1] = await db
    .insert(treatmentPlans)
    .values({
      patientId: patient1.id,
      planName: "All-on-4 Full Mouth Reconstruction",
      status: "approved",
      diagnosis: "K08.1 - Complete loss of teeth due to periodontal diseases",
      diagnosisCode: "K08.1",
      procedures: JSON.stringify([
        { code: "D7210", description: "Extraction with flap", qty: 0 },
        { code: "D6010", description: "Implant placement", qty: 8 },
        { code: "D6114", description: "Implant supported denture - mandibular", qty: 1 },
        { code: "D6114", description: "Implant supported denture - maxillary", qty: 1 },
        { code: "D7953", description: "Bone replacement graft", qty: 4 },
      ]),
      totalCost: "68000",
      insuranceCoverage: "22000",
      patientResponsibility: "46000",
      priorAuthStatus: "approved",
      priorAuthNumber: "PA-2024-001234",
    })
    .returning();

  const [plan2] = await db
    .insert(treatmentPlans)
    .values({
      patientId: patient2.id,
      planName: "All-on-6 Upper Arch with Extractions",
      status: "pending",
      diagnosis: "K05.4 - Chronic periodontitis, severe",
      diagnosisCode: "K05.4",
      procedures: JSON.stringify([
        { code: "D7210", description: "Extraction with flap", qty: 9 },
        { code: "D6010", description: "Implant placement", qty: 6 },
        { code: "D6114", description: "Implant supported denture", qty: 1 },
        { code: "D7953", description: "Bone replacement graft", qty: 3 },
        { code: "D4263", description: "Bone replacement graft - retained root", qty: 2 },
      ]),
      totalCost: "42000",
      insuranceCoverage: "12000",
      patientResponsibility: "30000",
      priorAuthStatus: "pending",
    })
    .returning();

  const [plan3] = await db
    .insert(treatmentPlans)
    .values({
      patientId: patient3.id,
      planName: "All-on-4 Upper Arch",
      status: "draft",
      diagnosis: "K08.109 - Complete loss of teeth, unspecified cause",
      diagnosisCode: "K08.109",
      procedures: JSON.stringify([
        { code: "D6010", description: "Implant placement", qty: 4 },
        { code: "D6114", description: "Implant supported denture", qty: 1 },
        { code: "D7953", description: "Bone replacement graft", qty: 2 },
      ]),
      totalCost: "32000",
      insuranceCoverage: "1000",
      patientResponsibility: "31000",
      priorAuthStatus: "not_required",
    })
    .returning();

  console.log("Created treatment plans:", plan1.id, plan2.id, plan3.id);

  // Add appointments
  const now = new Date();
  const tomorrow = new Date(now);
  tomorrow.setDate(tomorrow.getDate() + 1);
  const nextWeek = new Date(now);
  nextWeek.setDate(nextWeek.getDate() + 7);

  await db.insert(appointments).values([
    {
      patientId: patient1.id,
      treatmentPlanId: plan1.id,
      appointmentType: "surgery",
      title: "Full Arch Surgery - Phase 1",
      description: "Upper arch All-on-4 implant placement",
      startTime: new Date(tomorrow.setHours(8, 0, 0, 0)),
      endTime: new Date(tomorrow.setHours(12, 0, 0, 0)),
      status: "scheduled",
      location: "OR-1",
      providerName: "Dr. Smith",
    },
    {
      patientId: patient2.id,
      appointmentType: "consultation",
      title: "Treatment Plan Review",
      description: "Review All-on-6 treatment plan and discuss options",
      startTime: new Date(tomorrow.setHours(14, 0, 0, 0)),
      endTime: new Date(tomorrow.setHours(15, 0, 0, 0)),
      status: "scheduled",
      location: "Room 102",
      providerName: "Dr. Johnson",
    },
    {
      patientId: patient3.id,
      appointmentType: "imaging",
      title: "CBCT Scan",
      description: "Pre-operative CBCT scan for treatment planning",
      startTime: new Date(nextWeek.setHours(9, 0, 0, 0)),
      endTime: new Date(nextWeek.setHours(9, 30, 0, 0)),
      status: "scheduled",
      location: "Imaging Center",
      providerName: "Technician",
    },
    {
      patientId: patient1.id,
      treatmentPlanId: plan1.id,
      appointmentType: "follow_up",
      title: "Post-Op Check - Week 1",
      description: "One week post-operative examination",
      startTime: new Date(nextWeek.setHours(10, 0, 0, 0)),
      endTime: new Date(nextWeek.setHours(10, 30, 0, 0)),
      status: "scheduled",
      location: "Room 101",
      providerName: "Dr. Smith",
    },
  ]);

  // Add billing claims
  await db.insert(billingClaims).values([
    {
      patientId: patient1.id,
      treatmentPlanId: plan1.id,
      claimNumber: "CLM-2024-00123",
      claimStatus: "approved",
      serviceDate: new Date("2024-01-15").toISOString().split("T")[0],
      procedureCode: "D6010",
      icd10Code: "K08.1",
      description: "Surgical placement of implant body x4",
      chargedAmount: "8800",
      allowedAmount: "7200",
      paidAmount: "5760",
      patientPortion: "1440",
      submittedDate: new Date("2024-01-16").toISOString().split("T")[0],
      paidDate: new Date("2024-02-01").toISOString().split("T")[0],
    },
    {
      patientId: patient1.id,
      treatmentPlanId: plan1.id,
      claimNumber: "CLM-2024-00124",
      claimStatus: "paid",
      serviceDate: new Date("2024-01-15").toISOString().split("T")[0],
      procedureCode: "D6114",
      icd10Code: "K08.1",
      description: "Implant supported fixed denture",
      chargedAmount: "28500",
      allowedAmount: "24000",
      paidAmount: "19200",
      patientPortion: "4800",
      submittedDate: new Date("2024-01-16").toISOString().split("T")[0],
      paidDate: new Date("2024-02-05").toISOString().split("T")[0],
    },
    {
      patientId: patient2.id,
      claimNumber: "CLM-2024-00125",
      claimStatus: "pending",
      serviceDate: new Date("2024-01-20").toISOString().split("T")[0],
      procedureCode: "D7210",
      icd10Code: "K05.4",
      description: "Extraction with flap elevation x5",
      chargedAmount: "1425",
      submittedDate: new Date("2024-01-21").toISOString().split("T")[0],
    },
    {
      patientId: patient2.id,
      claimNumber: "CLM-2024-00126",
      claimStatus: "denied",
      serviceDate: new Date("2024-01-22").toISOString().split("T")[0],
      procedureCode: "D6010",
      icd10Code: "K05.4",
      description: "Surgical placement of implant body x2",
      chargedAmount: "4400",
      denialReason: "Prior authorization not obtained",
      appealStatus: "pending",
      submittedDate: new Date("2024-01-23").toISOString().split("T")[0],
    },
  ]);

  console.log("Database seeded successfully!");
  process.exit(0);
}

seed().catch((error) => {
  console.error("Error seeding database:", error);
  process.exit(1);
});
