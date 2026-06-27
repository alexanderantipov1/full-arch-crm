/**
 * full-arch-crm — Schema Translation Layer
 * ─────────────────────────────────────────
 * Converts raw source data into canonical types using a MappingSpec.
 *
 * HOW ONBOARDING WORKS:
 * ─────────────────────
 * 1. New DSO shares their API docs / data dictionary
 * 2. You fill in a MappingSpec (see examples/western-dental.mapping.ts)
 * 3. SchemaTranslator handles all field renames, type coercions, enum maps
 * 4. Only non-standard transformations need custom adapter code
 *
 * This means onboarding Western Dental or ClearChoice is a config file,
 * not a development project.
 */

import type {
  MappingSpec,
  CanonicalPatient,
  CanonicalPatientSummary,
  CanonicalAppointment,
  CanonicalTreatmentPlan,
  CanonicalClinicalNote,
  CanonicalInsurance,
  CanonicalClaim,
  PatientStage,
  AppointmentType,
  AppointmentStatus,
  ClaimStatus,
  InsuranceType,
  AgeBand,
  AdapterType,
  PlannedProcedure,
} from "./types";

// ─── Translator ───────────────────────────────────────────────────────────────

export class SchemaTranslator {
  constructor(private spec: MappingSpec) {}

  // ── Patient ───────────────────────────────────────────────────────────────

  toCanonicalPatient(source: Record<string, unknown>): Partial<CanonicalPatient> {
    const mapped = this.applyDirectMappings(source, this.spec.patient.direct);
    return {
      personUid: mapped.personUid as string,
      tenantId: mapped.tenantId as string,
      firstName: mapped.firstName as string,
      lastName: mapped.lastName as string,
      dateOfBirth: this.coerceDate(mapped.dateOfBirth),
      gender: mapped.gender as CanonicalPatient["gender"] ?? "Unknown",
      email: mapped.email as string | undefined,
      phone: mapped.phone ? this.normalizePhone(mapped.phone as string) : undefined,
      address: mapped.address as CanonicalPatient["address"] | undefined,
      patientStage: this.mapEnum(mapped.patientStage as string, this.spec.enumMaps.patientStage) as PatientStage ?? "lead",
      activeTreatmentPlan: Boolean(mapped.activeTreatmentPlan),
      insuranceType: this.mapEnum(mapped.insuranceType as string, this.spec.enumMaps.insuranceType) as InsuranceType | undefined,
      sourceAdapter: this.spec.adapterType as AdapterType,
      dataFreshness: new Date(),
    };
  }

  toCanonicalPatientSummary(source: Record<string, unknown>): CanonicalPatientSummary {
    const full = this.toCanonicalPatient(source);
    return {
      personUid: full.personUid!,
      tenantId: full.tenantId!,
      displayName: this.buildDisplayName(full.firstName, full.lastName),
      ageBand: full.dateOfBirth ? this.toAgeBand(full.dateOfBirth) : "35-44",
      gender: full.gender ?? "Unknown",
      insuranceType: full.insuranceType,
      patientStage: full.patientStage ?? "lead",
      lastVisitDate: full.lastVisitDate,
      activeTreatmentPlan: full.activeTreatmentPlan ?? false,
      riskScore: full.riskScore,
      scenarioTags: this.deriveScenarioTags(full),
      sourceAdapter: this.spec.adapterType as AdapterType,
    };
  }

  // ── Appointment ───────────────────────────────────────────────────────────

  toCanonicalAppointment(source: Record<string, unknown>): Partial<CanonicalAppointment> {
    const mapped = this.applyDirectMappings(source, this.spec.appointment.direct);
    const startTime = this.coerceDate(mapped.startTime)!;
    const endTime = this.coerceDate(mapped.endTime)!;
    return {
      appointmentId: mapped.appointmentId as string,
      tenantId: mapped.tenantId as string,
      personUid: mapped.personUid as string,
      title: mapped.title as string ?? "Appointment",
      appointmentType: this.mapEnum(mapped.appointmentType as string, this.spec.enumMaps.appointmentType) as AppointmentType ?? "other",
      startTime,
      endTime,
      durationMinutes: endTime && startTime
        ? Math.round((endTime.getTime() - startTime.getTime()) / 60000)
        : 60,
      status: this.mapEnum(mapped.status as string, this.spec.enumMaps.appointmentStatus) as AppointmentStatus ?? "scheduled",
      providerId: mapped.providerId as string | undefined,
      providerName: mapped.providerName as string | undefined,
      locationId: mapped.locationId as string | undefined,
      locationName: mapped.locationName as string | undefined,
      procedureCodes: this.coerceArray(mapped.procedureCodes),
      insuranceVerified: Boolean(mapped.insuranceVerified),
      notes: mapped.notes as string | undefined,
      sourceAdapter: this.spec.adapterType as AdapterType,
    };
  }

