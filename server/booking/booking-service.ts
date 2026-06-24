import { randomUUID } from 'crypto';
import type { BookingRequest, TimeSlot, AppointmentType, AvailabilityQuery } from './types';

const bookingStore = new Map<string, BookingRequest>();

// Generate synthetic availability (no real calendar integration needed — deterministic mock)
export function getAvailableSlots(query: AvailabilityQuery): TimeSlot[] {
  const slots: TimeSlot[] = [];
  const providers = [
    { id: 'prov-1', name: 'Dr. Antipov' },
    { id: 'prov-2', name: 'Dr. Johnson' },
  ];

  // Duration by appointment type
  const durations: Record<AppointmentType, number> = {
    full_arch_consult: 90,
    implant_consult: 60,
    implant_placement: 180,
    new_patient_exam: 60,
    recall_hygiene: 60,
    emergency: 30,
    post_op: 30,
    treatment_consult: 45,
  };

  // Generate slots for each day in range
  const start = new Date(query.startDate);
  const end = new Date(query.endDate);

  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    const dayOfWeek = d.getDay();
    if (dayOfWeek === 0 || dayOfWeek === 6) continue; // skip weekends

    const dateStr = d.toISOString().split('T')[0];
    const times = ['08:00', '09:00', '10:00', '11:00', '13:00', '14:00', '15:00', '16:00'];

    for (const provider of providers) {
      if (query.providerId && query.providerId !== provider.id) continue;

      for (const time of times) {
        // Deterministic availability — skip some slots to simulate a real calendar
        const hash = (dateStr + time + provider.id).split('').reduce((a, c) => a + c.charCodeAt(0), 0);
        const available = hash % 3 !== 0; // ~67% availability

        slots.push({
          date: dateStr,
          time,
          providerId: provider.id,
          providerName: provider.name,
          durationMinutes: durations[query.appointmentType] ?? 60,
          available,
        });
      }
    }
  }

  return slots.filter(s => s.available);
}

export async function createBookingRequest(input: Omit<BookingRequest, 'id' | 'status' | 'confirmationNumber' | 'createdAt'>): Promise<BookingRequest> {
  const booking: BookingRequest = {
    ...input,
    id: randomUUID(),
    status: 'pending',
    confirmationNumber: `FD-${Date.now().toString(36).toUpperCase()}`,
    createdAt: new Date().toISOString(),
  };
  bookingStore.set(booking.id, booking);
  return booking;
}

export function confirmBooking(id: string, slot: TimeSlot): BookingRequest | null {
  const b = bookingStore.get(id);
  if (!b) return null;
  b.status = 'confirmed';
  b.confirmedSlot = slot;
  bookingStore.set(id, b);
  return b;
}

export function getBooking(id: string): BookingRequest | undefined { return bookingStore.get(id); }
export function getBookingByConfirmation(confirmationNumber: string): BookingRequest | undefined {
  return Array.from(bookingStore.values()).find(b => b.confirmationNumber === confirmationNumber);
}
export function getAllBookings(): BookingRequest[] {
  return Array.from(bookingStore.values()).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
}
export function updateBookingStatus(id: string, status: BookingRequest['status']): BookingRequest | null {
  const b = bookingStore.get(id);
  if (!b) return null;
  b.status = status;
  bookingStore.set(id, b);
  return b;
}
