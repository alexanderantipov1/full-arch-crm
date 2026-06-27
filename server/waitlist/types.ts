export interface WaitlistEntry {
  id: string;
  patientName: string;
  patientPhone: string;
  patientEmail: string;
  patientId?: string;         // link to existing patient if known
  appointmentType: string;
  providerId?: string;        // preferred provider, null = any
  providerName?: string;
  minNoticeHours: number;     // minimum notice they need (e.g., 2 = 2 hours notice OK)
  preferredDays: string[];    // ['monday','tuesday','wednesday','thursday','friday']
  preferredTimeBlocks: string[]; // ['morning','afternoon','evening']
  notes: string;
  status: 'active' | 'contacted' | 'booked' | 'removed';
  contactAttempts: number;
  lastContactedAt: string | null;
  addedAt: string;
  bookedAt: string | null;
  priority: number;           // 1 = highest (shorter wait, higher value case, etc.)
}

export interface CancellationSlot {
  id: string;
  date: string;
  time: string;
  providerId: string;
  providerName: string;
  durationMinutes: number;
  appointmentType: string;
  openedAt: string;
  filledAt: string | null;
  filledByPatientId: string | null;
}