  // ── Treatment Plan ────────────────────────────────────────────────────────

  toCanonicalTreatmentPlan(source: Record<string, unknown>): Partial<CanonicalTreatmentPlan> {
    const mapped = this.applyDirectMappings(source, this.spec.treatmentPlan.direct);
    return {
      planId: mapped.planId as string,
      tenantId: mapped.tenantId as string,
      personUid: mapped.personUid as string,
      planName: mapped.planName as string,
      status: (mapped.status as CanonicalTreatmentPlan["status"]) ?? "draft",
      diagnosis: mapped.diagnosis as string | undefined,
      diagnosisCode: mapped.diagnosisCode as string | undefined,
      procedures: this.coerceProcedures(mapped.procedures),
      totalCost: Number(mapped.totalCost ?? 0),
      insuranceCoverage: Number(mapped.insuranceCoverage ?? 0),
      patientResponsibility: Number(mapped.patientResponsibility ?? 0),
      sourceAdapter: this.spec.adapterType as AdapterType,
    };
  }

  // ── Clinical Note ─────────────────────────────────────────────────────────

  toCanonicalClinicalNote(source: Record<string, unknown>): Partial<CanonicalClinicalNote> {
    const mapped = this.applyDirectMappings(source, this.spec.clinicalNote.direct);
    return {
      noteId: mapped.noteId as string,
      tenantId: mapped.tenantId as string,
      personUid: mapped.personUid as string,
      noteType: (mapped.noteType as CanonicalClinicalNote["noteType"]) ?? "other",
      title: mapped.title as string ?? "Clinical Note",
      soapSubjective: mapped.soapSubjective as string | undefined,
      soapObjective: mapped.soapObjective as string | undefined,
      soapAssessment: mapped.soapAssessment as string | undefined,
      soapPlan: mapped.soapPlan as string | undefined,
      cdtCodes: this.coerceArray(mapped.cdtCodes),
      authorName: mapped.authorName as string | undefined,
      aiGenerated: Boolean(mapped.aiGenerated),
      aiConfidenceScore: mapped.aiConfidenceScore ? Number(mapped.aiConfidenceScore) : undefined,
      sourceAdapter: this.spec.adapterType as AdapterType,
    };
  }

  // ── Insurance ─────────────────────────────────────────────────────────────

  toCanonicalInsurance(source: Record<string, unknown>): Partial<CanonicalInsurance> {
    const mapped = this.applyDirectMappings(source, this.spec.insurance.direct);
    return {
      personUid: mapped.personUid as string,
      tenantId: mapped.tenantId as string,
      insuranceType: (mapped.insuranceType as CanonicalInsurance["insuranceType"]) ?? "primary",
      providerName: mapped.providerName as string,
      policyNumber: mapped.policyNumber as string,
      groupNumber: mapped.groupNumber as string | undefined,
      subscriberName: mapped.subscriberName as string | undefined,
      subscriberDob: this.coerceDate(mapped.subscriberDob),
      relationship: (mapped.relationship as CanonicalInsurance["relationship"]) ?? "self",
      effectiveDate: this.coerceDate(mapped.effectiveDate),
      coveragePercentage: mapped.coveragePercentage ? Number(mapped.coveragePercentage) : undefined,
      annualMaximum: mapped.annualMaximum ? Number(mapped.annualMaximum) : undefined,
      deductible: mapped.deductible ? Number(mapped.deductible) : undefined,
      remainingBenefit: mapped.remainingBenefit ? Number(mapped.remainingBenefit) : undefined,
      priorAuthRequired: Boolean(mapped.priorAuthRequired ?? false),
    };
  }

  // ── Claim ─────────────────────────────────────────────────────────────────

