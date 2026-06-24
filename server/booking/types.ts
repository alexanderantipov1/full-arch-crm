export type AppointmentType =
  | 'full_arch_consult'      // All-on-4 / All-on-6 consultation
  | 'implant_consult'        // Single implant consultation
  | 'implant_placement'      // Surgery
  | 'new_patient_exam'       // New patient comprehensive exam
  | 'recall_hygiene'         // Routine hygiene recall
  | 'emergency'              // Emergency/pain visit
  | 'post_op'                // Post-operative follow-up
  | 'treatment_consult';     // General treatment consultation

export interface TimeSlot {
  date: string;        // YYYY-MM-DD
  time: string;        // HH:MM (24hr)
  providerId: string;
  providerName: string;
  durationMinutes: number;
  available: boolean;
}

export interface BookingRequest {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  phone: string;
  dateOfBirth?: string;
  appointmentType: AppointmentType;
  preferredDate: string;
  preferredTime: string;
  providerId?: string;
  insuranceCarrier?: string;
  notes?: string;
  source: 'website' | 'google' | 'facebook' | 'referral' | 'direct';
  status: 'pending' | 'confirmed' | 'cancelled' | 'rescheduled';
  confirmedSlot?: TimeSlot;
  confirmationNumber: string;
  createdAt: string;
}

export interface AvailabilityQuery {
  appointmentType: AppointmentType;
  startDate: string;  // YYYY-MM-DD
  endDate: string;    // YYYY-MM-DD
  providerId?: string;
}
