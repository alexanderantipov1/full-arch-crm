/**
 * DSO Analytics Service
 * ─────────────────────
 * Core analytics computation layer for DSO partner BI tool integration.
 *
 * All methods fetch raw canonical data via the adapter registry, then compute
 * analytics in-memory. No PHI is surfaced — only aggregate metrics.
 *
 * HIPAA note: All data access is for purpose "operations" / "quality_improvement".
 * No individual PHI fields are returned — only counts, rates, and aggregates.
 */

import { adapterRegistry } from "../adapters";
import type {
  CanonicalAppointment,
  CanonicalTreatmentPlan,
  CanonicalClaim,
  CanonicalPatientSummary,
} from "../adapters";

// ─── Public interfaces ───────────────────────────────────────────────────────

export interface RevenueByLocation {
  locationId: string;
  locationName: string;
  revenueMTD: number;
  revenueYTD: number;
  revenueLastMonth: number;
  growthPct: number;           // vs prior month
  implantCount: number;
  avgCaseValue: number;
}

export interface ConversionFunnel {
  stage: string;
  count: number;
  conversionPct: number;       // % that advance to next stage
}

export interface KPISnapshot {
  tenantId: string;
  asOf: string;                // ISO timestamp
  totalActivePatients: number;
  implantsMTD: number;
  revenueMTD: number;
  avgCaseValue: number;
  collectionRate: number;      // %
  caseAcceptanceRate: number;  // %
  chairUtilization: number;    // %
  locations: RevenueByLocation[];
  funnel: ConversionFunnel[];
}

export interface ImplantTrend {
  month: string;               // YYYY-MM
  count: number;
  revenue: number;
}

export interface CoordinatorAcceptance {
  coordinatorId: string;
  acceptanceRate: number;
  avgDaysToAccept: number;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const PHI_CTX = (tenantId: string) => ({
  purpose: "operations" as const,
  requestedBy: "analytics-service",
  tenantId,
  reason: "DSO partner BI analytics — aggregate only, no PHI surfaced",
  traceId: `analytics-${Date.now()}`,
});

function startOfMonth(date: Date): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 1));
}

function startOfYear(date: Date): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
}

function startOfPriorMonth(date: Date): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() - 1, 1));
}

function endOfPriorMonth(date: Date): Date {
  return new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), 0, 23, 59, 59, 999));
}

function isImplantAppointment(appt: CanonicalAppointment): boolean {
  const t = (appt.type ?? "").toLowerCase();
  const n = (appt.notes ?? "").toLowerCase();
  return (
    t.includes("implant") ||
    t.includes("surgery") ||
    n.includes("implant") ||
    n.includes("d6010") ||
    n.includes("d6040")
  );
}

/** Derive a location ID from an appointment (fall back to providerId or 'default') */
function locationIdOf(appt: CanonicalAppointment): string {
  return (appt as any).locationId ?? appt.providerId ?? "default";
}

/** Stable display name for a location */
function locationNameOf(locationId: string): string {
  if (locationId === "default") return "Main Office";
  return `Location ${locationId.slice(0, 8)}`;
}

/** Sum paid amounts from claims; fall back to appointment fee estimates */
function claimTotal(claims: CanonicalClaim[]): number {
  return claims.reduce((sum, c) => sum + (c.paidAmount ?? c.allowedAmount ?? 0), 0);
}

// ─── AnalyticsService ─────────────────────────────────────────────────────────

