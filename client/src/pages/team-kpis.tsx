import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Users, TrendingUp, TrendingDown, Star, Bot, Search, Award,
  ChevronRight, AlertTriangle, CheckCircle, Target, Phone,
  DollarSign, Clock, BarChart3, Zap, Brain, MessageSquare,
  FileText, Shield, Building2, Crown, Stethoscope, Activity,
  Download,
} from "lucide-react";
import { exportToPDF } from "@/lib/export";

// ─── Types ────────────────────────────────────────────────────────────────────
interface KPI {
  label: string;
  value: string | number;
  target: string | number;
  unit?: string;
  trend?: "up" | "down" | "flat";
  higherIsBetter?: boolean;
}

interface TeamMember {
  id: string;
  name: string;
  title: string;
  department: string;
  avatar: string;
  score: number; // 0–100
  status: "exceeding" | "on-track" | "at-risk" | "critical";
  isAI?: boolean;
  kpis: KPI[];
  directReports?: number;
  tenure?: string;
}

// ─── KPI Score helpers ─────────────────────────────────────────────────────────
const STATUS_CFG = {
  exceeding: { label: "Exceeding",  color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-500/10 border-emerald-400/40", icon: Star },
  "on-track": { label: "On Track",  color: "text-blue-600 dark:text-blue-400",      bg: "bg-blue-500/10 border-blue-400/40",     icon: CheckCircle },
  "at-risk":  { label: "At Risk",   color: "text-amber-600 dark:text-amber-400",    bg: "bg-amber-500/10 border-amber-400/40",   icon: AlertTriangle },
  critical:   { label: "Critical",  color: "text-red-600 dark:text-red-400",        bg: "bg-red-500/10 border-red-400/40",       icon: AlertTriangle },
};

function scoreBg(score: number): string {
  if (score >= 90) return "bg-emerald-500";
  if (score >= 75) return "bg-blue-500";
  if (score >= 60) return "bg-amber-500";
  return "bg-red-500";
}

// ─── Org Data ─────────────────────────────────────────────────────────────────
const TEAM: TeamMember[] = [
  // ── Executive Suite ──────────────────────────────────────────────────────────
  {
    id: "ceo", name: "Dr. Marcus Rivera", title: "CEO / Owner", department: "Executive",
    avatar: "MR", score: 94, status: "exceeding", directReports: 6, tenure: "8 yrs",
    kpis: [
      { label: "Monthly Revenue", value: "$847K", target: "$800K", trend: "up", higherIsBetter: true },
      { label: "EBITDA Margin", value: "38%", target: "35%", trend: "up", higherIsBetter: true },
      { label: "Patient NPS", value: 72, target: 70, unit: "/100", trend: "up", higherIsBetter: true },
      { label: "Staff Retention", value: "91%", target: "90%", trend: "flat", higherIsBetter: true },
      { label: "Case Acceptance", value: "74%", target: "70%", trend: "up", higherIsBetter: true },
      { label: "New Locations", value: 2, target: 2, trend: "flat", higherIsBetter: true },
    ],
  },
  {
    id: "coo", name: "Angela Torres", title: "Chief Operating Officer", department: "Executive",
    avatar: "AT", score: 88, status: "on-track", directReports: 4, tenure: "5 yrs",
    kpis: [
      { label: "Ops Efficiency", value: "89%", target: "85%", trend: "up", higherIsBetter: true },
      { label: "Overhead %", value: "52%", target: "55%", trend: "down", higherIsBetter: false },
      { label: "SOP Compliance", value: "97%", target: "95%", trend: "up", higherIsBetter: true },
      { label: "Avg Chair Util", value: "78%", target: "80%", trend: "up", higherIsBetter: true },
      { label: "Patient Wait Time", value: "8 min", target: "10 min", trend: "down", higherIsBetter: false },
      { label: "Open Projects", value: 3, target: 2, trend: "up", higherIsBetter: false },
    ],
  },
  {
    id: "cfo", name: "James Whitmore", title: "Chief Financial Officer", department: "Executive",
    avatar: "JW", score: 91, status: "exceeding", directReports: 3, tenure: "4 yrs",
    kpis: [
      { label: "Collection Rate", value: "97.2%", target: "95%", trend: "up", higherIsBetter: true },
      { label: "Days in A/R", value: 28, target: 30, unit: " days", trend: "down", higherIsBetter: false },
      { label: "Budget Variance", value: "-1.8%", target: "±5%", trend: "flat", higherIsBetter: false },
      { label: "Cash Runway", value: "14 mo", target: "12 mo", trend: "up", higherIsBetter: true },
      { label: "Claim Denial $", value: "$12K", target: "$15K", trend: "down", higherIsBetter: false },
      { label: "Payroll Accuracy", value: "100%", target: "100%", trend: "flat", higherIsBetter: true },
    ],
  },
  {
    id: "cdo", name: "Dr. Sofia Chen", title: "Chief Dental Officer", department: "Executive",
    avatar: "SC", score: 95, status: "exceeding", directReports: 8, tenure: "6 yrs",
    kpis: [
      { label: "Clinical Quality", value: "98%", target: "95%", trend: "up", higherIsBetter: true },
      { label: "Complications Rate", value: "0.8%", target: "< 2%", trend: "down", higherIsBetter: false },
      { label: "Peer Reviews Done", value: "12/12", target: "12", trend: "flat", higherIsBetter: true },
      { label: "Protocol Adherence", value: "99%", target: "95%", trend: "flat", higherIsBetter: true },
      { label: "Training Hours", value: 24, target: 20, unit: " hrs", trend: "up", higherIsBetter: true },
      { label: "CE Credits", value: 18, target: 15, trend: "up", higherIsBetter: true },
    ],
  },

  // ── Practice Management ───────────────────────────────────────────────────────
  {
    id: "pm", name: "Rachel Nguyen", title: "Practice Manager", department: "Management",
    avatar: "RN", score: 85, status: "on-track", directReports: 12, tenure: "3 yrs",
    kpis: [
      { label: "Staff Satisfaction", value: "87%", target: "85%", trend: "up", higherIsBetter: true },
      { label: "Scheduling Fill Rate", value: "94%", target: "95%", trend: "flat", higherIsBetter: true },
      { label: "Patient Complaints", value: 2, target: "≤3", trend: "down", higherIsBetter: false },
      { label: "Supply Cost Var", value: "+2%", target: "±3%", trend: "flat", higherIsBetter: false },
      { label: "Meetings On Time", value: "91%", target: "90%", trend: "up", higherIsBetter: true },
      { label: "Policy Updates", value: "8/10", target: "10", trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "hr", name: "Lisa Park", title: "HR & Payroll Manager", department: "Management",
    avatar: "LP", score: 82, status: "on-track", tenure: "2 yrs",
    kpis: [
      { label: "Time-to-Hire", value: "18 days", target: "21 days", trend: "down", higherIsBetter: false },
      { label: "Turnover Rate", value: "9%", target: "< 12%", trend: "up", higherIsBetter: false },
      { label: "Payroll Errors", value: 0, target: "0", trend: "flat", higherIsBetter: false },
      { label: "Onboarding Score", value: "4.6/5", target: "4.5", trend: "up", higherIsBetter: true },
      { label: "Benefits Enroll %", value: "96%", target: "95%", trend: "flat", higherIsBetter: true },
      { label: "Training Complete", value: "100%", target: "100%", trend: "flat", higherIsBetter: true },
    ],
  },
  {
    id: "compliance", name: "David Okafor", title: "HIPAA Compliance Officer", department: "Management",
    avatar: "DO", score: 97, status: "exceeding", tenure: "4 yrs",
    kpis: [
      { label: "Audit Pass Rate", value: "100%", target: "100%", trend: "flat", higherIsBetter: true },
      { label: "HIPAA Incidents", value: 0, target: "0", trend: "flat", higherIsBetter: false },
      { label: "PHI Access Reviews", value: "48/48", target: "48", trend: "flat", higherIsBetter: true },
      { label: "Staff HIPAA Training", value: "100%", target: "100%", trend: "flat", higherIsBetter: true },
      { label: "Policy Updates", value: "12/12", target: "12", trend: "flat", higherIsBetter: true },
      { label: "Risk Assessments", value: 4, target: 4, trend: "flat", higherIsBetter: true },
    ],
  },

  // ── Revenue Cycle Management ──────────────────────────────────────────────────
  {
    id: "billing-dir", name: "Carla Mendez", title: "Billing Director", department: "Revenue Cycle",
    avatar: "CM", score: 89, status: "on-track", directReports: 5, tenure: "5 yrs",
    kpis: [
      { label: "Net Collection Rate", value: "97.4%", target: "95%", trend: "up", higherIsBetter: true },
      { label: "Claim Denial Rate", value: "4.2%", target: "< 5%", trend: "down", higherIsBetter: false },
      { label: "Days in A/R", value: 27, target: 30, unit: " days", trend: "down", higherIsBetter: false },
      { label: "First-Pass Clean Rate", value: "93%", target: "90%", trend: "up", higherIsBetter: true },
      { label: "Monthly Revenue Cycle", value: "$743K", target: "$720K", trend: "up", higherIsBetter: true },
      { label: "Appeal Win Rate", value: "78%", target: "70%", trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "ins-coord1", name: "Miguel Santos", title: "Insurance Coordinator", department: "Revenue Cycle",
    avatar: "MS", score: 80, status: "on-track", tenure: "2 yrs",
    kpis: [
      { label: "Verifications/Day", value: 24, target: 20, trend: "up", higherIsBetter: true },
      { label: "Verification Accuracy", value: "98%", target: "95%", trend: "up", higherIsBetter: true },
      { label: "Prior Auth Approval %", value: "82%", target: "80%", trend: "up", higherIsBetter: true },
      { label: "Auth Turnaround", value: "2.1 days", target: "3 days", trend: "down", higherIsBetter: false },
      { label: "Benefits Errors", value: 1, target: "≤2", trend: "flat", higherIsBetter: false },
      { label: "Payer Calls/Wk", value: 68, target: 60, trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "appeals", name: "Tanya Brooks", title: "Appeals Specialist", department: "Revenue Cycle",
    avatar: "TB", score: 84, status: "on-track", tenure: "3 yrs",
    kpis: [
      { label: "Appeals Filed/Mo", value: 34, target: 30, trend: "up", higherIsBetter: true },
      { label: "Appeal Win Rate", value: "81%", target: "75%", trend: "up", higherIsBetter: true },
      { label: "Avg Appeal $", value: "$4,200", target: "$3,800", trend: "up", higherIsBetter: true },
      { label: "Response Time", value: "3.2 days", target: "5 days", trend: "down", higherIsBetter: false },
      { label: "Denials Reversed $", value: "$142K", target: "$120K", trend: "up", higherIsBetter: true },
      { label: "Letters Drafted", value: 34, target: 30, trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "payment-poster", name: "Keisha Williams", title: "Payment Poster / ERA", department: "Revenue Cycle",
    avatar: "KW", score: 92, status: "exceeding", tenure: "4 yrs",
    kpis: [
      { label: "ERA Posts/Day", value: 87, target: 70, trend: "up", higherIsBetter: true },
      { label: "Posting Accuracy", value: "99.7%", target: "99%", trend: "flat", higherIsBetter: true },
      { label: "Unapplied Cash", value: "$1.2K", target: "< $5K", trend: "down", higherIsBetter: false },
      { label: "Variance Resolved", value: "100%", target: "100%", trend: "flat", higherIsBetter: true },
      { label: "Reconciliation Time", value: "0.8 hrs", target: "2 hrs", trend: "down", higherIsBetter: false },
      { label: "Month-End Close", value: "Day 2", target: "Day 3", trend: "down", higherIsBetter: false },
    ],
  },

  // ── Marketing & Growth ────────────────────────────────────────────────────────
  {
    id: "mktg-dir", name: "Priya Patel", title: "Marketing Director", department: "Marketing",
    avatar: "PP", score: 86, status: "on-track", directReports: 3, tenure: "2 yrs",
    kpis: [
      { label: "New Patient Leads/Mo", value: 142, target: 120, trend: "up", higherIsBetter: true },
      { label: "Lead-to-Patient Conv", value: "34%", target: "30%", trend: "up", higherIsBetter: true },
      { label: "Google Avg Rating", value: "4.8", target: "4.7", trend: "flat", higherIsBetter: true },
      { label: "Monthly Ad Spend ROI", value: "6.2x", target: "5x", trend: "up", higherIsBetter: true },
      { label: "Online Reviews/Mo", value: 28, target: 25, trend: "up", higherIsBetter: true },
      { label: "Content Pieces/Mo", value: 18, target: 15, trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "patient-exp", name: "Jasmine Cole", title: "Patient Experience Manager", department: "Marketing",
    avatar: "JC", score: 78, status: "on-track", tenure: "1.5 yrs",
    kpis: [
      { label: "NPS Score", value: 72, target: 70, unit: "/100", trend: "up", higherIsBetter: true },
      { label: "Survey Response Rate", value: "61%", target: "60%", trend: "flat", higherIsBetter: true },
      { label: "Complaint Resolution", value: "1.8 days", target: "2 days", trend: "down", higherIsBetter: false },
      { label: "5-Star Reviews/Mo", value: 22, target: 20, trend: "up", higherIsBetter: true },
      { label: "Patient Retention %", value: "83%", target: "85%", trend: "down", higherIsBetter: true },
      { label: "Follow-Up Calls/Wk", value: 45, target: 40, trend: "up", higherIsBetter: true },
    ],
  },

  // ── Clinical Leadership ────────────────────────────────────────────────────────
  {
    id: "lead-surgeon", name: "Dr. Nathan Blake", title: "Lead Oral Surgeon", department: "Clinical",
    avatar: "NB", score: 96, status: "exceeding", directReports: 4, tenure: "7 yrs",
    kpis: [
      { label: "Cases/Month", value: 38, target: 30, trend: "up", higherIsBetter: true },
      { label: "Surgical Success Rate", value: "99.1%", target: "97%", trend: "up", higherIsBetter: true },
      { label: "Case Acceptance Rate", value: "79%", target: "70%", trend: "up", higherIsBetter: true },
      { label: "Avg Revenue/Case", value: "$18.4K", target: "$16K", trend: "up", higherIsBetter: true },
      { label: "Complication Rate", value: "0.6%", target: "< 2%", trend: "down", higherIsBetter: false },
      { label: "Patient Sat Score", value: "4.9/5", target: "4.7", trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "dentist1", name: "Dr. Aisha Moreau", title: "Associate Dentist", department: "Clinical",
    avatar: "AM", score: 82, status: "on-track", tenure: "3 yrs",
    kpis: [
      { label: "Patients/Day", value: 14, target: 14, trend: "flat", higherIsBetter: true },
      { label: "Production/Day", value: "$4,200", target: "$4,000", trend: "up", higherIsBetter: true },
      { label: "Tx Plan Accept Rate", value: "68%", target: "65%", trend: "up", higherIsBetter: true },
      { label: "Clinical Notes Done", value: "98%", target: "100%", trend: "up", higherIsBetter: true },
      { label: "Patient Sat", value: "4.7/5", target: "4.5", trend: "flat", higherIsBetter: true },
      { label: "No-Show Rate", value: "6%", target: "< 8%", trend: "down", higherIsBetter: false },
    ],
  },
  {
    id: "dentist2", name: "Dr. Ryan Kim", title: "Associate Dentist", department: "Clinical",
    avatar: "RK", score: 66, status: "at-risk", tenure: "1 yr",
    kpis: [
      { label: "Patients/Day", value: 11, target: 14, trend: "flat", higherIsBetter: true },
      { label: "Production/Day", value: "$3,100", target: "$4,000", trend: "down", higherIsBetter: true },
      { label: "Tx Plan Accept Rate", value: "55%", target: "65%", trend: "down", higherIsBetter: true },
      { label: "Clinical Notes Done", value: "88%", target: "100%", trend: "down", higherIsBetter: true },
      { label: "Patient Sat", value: "4.1/5", target: "4.5", trend: "down", higherIsBetter: true },
      { label: "No-Show Rate", value: "12%", target: "< 8%", trend: "up", higherIsBetter: false },
    ],
  },

  // ── Hygienists ────────────────────────────────────────────────────────────────
  {
    id: "hygienist1", name: "Sarah Bloom", title: "Dental Hygienist", department: "Clinical",
    avatar: "SB", score: 88, status: "on-track", tenure: "4 yrs",
    kpis: [
      { label: "Patients/Day", value: 10, target: 10, trend: "flat", higherIsBetter: true },
      { label: "Perio Chart Complete", value: "100%", target: "100%", trend: "flat", higherIsBetter: true },
      { label: "Recall Compliance %", value: "74%", target: "70%", trend: "up", higherIsBetter: true },
      { label: "Fluoride Treatment %", value: "68%", target: "60%", trend: "up", higherIsBetter: true },
      { label: "Bitewing X-ray Rate", value: "91%", target: "90%", trend: "flat", higherIsBetter: true },
      { label: "Patient Sat", value: "4.8/5", target: "4.6", trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "hygienist2", name: "Omar Farris", title: "Dental Hygienist", department: "Clinical",
    avatar: "OF", score: 75, status: "on-track", tenure: "1.5 yrs",
    kpis: [
      { label: "Patients/Day", value: 9, target: 10, trend: "up", higherIsBetter: true },
      { label: "Perio Chart Complete", value: "94%", target: "100%", trend: "up", higherIsBetter: true },
      { label: "Recall Compliance %", value: "65%", target: "70%", trend: "up", higherIsBetter: true },
      { label: "Fluoride Treatment %", value: "55%", target: "60%", trend: "up", higherIsBetter: true },
      { label: "Bitewing X-ray Rate", value: "85%", target: "90%", trend: "up", higherIsBetter: true },
      { label: "Patient Sat", value: "4.5/5", target: "4.6", trend: "flat", higherIsBetter: true },
    ],
  },

  // ── Dental Assistants ─────────────────────────────────────────────────────────
  {
    id: "da1", name: "Destiny Johnson", title: "Lead Dental Assistant", department: "Clinical",
    avatar: "DJ", score: 91, status: "exceeding", tenure: "5 yrs",
    kpis: [
      { label: "Setup Accuracy", value: "100%", target: "98%", trend: "flat", higherIsBetter: true },
      { label: "Chairs Turned/Day", value: 28, target: 24, trend: "up", higherIsBetter: true },
      { label: "Instrument Count Err", value: 0, target: "0", trend: "flat", higherIsBetter: false },
      { label: "Sterilization Comp %", value: "100%", target: "100%", trend: "flat", higherIsBetter: true },
      { label: "Patient Comfort Score", value: "4.9/5", target: "4.7", trend: "up", higherIsBetter: true },
      { label: "Overtime Hours/Mo", value: 4, target: "≤8", trend: "flat", higherIsBetter: false },
    ],
  },
  {
    id: "da2", name: "Carlos Vega", title: "Dental Assistant", department: "Clinical",
    avatar: "CV", score: 74, status: "on-track", tenure: "2 yrs",
    kpis: [
      { label: "Setup Accuracy", value: "97%", target: "98%", trend: "up", higherIsBetter: true },
      { label: "Chairs Turned/Day", value: 22, target: 24, trend: "up", higherIsBetter: true },
      { label: "Instrument Count Err", value: 1, target: "0", trend: "flat", higherIsBetter: false },
      { label: "Sterilization Comp %", value: "98%", target: "100%", trend: "up", higherIsBetter: true },
      { label: "Patient Comfort Score", value: "4.4/5", target: "4.7", trend: "flat", higherIsBetter: true },
      { label: "Tardiness/Mo", value: 2, target: "≤1", trend: "up", higherIsBetter: false },
    ],
  },
  {
    id: "da3", name: "Nina Reeves", title: "Dental Assistant", department: "Clinical",
    avatar: "NR", score: 58, status: "at-risk", tenure: "8 mo",
    kpis: [
      { label: "Setup Accuracy", value: "93%", target: "98%", trend: "down", higherIsBetter: true },
      { label: "Chairs Turned/Day", value: 18, target: 24, trend: "down", higherIsBetter: true },
      { label: "Instrument Count Err", value: 3, target: "0", trend: "up", higherIsBetter: false },
      { label: "Sterilization Comp %", value: "95%", target: "100%", trend: "down", higherIsBetter: true },
      { label: "Patient Comfort Score", value: "4.0/5", target: "4.7", trend: "flat", higherIsBetter: true },
      { label: "Training Due", value: "2 items", target: "0", trend: "up", higherIsBetter: false },
    ],
  },

  // ── Patient Services / Front Desk ─────────────────────────────────────────────
  {
    id: "tx-coord1", name: "Monica Hill", title: "Treatment Coordinator", department: "Patient Services",
    avatar: "MH", score: 93, status: "exceeding", tenure: "6 yrs",
    kpis: [
      { label: "Case Accept Rate", value: "81%", target: "70%", trend: "up", higherIsBetter: true },
      { label: "Consults/Mo", value: 48, target: 40, trend: "up", higherIsBetter: true },
      { label: "Avg Consult-to-Book", value: "3.2 days", target: "5 days", trend: "down", higherIsBetter: false },
      { label: "Financing Presented %", value: "100%", target: "100%", trend: "flat", higherIsBetter: true },
      { label: "Avg Case Value", value: "$22K", target: "$18K", trend: "up", higherIsBetter: true },
      { label: "Follow-Up Rate", value: "98%", target: "95%", trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "tx-coord2", name: "Andre Lewis", title: "Treatment Coordinator", department: "Patient Services",
    avatar: "AL", score: 71, status: "on-track", tenure: "1 yr",
    kpis: [
      { label: "Case Accept Rate", value: "63%", target: "70%", trend: "up", higherIsBetter: true },
      { label: "Consults/Mo", value: 36, target: 40, trend: "up", higherIsBetter: true },
      { label: "Avg Consult-to-Book", value: "6.1 days", target: "5 days", trend: "down", higherIsBetter: false },
      { label: "Financing Presented %", value: "92%", target: "100%", trend: "up", higherIsBetter: true },
      { label: "Avg Case Value", value: "$17K", target: "$18K", trend: "up", higherIsBetter: true },
      { label: "Follow-Up Rate", value: "87%", target: "95%", trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "receptionist1", name: "Brenda Torres", title: "Lead Receptionist", department: "Patient Services",
    avatar: "BT", score: 87, status: "on-track", tenure: "3 yrs",
    kpis: [
      { label: "Calls Answered/Day", value: 68, target: 60, trend: "up", higherIsBetter: true },
      { label: "Hold Abandonment Rate", value: "3.2%", target: "< 5%", trend: "down", higherIsBetter: false },
      { label: "Appts Scheduled/Day", value: 22, target: 20, trend: "up", higherIsBetter: true },
      { label: "Check-in Time", value: "2.8 min", target: "< 4 min", trend: "down", higherIsBetter: false },
      { label: "Co-pay Collection %", value: "100%", target: "100%", trend: "flat", higherIsBetter: true },
      { label: "No-Show Reminders", value: "100%", target: "100%", trend: "flat", higherIsBetter: true },
    ],
  },
  {
    id: "scheduler", name: "Kevin Park", title: "Scheduler", department: "Patient Services",
    avatar: "KP", score: 79, status: "on-track", tenure: "1 yr",
    kpis: [
      { label: "Schedule Fill Rate", value: "92%", target: "95%", trend: "up", higherIsBetter: true },
      { label: "Waitlist Utilization", value: "78%", target: "80%", trend: "up", higherIsBetter: true },
      { label: "No-Show Rate", value: "7.8%", target: "< 7%", trend: "flat", higherIsBetter: false },
      { label: "Appts Confirmed/Wk", value: 184, target: 180, trend: "up", higherIsBetter: true },
      { label: "Rebook Rate", value: "68%", target: "70%", trend: "up", higherIsBetter: true },
      { label: "Avg Lead Time", value: "4.2 days", target: "< 5 days", trend: "down", higherIsBetter: false },
    ],
  },

  // ── AI Agents ─────────────────────────────────────────────────────────────────
  {
    id: "ai-phone", name: "ARIA", title: "AI Phone Receptionist", department: "AI Agents",
    avatar: "AI", score: 97, status: "exceeding", isAI: true,
    kpis: [
      { label: "Calls Handled/Day", value: 124, target: 80, trend: "up", higherIsBetter: true },
      { label: "Resolution Rate", value: "91%", target: "85%", trend: "up", higherIsBetter: true },
      { label: "Avg Call Duration", value: "2.1 min", target: "< 3 min", trend: "down", higherIsBetter: false },
      { label: "Appts Booked/Day", value: 38, target: 25, trend: "up", higherIsBetter: true },
      { label: "Escalation Rate", value: "9%", target: "< 15%", trend: "down", higherIsBetter: false },
      { label: "Multilingual Calls", value: "23%", target: "15%", trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "ai-billing", name: "BILL-AI", title: "AI Medical Coder / Biller", department: "AI Agents",
    avatar: "BA", score: 99, status: "exceeding", isAI: true,
    kpis: [
      { label: "Claims Coded/Day", value: 143, target: 80, trend: "up", higherIsBetter: true },
      { label: "Coding Accuracy", value: "99.2%", target: "98%", trend: "up", higherIsBetter: true },
      { label: "CDT→ICD10 Matches", value: "100%", target: "98%", trend: "flat", higherIsBetter: true },
      { label: "Upcoding Flags", value: 0, target: "0", trend: "flat", higherIsBetter: false },
      { label: "Processing Time", value: "0.8 sec", target: "< 2 sec", trend: "down", higherIsBetter: false },
      { label: "Revenue Captured $", value: "$84K/mo", target: "$70K/mo", trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "ai-docs", name: "DocuBot", title: "AI Documentation Agent", department: "AI Agents",
    avatar: "DB", score: 96, status: "exceeding", isAI: true,
    kpis: [
      { label: "Docs Generated/Day", value: 62, target: 40, trend: "up", higherIsBetter: true },
      { label: "Medical Necessity Letters", value: 28, target: 20, unit: "/wk", trend: "up", higherIsBetter: true },
      { label: "Op Reports/Wk", value: 44, target: 35, trend: "up", higherIsBetter: true },
      { label: "Provider Edits Needed", value: "3%", target: "< 10%", trend: "down", higherIsBetter: false },
      { label: "HIPAA Compliance", value: "100%", target: "100%", trend: "flat", higherIsBetter: true },
      { label: "Turnaround Time", value: "42 sec", target: "< 2 min", trend: "down", higherIsBetter: false },
    ],
  },
  {
    id: "ai-appeals", name: "AppeAI", title: "AI Appeals Agent", department: "AI Agents",
    avatar: "AA", score: 94, status: "exceeding", isAI: true,
    kpis: [
      { label: "Appeals Drafted/Day", value: 18, target: 10, trend: "up", higherIsBetter: true },
      { label: "AI Win Rate Prediction", value: "78%", target: "70%", trend: "up", higherIsBetter: true },
      { label: "Actual Win Rate", value: "76%", target: "70%", trend: "up", higherIsBetter: true },
      { label: "Revenue Recovered $", value: "$142K/mo", target: "$100K/mo", trend: "up", higherIsBetter: true },
      { label: "Draft Approval Rate", value: "94%", target: "90%", trend: "up", higherIsBetter: true },
      { label: "Denial Pattern Flags", value: 12, target: 5, trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "ai-verify", name: "VeriBot", title: "AI Insurance Verifier", department: "AI Agents",
    avatar: "VB", score: 98, status: "exceeding", isAI: true,
    kpis: [
      { label: "Verifications/Day", value: 186, target: 80, trend: "up", higherIsBetter: true },
      { label: "Eligibility Accuracy", value: "99.8%", target: "98%", trend: "flat", higherIsBetter: true },
      { label: "Real-time Checks", value: "100%", target: "90%", trend: "flat", higherIsBetter: true },
      { label: "Manual Overrides", value: "0.2%", target: "< 2%", trend: "down", higherIsBetter: false },
      { label: "Time Saved/Day", value: "6.2 hrs", target: "4 hrs", trend: "up", higherIsBetter: true },
      { label: "Payer Connections", value: 847, target: 500, trend: "up", higherIsBetter: true },
    ],
  },
  {
    id: "ai-recall", name: "RecallBot", title: "AI Recall Coordinator", department: "AI Agents",
    avatar: "RC", score: 91, status: "exceeding", isAI: true,
    kpis: [
      { label: "Recall Outreaches/Day", value: 234, target: 100, trend: "up", higherIsBetter: true },
      { label: "Recall Booking Rate", value: "38%", target: "30%", trend: "up", higherIsBetter: true },
      { label: "SMS Open Rate", value: "94%", target: "80%", trend: "up", higherIsBetter: true },
      { label: "Email Open Rate", value: "42%", target: "30%", trend: "up", higherIsBetter: true },
      { label: "Reactivations/Mo", value: 68, target: 40, trend: "up", higherIsBetter: true },
      { label: "Revenue Recovered", value: "$31K/mo", target: "$20K/mo", trend: "up", higherIsBetter: true },
    ],
  },
];

const DEPARTMENTS = ["All", "Executive", "Management", "Revenue Cycle", "Marketing", "Clinical", "Patient Services", "AI Agents"];

const DEPT_ICONS: Record<string, any> = {
  "Executive":        Crown,
  "Management":       Building2,
  "Revenue Cycle":    DollarSign,
  "Marketing":        TrendingUp,
  "Clinical":         Stethoscope,
  "Patient Services": Users,
  "AI Agents":        Bot,
};

function KPIBar({ value, target, higherIsBetter }: { value: string | number; target: string | number; higherIsBetter?: boolean }) {
  const numVal = parseFloat(String(value).replace(/[^0-9.]/g, "")) || 0;
  const numTarget = parseFloat(String(target).replace(/[^0-9.]/g, "")) || 0;
  if (!numTarget) return null;
  const pct = Math.min((numVal / numTarget) * 100, 130);
  const good = higherIsBetter ? numVal >= numTarget : numVal <= numTarget;
  return (
    <div className="w-full h-1.5 rounded-full bg-muted overflow-hidden">
      <div className={`h-full rounded-full transition-all ${good ? "bg-emerald-500" : "bg-amber-500"}`}
        style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}

function MemberCard({ member }: { member: TeamMember }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = STATUS_CFG[member.status];
  const Icon = cfg.icon;
  const DeptIcon = DEPT_ICONS[member.department] || Users;

  return (
    <div className={`rounded-xl border ${member.isAI ? "border-primary/40 bg-primary/[0.02]" : "border-border"} transition-all`}
      data-testid={`card-member-${member.id}`}>
      <div className="p-4">
        <div className="flex items-start gap-3">
          {/* Avatar */}
          <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 text-sm font-bold
            ${member.isAI
              ? "bg-gradient-to-br from-primary/80 to-purple-500/80 text-white"
              : "bg-primary/10 text-primary"
            }`}>
            {member.isAI ? <Bot className="h-5 w-5" /> : member.avatar}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
              <span className="font-semibold text-sm">{member.name}</span>
              {member.isAI && <Badge className="text-[9px] bg-primary/10 text-primary border-primary/30 px-1 py-0">AI</Badge>}
            </div>
            <div className="text-xs text-muted-foreground truncate">{member.title}</div>
            {member.tenure && <div className="text-[10px] text-muted-foreground">{member.tenure} tenure</div>}
          </div>

          {/* Score ring */}
          <div className="shrink-0 text-center">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white ${scoreBg(member.score)}`}>
              {member.score}
            </div>
          </div>
        </div>

        {/* Status + department */}
        <div className="flex items-center gap-2 mt-3">
          <Badge className={`text-[10px] px-1.5 border ${cfg.bg} ${cfg.color} flex items-center gap-0.5`}>
            <Icon className="h-2.5 w-2.5" /> {cfg.label}
          </Badge>
          <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
            <DeptIcon className="h-2.5 w-2.5" /> {member.department}
          </span>
          {member.directReports && (
            <span className="text-[10px] text-muted-foreground ml-auto">{member.directReports} reports</span>
          )}
        </div>

        {/* Top 3 KPIs preview */}
        <div className="mt-3 space-y-1.5">
          {member.kpis.slice(0, expanded ? 6 : 3).map((kpi, i) => (
            <div key={i}>
              <div className="flex items-center justify-between text-[10px] mb-0.5">
                <span className="text-muted-foreground">{kpi.label}</span>
                <div className="flex items-center gap-1">
                  <span className="font-semibold">{kpi.value}{kpi.unit || ""}</span>
                  <span className="text-muted-foreground">/ {kpi.target}</span>
                  {kpi.trend === "up" && <TrendingUp className={`h-2.5 w-2.5 ${kpi.higherIsBetter ? "text-emerald-500" : "text-red-500"}`} />}
                  {kpi.trend === "down" && <TrendingDown className={`h-2.5 w-2.5 ${kpi.higherIsBetter ? "text-red-500" : "text-emerald-500"}`} />}
                </div>
              </div>
              <KPIBar value={kpi.value} target={kpi.target} higherIsBetter={kpi.higherIsBetter} />
            </div>
          ))}
        </div>

        <button
          onClick={() => setExpanded(e => !e)}
          className="mt-2 text-[10px] text-primary hover:underline flex items-center gap-0.5"
          data-testid={`expand-${member.id}`}
        >
          {expanded ? "Show less" : "Show all KPIs"} <ChevronRight className={`h-3 w-3 transition-transform ${expanded ? "rotate-90" : ""}`} />
        </button>
      </div>
    </div>
  );
}

function OrgTierRow({ title, members, icon: Icon, color }: {
  title: string; members: TeamMember[]; icon: any; color: string;
}) {
  return (
    <div className="space-y-2">
      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg ${color}`}>
        <Icon className="h-4 w-4" />
        <span className="text-xs font-semibold uppercase tracking-wider">{title}</span>
        <span className="text-xs text-muted-foreground ml-auto">{members.length} members</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
        {members.map(m => <MemberCard key={m.id} member={m} />)}
      </div>
    </div>
  );
}

export default function TeamKPIsPage() {
  const [search, setSearch] = useState("");
  const [dept, setDept] = useState("All");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = TEAM.filter(m => {
    const matchDept = dept === "All" || m.department === dept;
    const matchSearch = !search || m.name.toLowerCase().includes(search.toLowerCase()) || m.title.toLowerCase().includes(search.toLowerCase());
    const matchStatus = statusFilter === "all" || m.status === statusFilter;
    return matchDept && matchSearch && matchStatus;
  });

  // Aggregate stats
  const totalScore = Math.round(TEAM.reduce((a, m) => a + m.score, 0) / TEAM.length);
  const exceeding = TEAM.filter(m => m.status === "exceeding").length;
  const atRisk = TEAM.filter(m => m.status === "at-risk" || m.status === "critical").length;
  const aiAgents = TEAM.filter(m => m.isAI);
  const avgAiScore = Math.round(aiAgents.reduce((a, m) => a + m.score, 0) / aiAgents.length);

  // Org tier groups (for the org view)
  const orgTiers = [
    { title: "C-Suite / Executive", dept: "Executive", icon: Crown, color: "bg-amber-500/10 text-amber-600" },
    { title: "Practice Management", dept: "Management", icon: Building2, color: "bg-blue-500/10 text-blue-600" },
    { title: "Revenue Cycle Management", dept: "Revenue Cycle", icon: DollarSign, color: "bg-emerald-500/10 text-emerald-600" },
    { title: "Marketing & Growth", dept: "Marketing", icon: TrendingUp, color: "bg-purple-500/10 text-purple-600" },
    { title: "Clinical Staff", dept: "Clinical", icon: Stethoscope, color: "bg-red-500/10 text-red-600" },
    { title: "Patient Services & Front Desk", dept: "Patient Services", icon: Users, color: "bg-teal-500/10 text-teal-600" },
    { title: "AI Agents", dept: "AI Agents", icon: Bot, color: "bg-primary/10 text-primary" },
  ];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Team KPIs & Org Structure</h1>
          <p className="text-sm text-muted-foreground">Performance scorecards for every team member — from C-suite to AI agents</p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            const sorted = [...TEAM].sort((a, b) => b.score - a.score);
            exportToPDF(
              [
                {
                  type: "title",
                  title: "Team Performance Scorecard",
                  subtitle: `${new Date().toLocaleDateString()} — Golden State Dental`,
                },
                {
                  type: "kpis",
                  heading: "Team Overview",
                  items: [
                    { label: "Team Members", value: String(TEAM.length) },
                    { label: "Avg Team Score", value: `${totalScore}/100` },
                    { label: "Exceeding KPIs", value: `${exceeding} members` },
                    { label: "At Risk", value: `${atRisk} members` },
                    { label: "AI Agents", value: String(aiAgents.length) },
                    { label: "Avg AI Score", value: `${avgAiScore}/100` },
                  ],
                },
                {
                  type: "table",
                  heading: "Performance Leaderboard",
                  columns: ["Rank", "Name", "Title", "Department", "Score", "Status"],
                  rows: sorted.map((m, i) => [
                    i + 1,
                    m.name,
                    m.title,
                    m.department,
                    `${m.score}/100`,
                    STATUS_CFG[m.status].label,
                  ]),
                },
              ],
              "TeamKPIs",
            );
          }}
          data-testid="button-export-kpis-pdf"
        >
          <Download className="mr-2 h-3.5 w-3.5" />
          Export PDF
        </Button>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: "Team Members", value: TEAM.length, icon: Users, color: "text-blue-600 dark:text-blue-400" },
          { label: "Avg Team Score", value: `${totalScore}/100`, icon: Target, color: totalScore >= 85 ? "text-emerald-600" : "text-amber-600" },
          { label: "Exceeding KPIs", value: `${exceeding} members`, icon: Star, color: "text-emerald-600 dark:text-emerald-400" },
          { label: "At Risk", value: `${atRisk} members`, icon: AlertTriangle, color: atRisk > 0 ? "text-amber-600" : "text-emerald-600" },
        ].map(k => {
          const Icon = k.icon;
          return (
            <Card key={k.label}>
              <CardContent className="pt-4 pb-4">
                <div className="flex items-center gap-2 mb-1">
                  <Icon className={`h-4 w-4 ${k.color}`} />
                  <div className="text-[10px] text-muted-foreground uppercase tracking-wider">{k.label}</div>
                </div>
                <div className={`text-xl font-bold font-mono ${k.color}`} data-testid={`kpi-${k.label.toLowerCase().replace(/ /g, "-")}`}>{k.value}</div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* AI Agents summary strip */}
      <Card className="border-primary/30 bg-primary/[0.02]">
        <CardContent className="pt-4 pb-4">
          <div className="flex items-center gap-3 mb-3">
            <Bot className="h-5 w-5 text-primary" />
            <span className="font-semibold text-sm">AI Agent Fleet Performance</span>
            <Badge className="bg-primary/10 text-primary border-primary/30 text-[10px]">Avg Score: {avgAiScore}/100</Badge>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {aiAgents.map(agent => (
              <div key={agent.id} className="text-center rounded-lg border border-primary/20 p-2">
                <div className={`w-8 h-8 rounded-full ${scoreBg(agent.score)} text-white text-xs font-bold flex items-center justify-center mx-auto mb-1`}>{agent.score}</div>
                <div className="text-xs font-semibold">{agent.name}</div>
                <div className="text-[9px] text-muted-foreground">{agent.title.replace("AI ", "").replace(" Agent", "")}</div>
                <Badge className={`text-[9px] mt-1 px-1 border ${STATUS_CFG[agent.status].bg} ${STATUS_CFG[agent.status].color}`}>{STATUS_CFG[agent.status].label}</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="grid">
        <div className="flex items-center gap-3 flex-wrap">
          <TabsList>
            <TabsTrigger value="grid" data-testid="tab-grid">By Department</TabsTrigger>
            <TabsTrigger value="org" data-testid="tab-org">Org Structure</TabsTrigger>
            <TabsTrigger value="leaderboard" data-testid="tab-leaderboard">Leaderboard</TabsTrigger>
          </TabsList>

          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
            <Input className="pl-8 h-8 text-xs w-48" placeholder="Search team…" value={search} onChange={e => setSearch(e.target.value)} data-testid="input-search" />
          </div>

          <div className="flex gap-1.5 flex-wrap">
            {["all", "exceeding", "on-track", "at-risk", "critical"].map(s => (
              <button key={s} onClick={() => setStatusFilter(s)}
                className={`px-2.5 py-1 rounded-full text-[10px] font-medium border transition-colors capitalize ${
                  statusFilter === s ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:border-primary/50"
                }`} data-testid={`filter-${s}`}>
                {s === "all" ? "All Status" : s.replace("-", " ")}
              </button>
            ))}
          </div>
        </div>

        {/* Grid Tab */}
        <TabsContent value="grid" className="mt-4 space-y-6">
          {DEPARTMENTS.filter(d => d !== "All").map(deptName => {
            const members = filtered.filter(m => m.department === deptName);
            if (!members.length) return null;
            const DIcon = DEPT_ICONS[deptName] || Users;
            return (
              <div key={deptName} className="space-y-3">
                <div className="flex items-center gap-2 pb-1 border-b">
                  <DIcon className="h-4 w-4 text-primary" />
                  <h2 className="font-semibold text-sm">{deptName}</h2>
                  <span className="text-xs text-muted-foreground">({members.length})</span>
                  <div className="ml-auto text-xs text-muted-foreground">
                    Avg: <span className="font-semibold text-foreground">
                      {Math.round(members.reduce((a, m) => a + m.score, 0) / members.length)}/100
                    </span>
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {members.map(m => <MemberCard key={m.id} member={m} />)}
                </div>
              </div>
            );
          })}
        </TabsContent>

        {/* Org Structure Tab */}
        <TabsContent value="org" className="mt-4 space-y-5">
          {orgTiers.map(tier => {
            const members = TEAM.filter(m => m.department === tier.dept);
            return (
              <OrgTierRow key={tier.dept} title={tier.title} members={members} icon={tier.icon} color={tier.color} />
            );
          })}
        </TabsContent>

        {/* Leaderboard Tab */}
        <TabsContent value="leaderboard" className="mt-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm flex items-center gap-2">
                <Award className="h-4 w-4 text-primary" /> Team Performance Leaderboard
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-2">
                {[...TEAM].sort((a, b) => b.score - a.score).map((m, rank) => {
                  const cfg = STATUS_CFG[m.status];
                  const DeptIcon = DEPT_ICONS[m.department] || Users;
                  return (
                    <div key={m.id} className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-muted/40 transition-colors" data-testid={`leaderboard-${m.id}`}>
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 
                        ${rank === 0 ? "bg-amber-400 text-white" : rank === 1 ? "bg-gray-300 text-gray-700" : rank === 2 ? "bg-amber-600 text-white" : "bg-muted text-muted-foreground"}`}>
                        {rank + 1}
                      </div>
                      <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0
                        ${m.isAI ? "bg-gradient-to-br from-primary/80 to-purple-500/80 text-white" : "bg-primary/10 text-primary"}`}>
                        {m.isAI ? <Bot className="h-3.5 w-3.5" /> : m.avatar}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-medium text-sm">{m.name}</span>
                          {m.isAI && <Badge className="text-[9px] bg-primary/10 text-primary border-primary/30 px-1 py-0">AI</Badge>}
                        </div>
                        <div className="text-xs text-muted-foreground flex items-center gap-1">
                          <DeptIcon className="h-2.5 w-2.5" /> {m.title}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Badge className={`text-[10px] border ${cfg.bg} ${cfg.color}`}>{cfg.label}</Badge>
                        <div className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold text-white ${scoreBg(m.score)}`}>
                          {m.score}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
