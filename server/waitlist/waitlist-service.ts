import { randomUUID } from 'crypto';
import type { WaitlistEntry, CancellationSlot } from './types';

const waitlist = new Map<string, WaitlistEntry>();
const cancellationSlots = new Map<string, CancellationSlot>();

export function addToWaitlist(input: Omit<WaitlistEntry, 'id' | 'status' | 'contactAttempts' | 'lastContactedAt' | 'addedAt' | 'bookedAt' | 'priority'>): WaitlistEntry {
  // Priority score: shorter min notice = higher priority, full arch = higher priority
  const noticePriority = input.minNoticeHours <= 2 ? 3 : input.minNoticeHours <= 24 ? 2 : 1;
  const typePriority = input.appointmentType.includes('full_arch') || input.appointmentType.includes('implant') ? 2 : 1;
  const priority = noticePriority * typePriority;

  const entry: WaitlistEntry = {
    ...input,
    id: randomUUID(),
    status: 'active',
    contactAttempts: 0,
    lastContactedAt: null,
    addedAt: new Date().toISOString(),
    bookedAt: null,
    priority,
  };
  waitlist.set(entry.id, entry);
  return entry;
}

export function getWaitlist(status?: WaitlistEntry['status']): WaitlistEntry[] {
  const all = Array.from(waitlist.values());
  const filtered = status ? all.filter(e => e.status === status) : all;
  return filtered.sort((a, b) => b.priority - a.priority || new Date(a.addedAt).getTime() - new Date(b.addedAt).getTime());
}

export function updateEntryStatus(id: string, status: WaitlistEntry['status']): WaitlistEntry | null {
  const e = waitlist.get(id);
  if (!e) return null;
  e.status = status;
  if (status === 'booked') e.bookedAt = new Date().toISOString();
  waitlist.set(id, e);
  return e;
}

export function recordContactAttempt(id: string): WaitlistEntry | null {
  const e = waitlist.get(id);
  if (!e) return null;
  e.contactAttempts += 1;
  e.lastContactedAt = new Date().toISOString();
  e.status = 'contacted';
  waitlist.set(id, e);
  return e;
}

export function removeFromWaitlist(id: string): boolean {
  const e = waitlist.get(id);
  if (!e) return false;
  e.status = 'removed';
  waitlist.set(id, e);
  return true;
}

// Find best waitlist matches for a newly opened slot
export function matchSlotToWaitlist(slot: CancellationSlot): WaitlistEntry[] {
  const active = getWaitlist('active').concat(getWaitlist('contacted'));
  const slotDate = new Date(slot.date);
  const dayName = slotDate.toLocaleDateString('en-US', { weekday: 'long' }).toLowerCase();
  const slotHour = parseInt(slot.time.split(':')[0]);
  const timeBlock = slotHour < 12 ? 'morning' : slotHour < 17 ? 'afternoon' : 'evening';

  return active.filter(entry => {
    const dayMatch = entry.preferredDays.length === 0 || entry.preferredDays.includes(dayName);
    const timeMatch = entry.preferredTimeBlocks.length === 0 || entry.preferredTimeBlocks.includes(timeBlock);
    const providerMatch = !entry.providerId || entry.providerId === slot.providerId;
    const typeMatch = !entry.appointmentType || entry.appointmentType === slot.appointmentType;
    // Notice check: hours until slot
    const hoursUntilSlot = (slotDate.getTime() - Date.now()) / (1000 * 60 * 60);
    const noticeOk = hoursUntilSlot >= entry.minNoticeHours;
    return dayMatch && timeMatch && providerMatch && noticeOk;
  }).slice(0, 5); // return top 5 matches
}

export function openCancellationSlot(slot: Omit<CancellationSlot, 'id' | 'openedAt' | 'filledAt' | 'filledByPatientId'>): { slot: CancellationSlot; matches: WaitlistEntry[] } {
  const cancSlot: CancellationSlot = {
    ...slot,
    id: randomUUID(),
    openedAt: new Date().toISOString(),
    filledAt: null,
    filledByPatientId: null,
  };
  cancellationSlots.set(cancSlot.id, cancSlot);
  const matches = matchSlotToWaitlist(cancSlot);
  return { slot: cancSlot, matches };
}

export function fillSlot(slotId: string, patientId: string): boolean {
  const slot = cancellationSlots.get(slotId);
  if (!slot) return false;
  slot.filledAt = new Date().toISOString();
  slot.filledByPatientId = patientId;
  cancellationSlots.set(slotId, slot);
  return true;
}

export function getOpenSlots(): CancellationSlot[] {
  return Array.from(cancellationSlots.values()).filter(s => !s.filledAt);
}

export function getWaitlistStats() {
  const all = Array.from(waitlist.values());
  return {
    total: all.length,
    active: all.filter(e => e.status === 'active').length,
    contacted: all.filter(e => e.status === 'contacted').length,
    booked: all.filter(e => e.status === 'booked').length,
    openSlots: getOpenSlots().length,
    avgWaitDays: all.filter(e => e.status === 'booked' && e.bookedAt).reduce((s, e) => {
      return s + (new Date(e.bookedAt!).getTime() - new Date(e.addedAt).getTime()) / (1000 * 60 * 60 * 24);
    }, 0) / Math.max(1, all.filter(e => e.status === 'booked').length),
  };
}