export const AnalyticsService = {

  // ── getKPISnapshot ──────────────────────────────────────────────────────────

  async getKPISnapshot(tenantId: string): Promise<KPISnapshot> {
    const [locations, funnel] = await Promise.all([
      this.getRevenueByLocation(tenantId),
      this.getConversionFunnel(tenantId),
    ]);

    const adapter = adapterRegistry.getAdapter(tenantId);
    const now = new Date();
    const mtdStart = startOfMonth(now);
    const phiCtx = PHI_CTX(tenantId);

    // Patient count
    const patientList = await adapter.listPatients({ limit: 5000 });
    const totalActivePatients = patientList.items.filter(
      (p) => p.activeTreatmentPlan || p.patientStage === "treatment_in_progress"
    ).length;

    // Appointments MTD for implant count
    const apptsMTD = await adapter.listAppointments({
      tenantId,
      startDate: mtdStart,
      endDate: now,
    });

    const implantsMTD = apptsMTD.filter(isImplantAppointment).length;

    // Claims for revenue / collection rate
    const claimsMTD = await adapter.listClaims({
      tenantId,
      startDate: mtdStart,
      endDate: now,
    });

    const revenueMTD = locations.reduce((s, l) => s + l.revenueMTD, 0);
    const totalBilled = claimsMTD.reduce((s, c) => s + (c.billedAmount ?? 0), 0);
    const totalCollected = claimsMTD.reduce((s, c) => s + (c.paidAmount ?? 0), 0);
    const collectionRate = totalBilled > 0
      ? Math.round((totalCollected / totalBilled) * 100 * 10) / 10
      : 0;

    // Average case value from treatment plans
    const treatmentPlans: CanonicalTreatmentPlan[] = [];
    const patientSample = patientList.items.slice(0, 200);
    await Promise.allSettled(
      patientSample.map(async (p) => {
        const plans = await adapter.getTreatmentPlans(p.personUid, phiCtx);
        treatmentPlans.push(...plans.filter((pl) => pl.status === "accepted"));
      })
    );

    const acceptedPlans = treatmentPlans.filter((pl) => pl.status === "accepted");
    const avgCaseValue =
      acceptedPlans.length > 0
        ? Math.round(
            acceptedPlans.reduce((s, pl) => s + (pl.totalFee ?? 0), 0) /
              acceptedPlans.length
          )
        : 0;

    // Case acceptance rate (accepted / (accepted + rejected))
    const rejectedPlans = treatmentPlans.filter((pl) => pl.status === "rejected");
    const caseAcceptanceRate =
      acceptedPlans.length + rejectedPlans.length > 0
        ? Math.round(
            (acceptedPlans.length /
              (acceptedPlans.length + rejectedPlans.length)) *
              100 *
              10
          ) / 10
        : 0;

    // Chair utilization: scheduled / (scheduled + available) — approximate from appts
    // Use 8 hours/chair/day, assume 2 chairs by default
    const workingDaysMTD = Math.max(
      1,
      Math.ceil((now.getTime() - mtdStart.getTime()) / (1000 * 60 * 60 * 24))
    );
    const totalChairHours = workingDaysMTD * 8 * 2; // 2 chairs
    const scheduledHours = apptsMTD.reduce((s, a) => {
      const start = new Date(a.startTime);
      const end = new Date(a.endTime);
      return s + Math.abs(end.getTime() - start.getTime()) / (1000 * 60 * 60);
    }, 0);
    const chairUtilization =
      Math.round(
        Math.min(100, (scheduledHours / totalChairHours) * 100) * 10
      ) / 10;

    return {
      tenantId,
      asOf: now.toISOString(),
      totalActivePatients,
      implantsMTD,
      revenueMTD,
      avgCaseValue,
      collectionRate,
      caseAcceptanceRate,
      chairUtilization,
      locations,
      funnel,
    };
  },

  // ── getRevenueByLocation ────────────────────────────────────────────────────

  async getRevenueByLocation(
    tenantId: string,
    startDate?: Date,
    endDate?: Date
  ): Promise<RevenueByLocation[]> {
    const adapter = adapterRegistry.getAdapter(tenantId);
    const now = new Date();
    const mtdStart = startOfMonth(now);
    const ytdStart = startOfYear(now);
    const priorStart = startOfPriorMonth(now);
    const priorEnd = endOfPriorMonth(now);

    const effectiveStart = startDate ?? mtdStart;
    const effectiveEnd = endDate ?? now;

    // Fetch appointment windows in parallel
    const [apptsMTD, apptsYTD, apptsPrior, claimsMTD, claimsYTD, claimsPrior] =
      await Promise.all([
        adapter.listAppointments({ tenantId, startDate: mtdStart, endDate: now }),
        adapter.listAppointments({ tenantId, startDate: ytdStart, endDate: now }),
        adapter.listAppointments({ tenantId, startDate: priorStart, endDate: priorEnd }),
        adapter.listClaims({ tenantId, startDate: mtdStart, endDate: now }),
        adapter.listClaims({ tenantId, startDate: ytdStart, endDate: now }),
        adapter.listClaims({ tenantId, startDate: priorStart, endDate: priorEnd }),
      ]);

    // Group by location
    const locationIds = new Set<string>();
    [...apptsMTD, ...apptsYTD, ...apptsPrior].forEach((a) =>
      locationIds.add(locationIdOf(a))
    );

    if (locationIds.size === 0) {
      locationIds.add("default");
    }

    function revenueForAppts(
      appts: CanonicalAppointment[],
      claims: CanonicalClaim[],
      locId: string
    ): number {
      const locAppts = appts.filter((a) => locationIdOf(a) === locId);
      if (locAppts.length === 0) return 0;
      const apptIds = new Set(locAppts.map((a) => a.appointmentId));
      const locClaims = claims.filter(
        (c) => c.appointmentId && apptIds.has(c.appointmentId)
      );
      if (locClaims.length > 0) return claimTotal(locClaims);
      // Estimate: count × $3,500 avg implant / $800 avg general
      return locAppts.reduce((s, a) => {
        return s + (isImplantAppointment(a) ? 3500 : 800);
      }, 0);
    }

    const results: RevenueByLocation[] = [];

    for (const locId of locationIds) {
      const revMTD = revenueForAppts(apptsMTD, claimsMTD, locId);
      const revYTD = revenueForAppts(apptsYTD, claimsYTD, locId);
      const revPrior = revenueForAppts(apptsPrior, claimsPrior, locId);
      const growthPct =
        revPrior > 0
          ? Math.round(((revMTD - revPrior) / revPrior) * 100 * 10) / 10
          : 0;

      const implantsMTDLoc = apptsMTD
        .filter((a) => locationIdOf(a) === locId && isImplantAppointment(a))
        .length;

      const mtdApptCount = apptsMTD.filter(
        (a) => locationIdOf(a) === locId
      ).length;
      const avgCaseValue =
        mtdApptCount > 0 ? Math.round(revMTD / mtdApptCount) : 0;

      results.push({
        locationId: locId,
        locationName: locationNameOf(locId),
        revenueMTD: revMTD,
        revenueYTD: revYTD,
        revenueLastMonth: revPrior,
        growthPct,
        implantCount: implantsMTDLoc,
        avgCaseValue,
      });
    }

    return results.sort((a, b) => b.revenueMTD - a.revenueMTD);
  },

  // ── getConversionFunnel ─────────────────────────────────────────────────────

  async getConversionFunnel(tenantId: string): Promise<ConversionFunnel[]> {
    const adapter = adapterRegistry.getAdapter(tenantId);
    const phiCtx = PHI_CTX(tenantId);

    const patientList = await adapter.listPatients({ limit: 5000 });
    const total = patientList.items.length;

    // Count by stage
    const stageCounts: Record<string, number> = {
      lead: 0,
      consultation_scheduled: 0,
      consultation_completed: 0,
      treatment_in_progress: 0,
      treatment_complete: 0,
    };

    for (const p of patientList.items) {
      const stage = p.patientStage ?? "lead";
      if (stage in stageCounts) {
        stageCounts[stage]++;
      } else {
        stageCounts["lead"]++;
      }
    }

    const stageOrder = [
      { key: "lead", label: "Lead / Inquiry" },
      { key: "consultation_scheduled", label: "Consultation Scheduled" },
      { key: "consultation_completed", label: "Consultation Completed" },
      { key: "treatment_in_progress", label: "Treatment In Progress" },
      { key: "treatment_complete", label: "Treatment Complete" },
    ];

    const funnel: ConversionFunnel[] = stageOrder.map((s, idx) => {
      const count = stageCounts[s.key] ?? 0;
      const prevCount =
        idx === 0 ? total : stageCounts[stageOrder[idx - 1].key] ?? 0;
      const conversionPct =
        prevCount > 0
          ? Math.round((count / prevCount) * 100 * 10) / 10
          : 0;
      return {
        stage: s.label,
        count,
        conversionPct,
      };
    });

    return funnel;
  },

  // ── getImplantTrends ────────────────────────────────────────────────────────

  async getImplantTrends(
    tenantId: string,
    months = 12
  ): Promise<ImplantTrend[]> {
    const adapter = adapterRegistry.getAdapter(tenantId);
    const now = new Date();

    // Build month buckets going back `months` months
    const buckets: { month: string; start: Date; end: Date }[] = [];
    for (let i = months - 1; i >= 0; i--) {
      const d = new Date(
        Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - i, 1)
      );
      const start = new Date(
        Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1)
      );
      const end = new Date(
        Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0, 23, 59, 59, 999)
      );
      const yyyy = d.getUTCFullYear();
      const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
      buckets.push({ month: `${yyyy}-${mm}`, start, end });
    }

    // Fetch all appointments over the full range in one call
    const rangeStart = buckets[0].start;
    const rangeEnd = buckets[buckets.length - 1].end;

    const [appts, claims] = await Promise.all([
      adapter.listAppointments({ tenantId, startDate: rangeStart, endDate: rangeEnd }),
      adapter.listClaims({ tenantId, startDate: rangeStart, endDate: rangeEnd }),
    ]);

    const implantAppts = appts.filter(isImplantAppointment);

    return buckets.map(({ month, start, end }) => {
      const monthImplants = implantAppts.filter((a) => {
        const d = new Date(a.startTime);
        return d >= start && d <= end;
      });

      const monthApptIds = new Set(monthImplants.map((a) => a.appointmentId));
      const monthClaims = claims.filter(
        (c) => c.appointmentId && monthApptIds.has(c.appointmentId)
      );

      const revenue =
        monthClaims.length > 0
          ? claimTotal(monthClaims)
          : monthImplants.length * 3500; // $3,500 estimate per implant case

      return { month, count: monthImplants.length, revenue };
    });
  },

  // ── getCaseAcceptanceByCoordinator ─────────────────────────────────────────

  async getCaseAcceptanceByCoordinator(
    tenantId: string
  ): Promise<CoordinatorAcceptance[]> {
    const adapter = adapterRegistry.getAdapter(tenantId);
    const phiCtx = PHI_CTX(tenantId);

    const patientList = await adapter.listPatients({ limit: 5000 });

    // Collect treatment plans from a patient sample
    const plansByCoordinator: Record<
      string,
      { accepted: number; total: number; daysToAccept: number[] }
    > = {};

    // Process in batches of 50 to avoid overwhelming the adapter
    const batchSize = 50;
    for (let i = 0; i < Math.min(patientList.items.length, 500); i += batchSize) {
      const batch = patientList.items.slice(i, i + batchSize);
      await Promise.allSettled(
        batch.map(async (p) => {
          const plans = await adapter.getTreatmentPlans(p.personUid, phiCtx);
          for (const plan of plans) {
            const coordId = (plan as any).coordinatorId ?? (plan as any).providerId ?? "unassigned";
            if (!plansByCoordinator[coordId]) {
              plansByCoordinator[coordId] = { accepted: 0, total: 0, daysToAccept: [] };
            }
            plansByCoordinator[coordId].total++;
            if (plan.status === "accepted") {
              plansByCoordinator[coordId].accepted++;
              // Days to accept: time from creation to acceptance
              if (plan.createdAt && plan.updatedAt) {
                const days = Math.max(
                  0,
                  Math.round(
                    (new Date(plan.updatedAt).getTime() -
                      new Date(plan.createdAt).getTime()) /
                      (1000 * 60 * 60 * 24)
                  )
                );
                plansByCoordinator[coordId].daysToAccept.push(days);
              }
            }
          }
        })
      );
    }

    return Object.entries(plansByCoordinator)
      .map(([coordinatorId, data]) => {
        const acceptanceRate =
          data.total > 0
            ? Math.round((data.accepted / data.total) * 100 * 10) / 10
            : 0;
        const avgDaysToAccept =
          data.daysToAccept.length > 0
            ? Math.round(
                data.daysToAccept.reduce((s, d) => s + d, 0) /
                  data.daysToAccept.length *
                  10
              ) / 10
            : 0;
        return { coordinatorId, acceptanceRate, avgDaysToAccept };
      })
      .sort((a, b) => b.acceptanceRate - a.acceptanceRate);
  },
};
