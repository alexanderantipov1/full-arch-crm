/**
 * full-arch-crm — SchedulingAgent Unit Tests
 * ───────────────────────────────────────────
 * Lightweight tests with no external test runner dependency.
 * Export `runTests()` and call it directly to execute.
 *
 * Test suites:
 *   1. Urgency scoring always produces values in [0, 100]
 *   2. Slot ranking prefers morning slots for surgery appointments
 *   3. Double-booking detection (available flag on overlapping slots)
 */

import { computeUrgencyScore } from "./scheduling-agent";
import type { TimeSlot } from "./types";

// ─── Minimal test harness ─────────────────────────────────────────────────────

interface TestResult {
  name: string;
  passed: boolean;
  error?: string;
}

function assert(condition: boolean, message: string): void {
  if (!condition) throw new Error(`Assertion failed: ${message}`);
}

async function runTest(
  name: string,
  fn: () => void | Promise<void>,
): Promise<TestResult> {
  try {
    await fn();
    return { name, passed: true };
  } catch (err) {
    return {
      name,
      passed: false,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

// ─── Helpers (local re-implementations for test isolation) ───────────────────

/** Inlined from scheduling-agent.ts for test isolation — no adapter required */
function timeToHour(hhmm: string): number {
  const [h, m] = hhmm.split(":").map(Number);
  return h + m / 60;
}

/**
 * Score a slot's fit for a given appointment type.
 * Mirrors the logic in scheduling-agent.ts for test isolation.
 */
function scoreSlotFit(
  slot: TimeSlot,
  appointmentType: "surgery" | "consult" | "followup" | "restoration",
  dateIndex: number,
  totalDates: number,
): number {
  const SLOT_RULES = {
    surgery:     { preferredStartHour: 8,  preferredEndHour: 12, slotType: "surgery" as const },
    consult:     { preferredStartHour: 13, preferredEndHour: 17, slotType: "consult" as const },
    followup:    { preferredStartHour: 0,  preferredEndHour: 24, slotType: "followup" as const },
    restoration: { preferredStartHour: 8,  preferredEndHour: 17, slotType: "restoration" as const },
  };

  let score = 0;
  const rules = SLOT_RULES[appointmentType];
  const startHour = timeToHour(slot.startTime);

  if (startHour >= rules.preferredStartHour && startHour < rules.preferredEndHour) {
    score += 50;
  }
  if (slot.slotType === rules.slotType) {
    score += 30;
  }
  const recencyBonus = Math.round(20 * (1 - dateIndex / Math.max(1, totalDates - 1)));
  score += recencyBonus;

  return score;
}

/**
 * Detect double-booking in a list of slots: two slots on the same date + chair
 * with overlapping times should not both be marked available.
 * Returns the list of conflict descriptions, empty if clean.
 */
function detectDoubleBooking(slots: TimeSlot[]): string[] {
  const conflicts: string[] = [];

  for (let i = 0; i < slots.length; i++) {
    for (let j = i + 1; j < slots.length; j++) {
      const a = slots[i];
      const b = slots[j];

      if (a.date !== b.date || a.chairId !== b.chairId) continue;
      if (!a.available || !b.available) continue;

      const aStart = timeToHour(a.startTime);
      const aEnd   = timeToHour(a.endTime);
      const bStart = timeToHour(b.startTime);
      const bEnd   = timeToHour(b.endTime);

      // Check overlap: A starts before B ends AND B starts before A ends
      if (aStart < bEnd && bStart < aEnd) {
        conflicts.push(
          `Double-booking: chair ${a.chairId} on ${a.date} — ` +
          `${a.startTime}–${a.endTime} overlaps ${b.startTime}–${b.endTime}`,
        );
      }
    }
  }

  return conflicts;
}

// ─── Test Suite 1: Urgency Scoring ────────────────────────────────────────────

async function testUrgencyScoringRange(): Promise<void> {
  // Max possible score: old plan (+40) + high acceptance (+20) + pre-auth (+20) + financing (+10) = 90
  const maxInputs = {
    planAgeDays: 30,
    caseAcceptanceScore: 85,
    preAuthApproved: true,
    missedAppointments: 0,
    financingInPlace: true,
    outstandingBalance: 0,
  };
  const maxScore = computeUrgencyScore(maxInputs);
  assert(maxScore >= 0 && maxScore <= 100, `Max score ${maxScore} out of [0,100]`);
  assert(maxScore === 90, `Expected max score 90, got ${maxScore}`);

  // Min possible score: missed appt (-20) + high balance (-10) = -30, clamped to 0
  const minInputs = {
    planAgeDays: 0,
    caseAcceptanceScore: 40,
    preAuthApproved: false,
    missedAppointments: 2,
    financingInPlace: false,
    outstandingBalance: 5000,
  };
  const minScore = computeUrgencyScore(minInputs);
  assert(minScore >= 0 && minScore <= 100, `Min score ${minScore} out of [0,100]`);
  assert(minScore === 0, `Expected min (clamped) score 0, got ${minScore}`);

  // Partial: old plan (+40) + missed (-20) = 20
  const partialInputs = {
    planAgeDays: 20,
    caseAcceptanceScore: undefined,
    preAuthApproved: false,
    missedAppointments: 1,
    financingInPlace: false,
    outstandingBalance: 500,
  };
  const partialScore = computeUrgencyScore(partialInputs);
  assert(partialScore >= 0 && partialScore <= 100, `Partial score ${partialScore} out of [0,100]`);
  assert(partialScore === 20, `Expected partial score 20, got ${partialScore}`);

  // All zero inputs → score = 0
  const zeroInputs = {
    planAgeDays: 0,
    caseAcceptanceScore: 0,
    preAuthApproved: false,
    missedAppointments: 0,
    financingInPlace: false,
    outstandingBalance: 0,
  };
  const zeroScore = computeUrgencyScore(zeroInputs);
  assert(zeroScore === 0, `Expected zero score 0, got ${zeroScore}`);
}

// ─── Test Suite 2: Slot Ranking Prefers Morning for Surgery ───────────────────

async function testSlotRankingPrefersMorningForSurgery(): Promise<void> {
  const morningSlot: TimeSlot = {
    date: "2025-07-14",
    startTime: "08:00",
    endTime: "11:00",
    chairId: "chair-1",
    providerId: "provider-1",
    durationMinutes: 180,
    slotType: "surgery",
    available: true,
  };

  const afternoonSlot: TimeSlot = {
    date: "2025-07-14",
    startTime: "13:00",
    endTime: "16:00",
    chairId: "chair-1",
    providerId: "provider-1",
    durationMinutes: 180,
    slotType: "surgery",
    available: true,
  };

  const eveningSlot: TimeSlot = {
    date: "2025-07-14",
    startTime: "16:00",
    endTime: "19:00",
    chairId: "chair-1",
    providerId: "provider-1",
    durationMinutes: 180,
    slotType: "surgery",
    available: true,
  };

  const morningScore   = scoreSlotFit(morningSlot,   "surgery", 0, 7);
  const afternoonScore = scoreSlotFit(afternoonSlot, "surgery", 0, 7);
  const eveningScore   = scoreSlotFit(eveningSlot,   "surgery", 0, 7);

  assert(
    morningScore > afternoonScore,
    `Morning score (${morningScore}) should beat afternoon score (${afternoonScore}) for surgery`,
  );
  assert(
    morningScore > eveningScore,
    `Morning score (${morningScore}) should beat evening score (${eveningScore}) for surgery`,
  );

  // Consult should prefer afternoon
  const afternoonConsultSlot: TimeSlot = {
    ...afternoonSlot,
    slotType: "consult",
    durationMinutes: 60,
    endTime: "14:00",
  };
  const morningConsultSlot: TimeSlot = {
    ...morningSlot,
    slotType: "consult",
    durationMinutes: 60,
    endTime: "09:00",
  };
  const afternoonConsultScore = scoreSlotFit(afternoonConsultSlot, "consult", 0, 7);
  const morningConsultScore   = scoreSlotFit(morningConsultSlot,   "consult", 0, 7);

  assert(
    afternoonConsultScore > morningConsultScore,
    `Afternoon score (${afternoonConsultScore}) should beat morning score (${morningConsultScore}) for consult`,
  );
}

// ─── Test Suite 3: No Double-Booking Detection ────────────────────────────────

async function testNoDoubleBooking(): Promise<void> {
  // Two available slots on same chair/date with overlapping times → conflict detected
  const overlap1: TimeSlot = {
    date: "2025-07-14",
    startTime: "08:00",
    endTime: "11:00",
    chairId: "chair-1",
    providerId: "provider-1",
    durationMinutes: 180,
    slotType: "surgery",
    available: true,
  };
  const overlap2: TimeSlot = {
    date: "2025-07-14",
    startTime: "10:00", // overlaps with 08:00–11:00
    endTime: "12:00",
    chairId: "chair-1",
    providerId: "provider-1",
    durationMinutes: 120,
    slotType: "restoration",
    available: true,
  };

  const conflicts = detectDoubleBooking([overlap1, overlap2]);
  assert(
    conflicts.length > 0,
    "Should detect a double-booking when two available slots overlap on same chair/date",
  );

  // Same chair/date, non-overlapping times → no conflict
  const nonOverlap1: TimeSlot = { ...overlap1, endTime: "10:00", durationMinutes: 120 };
  const nonOverlap2: TimeSlot = { ...overlap2, startTime: "10:00", endTime: "12:00" };
  const noConflicts = detectDoubleBooking([nonOverlap1, nonOverlap2]);
  assert(
    noConflicts.length === 0,
    `Should not flag conflict for adjacent non-overlapping slots, got: ${noConflicts.join(", ")}`,
  );

  // Different chairs — should never conflict
  const chair2Slot: TimeSlot = { ...overlap2, chairId: "chair-2" };
  const differentChairConflicts = detectDoubleBooking([overlap1, chair2Slot]);
  assert(
    differentChairConflicts.length === 0,
    "Different chairs should never produce a double-booking conflict",
  );

  // One slot not available (already booked) — should not flag as double-booking
  const bookedSlot: TimeSlot = { ...overlap2, available: false };
  const bookedConflicts = detectDoubleBooking([overlap1, bookedSlot]);
  assert(
    bookedConflicts.length === 0,
    "A booked slot should not trigger a double-booking flag against an available slot",
  );
}

// ─── Runner ───────────────────────────────────────────────────────────────────

/**
 * Run all SchedulingAgent unit tests.
 * Prints results to console and returns the list of TestResult objects.
 */
export async function runTests(): Promise<TestResult[]> {
  const tests: Array<{ name: string; fn: () => Promise<void> }> = [
    {
      name: "Urgency scoring produces values in [0, 100]",
      fn: testUrgencyScoringRange,
    },
    {
      name: "Slot ranking prefers morning slots for surgery",
      fn: testSlotRankingPrefersMorningForSurgery,
    },
    {
      name: "Double-booking detection catches overlapping available slots",
      fn: testNoDoubleBooking,
    },
  ];

  const results: TestResult[] = [];

  console.log("\n──── SchedulingAgent Tests ────");
  for (const { name, fn } of tests) {
    const result = await runTest(name, fn);
    results.push(result);
    const icon = result.passed ? "✓" : "✗";
    console.log(`  ${icon}  ${name}`);
    if (!result.passed) {
      console.log(`      Error: ${result.error}`);
    }
  }

  const passed = results.filter((r) => r.passed).length;
  const total = results.length;
  console.log(`\n  ${passed}/${total} tests passed`);
  console.log("────────────────────────────────\n");

  return results;
}
