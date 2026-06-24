import { Router } from 'express';
import {
  getAvailableSlots,
  createBookingRequest,
  confirmBooking,
  getAllBookings,
  updateBookingStatus,
  getBookingByConfirmation,
} from './booking-service';

export const bookingRouter = Router();

// Public endpoints (no auth) — for patient-facing use
bookingRouter.get('/api/booking/slots', (req, res) => {
  const { appointmentType, startDate, endDate, providerId } = req.query as Record<string, string>;
  if (!appointmentType || !startDate || !endDate) {
    return res.status(400).json({ error: 'appointmentType, startDate, endDate required' });
  }
  const slots = getAvailableSlots({ appointmentType: appointmentType as any, startDate, endDate, providerId });
  res.json(slots);
});

bookingRouter.post('/api/booking/request', async (req, res) => {
  try {
    const booking = await createBookingRequest(req.body);
    res.json(booking);
  } catch (err: any) { res.status(500).json({ error: String(err?.message ?? err) }); }
});

bookingRouter.post('/api/booking/confirm/:id', (req, res) => {
  const b = confirmBooking(req.params.id, req.body.slot);
  b ? res.json(b) : res.status(404).json({ error: 'Booking not found' });
});

bookingRouter.get('/api/booking/status/:confirmationNumber', (req, res) => {
  const b = getBookingByConfirmation(req.params.confirmationNumber);
  b ? res.json(b) : res.status(404).json({ error: 'Booking not found' });
});

// Internal — staff view
bookingRouter.get('/api/booking/all', (_req, res) => { res.json(getAllBookings()); });
bookingRouter.patch('/api/booking/:id/status', (req, res) => {
  const b = updateBookingStatus(req.params.id, req.body.status);
  b ? res.json(b) : res.status(404).json({ error: 'Booking not found' });
});