  toCanonicalClaim(source: Record<string, unknown>): Partial<CanonicalClaim> {
    const mapped = this.applyDirectMappings(source, this.spec.claim.direct);
    return {
      claimId: mapped.claimId as string,
      tenantId: mapped.tenantId as string,
      personUid: mapped.personUid as string,
      claimNumber: mapped.claimNumber as string,
      claimStatus: this.mapEnum(mapped.claimStatus as string, this.spec.enumMaps.claimStatus) as ClaimStatus ?? "pending",
      serviceDate: this.coerceDate(mapped.serviceDate)!,
      cdtCode: mapped.cdtCode as string,
      description: mapped.description as string ?? "",
      chargedAmount: Number(mapped.chargedAmount ?? 0),
      allowedAmount: mapped.allowedAmount ? Number(mapped.allowedAmount) : undefined,
      paidAmount: mapped.paidAmount ? Number(mapped.paidAmount) : undefined,
      patientPortion: mapped.patientPortion ? Number(mapped.patientPortion) : undefined,
      denialReason: mapped.denialReason as string | undefined,
      sourceAdapter: this.spec.adapterType as AdapterType,
    };
  }

  // ── Utility methods ───────────────────────────────────────────────────────

  private applyDirectMappings(
    source: Record<string, unknown>,
    mapping: Record<string, string>
  ): Record<string, unknown> {
    const result: Record<string, unknown> = {};
    for (const [canonicalField, sourcePath] of Object.entries(mapping)) {
      result[canonicalField] = this.getNestedValue(source, sourcePath);
    }
    return result;
  }

  private getNestedValue(obj: Record<string, unknown>, path: string): unknown {
    return path.split(".").reduce((current: unknown, key: string) => {
      if (current && typeof current === "object") {
        return (current as Record<string, unknown>)[key];
      }
      return undefined;
    }, obj);
  }

  private mapEnum<T>(
    value: string | undefined,
    enumMap?: Record<string, T>
  ): T | undefined {
    if (!value || !enumMap) return undefined;
    return enumMap[value] ?? enumMap[value.toLowerCase()] ?? undefined;
  }

  private coerceDate(value: unknown): Date | undefined {
    if (!value) return undefined;
    if (value instanceof Date) return value;
    const d = new Date(value as string);
    return isNaN(d.getTime()) ? undefined : d;
  }

  private coerceArray(value: unknown): string[] {
    if (!value) return [];
    if (Array.isArray(value)) return value.map(String);
    if (typeof value === "string") {
      try { return JSON.parse(value); } catch { return [value]; }
    }
    return [];
  }

  private normalizePhone(phone: string): string {
    return phone.replace(/\D/g, "");
  }

  private buildDisplayName(firstName?: string, lastName?: string): string {
    if (!firstName && !lastName) return "Unknown Patient";
    const lastInitial = lastName ? lastName.charAt(0).toUpperCase() + "." : "";
    return `${firstName ?? ""} ${lastInitial}`.trim();
  }

  private toAgeBand(dob: Date): AgeBand {
    const age = Math.floor((Date.now() - dob.getTime()) / (365.25 * 24 * 3600 * 1000));
    if (age < 25) return "18-24";
    if (age < 35) return "25-34";
    if (age < 45) return "35-44";
    if (age < 55) return "45-54";
    if (age < 65) return "55-64";
    if (age < 75) return "65-74";
    return "75+";
  }

  private deriveScenarioTags(patient: Partial<CanonicalPatient>): string[] {
    const tags: string[] = [];
    if (patient.patientStage === "lead") tags.push("lead");
    if (patient.patientStage === "inactive") tags.push("recall_candidate");
    if (patient.activeTreatmentPlan) tags.push("active_treatment");
    if (!patient.insuranceType || patient.insuranceType === "self_pay") tags.push("self_pay");
    if (patient.riskScore && patient.riskScore > 70) tags.push("high_risk");
    return tags;
  }

  /**
   * Coerce an unknown value into a PlannedProcedure array.
   * Handles: already-typed arrays, JSON strings, single object, or empty/null.
   */
  private coerceProcedures(value: unknown): PlannedProcedure[] {
    if (!value) return [];

    const normalize = (item: unknown): PlannedProcedure | null => {
      if (!item || typeof item !== "object") return null;
      const r = item as Record<string, unknown>;
      return {
        cdtCode:      String(r.cdtCode      ?? r.cdt_code      ?? ""),
        description:  String(r.description  ?? r.name          ?? ""),
        quantity:     Number(r.quantity      ?? 1),
        unitFee:      Number(r.unitFee       ?? r.unit_fee      ?? 0),
        totalFee:     Number(r.totalFee      ?? r.total_fee     ?? 0),
        toothNumbers: r.toothNumbers
          ? this.coerceArray(r.toothNumbers).map(Number).filter(n => !isNaN(n))
          : r.tooth_numbers
            ? this.coerceArray(r.tooth_numbers).map(Number).filter(n => !isNaN(n))
            : undefined,
        status: (r.status as PlannedProcedure["status"]) ?? "planned",
      };
    };

    if (Array.isArray(value)) {
      return value.map(normalize).filter((p): p is PlannedProcedure => p !== null);
    }

    if (typeof value === "string") {
      try {
        const parsed = JSON.parse(value);
        return this.coerceProcedures(parsed);
      } catch {
        return [];
      }
    }

    // Single procedure object
    const single = normalize(value);
    return single ? [single] : [];
  }
}

// ─── Built-in Mapping Specs ──────────────────────────────────────────────────

/**
 * fusion_crm mapping — Fusion Dental Corp
 * These field names match what fusion_crm's /api/v1/ endpoints return.
 */
export const FUSION_CRM_MAPPING: MappingSpec = {
  adapterType: "fusion_crm",
  version: "1.0.0",
  description: "Fusion Dental Corp — fusion_crm REST API v1",

  patient: {
    direct: {
      personUid: "person_uid",
      firstName: "full_name",        // computed: split on space
      lastName: "display_name",      // overridden by FusionCrmAdapter
      dateOfBirth: "dob",
      gender: "gender",
      email: "email",
      phone: "phone",
      patientStage: "scenario_tag",
      lastVisitDate: "last_visit_date",
      activeTreatmentPlan: "active_treatment_plan",
      insuranceType: "insurance_type",
    },
    computed: {
      firstName: "splitFullNameFirst",
      lastName: "splitFullNameLast",
    },
    ignored: ["age_band", "cursor"],
  },

  appointment: {
    direct: {
      appointmentId: "appointment_id",
      personUid: "person_uid",
      title: "notes",
      appointmentType: "appointment_type",
      startTime: "start_time",
      endTime: "end_time",
      status: "status",
      providerName: "provider_name",
      procedureCodes: "procedure_codes",
      insuranceVerified: "insurance_verified",
      chair: "chair",
    },
    computed: {},
    ignored: ["patient_display"],
  },

  treatmentPlan: {
    direct: {
      planId: "plan_id",
      personUid: "person_uid",
      planName: "plan_name",
      status: "status",
      diagnosis: "diagnosis",
      diagnosisCode: "diagnosis_code",
      procedures: "procedures",
      totalCost: "total_cost",
      insuranceCoverage: "insurance_coverage",
      patientResponsibility: "patient_responsibility",
      priorAuthStatus: "prior_auth_status",
    },
    computed: {},
    ignored: [],
  },

  clinicalNote: {
    direct: {
      noteId: "note_id",
      personUid: "person_uid",
      appointmentId: "appointment_id",
      noteType: "note_type",
      title: "title",
      soapSubjective: "soap_subjective",
      soapObjective: "soap_objective",
      soapAssessment: "soap_assessment",
      soapPlan: "soap_plan",
      cdtCodes: "cdt_codes",
      authorName: "provider_name",
      aiGenerated: "ai_generated",
      aiConfidenceScore: "ai_confidence",
    },
    computed: {},
    ignored: [],
  },

  insurance: {
    direct: {
      personUid: "person_uid",
      insuranceType: "insurance_type",
      providerName: "provider_name",
      policyNumber: "member_id",
      groupNumber: "group_id",
      coveragePercentage: "coverage_percentage",
      annualMaximum: "annual_max",
      deductible: "deductible",
      remainingBenefit: "deductible_remaining",
      priorAuthRequired: "prior_auth_required",
    },
    computed: {},
    ignored: ["plan_name"],
  },

  claim: {
    direct: {
      claimId: "claim_id",
      personUid: "person_uid",
      claimNumber: "claim_number",
      claimStatus: "status",
      serviceDate: "service_date",
      cdtCode: "procedure_code",
      description: "description",
      chargedAmount: "charged_amount",
      allowedAmount: "allowed_amount",
      paidAmount: "paid_amount",
      patientPortion: "patient_portion",
      denialReason: "denial_reason",
      submittedDate: "submitted_date",
      paidDate: "paid_date",
    },
    computed: {},
    ignored: [],
  },

  enumMaps: {
    patientStage: {
      "lead": "lead",
      "recall_overdue": "inactive",
      "active_treatment": "treatment_plan_accepted",
      "post_op": "post_op",
      "maintenance": "maintenance",
    },
    appointmentType: {
      "consultation": "consultation",
      "surgery": "surgery",
      "pre_op": "pre_op",
      "post_op": "post_op",
      "maintenance": "maintenance",
      "emergency": "emergency",
    },
    appointmentStatus: {
      "confirmed": "confirmed",
      "completed": "completed",
      "cancelled": "cancelled",
      "no_show": "no_show",
      "scheduled": "scheduled",
    },
    claimStatus: {
      "pending": "pending",
      "submitted": "submitted",
      "approved": "approved",
      "denied": "denied",
      "paid": "paid",
      "appealed": "appealed",
    },
    insuranceType: {
      "ppo": "ppo",
      "hmo": "hmo",
      "medicaid": "medicaid",
      "medicare": "medicare",
      "self_pay": "self_pay",
    },
  },
};

/**
 * Generic REST API mapping — starting point for new DSO onboarding.
 * Copy this, rename to western-dental.mapping.ts, adjust field names.
 * Only add custom adapter code for transformations that can't be done here.
 */
export const GENERIC_REST_MAPPING: MappingSpec = {
  adapterType: "generic_rest",
  version: "1.0.0",
  description: "Generic REST API — copy and customize per DSO",

  patient: {
    direct: {
      personUid: "id",
      firstName: "first_name",
      lastName: "last_name",
      dateOfBirth: "date_of_birth",
      gender: "gender",
      email: "email",
      phone: "phone",
      patientStage: "status",
      lastVisitDate: "last_visit",
      activeTreatmentPlan: "has_active_plan",
    },
    computed: {},
    ignored: [],
  },

  appointment: {
    direct: {
      appointmentId: "id",
      personUid: "patient_id",
      title: "title",
      appointmentType: "type",
      startTime: "start",
      endTime: "end",
      status: "status",
      providerName: "provider",
      procedureCodes: "procedures",
      insuranceVerified: "insurance_verified",
    },
    computed: {},
    ignored: [],
  },

  treatmentPlan: {
    direct: {
      planId: "id",
      personUid: "patient_id",
      planName: "name",
      status: "status",
      diagnosis: "diagnosis",
      procedures: "procedures",
      totalCost: "total",
      insuranceCoverage: "insurance_amount",
      patientResponsibility: "patient_amount",
    },
    computed: {},
    ignored: [],
  },

  clinicalNote: {
    direct: {
      noteId: "id",
      personUid: "patient_id",
      noteType: "type",
      title: "title",
      soapSubjective: "subjective",
      soapObjective: "objective",
      soapAssessment: "assessment",
      soapPlan: "plan",
      cdtCodes: "codes",
      authorName: "author",
      aiGenerated: "ai_generated",
    },
    computed: {},
    ignored: [],
  },

  insurance: {
    direct: {
      personUid: "patient_id",
      insuranceType: "type",
      providerName: "provider",
      policyNumber: "policy_id",
      groupNumber: "group_id",
      coveragePercentage: "coverage_pct",
      annualMaximum: "annual_max",
      deductible: "deductible",
      priorAuthRequired: "requires_auth",
    },
    computed: {},
    ignored: [],
  },

  claim: {
    direct: {
      claimId: "id",
      personUid: "patient_id",
      claimNumber: "claim_number",
      claimStatus: "status",
      serviceDate: "service_date",
      cdtCode: "cdt_code",
      description: "description",
      chargedAmount: "amount",
      allowedAmount: "allowed",
      paidAmount: "paid",
      patientPortion: "patient_owes",
      denialReason: "denial_reason",
    },
    computed: {},
    ignored: [],
  },

  enumMaps: {
    patientStage: {},
    appointmentType: {},
    appointmentStatus: {},
    claimStatus: {},
    insuranceType: {},
  },
};
