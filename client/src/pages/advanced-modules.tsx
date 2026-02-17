import { useState } from "react";
import {
  ClipboardList, BarChart3, FileText, Eye, Pen, Pill, CircleDot, Wrench,
  FlaskConical, RefreshCcw, Package, Users, TestTube, DollarSign, CreditCard,
  Megaphone, Star, Building2, Video, Brain, Bot, AlertTriangle, CheckCircle,
  Clock, Activity, Search, Camera, Shield, TrendingUp, AlertCircle,
  ArrowRight, Send, Mic, Hash,
  Calendar, Gauge, SearchCheck, FileCheck, ArrowLeftRight, ScrollText,
  Swords, Phone, Target, Receipt, Stethoscope, Landmark, ShieldCheck, PieChart,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";

type ModuleId = "intake" | "perio" | "soap" | "aiimaging" | "consent" | "erx" | "aiclinical" |
  "ortho" | "implant" | "lab" | "referral" |
  "inventory" | "hr" | "sterilization" | "schedule" |
  "rcm" | "verify" | "claims" | "crosscode" | "necessity" | "denials" |
  "phone" | "voice" | "txplan" | "acceptance" | "telehealth" |
  "financial" | "financing" | "marketing" | "nps" | "fees" | "provider" | "payer" | "multiloc" | "compliance" | "bi";

interface ModuleDef {
  id: ModuleId;
  label: string;
  icon: typeof ClipboardList;
  group: string;
}

const MODULES: ModuleDef[] = [
  { id: "intake", label: "Patient Intake", icon: ClipboardList, group: "Clinical" },
  { id: "perio", label: "Perio Charting", icon: BarChart3, group: "Clinical" },
  { id: "soap", label: "Clinical Notes", icon: FileText, group: "Clinical" },
  { id: "aiimaging", label: "AI Imaging Intel", icon: Eye, group: "Clinical" },
  { id: "consent", label: "Consent Forms", icon: Pen, group: "Clinical" },
  { id: "erx", label: "E-Prescribing", icon: Pill, group: "Clinical" },
  { id: "aiclinical", label: "Decision Support", icon: Bot, group: "Clinical" },
  { id: "ortho", label: "Ortho Tracker", icon: CircleDot, group: "Specialty" },
  { id: "implant", label: "Implant Tracker", icon: Wrench, group: "Specialty" },
  { id: "lab", label: "Lab Cases", icon: FlaskConical, group: "Specialty" },
  { id: "referral", label: "Referrals", icon: RefreshCcw, group: "Specialty" },
  { id: "inventory", label: "Inventory", icon: Package, group: "Operations" },
  { id: "hr", label: "HR & Payroll", icon: Users, group: "Operations" },
  { id: "sterilization", label: "Sterilization", icon: TestTube, group: "Operations" },
  { id: "schedule", label: "Smart Schedule", icon: Calendar, group: "Operations" },
  { id: "rcm", label: "Revenue Command", icon: Gauge, group: "Revenue AI" },
  { id: "verify", label: "Insurance Verify", icon: SearchCheck, group: "Revenue AI" },
  { id: "claims", label: "Claims Engine", icon: FileCheck, group: "Revenue AI" },
  { id: "crosscode", label: "Cross-Coding", icon: ArrowLeftRight, group: "Revenue AI" },
  { id: "necessity", label: "Necessity Letters", icon: ScrollText, group: "Revenue AI" },
  { id: "denials", label: "Denial Appeals", icon: Swords, group: "Revenue AI" },
  { id: "phone", label: "AI Phone Agent", icon: Phone, group: "AI Engines" },
  { id: "voice", label: "Voice-to-Code", icon: Mic, group: "AI Engines" },
  { id: "txplan", label: "AI Tx Planning", icon: Brain, group: "AI Engines" },
  { id: "acceptance", label: "Case Acceptance", icon: Target, group: "AI Engines" },
  { id: "telehealth", label: "Teledentistry", icon: Video, group: "AI Engines" },
  { id: "financial", label: "Financial Center", icon: DollarSign, group: "Intelligence" },
  { id: "financing", label: "Patient Finance", icon: CreditCard, group: "Intelligence" },
  { id: "marketing", label: "Marketing Suite", icon: Megaphone, group: "Intelligence" },
  { id: "nps", label: "Patient NPS", icon: Star, group: "Intelligence" },
  { id: "fees", label: "Fee Optimizer", icon: Receipt, group: "Intelligence" },
  { id: "provider", label: "Provider Intel", icon: Stethoscope, group: "Intelligence" },
  { id: "payer", label: "Payer Intel", icon: Landmark, group: "Intelligence" },
  { id: "multiloc", label: "Multi-Location", icon: Building2, group: "Intelligence" },
  { id: "compliance", label: "Compliance Audit", icon: ShieldCheck, group: "Intelligence" },
  { id: "bi", label: "Business Intel", icon: PieChart, group: "Intelligence" },
];

const GROUPS = ["Clinical", "Specialty", "Operations", "Revenue AI", "AI Engines", "Intelligence"];

function KpiCard({ icon: Icon, label, value, sub, subColor }: {
  icon: typeof ClipboardList; label: string; value: string; sub?: string; subColor?: string;
}) {
  return (
    <Card data-testid={`kpi-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <CardContent className="p-4">
        <div className="flex items-center gap-2 mb-1">
          <Icon className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-[10px] font-semibold tracking-wider uppercase text-muted-foreground">{label}</span>
        </div>
        <div className="text-2xl font-extrabold tracking-tight">{value}</div>
        {sub && <div className={`text-xs font-semibold mt-0.5 ${subColor || "text-muted-foreground"}`}>{sub}</div>}
      </CardContent>
    </Card>
  );
}

function SectionHeader({ title, subtitle, actionLabel, onAction }: {
  title: string; subtitle?: string; actionLabel?: string; onAction?: () => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
      <div>
        <h2 className="text-xl font-black">{title}</h2>
        {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {actionLabel && onAction && (
        <Button size="sm" onClick={onAction} data-testid={`button-${actionLabel.toLowerCase().replace(/\s+/g, "-")}`}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    active: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    live: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    signed: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    pass: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    current: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    confirmed: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    on_track: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    ready: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    ok: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    completed: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    published: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    sent: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    beta: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    draft: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    pending: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    warning: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    low: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    behind: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    fabricating: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    in_progress: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
    submitted: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
    scheduled: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
    waiting: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
    overdue: "bg-red-500/15 text-red-700 dark:text-red-400",
    critical: "bg-red-500/15 text-red-700 dark:text-red-400",
    blocked: "bg-red-500/15 text-red-700 dark:text-red-400",
    late: "bg-red-500/15 text-red-700 dark:text-red-400",
    high: "bg-red-500/15 text-red-700 dark:text-red-400",
    declined: "bg-red-500/15 text-red-700 dark:text-red-400",
    due_soon: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    medium: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    scrubbing: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    "pre-auth": "bg-purple-500/15 text-purple-700 dark:text-purple-400",
    pre_auth: "bg-purple-500/15 text-purple-700 dark:text-purple-400",
    resolved: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    approved: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    recovered: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
    transferred: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
    escalated: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  };
  const cls = map[status.toLowerCase().replace(/\s+/g, "_")] || "bg-muted text-muted-foreground";
  return (
    <Badge variant="secondary" className={`text-[10px] no-default-hover-elevate no-default-active-elevate ${cls}`} data-testid={`badge-${status}`}>
      {status}
    </Badge>
  );
}

const INTAKE_FORMS = [
  { name: "New Patient Registration", fields: 24, completion: "98%" },
  { name: "Medical History Questionnaire", fields: 42, completion: "96%" },
  { name: "HIPAA Privacy Acknowledgment", fields: 3, completion: "100%" },
  { name: "Financial Policy Agreement", fields: 5, completion: "99%" },
  { name: "Insurance Card Upload", fields: 2, completion: "94%" },
  { name: "Consent for Treatment (General)", fields: 4, completion: "100%" },
  { name: "Orthodontic Consent & Agreement", fields: 12, completion: "97%" },
  { name: "Implant Surgical Consent", fields: 8, completion: "95%" },
];

const PORTAL_FEATURES = [
  { feat: "View & manage appointments", status: "live" },
  { feat: "Pay bills & view statements", status: "live" },
  { feat: "Message practice securely", status: "live" },
  { feat: "View treatment plans & accept", status: "live" },
  { feat: "Download receipts & EOBs", status: "live" },
  { feat: "Update medical history", status: "live" },
  { feat: "Upload insurance card photos", status: "live" },
  { feat: "Request prescription refills", status: "live" },
  { feat: "View X-rays & treatment photos", status: "beta" },
  { feat: "Book teledentistry consult", status: "beta" },
];

const PROBING_DATA: Record<number, number[]> = {
  3: [3, 2, 3, 4, 5, 3], 8: [2, 2, 2, 2, 3, 2], 14: [5, 6, 4, 4, 5, 6],
  19: [4, 3, 3, 3, 4, 4], 30: [6, 7, 5, 5, 6, 7],
};
const DEFAULT_PROBING = [2, 2, 2, 2, 2, 2];
const UPPER_TEETH = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16];
const LOWER_TEETH = [32, 31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21, 20, 19, 18, 17];

const SOAP_NOTES = [
  { patient: "Margaret Sullivan", proc: "Implant Follow-up #14", time: "8:00 AM", status: "signed", provider: "Dr. Chen" },
  { patient: "Robert Kim", proc: "Implant Consult + CBCT", time: "9:00 AM", status: "draft", provider: "Dr. Chen" },
  { patient: "James Okafor", proc: "Perio Maintenance", time: "8:00 AM", status: "signed", provider: "Dr. Park" },
  { patient: "Diana Patel", proc: "Invisalign Check #8", time: "9:00 AM", status: "pending", provider: "Dr. Park" },
];

const SOAP_SECTIONS = [
  { label: "S - Subjective", text: "Patient reports mild sensitivity at implant site #14 when chewing. No spontaneous pain. Ibuprofen provides relief. Denies numbness, swelling, or drainage.", color: "border-blue-500 bg-blue-500/5" },
  { label: "O - Objective", text: "Implant #14 stable, no mobility. Tissue healthy, pink, stippled. No suppuration. Probing: 3mm circumferential. CBCT confirms osseointegration progressing normally at 6 weeks. Occlusion checked - no premature contacts.", color: "border-teal-500 bg-teal-500/5" },
  { label: "A - Assessment", text: "Implant #14 healing within normal parameters. Sensitivity consistent with early loading adaptation. No signs of peri-implantitis or failure.", color: "border-purple-500 bg-purple-500/5" },
  { label: "P - Plan", text: "Continue soft diet for 2 more weeks. Return in 8 weeks for final impression (D6058 abutment + D6065 implant crown). Continue home care instructions. Patient educated and consented to next phase.", color: "border-orange-500 bg-orange-500/5" },
];

const AI_FINDINGS = [
  { finding: "Caries - Tooth #14 mesial", confidence: 94, severity: "moderate" },
  { finding: "Caries - Tooth #3 distal", confidence: 87, severity: "early" },
  { finding: "Caries - Tooth #19 occlusal", confidence: 91, severity: "moderate" },
  { finding: "Bone loss - #14 mesial", confidence: 88, severity: "moderate" },
  { finding: "Bone loss - #30 distal", confidence: 82, severity: "severe" },
  { finding: "Periapical radiolucency - #19", confidence: 78, severity: "moderate" },
];

const CONSENT_FORMS = [
  { name: "General Treatment Consent", fields: 8, procedures: "All procedures", sigs: 1240 },
  { name: "Implant Surgical Consent", fields: 14, procedures: "D6010, D6012", sigs: 342 },
  { name: "Extraction Consent", fields: 10, procedures: "D7140, D7210, D7220", sigs: 567 },
  { name: "Orthodontic Consent", fields: 12, procedures: "D8080, D8090", sigs: 189 },
  { name: "Endodontic Consent", fields: 9, procedures: "D3310, D3320, D3330", sigs: 234 },
  { name: "Sedation Consent", fields: 16, procedures: "D9230, D9241, D9242", sigs: 156 },
  { name: "HIPAA Privacy Notice", fields: 3, procedures: "All patients", sigs: 3105 },
  { name: "Financial Agreement", fields: 5, procedures: "All patients", sigs: 3105 },
  { name: "Whitening Consent", fields: 6, procedures: "D9975", sigs: 98 },
  { name: "Periodontal Surgery Consent", fields: 11, procedures: "D4240, D4249, D4260", sigs: 78 },
];

const ERX_PRESCRIPTIONS = [
  { patient: "Margaret Sullivan", drug: "Amoxicillin 500mg", sig: "1 cap TID x 7d", pharmacy: "CVS - Auburn", alert: "" },
  { patient: "Robert Kim", drug: "Ibuprofen 600mg", sig: "1 tab Q6H PRN pain", pharmacy: "Walgreens - Roseville", alert: "" },
  { patient: "Michael Torres", drug: "Clindamycin 300mg", sig: "1 cap QID x 10d", pharmacy: "Rite Aid - Folsom", alert: "Warfarin interaction" },
  { patient: "Diana Patel", drug: "Chlorhexidine 0.12%", sig: "15mL rinse BID", pharmacy: "CVS - Auburn", alert: "" },
];

const ORTHO_CASES = [
  { patient: "Diana Patel", current: 8, total: 22, compliance: 96, status: "on_track", next: "Feb 20" },
  { patient: "Emma Rodriguez", current: 14, total: 30, compliance: 88, status: "on_track", next: "Feb 25" },
  { patient: "Tyler Nguyen", current: 3, total: 18, compliance: 94, status: "on_track", next: "Mar 1" },
  { patient: "Sophia Adams", current: 18, total: 24, compliance: 72, status: "behind", next: "Feb 15" },
];

const IMPLANT_PIPELINE = {
  consult: [{ name: "Robert Kim", tooth: "#14" }, { name: "Sarah Chen", tooth: "#19, #30" }, { name: "Carlos Mendez", tooth: "#3" }, { name: "Lisa Wang", tooth: "#19, #30" }],
  surgery: [{ name: "Tom Bradley", tooth: "#8, #9" }, { name: "Angela Foster", tooth: "#14" }, { name: "David Park", tooth: "#30" }],
  healing: [{ name: "Margaret Sullivan", tooth: "#14" }, { name: "James Liu", tooth: "#19" }, { name: "Karen White", tooth: "#3, #4" }, { name: "Paul Garcia", tooth: "#30" }, { name: "Nancy Kim", tooth: "#14" }, { name: "Eric Johnson", tooth: "#8" }],
  impression: [{ name: "Frank Miller", tooth: "#19" }, { name: "Jennifer Lee", tooth: "#14" }, { name: "Mark Thompson", tooth: "#30" }],
  restoration: [{ name: "Susan Davis", tooth: "#3" }, { name: "Brian Wilson", tooth: "#14" }],
};

const LAB_CASES = [
  { patient: "Margaret Sullivan", type: "Crown PFM", lab: "Pacific Dental Lab", sent: "Feb 1", due: "Feb 8", status: "overdue" },
  { patient: "Emily Watson", type: "Crown e.max", lab: "Glidewell", sent: "Feb 5", due: "Feb 14", status: "in_progress" },
  { patient: "Robert Kim", type: "Implant Abutment", lab: "Straumann", sent: "Feb 8", due: "Feb 18", status: "submitted" },
  { patient: "Diana Patel", type: "Invisalign Trays", lab: "Align Technology", sent: "Feb 3", due: "Feb 17", status: "fabricating" },
  { patient: "Frank Miller", type: "Implant Crown", lab: "Pacific Dental Lab", sent: "Jan 28", due: "Feb 10", status: "ready" },
];

const REFERRING_DOCTORS = [
  { name: "Dr. Sarah Mitchell - Endodontist", referred: 34, revenue: "$48,200" },
  { name: "Dr. James Park - Periodontist", referred: 28, revenue: "$42,800" },
  { name: "Dr. Lisa Chen - Oral Surgeon", referred: 22, revenue: "$38,400" },
  { name: "Dr. Mark Davis - Orthodontist", referred: 18, revenue: "$32,600" },
  { name: "Dr. Amy Wilson - Pediatric", referred: 12, revenue: "$24,000" },
];

const OUTBOUND_REFERRALS = [
  { patient: "Robert Kim", specialist: "Dr. Sarah Mitchell", reason: "Root canal #14 pre-implant", status: "completed" },
  { patient: "Margaret Sullivan", specialist: "Dr. James Park", reason: "Perio evaluation - bone loss", status: "scheduled" },
  { patient: "Michael Torres", specialist: "Dr. Lisa Chen", reason: "Wisdom tooth #17 surgical extraction", status: "pending" },
];

const INVENTORY_ITEMS = [
  { name: "Composite Resin A2", sku: "CR-A2-001", qty: 8, reorder: 15, unit: "syringe", cost: "$28.50", status: "low" },
  { name: "Implant Body 4.1x10mm", sku: "IB-41-010", qty: 1, reorder: 5, unit: "unit", cost: "$385.00", status: "critical" },
  { name: "Nitrile Gloves (M)", sku: "NG-M-100", qty: 42, reorder: 20, unit: "box", cost: "$12.50", status: "ok" },
  { name: "Anesthetic Lidocaine 2%", sku: "AL-2-050", qty: 35, reorder: 10, unit: "carpule", cost: "$2.80", status: "ok" },
  { name: "Bite Registration Material", sku: "BR-001", qty: 4, reorder: 8, unit: "cartridge", cost: "$18.00", status: "low" },
  { name: "Sterilization Pouches 3x9", sku: "SP-3x9", qty: 50, reorder: 200, unit: "pouch", cost: "$0.15", status: "critical" },
];

const HR_EMPLOYEES = [
  { name: "Dr. Alan Chen", role: "Lead Implantologist", clockedIn: true, clockTime: "7:45 AM", hours: "6.5h", pto: "12 days", license: "Jun 2026" },
  { name: "Dr. Sarah Park", role: "Orthodontist", clockedIn: true, clockTime: "7:50 AM", hours: "6.4h", pto: "8 days", license: "Sep 2026" },
  { name: "Dr. David Okafor", role: "Oral Surgeon", clockedIn: true, clockTime: "8:00 AM", hours: "6.2h", pto: "15 days", license: "Mar 2026" },
  { name: "Maria Lopez", role: "Office Manager", clockedIn: true, clockTime: "7:30 AM", hours: "6.8h", pto: "10 days", license: "N/A" },
  { name: "Sarah Miller", role: "Dental Hygienist", clockedIn: true, clockTime: "7:55 AM", hours: "6.3h", pto: "6 days", license: "Apr 2026" },
  { name: "Jake Roberts", role: "Treatment Coordinator", clockedIn: true, clockTime: "8:00 AM", hours: "6.2h", pto: "9 days", license: "N/A" },
  { name: "Emily Watson", role: "Dental Assistant", clockedIn: false, clockTime: "-", hours: "0h", pto: "14 days", license: "Aug 2026" },
];

const AUTOCLAVE_LOG = [
  { cycle: 1, time: "7:30 AM", load: "General instruments", temp: "270F", duration: "30 min", status: "pass" },
  { cycle: 2, time: "8:15 AM", load: "Handpieces", temp: "270F", duration: "30 min", status: "pass" },
  { cycle: 3, time: "9:00 AM", load: "Surgical kit #1", temp: "275F", duration: "30 min", status: "pass" },
  { cycle: 4, time: "9:45 AM", load: "Implant instruments", temp: "270F", duration: "30 min", status: "pass" },
  { cycle: 5, time: "10:30 AM", load: "General instruments", temp: "270F", duration: "30 min", status: "pass" },
  { cycle: 6, time: "11:15 AM", load: "Endo files", temp: "275F", duration: "30 min", status: "pass" },
  { cycle: 7, time: "1:00 PM", load: "General instruments", temp: "270F", duration: "30 min", status: "pass" },
  { cycle: 8, time: "2:00 PM", load: "Surgical kit #2", temp: "275F", duration: "30 min", status: "pass" },
];

const OSHA_CHECKLIST = [
  { item: "Bloodborne Pathogen Training", frequency: "Annual", lastDone: "Jan 15, 2026", status: "current" },
  { item: "Hazard Communication Training", frequency: "Annual", lastDone: "Jan 15, 2026", status: "current" },
  { item: "Fire Extinguisher Inspection", frequency: "Monthly", lastDone: "Feb 1, 2026", status: "current" },
  { item: "Eyewash Station Check", frequency: "Weekly", lastDone: "Feb 10, 2026", status: "current" },
  { item: "SDS Binder Update", frequency: "As needed", lastDone: "Dec 20, 2025", status: "current" },
  { item: "Radiation Badge Exchange", frequency: "Quarterly", lastDone: "Jan 5, 2026", status: "due_soon" },
  { item: "Emergency Action Plan Review", frequency: "Annual", lastDone: "Nov 10, 2025", status: "due_soon" },
];

const PNL_ITEMS = [
  { label: "Production", value: "$200,000", bold: true },
  { label: "Adjustments", value: "($12,400)", bold: false },
  { label: "Net Production", value: "$187,600", bold: true },
  { label: "Collections", value: "$182,200", bold: true },
  { label: "Staff Costs", value: "$62,400", bold: false },
  { label: "Facility", value: "$14,800", bold: false },
  { label: "Supplies", value: "$11,400", bold: false },
  { label: "Marketing", value: "$8,200", bold: false },
  { label: "Admin / Other", value: "$6,800", bold: false },
  { label: "Total Overhead", value: "$103,600", bold: true },
  { label: "NET INCOME", value: "$86,400", bold: true },
];

const OVERHEAD_BREAKDOWN = [
  { category: "Staff Costs", pct: 34.2, target: 35, color: "bg-emerald-500" },
  { category: "Facility & Rent", pct: 8.1, target: 10, color: "bg-blue-500" },
  { category: "Supplies & Lab", pct: 6.3, target: 7, color: "bg-purple-500" },
  { category: "Marketing", pct: 4.5, target: 5, color: "bg-amber-500" },
  { category: "Admin & Other", pct: 4.2, target: 5, color: "bg-gray-500" },
];

const FINANCING_PLANS = [
  { patient: "Margaret Sullivan", treatment: "Implant #14 + Crown", total: 4800, monthly: 200, remaining: 3600, payments: "18/24", status: "active" },
  { patient: "Diana Patel", treatment: "Invisalign Comprehensive", total: 5800, monthly: 241.67, remaining: 4350, payments: "6/24", status: "active" },
  { patient: "Michael Torres", treatment: "Bone graft + Extraction", total: 1035, monthly: 172.50, remaining: 475, payments: "3/6", status: "active" },
  { patient: "Tom Bradley", treatment: "Full arch implants", total: 24000, monthly: 500, remaining: 18000, payments: "12/48", status: "late" },
];

const MARKETING_CHANNELS = [
  { channel: "Google Ads", spend: "$3,200", patients: 14, cpa: "$229", roi: "4.2x" },
  { channel: "Meta/Instagram", spend: "$1,800", patients: 8, cpa: "$225", roi: "3.8x" },
  { channel: "SEO/Organic", spend: "$1,200", patients: 6, cpa: "$200", roi: "5.1x" },
  { channel: "Referral Program", spend: "$800", patients: 5, cpa: "$160", roi: "6.2x" },
  { channel: "Direct Mail", spend: "$600", patients: 3, cpa: "$200", roi: "2.8x" },
  { channel: "Community Events", spend: "$600", patients: 2, cpa: "$300", roi: "2.1x" },
];

const CONTENT_CALENDAR = [
  { day: "Mon Feb 10", content: "Implant success story - Margaret S.", platform: "Instagram", status: "published" },
  { day: "Tue Feb 11", content: "Oral health tips for diabetics", platform: "Blog + Facebook", status: "published" },
  { day: "Wed Feb 12", content: "Behind-the-scenes: CBCT technology", platform: "TikTok + IG Reels", status: "scheduled" },
  { day: "Thu Feb 13", content: "Valentine's whitening promo", platform: "Email + SMS", status: "scheduled" },
  { day: "Fri Feb 14", content: "Patient testimonial video - Michael T.", platform: "YouTube + Website", status: "draft" },
];

const MULTILOC_DATA = [
  { location: "Auburn Main", production: "$98,400", collections: "96.2%", newPatients: 12, caseAccept: "74%", overhead: "56.8%", margin: "43.2%" },
  { location: "Roseville", production: "$72,800", collections: "94.8%", newPatients: 10, caseAccept: "71%", overhead: "58.4%", margin: "41.6%" },
  { location: "Folsom", production: "$54,200", collections: "95.1%", newPatients: 9, caseAccept: "68%", overhead: "61.2%", margin: "38.8%" },
  { location: "Rocklin", production: "$38,600", collections: "93.4%", newPatients: 7, caseAccept: "66%", overhead: "63.5%", margin: "36.5%" },
];

const TELEHEALTH_QUEUE = [
  { patient: "Emily Watson", reason: "Post-op pain check", time: "2:00 PM", status: "waiting" },
  { patient: "Carlos Mendez", reason: "Pre-consult screening", time: "2:30 PM", status: "scheduled" },
  { patient: "Lisa Wang", reason: "Implant healing check", time: "3:00 PM", status: "scheduled" },
];

const AI_TX_FINDINGS = [
  { finding: "Tooth #14: Extensive carious lesion involving pulp", confidence: 94, color: "border-red-500 bg-red-500/5", recommendation: "Extraction + Implant recommended" },
  { finding: "Tooth #19: Moderate occlusal caries", confidence: 89, color: "border-amber-500 bg-amber-500/5", recommendation: "Direct composite restoration" },
  { finding: "Tooth #30: Periapical radiolucency", confidence: 86, color: "border-red-500 bg-red-500/5", recommendation: "RCT or extraction + implant" },
  { finding: "Generalized mild bone loss", confidence: 78, color: "border-amber-500 bg-amber-500/5", recommendation: "Perio evaluation, SRP if indicated" },
];

const AI_TX_PHASES = [
  {
    name: "Phase 1: Urgent / Pathology",
    items: [
      { cdt: "D7210", desc: "Surgical extraction #14", fee: 385 },
      { cdt: "D6010", desc: "Implant body #14", fee: 2200 },
      { cdt: "D2392", desc: "Composite #19 MOD", fee: 315 },
    ],
  },
  {
    name: "Phase 2: Restoration",
    items: [
      { cdt: "D6058", desc: "Abutment #14", fee: 950 },
      { cdt: "D6065", desc: "Implant crown #14", fee: 1200 },
    ],
  },
];

const AI_CLINICAL_ALERTS = [
  { severity: "high", patient: "Margaret Sullivan", alert: "Penicillin allergy flagged", detail: "Patient has documented penicillin allergy. Amoxicillin prescribed by external provider. ACTION: Contact prescriber, recommend Clindamycin 300mg QID alternative.", color: "border-red-500 bg-red-500/5" },
  { severity: "high", patient: "Michael Torres", alert: "Warfarin interaction risk", detail: "Current INR 2.8. Clindamycin may increase anticoagulant effect. ACTION: Coordinate with cardiologist, monitor INR post-procedure, consider INR check at 48h.", color: "border-red-500 bg-red-500/5" },
  { severity: "medium", patient: "James Okafor", alert: "Diabetes - HbA1c elevated", detail: "Last HbA1c: 8.2% (target <7%). Increased perio risk. ACTION: Enhanced perio protocol, 3-month recall, coordinate with endocrinologist.", color: "border-amber-500 bg-amber-500/5" },
  { severity: "medium", patient: "Diana Patel", alert: "Latex allergy - materials check", detail: "Ensure all materials are latex-free for upcoming procedures. Verified: gloves, dam, elastics. ACTION: Confirm lab materials for Invisalign trays.", color: "border-amber-500 bg-amber-500/5" },
  { severity: "low", patient: "Robert Kim", alert: "Radiograph interval reminder", detail: "Last FMX: Feb 5, 2026. Next recommended: Feb 2029 (3yr interval for low-risk adult). Bitewings due Feb 2027.", color: "border-blue-500 bg-blue-500/5" },
];

const AI_PROTOCOLS = [
  { title: "Pre-Surgical Antibiotics", desc: "Based on AHA guidelines, pre-medication is NOT indicated for Margaret Sullivan (no prosthetic joint, no cardiac conditions requiring prophylaxis). Standard antibiotic prophylaxis for implant surgery per protocol." },
  { title: "Perio-Systemic Risk", desc: "James Okafor: Type 2 Diabetes with elevated HbA1c. Evidence-based recommendation: more frequent perio maintenance (3-month intervals), enhanced homecare instruction, glucose monitoring coordination with PCP." },
  { title: "Radiograph Intervals", desc: "AI recommends individualized radiograph scheduling based on caries risk assessment. High-risk patients: 6-month bitewings. Low-risk: 24-36 month bitewings. CBCT only when 2D inadequate for diagnosis." },
  { title: "Emergency Protocol", desc: "Avulsed tooth protocol: Reimplant within 60 min if possible. Store in Hanks solution or milk. Splint 7-14 days. Initiate RCT at 7-10 days. Follow-up radiographs at 4 weeks, 3 months, 6 months, 1 year." },
];

const SCHEDULE_TOMORROW = [
  { time: "8:00", dur: "60m", chair: "Op 1", prov: "Dr. Chen", pt: "Robert Kim", proc: "Implant Consult + CBCT", prod: "$2,450", risk: "low" },
  { time: "8:00", dur: "60m", chair: "Op 2", prov: "Dr. Park", pt: "Diana Patel", proc: "Invisalign Check #9", prod: "$280", risk: "low" },
  { time: "8:00", dur: "60m", chair: "Hyg 1", prov: "Sarah RDH", pt: "James Okafor", proc: "Perio Maintenance", prod: "$180", risk: "medium" },
  { time: "8:00", dur: "60m", chair: "Hyg 2", prov: "Jamie RDH", pt: "New Pt \u2014 Garcia", proc: "NP Exam + BWX", prod: "$342", risk: "high" },
  { time: "9:00", dur: "90m", chair: "Op 1", prov: "Dr. Chen", pt: "Margaret Sullivan", proc: "Crown Seat #14", prod: "$1,280", risk: "low" },
  { time: "9:00", dur: "60m", chair: "Op 2", prov: "Dr. Park", pt: "Tyler Nguyen", proc: "Ortho Consult", prod: "$250", risk: "medium" },
  { time: "10:00", dur: "120m", chair: "Op 1", prov: "Dr. Chen", pt: "Michael Torres", proc: "Crown Prep #3", prod: "$1,840", risk: "low" },
];

const NOSHOW_RISKS = [
  { patient: "Maria Garcia (New)", risk: "38%", reason: "New pt, no deposit", color: "text-red-500" },
  { patient: "James Okafor", risk: "22%", reason: "Missed last 2 hyg", color: "text-amber-500" },
  { patient: "Tyler Nguyen", risk: "18%", reason: "History of reschedule", color: "text-amber-500" },
];

const WAITLIST_PATIENTS = [
  { patient: "Frank Morris", proc: "Crown seat #8", prod: "$1,280", flex: "Any AM" },
  { patient: "Karen Brown", proc: "Filling #18", prod: "$240", flex: "Tue/Thu PM" },
  { patient: "Pete Hall", proc: "Implant F/U", prod: "$0", flex: "Flexible" },
];

const RCM_ACTIVITY = [
  { time: "2:42 PM", action: "Claim D2740 #3 \u2014 Margaret Sullivan auto-submitted to Delta", amt: "$1,280", color: "text-emerald-500" },
  { time: "2:38 PM", action: "Insurance verified \u2014 Robert Kim (Cigna PPO) implant benefits confirmed", amt: "\u2014", color: "text-blue-500" },
  { time: "2:31 PM", action: "Cross-coded: Sleep appliance D5988 \u2192 G47.33 \u2192 E0486 for medical billing", amt: "$2,400", color: "text-purple-500" },
  { time: "2:24 PM", action: "Medical necessity letter generated for SRP D4341 \u2014 James Okafor", amt: "\u2014", color: "text-indigo-500" },
  { time: "2:18 PM", action: "Appeal auto-submitted: Denied crown D2740 \u2014 MetLife \u2014 clinical narrative attached", amt: "$1,280", color: "text-amber-500" },
  { time: "2:10 PM", action: "Voice note \u2192 SOAP \u2192 CDT auto-coded: Dr. Chen \u2014 Michael Torres implant follow-up", amt: "\u2014", color: "text-cyan-500" },
  { time: "1:55 PM", action: "ERA auto-posted: Cigna batch $8,420 \u2014 12 claims reconciled", amt: "$8,420", color: "text-emerald-500" },
];

const RCM_ENGINE_PERF = [
  { label: "Claim Accuracy", val: "97.8%", pct: 97.8, color: "text-emerald-500" },
  { label: "Verification Speed", val: "4.2 sec", pct: 95, color: "text-blue-500" },
  { label: "Cross-Code Match", val: "89%", pct: 89, color: "text-purple-500" },
  { label: "Necessity Approval", val: "91%", pct: 91, color: "text-indigo-500" },
  { label: "Appeal Overturn", val: "68%", pct: 68, color: "text-amber-500" },
  { label: "Voice-to-Code", val: "98.4%", pct: 98.4, color: "text-cyan-500" },
  { label: "ERA Auto-Post", val: "96%", pct: 96, color: "text-teal-500" },
  { label: "First-Pass Rate", val: "94.2%", pct: 94.2, color: "text-emerald-500" },
];

const VERIFY_RESULTS = [
  { patient: "Robert Kim", plan: "Cigna PPO", status: "Active", benefits: "50% major, $2K max, $1,450 remaining", check: "pass" },
  { patient: "Margaret Sullivan", plan: "Delta Premier", status: "Active", benefits: "80% basic, 50% major, $1,800 remaining", check: "pass" },
  { patient: "Diana Patel", plan: "MetLife PPO", status: "Active", benefits: "$2K ortho lifetime, $800 remaining", check: "warning" },
  { patient: "James Okafor", plan: "Aetna DMO", status: "Active", benefits: "100% prev, 80% basic, 50% major", check: "pass" },
  { patient: "New \u2014 Garcia", plan: "Delta PPO", status: "Active", benefits: "100% prev, 80% basic, 50% major, $2K max", check: "pass" },
  { patient: "Tom Davis", plan: "BCBS FEP", status: "Active", benefits: "50% implant, $2.5K max, $400 remaining", check: "warning" },
];

const CLAIMS_QUEUE = [
  { patient: "Margaret Sullivan", proc: "D2740 Crown #3", fee: "$1,280", payer: "Delta Premier", status: "submitted" },
  { patient: "Robert Kim", proc: "D0367 CBCT", fee: "$250", payer: "Cigna PPO", status: "submitted" },
  { patient: "James Okafor", proc: "D4910 Perio Maint", fee: "$180", payer: "Aetna DMO", status: "pending" },
  { patient: "Diana Patel", proc: "D8040 Ortho Comprehensive", fee: "$280", payer: "MetLife", status: "pre-auth" },
  { patient: "Michael Torres", proc: "D2950+D2740 #17", fee: "$1,620", payer: "UHC", status: "scrubbing" },
];

const CLAIMS_SCRUB_CATCHES = [
  { issue: "Missing tooth # on D2740", fix: "Auto-added from chart", severity: "warning" },
  { issue: "D1110 frequency violation (Cigna)", fix: "Changed to D4910 \u2014 eligible", severity: "high" },
  { issue: "D2950 bundling risk", fix: "Attached narrative justification", severity: "warning" },
  { issue: "Pre-auth required D8040", fix: "Auto-submitted to MetLife", severity: "low" },
  { issue: "Missing X-ray attachment D2740", fix: "Auto-attached PA from chart", severity: "warning" },
];

const CROSSCODE_OPPS = [
  { proc: "Sleep Apnea Appliance", cdt: "D5988", icd: "G47.33", cpt: "E0486", dental: "$2,400", medical: "$1,680", status: "approved" },
  { proc: "TMJ Splint Therapy", cdt: "D7880", icd: "M26.60", cpt: "21085", dental: "$1,800", medical: "$1,260", status: "approved" },
  { proc: "Oral Biopsy", cdt: "D7286", icd: "K13.1", cpt: "40808", dental: "$450", medical: "$380", status: "pending" },
  { proc: "Bone Graft (Implant)", cdt: "D7953", icd: "M27.8", cpt: "21210", dental: "$1,200", medical: "$840", status: "submitted" },
  { proc: "CBCT \u2014 Pathology Eval", cdt: "D0367", icd: "Z13.89", cpt: "70553", dental: "$250", medical: "$220", status: "approved" },
];

const NECESSITY_LETTERS = [
  { patient: "James Okafor", proc: "D4341 SRP \u2014 All Quads", evidence: "Perio probing 4-7mm, 18% BOP, Stage III", payer: "Delta", status: "approved", val: "$820" },
  { patient: "Margaret Sullivan", proc: "D2740 Crown #3", evidence: "Fracture line visible, >50% tooth structure loss", payer: "MetLife", status: "approved", val: "$1,280" },
  { patient: "Robert Kim", proc: "D6010 Implant #14", evidence: "Missing tooth, bone sufficient per CBCT, adjacent teeth healthy", payer: "Cigna", status: "pending", val: "$2,200" },
  { patient: "Tom Davis", proc: "D6010-D6065 Full Arch", evidence: "Complete edentulism, CBCT bone eval, medical necessity for function", payer: "BCBS", status: "submitted", val: "$24,800" },
  { patient: "Diana Patel", proc: "D8080 Comprehensive Ortho", evidence: "Class II div 1 malocclusion, TMJ symptoms, functional impairment", payer: "MetLife", status: "approved", val: "$5,500" },
];

const ACTIVE_DENIALS = [
  { patient: "Margaret Sullivan", proc: "D2740 Crown #3", payer: "MetLife", reason: "Missing documentation", action: "Appeal sent \u2014 narrative + X-ray attached", val: "$1,280" },
  { patient: "Robert Kim", proc: "D0367 CBCT", payer: "Cigna", reason: "Not medically necessary", action: "Appeal + medical necessity letter auto-generated", val: "$250" },
  { patient: "Diana Patel", proc: "D8080 Ortho", payer: "MetLife", reason: "Frequency limitation", action: "Appealing \u2014 prior auth was approved", val: "$5,500" },
  { patient: "Tom Davis", proc: "D6010 Implant", payer: "BCBS", reason: "Pre-auth required", action: "Pre-auth submitted retroactively + appeal", val: "$2,200" },
];

const DENIAL_CAUSES = [
  { reason: "Missing documentation", pct: 35, color: "text-red-500" },
  { reason: "Frequency limitations", pct: 22, color: "text-amber-500" },
  { reason: "Medical necessity", pct: 17, color: "text-orange-500" },
  { reason: "Pre-auth required", pct: 13, color: "text-purple-500" },
  { reason: "Not covered \u2192 cross-code", pct: 9, color: "text-blue-500" },
  { reason: "Coding errors", pct: 4, color: "text-teal-500" },
];

const PHONE_CALLS = [
  { time: "2:42 PM", caller: "New \u2014 Maria Garcia", dur: "3:12", type: "AI", action: "Booked NP exam 02/18. Collected insurance (Delta PPO). Sent intake SMS.", status: "resolved" },
  { time: "2:38 PM", caller: "Diana Patel", dur: "1:45", type: "AI", action: "Confirmed Invisalign check 02/14. Asked about whitening \u2014 offered consult.", status: "resolved" },
  { time: "2:31 PM", caller: "Unknown 916-555-8821", dur: "2:08", type: "AI", action: "Insurance implant question. Explained benefits. Booked free consult.", status: "resolved" },
  { time: "2:24 PM", caller: "Tom Davis", dur: "0:45", type: "AI", action: "Rx refill request. Flagged for Dr. Chen approval.", status: "escalated" },
  { time: "2:18 PM", caller: "Dr. Anderson's Office", dur: "2:30", type: "Staff", action: "Specialist referral \u2014 transferred to Maria G.", status: "transferred" },
  { time: "1:55 PM", caller: "Missed 916-555-3344", dur: "\u2014", type: "AI", action: "Auto-callback <2 min. New patient booked 02/20 8AM.", status: "recovered" },
];

const AI_CAPABILITIES = [
  "Answer with practice greeting",
  "Book/reschedule/cancel appointments",
  "Verify insurance on call",
  "Send intake forms via SMS",
  "Answer FAQs (hours, services, pricing)",
  "After-hours emergency triage",
  "Auto-callback missed calls <2min",
  "Reactivation calls to overdue patients",
  "Collections reminder calls",
  "Spanish/Mandarin/Vietnamese",
  "Escalate with full context",
  "Record & transcribe all calls",
];

const VOICE_SOAP = [
  { label: "S", text: "Patient presents for implant follow-up #17. Reports mild tenderness, no pain. Chewing carefully.", color: "text-blue-500 border-blue-500/30" },
  { label: "O", text: "Implant #17 stable. Tissue healing well. No suppuration. Probing 2mm circumferential. Occlusion checked.", color: "text-teal-500 border-teal-500/30" },
  { label: "A", text: "Implant #17 osseointegration progressing normally at 8 weeks.", color: "text-purple-500 border-purple-500/30" },
  { label: "P", text: "Continue soft diet 2 weeks. Return 4 weeks for final impression. D6058 abutment + D6065 crown.", color: "text-orange-500 border-orange-500/30" },
];

const ACCEPTANCE_PRESENTATIONS = [
  { patient: "Robert Kim", tx: "Implant #14", total: "$5,050", ins: "$2,095", oop: "$2,955", mo: "$123/mo", status: "pending", days: 3 },
  { patient: "Margaret Sullivan", tx: "Crown #3 + SRP", total: "$2,100", ins: "$1,240", oop: "$860", mo: "$143/mo", status: "accepted", days: 0 },
  { patient: "Sophia Adams", tx: "Invisalign Full", total: "$5,500", ins: "$2,000", oop: "$3,500", mo: "$291/mo", status: "pending", days: 7 },
  { patient: "Tom Davis", tx: "Full Arch", total: "$24,800", ins: "$4,000", oop: "$20,800", mo: "$433/mo", status: "pending", days: 14 },
  { patient: "Emma Rodriguez", tx: "Veneers x4", total: "$6,400", ins: "$0", oop: "$6,400", mo: "$266/mo", status: "declined", days: 5 },
];

const OBJECTION_ANALYSIS = [
  { obj: "Too expensive", pct: 42, ai: "Auto-show monthly payment", color: "text-red-500" },
  { obj: "Need to think", pct: 28, ai: "3-day follow-up w/ education", color: "text-amber-500" },
  { obj: "Not sure necessary", pct: 18, ai: "Send AI X-ray overlay", color: "text-orange-500" },
  { obj: "Want 2nd opinion", pct: 8, ai: "Share clinical guidelines", color: "text-blue-500" },
  { obj: "Dental anxiety", pct: 4, ai: "Offer sedation + testimonials", color: "text-purple-500" },
];

const FEE_SCHEDULE = [
  { cdt: "D0120", proc: "Periodic Exam", your: "$65", ucr: "$78", delta: "$58", cigna: "$62", action: "Raise $13" },
  { cdt: "D0274", proc: "Bitewings (4)", your: "$72", ucr: "$85", delta: "$64", cigna: "$68", action: "Raise $13" },
  { cdt: "D1110", proc: "Prophy Adult", your: "$105", ucr: "$128", delta: "$98", cigna: "$102", action: "Raise $23" },
  { cdt: "D2740", proc: "Crown Porcelain", your: "$1,180", ucr: "$1,340", delta: "$1,040", cigna: "$1,120", action: "Raise $160" },
  { cdt: "D2750", proc: "Crown PFM", your: "$1,080", ucr: "$1,240", delta: "$960", cigna: "$1,020", action: "Raise $160" },
  { cdt: "D6010", proc: "Implant Body", your: "$2,200", ucr: "$2,480", delta: "N/A", cigna: "$1,980", action: "Raise $280" },
  { cdt: "D7210", proc: "Surg Extraction", your: "$340", ucr: "$385", delta: "$310", cigna: "$325", action: "Raise $45" },
];

const PROVIDER_SCORECARD = [
  { name: "Dr. Chen", prod: "$98,400", perDay: "$9,840", patients: 124, accept: "78%", avgTx: "$2,840", collections: "99.2%", score: 96 },
  { name: "Dr. Park", prod: "$62,800", perDay: "$6,980", patients: 98, accept: "72%", avgTx: "$1,920", collections: "98.8%", score: 91 },
  { name: "Dr. Smith", prod: "$37,000", perDay: "$7,400", patients: 62, accept: "68%", avgTx: "$1,480", collections: "97.4%", score: 84 },
];

const PAYER_SCORECARD = [
  { payer: "Delta Dental", approval: "94%", days: "12", denial: "6%", reimburse: "82%", crossCode: "$4,200", score: 92 },
  { payer: "Cigna PPO", approval: "88%", days: "18", denial: "12%", reimburse: "78%", crossCode: "$6,800", score: 85 },
  { payer: "MetLife PPO", approval: "86%", days: "22", denial: "14%", reimburse: "75%", crossCode: "$3,400", score: 78 },
  { payer: "Aetna DMO", approval: "92%", days: "8", denial: "8%", reimburse: "68%", crossCode: "$1,200", score: 82 },
  { payer: "BCBS FEP", approval: "90%", days: "14", denial: "10%", reimburse: "84%", crossCode: "$2,800", score: 88 },
];

const COMPLIANCE_ISSUES = [
  { issue: "Missing narrative D2740", provider: "Dr. Park", cases: 3, risk: "$3,840", action: "Auto-fix available" },
  { issue: "Incomplete perio charting", provider: "Sarah RDH", cases: 4, risk: "$2,160", action: "Template applied" },
  { issue: "D0220 without clinical justification", provider: "Dr. Chen", cases: 2, risk: "$500", action: "Narrative added" },
  { issue: "Bundling risk D2950+D2740", provider: "Dr. Smith", cases: 2, risk: "$3,200", action: "Separate claims" },
  { issue: "CDT code mismatch vs notes", provider: "Dr. Park", cases: 1, risk: "$1,280", action: "Code corrected" },
];

const DOC_COMPLETENESS = [
  { label: "Clinical Notes", pct: 98, color: "text-emerald-500" },
  { label: "Radiograph Documentation", pct: 94, color: "text-emerald-500" },
  { label: "Treatment Narratives", pct: 87, color: "text-amber-500" },
  { label: "Consent Forms", pct: 96, color: "text-emerald-500" },
  { label: "Insurance Attachments", pct: 91, color: "text-blue-500" },
];

const BI_METRICS = [
  { label: "Revenue vs Target", value: "$198,240 / $195,000", pct: 101.7, color: "text-emerald-500" },
  { label: "New Patients vs Target", value: "38 / 45", pct: 84.4, color: "text-amber-500" },
  { label: "Case Acceptance", value: "74% / 70%", pct: 105.7, color: "text-emerald-500" },
  { label: "Collections Ratio", value: "99.5% / 98%", pct: 101.5, color: "text-emerald-500" },
  { label: "Overhead Ratio", value: "57.3% / 59%", pct: 97.1, color: "text-emerald-500" },
  { label: "AI Automation", value: "84% tasks automated", pct: 84, color: "text-blue-500" },
];

const BI_RECOMMENDATIONS = [
  "Raise fees on 34 procedures below UCR 80th percentile \u2014 projected +$42,800/yr",
  "Cross-code sleep appliances and TMJ cases to medical \u2014 projected +$28,400/yr",
  "Reduce no-show rate from 8% to 3% with AI reminders \u2014 projected +$18,200/yr",
  "Expand hygiene hours by 1 day/week \u2014 demand supports 12 additional patients",
  "Add CBCT implant marketing campaign \u2014 ROI projected 8.2x based on current conversion",
];

function IntakeModule() {
  return (
    <div>
      <SectionHeader title="Digital Intake & Patient Portal" subtitle="Online forms, e-signatures, insurance card capture, patient self-service" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={ClipboardList} label="Forms Submitted Today" value="12" sub="8 new patients" subColor="text-blue-500" />
        <KpiCard icon={Pen} label="E-Signatures" value="34" sub="100% HIPAA compliant" subColor="text-emerald-500" />
        <KpiCard icon={Camera} label="Insurance Cards Captured" value="11" sub="Auto-verified" subColor="text-purple-500" />
        <KpiCard icon={Clock} label="Avg Intake Time" value="4.2 min" sub="Down from 18 min paper" subColor="text-teal-500" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Active Intake Forms</div>
            <div className="space-y-0">
              {INTAKE_FORMS.map((f, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b last:border-0" data-testid={`intake-form-${i}`}>
                  <div>
                    <div className="text-sm font-semibold">{f.name}</div>
                    <div className="text-xs text-muted-foreground">{f.fields} fields</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-emerald-500">{f.completion}</span>
                    <StatusBadge status="Active" />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Patient Portal Features</div>
            <div className="space-y-0">
              {PORTAL_FEATURES.map((f, i) => (
                <div key={i} className="flex items-center gap-3 py-2 border-b last:border-0" data-testid={`portal-feature-${i}`}>
                  <span className="text-sm flex-1">{f.feat}</span>
                  <StatusBadge status={f.status} />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="text-sm font-bold mb-3">AI Intake Automation Flow</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs text-muted-foreground">
            <div><strong className="text-blue-500">1. Pre-Visit (48hr):</strong> SMS sent with intake link. Patient completes forms on phone. Insurance card auto-OCR extracts plan info.</div>
            <div><strong className="text-purple-500">2. Auto-Verify:</strong> Insurance eligibility checked instantly. Benefits breakdown populated. Copay/deductible calculated. Treatment estimates ready.</div>
            <div><strong className="text-emerald-500">3. Day-Of:</strong> Patient checks in via QR code. Med hx flagged for provider review. Allergies/alerts populated in chart. Zero clipboard time.</div>
            <div><strong className="text-orange-500">4. Post-Visit:</strong> Portal access activated. Treatment plan viewable. Payment link sent. Next appointment booking. Recall scheduled.</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function PerioModule() {
  return (
    <div>
      <SectionHeader title="Periodontal Charting" subtitle="6-point probing, BOP, recession, furcation, mobility" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={BarChart3} label="Avg Probing Depth" value="3.2mm" sub="Previous: 3.8mm" subColor="text-emerald-500" />
        <KpiCard icon={Activity} label="BOP Sites" value="18%" sub="Target: <10%" subColor="text-red-500" />
        <KpiCard icon={TrendingUp} label="Sites >4mm" value="24" sub="Previous: 31" subColor="text-amber-500" />
        <KpiCard icon={Shield} label="Perio Diagnosis" value="Stage III" sub="Grade B generalized" subColor="text-purple-500" />
      </div>
      <Card className="mb-4">
        <CardContent className="p-4">
          <div className="text-sm font-bold mb-4">Probing Chart - Margaret Sullivan - 2026-02-11</div>
          {[
            { label: "Facial - Upper", teeth: UPPER_TEETH, side: "F" as const },
            { label: "Lingual - Upper", teeth: UPPER_TEETH, side: "L" as const },
            { label: "Facial - Lower", teeth: LOWER_TEETH, side: "F" as const },
            { label: "Lingual - Lower", teeth: LOWER_TEETH, side: "L" as const },
          ].map((row, ri) => (
            <div key={ri} className="mb-3">
              <div className="text-[10px] font-bold tracking-wider uppercase text-muted-foreground mb-1">{row.label}</div>
              <div className="flex gap-0.5">
                {row.teeth.map((t) => {
                  const p = PROBING_DATA[t] || DEFAULT_PROBING;
                  const vals = row.side === "F" ? p.slice(0, 3) : p.slice(3, 6);
                  return (
                    <div key={t} className="flex-1 text-center" data-testid={`tooth-${t}-${row.side}`}>
                      <div className="flex justify-center gap-px mb-0.5">
                        {vals.map((v, vi) => (
                          <div
                            key={vi}
                            className={`w-3.5 h-[18px] rounded-sm flex items-center justify-center text-[9px] font-extrabold font-mono ${
                              v >= 6 ? "bg-red-500/20 text-red-600 dark:text-red-400" :
                              v >= 4 ? "bg-amber-500/20 text-amber-600 dark:text-amber-400" :
                              "bg-muted text-emerald-600 dark:text-emerald-400"
                            }`}
                          >
                            {v}
                          </div>
                        ))}
                      </div>
                      <div className="text-[8px] font-bold text-muted-foreground">{t}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
          <div className="flex gap-4 pt-3 border-t mt-2">
            {[
              { range: "1-3mm", label: "Healthy", cls: "bg-emerald-500" },
              { range: "4-5mm", label: "Moderate", cls: "bg-amber-500" },
              { range: "6mm+", label: "Severe", cls: "bg-red-500" },
            ].map((l) => (
              <div key={l.range} className="flex items-center gap-1.5">
                <div className={`w-3 h-3 rounded-sm ${l.cls}`} />
                <span className="text-[10px] text-muted-foreground">{l.range} - {l.label}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      <Card className="border-purple-500/20 bg-purple-500/5">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <Brain className="h-4 w-4 text-purple-500" />
            <span className="text-sm font-bold text-purple-600 dark:text-purple-400">AI Perio Assessment</span>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Diagnosis: <strong className="text-foreground">Periodontitis Stage III, Grade B, Generalized</strong>. 24 sites &ge;4mm (improved from 31). BOP at 18% (target &lt;10%). Recommend: continued SRP remaining quadrants, 3-month perio maintenance intervals, consider localized antibiotic therapy (Arestin) for sites &ge;5mm. Insurance narrative auto-generated for D4341/D4342 with clinical justification.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function SoapModule() {
  return (
    <div>
      <SectionHeader title="Clinical Notes - AI-Assisted SOAP" subtitle="Voice-to-text, AI expansion, CDT auto-coding" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Today's Notes</div>
            {SOAP_NOTES.map((n, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b last:border-0" data-testid={`soap-note-${i}`}>
                <div>
                  <div className="text-sm font-semibold">{n.patient}</div>
                  <div className="text-xs text-muted-foreground">{n.proc} - {n.time} - {n.provider}</div>
                </div>
                <StatusBadge status={n.status} />
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">SOAP Note - Margaret Sullivan</div>
            {SOAP_SECTIONS.map((s, i) => (
              <div key={i} className={`mb-3 p-3 border-l-4 rounded-r-md ${s.color}`}>
                <div className="text-[10px] font-bold tracking-wider uppercase mb-1">{s.label}</div>
                <div className="text-xs text-muted-foreground leading-relaxed">{s.text}</div>
              </div>
            ))}
            <div className="flex gap-2 mt-3 flex-wrap">
              <Button size="sm" data-testid="button-sign-note">
                <CheckCircle className="h-3.5 w-3.5 mr-1" />Sign Note
              </Button>
              <Button size="sm" variant="outline" data-testid="button-voice-to-text">
                <Mic className="h-3.5 w-3.5 mr-1" />Voice-to-Text
              </Button>
              <Button size="sm" variant="outline" data-testid="button-ai-expand">
                <Brain className="h-3.5 w-3.5 mr-1" />AI Expand
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function AIImagingModule() {
  return (
    <div>
      <SectionHeader title="Digital Imaging Viewer" subtitle="X-ray viewer, CBCT, intraoral photos, AI pathology detection" />
      <div className="grid grid-cols-3 gap-3 mb-4">
        <KpiCard icon={Camera} label="Images Today" value="28" />
        <KpiCard icon={Bot} label="AI Detections" value="6" sub="3 caries, 2 perio, 1 periapical" subColor="text-red-500" />
        <KpiCard icon={Hash} label="Storage Used" value="124 GB" sub="of 500 GB" subColor="text-muted-foreground" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2 bg-card dark:bg-zinc-900">
          <CardContent className="p-4">
            <div className="rounded-lg bg-zinc-950 h-48 flex items-center justify-center mb-3 relative">
              <Eye className="h-10 w-10 text-zinc-700" />
              <div className="absolute top-2 left-2 flex gap-1">
                <StatusBadge status="active" />
              </div>
            </div>
            <div className="flex gap-1.5 flex-wrap">
              {["Brightness", "Contrast", "Invert", "Zoom", "Measure", "Annotate", "Compare", "AI Detect"].map((t) => (
                <Button key={t} size="sm" variant="outline" className="text-xs" data-testid={`button-imaging-${t.toLowerCase()}`}>
                  {t}
                </Button>
              ))}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">AI Pathology Detection</div>
            {AI_FINDINGS.map((f, i) => (
              <div key={i} className="py-2 border-b last:border-0" data-testid={`ai-finding-${i}`}>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs font-semibold">{f.finding}</span>
                  <StatusBadge status={f.severity} />
                </div>
                <div className="flex items-center gap-2">
                  <Progress value={f.confidence} className="h-1.5 flex-1" />
                  <span className="text-[10px] font-bold text-muted-foreground">{f.confidence}%</span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ConsentModule() {
  return (
    <div>
      <SectionHeader title="Consent Form Builder" subtitle="Digital consents with e-signature, procedure-specific templates" />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {CONSENT_FORMS.map((f, i) => (
          <Card key={i} data-testid={`consent-form-${i}`}>
            <CardContent className="p-4">
              <div className="text-sm font-bold mb-1">{f.name}</div>
              <div className="text-xs text-muted-foreground mb-2">{f.fields} fields - {f.procedures}</div>
              <div className="text-xs text-muted-foreground mb-3">{f.sigs.toLocaleString()} signatures</div>
              <div className="flex gap-1.5 flex-wrap">
                <StatusBadge status="Active" />
                <StatusBadge status="E-Signature" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

function ErxModule() {
  return (
    <div>
      <SectionHeader title="E-Prescribing (eRx)" subtitle="EPCS-compliant, drug interaction checking, pharmacy integration" />
      <div className="grid grid-cols-3 gap-3 mb-4">
        <KpiCard icon={Send} label="Rx Sent Today" value="8" />
        <KpiCard icon={AlertTriangle} label="Interactions Flagged" value="2" sub="Requires review" subColor="text-amber-500" />
        <KpiCard icon={Building2} label="Pharmacies Connected" value="47" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Recent Prescriptions</div>
            {ERX_PRESCRIPTIONS.map((rx, i) => (
              <div key={i} className="py-2 border-b last:border-0" data-testid={`rx-${i}`}>
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold">{rx.patient}</div>
                  {rx.alert && <StatusBadge status="warning" />}
                </div>
                <div className="text-xs text-muted-foreground">{rx.drug} - {rx.sig}</div>
                <div className="text-xs text-muted-foreground">{rx.pharmacy}</div>
                {rx.alert && <div className="text-xs text-amber-500 font-semibold mt-1">{rx.alert}</div>}
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">AI Drug Interaction Engine</div>
            <div className="p-3 border-l-4 border-red-500 bg-red-500/5 rounded-r-md mb-3">
              <div className="flex items-center gap-2 mb-1">
                <AlertCircle className="h-4 w-4 text-red-500" />
                <span className="text-xs font-bold text-red-600 dark:text-red-400">BLOCKED</span>
              </div>
              <p className="text-xs text-muted-foreground">Margaret Sullivan: Penicillin allergy documented. Amoxicillin auto-blocked. Alternative: Clindamycin 300mg QID recommended.</p>
            </div>
            <div className="p-3 border-l-4 border-amber-500 bg-amber-500/5 rounded-r-md">
              <div className="flex items-center gap-2 mb-1">
                <AlertTriangle className="h-4 w-4 text-amber-500" />
                <span className="text-xs font-bold text-amber-600 dark:text-amber-400">WARNING</span>
              </div>
              <p className="text-xs text-muted-foreground">Michael Torres: Warfarin + Clindamycin interaction. May increase anticoagulant effect. Monitor INR closely. Prescriber acknowledged.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function OrthoModule() {
  return (
    <div>
      <SectionHeader title="Orthodontic Tracker" subtitle="Invisalign tray tracking, bracket charting, compliance" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={CircleDot} label="Active Ortho Cases" value="34" />
        <KpiCard icon={Clock} label="Check-ins This Week" value="12" />
        <KpiCard icon={CheckCircle} label="On-Track Rate" value="91%" subColor="text-emerald-500" />
        <KpiCard icon={DollarSign} label="Ortho Revenue MTD" value="$48,200" />
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="text-sm font-bold mb-3">Invisalign Case Tracker</div>
          <div className="grid grid-cols-6 gap-2 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
            <div>Patient</div><div>Tray Progress</div><div>Progress</div><div>Compliance</div><div>Status</div><div>Next Appt</div>
          </div>
          {ORTHO_CASES.map((c, i) => (
            <div key={i} className="grid grid-cols-6 gap-2 py-3 border-b last:border-0 items-center" data-testid={`ortho-case-${i}`}>
              <div className="text-sm font-semibold">{c.patient}</div>
              <div className="text-xs">{c.current}/{c.total}</div>
              <div><Progress value={(c.current / c.total) * 100} className="h-2" /></div>
              <div className="text-xs font-semibold">{c.compliance}%</div>
              <div><StatusBadge status={c.status} /></div>
              <div className="text-xs text-muted-foreground">{c.next}</div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ImplantModule() {
  return (
    <div>
      <SectionHeader title="Implant Case Tracker" subtitle="Stage-based workflow from consult through final restoration" />
      <div className="grid grid-cols-3 gap-3 mb-4">
        <KpiCard icon={Wrench} label="Active Implant Cases" value="18" />
        <KpiCard icon={DollarSign} label="Implant Revenue MTD" value="$87,400" />
        <KpiCard icon={CheckCircle} label="Success Rate" value="98.4%" subColor="text-emerald-500" />
      </div>
      <div className="grid grid-cols-5 gap-3">
        {(["Consult", "Surgery", "Healing", "Impression", "Restoration"] as const).map((stage) => {
          const key = stage.toLowerCase() as keyof typeof IMPLANT_PIPELINE;
          const patients = IMPLANT_PIPELINE[key];
          return (
            <Card key={stage}>
              <CardContent className="p-3">
                <div className="flex items-center justify-between gap-2 mb-3 flex-wrap">
                  <span className="text-xs font-bold">{stage}</span>
                  <Badge variant="secondary" className="text-[10px] no-default-hover-elevate no-default-active-elevate">{patients.length}</Badge>
                </div>
                <div className="space-y-2">
                  {patients.map((p, i) => (
                    <div key={i} className="text-xs py-1.5 border-b last:border-0" data-testid={`implant-${stage.toLowerCase()}-${i}`}>
                      <div className="font-semibold">{p.name}</div>
                      <div className="text-muted-foreground">{p.tooth}</div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function LabModule() {
  return (
    <div>
      <SectionHeader title="Lab Case Manager" subtitle="Track cases from scan to delivery" />
      <div className="grid grid-cols-3 gap-3 mb-4">
        <KpiCard icon={FlaskConical} label="Active Lab Cases" value="23" sub="8 overdue" subColor="text-red-500" />
        <KpiCard icon={DollarSign} label="Lab Costs MTD" value="$14,200" />
        <KpiCard icon={Clock} label="Avg Turnaround" value="8.2 days" />
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-6 gap-2 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
            <div>Patient</div><div>Type</div><div>Lab</div><div>Sent</div><div>Due</div><div>Status</div>
          </div>
          {LAB_CASES.map((c, i) => (
            <div key={i} className="grid grid-cols-6 gap-2 py-3 border-b last:border-0 items-center" data-testid={`lab-case-${i}`}>
              <div className="text-sm font-semibold">{c.patient}</div>
              <div className="text-xs">{c.type}</div>
              <div className="text-xs text-muted-foreground">{c.lab}</div>
              <div className="text-xs text-muted-foreground">{c.sent}</div>
              <div className="text-xs text-muted-foreground">{c.due}</div>
              <div><StatusBadge status={c.status} /></div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ReferralModule() {
  return (
    <div>
      <SectionHeader title="Referral Management" subtitle="Track inbound/outbound referrals, specialist network" />
      <div className="grid grid-cols-3 gap-3 mb-4">
        <KpiCard icon={ArrowRight} label="Referrals Out" value="14" />
        <KpiCard icon={RefreshCcw} label="Referrals In" value="22" sub="$186K referred revenue" subColor="text-emerald-500" />
        <KpiCard icon={Users} label="Network Specialists" value="12" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Top Referring Doctors</div>
            {REFERRING_DOCTORS.map((d, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b last:border-0" data-testid={`referring-doc-${i}`}>
                <div className="text-sm">{d.name}</div>
                <div className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground">{d.referred} referred</span>
                  <span className="text-xs font-semibold text-emerald-500">{d.revenue}</span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Outbound Referral Status</div>
            {OUTBOUND_REFERRALS.map((r, i) => (
              <div key={i} className="py-2 border-b last:border-0" data-testid={`outbound-ref-${i}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold">{r.patient}</span>
                  <StatusBadge status={r.status} />
                </div>
                <div className="text-xs text-muted-foreground">{r.specialist} - {r.reason}</div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function InventoryModule() {
  return (
    <div>
      <SectionHeader title="Inventory & Supply Management" subtitle="Auto-reorder, vendor comparison, expiration tracking" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={Package} label="Total SKUs" value="342" />
        <KpiCard icon={AlertTriangle} label="Low Stock Alerts" value="8" sub="3 critical" subColor="text-red-500" />
        <KpiCard icon={Clock} label="Expiring Soon" value="12" subColor="text-amber-500" />
        <KpiCard icon={DollarSign} label="Monthly Spend" value="$11,400" />
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-7 gap-2 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
            <div>Item</div><div>SKU</div><div>Qty</div><div>Reorder At</div><div>Unit</div><div>Cost</div><div>Status</div>
          </div>
          {INVENTORY_ITEMS.map((item, i) => (
            <div key={i} className="grid grid-cols-7 gap-2 py-3 border-b last:border-0 items-center" data-testid={`inventory-item-${i}`}>
              <div className="text-sm font-semibold">{item.name}</div>
              <div className="text-xs text-muted-foreground font-mono">{item.sku}</div>
              <div className="text-xs font-semibold">{item.qty}</div>
              <div className="text-xs text-muted-foreground">{item.reorder}</div>
              <div className="text-xs text-muted-foreground">{item.unit}</div>
              <div className="text-xs">{item.cost}</div>
              <div><StatusBadge status={item.status} /></div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function HrModule() {
  return (
    <div>
      <SectionHeader title="HR & Employee Management" subtitle="Time clock, PTO, scheduling, payroll, CE tracking" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={Users} label="Total Staff" value="14" />
        <KpiCard icon={CheckCircle} label="Clocked In Now" value="12" subColor="text-emerald-500" />
        <KpiCard icon={Clock} label="PTO Requests" value="3" subColor="text-amber-500" />
        <KpiCard icon={AlertTriangle} label="CE Expiring <90d" value="2" subColor="text-red-500" />
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-7 gap-2 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
            <div>Employee</div><div>Role</div><div>Status</div><div>Clock In</div><div>Hours</div><div>PTO Balance</div><div>License Exp</div>
          </div>
          {HR_EMPLOYEES.map((emp, i) => (
            <div key={i} className="grid grid-cols-7 gap-2 py-3 border-b last:border-0 items-center" data-testid={`employee-${i}`}>
              <div className="text-sm font-semibold">{emp.name}</div>
              <div className="text-xs text-muted-foreground">{emp.role}</div>
              <div><StatusBadge status={emp.clockedIn ? "active" : "pending"} /></div>
              <div className="text-xs">{emp.clockTime}</div>
              <div className="text-xs font-semibold">{emp.hours}</div>
              <div className="text-xs">{emp.pto}</div>
              <div className="text-xs text-muted-foreground">{emp.license}</div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function SterilizationModule() {
  return (
    <div>
      <SectionHeader title="Sterilization & OSHA Compliance" subtitle="Autoclave logs, biological indicators, compliance checklists" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={TestTube} label="Autoclave Cycles Today" value="8" sub="All passed" subColor="text-emerald-500" />
        <KpiCard icon={CheckCircle} label="Last Spore Test" value="Pass" subColor="text-emerald-500" />
        <KpiCard icon={Shield} label="OSHA Compliance" value="98%" />
        <KpiCard icon={Activity} label="Radiation Badges" value="Current" subColor="text-emerald-500" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Today's Autoclave Log</div>
            {AUTOCLAVE_LOG.map((c, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b last:border-0" data-testid={`autoclave-${i}`}>
                <div>
                  <div className="text-xs font-semibold">Cycle {c.cycle} - {c.time}</div>
                  <div className="text-xs text-muted-foreground">{c.load} - {c.temp} - {c.duration}</div>
                </div>
                <StatusBadge status={c.status} />
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">OSHA Compliance Checklist</div>
            {OSHA_CHECKLIST.map((item, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b last:border-0" data-testid={`osha-${i}`}>
                <div>
                  <div className="text-xs font-semibold">{item.item}</div>
                  <div className="text-xs text-muted-foreground">{item.frequency} - Last: {item.lastDone}</div>
                </div>
                <StatusBadge status={item.status} />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function FinancialModule() {
  return (
    <div>
      <SectionHeader title="Financial Command Center" subtitle="P&L, cash flow, budgets, overhead breakdown" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={DollarSign} label="YTD Revenue" value="$498,240" sub="+18% vs LY" subColor="text-emerald-500" />
        <KpiCard icon={TrendingUp} label="Net Income MTD" value="$86,400" sub="43.2% margin" subColor="text-emerald-500" />
        <KpiCard icon={Activity} label="Overhead %" value="57.3%" />
        <KpiCard icon={AlertCircle} label="A/P Outstanding" value="$18,200" subColor="text-amber-500" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">P&L Summary - February 2026</div>
            {PNL_ITEMS.map((item, i) => (
              <div key={i} className={`flex items-center justify-between py-2 border-b last:border-0 ${item.bold ? "font-bold" : ""}`} data-testid={`pnl-${i}`}>
                <span className={`text-xs ${item.bold ? "font-bold" : "text-muted-foreground"}`}>{item.label}</span>
                <span className={`text-xs ${item.bold ? "font-bold" : ""}`}>{item.value}</span>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Overhead Breakdown</div>
            {OVERHEAD_BREAKDOWN.map((cat, i) => (
              <div key={i} className="py-3 border-b last:border-0" data-testid={`overhead-${i}`}>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-semibold">{cat.category}</span>
                  <span className="text-xs text-muted-foreground">{cat.pct}% / {cat.target}% target</span>
                </div>
                <Progress value={(cat.pct / cat.target) * 100} className="h-2" />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function FinancingModule() {
  return (
    <div>
      <SectionHeader title="Patient Financing Engine" subtitle="In-house payment plans, auto-charge" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={CreditCard} label="Active Plans" value="47" sub="$284K outstanding" subColor="text-blue-500" />
        <KpiCard icon={CheckCircle} label="On-Time Rate" value="94%" subColor="text-emerald-500" />
        <KpiCard icon={DollarSign} label="Collected via Plans MTD" value="$42,800" />
        <KpiCard icon={Activity} label="Avg Plan Size" value="$3,240" />
      </div>
      <Card className="mb-4">
        <CardContent className="p-4">
          <div className="grid grid-cols-7 gap-2 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
            <div>Patient</div><div>Treatment</div><div>Total</div><div>Monthly</div><div>Remaining</div><div>Payments</div><div>Status</div>
          </div>
          {FINANCING_PLANS.map((plan, i) => (
            <div key={i} className="grid grid-cols-7 gap-2 py-3 border-b last:border-0 items-center" data-testid={`financing-plan-${i}`}>
              <div className="text-sm font-semibold">{plan.patient}</div>
              <div className="text-xs">{plan.treatment}</div>
              <div className="text-xs font-semibold">${plan.total.toLocaleString()}</div>
              <div className="text-xs">${plan.monthly.toFixed(2)}</div>
              <div className="text-xs">${plan.remaining.toLocaleString()}</div>
              <div className="text-xs">{plan.payments}</div>
              <div><StatusBadge status={plan.status} /></div>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardContent className="p-4">
          <div className="text-sm font-bold mb-3">Auto-Financing Flow</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 text-xs text-muted-foreground">
            <div><strong className="text-blue-500">1. Treatment Accepted:</strong> Patient accepts plan. System auto-calculates payment options: 6, 12, 18, 24 month terms with 0% or low interest.</div>
            <div><strong className="text-purple-500">2. Credit Check:</strong> Soft credit check via integrated lending partner. Instant approval/denial. Multiple plan options presented.</div>
            <div><strong className="text-emerald-500">3. Auto-Charge:</strong> Card on file auto-charged monthly. SMS receipt sent. Dashboard tracks all active plans and payment status.</div>
            <div><strong className="text-orange-500">4. Collections:</strong> Missed payment auto-alerts. 3-day grace period. SMS/email reminders. Escalation to payment plan modification if needed.</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function MarketingModule() {
  return (
    <div>
      <SectionHeader title="Marketing Suite" subtitle="Content calendar, ad management, review monitoring, ROI" />
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 mb-4">
        <KpiCard icon={Users} label="New Patients Feb" value="38" />
        <KpiCard icon={DollarSign} label="Marketing Spend" value="$8,200" />
        <KpiCard icon={TrendingUp} label="Cost Per Patient" value="$216" />
        <KpiCard icon={Star} label="Google Rating" value="4.9" subColor="text-emerald-500" />
        <KpiCard icon={Activity} label="Social Followers" value="2,840" />
        <KpiCard icon={DollarSign} label="Referral Revenue" value="$186K" subColor="text-emerald-500" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Channel Performance</div>
            <div className="grid grid-cols-5 gap-2 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
              <div>Channel</div><div>Spend</div><div>Patients</div><div>CPA</div><div>ROI</div>
            </div>
            {MARKETING_CHANNELS.map((ch, i) => (
              <div key={i} className="grid grid-cols-5 gap-2 py-2 border-b last:border-0 items-center" data-testid={`channel-${i}`}>
                <div className="text-xs font-semibold">{ch.channel}</div>
                <div className="text-xs">{ch.spend}</div>
                <div className="text-xs font-semibold">{ch.patients}</div>
                <div className="text-xs">{ch.cpa}</div>
                <div className="text-xs font-semibold text-emerald-500">{ch.roi}</div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Content Calendar</div>
            {CONTENT_CALENDAR.map((item, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b last:border-0" data-testid={`content-${i}`}>
                <div>
                  <div className="text-xs font-semibold">{item.day}</div>
                  <div className="text-xs text-muted-foreground">{item.content}</div>
                  <div className="text-xs text-muted-foreground">{item.platform}</div>
                </div>
                <StatusBadge status={item.status} />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function NpsModule() {
  return (
    <div>
      <SectionHeader title="Patient Satisfaction & NPS" subtitle="Post-visit surveys, NPS tracking, sentiment analysis" />
      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-3 mb-4">
        <KpiCard icon={Star} label="NPS Score" value="78" subColor="text-emerald-500" />
        <KpiCard icon={CheckCircle} label="Promoters" value="82%" subColor="text-emerald-500" />
        <KpiCard icon={Activity} label="Passives" value="14%" subColor="text-amber-500" />
        <KpiCard icon={AlertTriangle} label="Detractors" value="4%" subColor="text-red-500" />
        <KpiCard icon={Send} label="Response Rate" value="64%" />
        <KpiCard icon={Star} label="Avg Rating" value="4.87" subColor="text-emerald-500" />
      </div>
      <Card className="border-blue-500/20 bg-blue-500/5">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <Bot className="h-4 w-4 text-blue-500" />
            <span className="text-sm font-bold text-blue-600 dark:text-blue-400">AI Review Routing</span>
          </div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            Promoters (9-10) automatically receive Google/Yelp review request via SMS within 30 minutes of survey completion. Detractors (0-6) are routed to office manager for immediate follow-up call. Passives (7-8) receive a thank-you email with improvement feedback form. All reviews monitored in real-time with AI sentiment analysis.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function MultilocModule() {
  return (
    <div>
      <SectionHeader title="Multi-Location Command Center" subtitle="Side-by-side performance, location benchmarking" />
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-7 gap-2 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
            <div>Location</div><div>MTD Production</div><div>Collections %</div><div>New Patients</div><div>Case Accept</div><div>Overhead</div><div>Net Margin</div>
          </div>
          {MULTILOC_DATA.map((loc, i) => (
            <div key={i} className="grid grid-cols-7 gap-2 py-3 border-b items-center" data-testid={`location-${i}`}>
              <div className="text-sm font-semibold">{loc.location}</div>
              <div className="text-xs font-semibold">{loc.production}</div>
              <div className="text-xs">{loc.collections}</div>
              <div className="text-xs">{loc.newPatients}</div>
              <div className="text-xs">{loc.caseAccept}</div>
              <div className="text-xs">{loc.overhead}</div>
              <div className="text-xs font-semibold text-emerald-500">{loc.margin}</div>
            </div>
          ))}
          <div className="grid grid-cols-7 gap-2 py-3 items-center font-bold">
            <div className="text-sm">Total</div>
            <div className="text-xs">$264,000</div>
            <div className="text-xs">95.1%</div>
            <div className="text-xs">38</div>
            <div className="text-xs">71%</div>
            <div className="text-xs">59.2%</div>
            <div className="text-xs text-emerald-500">40.8%</div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function TelehealthModule() {
  return (
    <div>
      <SectionHeader title="Teledentistry Module" subtitle="HIPAA-compliant video consults, photo triage" />
      <div className="grid grid-cols-3 gap-3 mb-4">
        <KpiCard icon={Video} label="Video Consults MTD" value="24" sub="$4,800 billed" subColor="text-emerald-500" />
        <KpiCard icon={Camera} label="Photo Triage" value="18" />
        <KpiCard icon={CheckCircle} label="Post-Op Checks" value="34" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Today's Telehealth Queue</div>
            {TELEHEALTH_QUEUE.map((entry, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b last:border-0" data-testid={`telehealth-${i}`}>
                <div>
                  <div className="text-sm font-semibold">{entry.patient}</div>
                  <div className="text-xs text-muted-foreground">{entry.reason} - {entry.time}</div>
                </div>
                <StatusBadge status={entry.status} />
              </div>
            ))}
          </CardContent>
        </Card>
        <Card className="bg-card dark:bg-zinc-900">
          <CardContent className="p-4 flex flex-col items-center justify-center min-h-[200px]">
            <div className="rounded-full bg-zinc-800 p-4 mb-4">
              <Video className="h-8 w-8 text-emerald-400" />
            </div>
            <div className="text-sm font-bold mb-2">Video Consultation Room</div>
            <div className="text-xs text-muted-foreground mb-4">HIPAA-Compliant, End-to-End Encrypted</div>
            <Button data-testid="button-start-video-consult">
              <Video className="h-4 w-4 mr-2" />Start Video Consult
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function AiTreatmentModule() {
  return (
    <div>
      <SectionHeader title="AI Treatment Planning Assistant" subtitle="Upload imaging, AI suggests diagnosis + CDT codes" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">AI Analysis - Robert Kim</div>
            {AI_TX_FINDINGS.map((f, i) => (
              <div key={i} className={`mb-3 p-3 border-l-4 rounded-r-md ${f.color}`} data-testid={`ai-tx-finding-${i}`}>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs font-bold">{f.finding}</span>
                  <span className="text-[10px] font-bold text-muted-foreground">{f.confidence}%</span>
                </div>
                <div className="text-xs text-muted-foreground">{f.recommendation}</div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">AI-Generated Treatment Plan</div>
            {AI_TX_PHASES.map((phase, pi) => (
              <div key={pi} className="mb-4">
                <div className="text-xs font-bold tracking-wider uppercase text-muted-foreground mb-2">{phase.name}</div>
                {phase.items.map((item, ii) => (
                  <div key={ii} className="flex items-center justify-between py-1.5 border-b last:border-0">
                    <div>
                      <span className="text-xs font-mono font-bold mr-2">{item.cdt}</span>
                      <span className="text-xs">{item.desc}</span>
                    </div>
                    <span className="text-xs font-semibold">${item.fee.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            ))}
            <div className="border-t pt-3 mt-2 space-y-1">
              <div className="flex justify-between text-xs font-bold"><span>Total</span><span>$5,050</span></div>
              <div className="flex justify-between text-xs text-muted-foreground"><span>Est. Insurance</span><span>$2,095</span></div>
              <div className="flex justify-between text-xs font-bold"><span>Patient Responsibility</span><span>$2,955</span></div>
              <div className="flex justify-between text-xs text-blue-500 font-semibold"><span>Payment option</span><span>$123.13/mo x 24</span></div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function AiClinicalModule() {
  return (
    <div>
      <SectionHeader title="AI Clinical Decision Support" subtitle="Drug interactions, treatment contraindications, risk assessments" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Active Patient Alerts</div>
            {AI_CLINICAL_ALERTS.map((alert, i) => (
              <div key={i} className={`mb-3 p-3 border-l-4 rounded-r-md ${alert.color}`} data-testid={`clinical-alert-${i}`}>
                <div className="flex items-center gap-2 mb-1">
                  <StatusBadge status={alert.severity} />
                  <span className="text-xs font-bold">{alert.patient}</span>
                </div>
                <div className="text-xs font-semibold mb-1">{alert.alert}</div>
                <div className="text-xs text-muted-foreground leading-relaxed">{alert.detail}</div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">AI Protocol Recommendations</div>
            {AI_PROTOCOLS.map((protocol, i) => (
              <div key={i} className="py-3 border-b last:border-0" data-testid={`protocol-${i}`}>
                <div className="flex items-center gap-2 mb-1">
                  <Brain className="h-3.5 w-3.5 text-purple-500" />
                  <span className="text-xs font-bold">{protocol.title}</span>
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">{protocol.desc}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function ScheduleModule() {
  return (
    <div>
      <SectionHeader title="AI Scheduling & Capacity Optimizer" subtitle="Production-based scheduling, no-show prediction, same-day fill" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={Calendar} label="Chair Utilization" value="91%" sub="Target: 85%" subColor="text-emerald-500" />
        <KpiCard icon={DollarSign} label="Tomorrow's Production" value="$24,800" subColor="text-blue-500" />
        <KpiCard icon={AlertTriangle} label="No-Show Risk" value="3" sub="AI sending reminders" subColor="text-amber-500" />
        <KpiCard icon={RefreshCcw} label="Same-Day Fills" value="4" sub="From AI waitlist" subColor="text-emerald-500" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card className="lg:col-span-2">
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Tomorrow's Schedule</div>
            <div className="grid grid-cols-8 gap-1 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
              <div>Time</div><div>Dur</div><div>Chair</div><div>Provider</div><div>Patient</div><div className="col-span-1">Procedure</div><div>Prod</div><div>Risk</div>
            </div>
            {SCHEDULE_TOMORROW.map((s, i) => (
              <div key={i} className="grid grid-cols-8 gap-1 py-2 border-b last:border-0 items-center text-xs" data-testid={`schedule-row-${i}`}>
                <span className="font-mono font-bold text-blue-500">{s.time}</span>
                <span className="text-muted-foreground">{s.dur}</span>
                <span className="text-muted-foreground">{s.chair}</span>
                <span className="font-semibold text-[10px]">{s.prov}</span>
                <span className="font-bold">{s.pt}</span>
                <span className="text-muted-foreground text-[10px]">{s.proc}</span>
                <span className="font-extrabold text-emerald-500 font-mono">{s.prod}</span>
                <StatusBadge status={s.risk} />
              </div>
            ))}
          </CardContent>
        </Card>
        <div className="space-y-4">
          <Card>
            <CardContent className="p-4">
              <div className="text-sm font-bold mb-3">No-Show Risk</div>
              {NOSHOW_RISKS.map((n, i) => (
                <div key={i} className="py-2 border-b last:border-0" data-testid={`noshow-risk-${i}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold">{n.patient}</span>
                    <Badge variant="secondary" className={`text-[10px] no-default-hover-elevate no-default-active-elevate ${n.color === "text-red-500" ? "bg-red-500/15 text-red-700 dark:text-red-400" : "bg-amber-500/15 text-amber-700 dark:text-amber-400"}`}>{n.risk}</Badge>
                  </div>
                  <div className="text-[10px] text-muted-foreground">{n.reason}</div>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-sm font-bold mb-3">AI Waitlist</div>
              {WAITLIST_PATIENTS.map((w, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b last:border-0" data-testid={`waitlist-${i}`}>
                  <div>
                    <div className="text-xs font-bold">{w.patient}</div>
                    <div className="text-[10px] text-muted-foreground">{w.proc}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs font-bold text-emerald-500">{w.prod}</div>
                    <div className="text-[10px] text-muted-foreground">{w.flex}</div>
                  </div>
                </div>
              ))}
              <div className="text-[10px] text-emerald-500 mt-2 flex items-center gap-1">
                <Bot className="h-3 w-3" />Cancellation triggers AI waitlist contact in 30 sec
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function RcmModule() {
  return (
    <div>
      <SectionHeader title="Revenue Cycle Command Center" subtitle="Real-time pipeline from verification to payment \u2014 entire revenue cycle at a glance" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={FileCheck} label="Claims MTD" value="847" sub="94.2% first-pass rate" subColor="text-blue-500" />
        <KpiCard icon={DollarSign} label="Collections MTD" value="$198,240" sub="99.5% of net production" subColor="text-emerald-500" />
        <KpiCard icon={Clock} label="Days in A/R" value="18.4" sub="Down from 32 days" subColor="text-emerald-500" />
        <KpiCard icon={ArrowLeftRight} label="Cross-Coded" value="34" sub="$28,400 medical revenue" subColor="text-purple-500" />
      </div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={ScrollText} label="Necessity Letters" value="18" sub="91% approval rate" subColor="text-indigo-500" />
        <KpiCard icon={Swords} label="Open Denials" value="$12,840" sub="68% overturn rate" subColor="text-amber-500" />
        <KpiCard icon={Mic} label="Voice Notes" value="24" sub="6.8 hrs saved today" subColor="text-cyan-500" />
        <KpiCard icon={Landmark} label="Payer Connections" value="340+" sub="All major payers" subColor="text-teal-500" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Live Revenue Activity</div>
            {RCM_ACTIVITY.map((a, i) => (
              <div key={i} className="py-2 border-b last:border-0" data-testid={`rcm-activity-${i}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[10px] text-muted-foreground">{a.time}</span>
                  {a.amt !== "\u2014" && <span className={`text-xs font-extrabold font-mono ${a.color}`}>{a.amt}</span>}
                </div>
                <div className="text-[10px] text-muted-foreground mt-1">{a.action}</div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Engine Performance</div>
            {RCM_ENGINE_PERF.map((e, i) => (
              <div key={i} className="mb-3" data-testid={`rcm-engine-${i}`}>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs">{e.label}</span>
                  <span className={`text-xs font-bold font-mono ${e.color}`}>{e.val}</span>
                </div>
                <Progress value={e.pct} className="h-1" />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function VerifyModule() {
  return (
    <div>
      <SectionHeader title="AI Insurance Verification Engine" subtitle="Real-time eligibility, benefits breakdown, auto-estimate" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={SearchCheck} label="Verified Today" value="48" sub="Tomorrow's schedule" subColor="text-blue-500" />
        <KpiCard icon={Activity} label="Avg Speed" value="4.2 sec" sub="vs 12 min manual" subColor="text-emerald-500" />
        <KpiCard icon={CheckCircle} label="Accuracy" value="98.6%" subColor="text-emerald-500" />
        <KpiCard icon={Landmark} label="Payers Connected" value="340+" subColor="text-teal-500" />
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="text-sm font-bold mb-3">Tomorrow's Verification Results</div>
          {VERIFY_RESULTS.map((v, i) => (
            <div key={i} className="py-2 border-b last:border-0" data-testid={`verify-result-${i}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-bold">{v.patient}</span>
                <div className="flex items-center gap-1.5">
                  <StatusBadge status={v.status} />
                  <Badge variant="secondary" className={`text-[10px] no-default-hover-elevate no-default-active-elevate ${v.check === "pass" ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400" : "bg-amber-500/15 text-amber-700 dark:text-amber-400"}`}>
                    {v.check === "pass" ? <CheckCircle className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
                  </Badge>
                </div>
              </div>
              <div className="text-xs text-muted-foreground">{v.plan} \u2014 {v.benefits}</div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ClaimsModule() {
  return (
    <div>
      <SectionHeader title="AI Claims Processing Engine" subtitle="Auto-code from notes, pre-submit scrubbing, ERA auto-posting" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={FileCheck} label="Submitted Today" value="34" sub="$42,800 total" subColor="text-blue-500" />
        <KpiCard icon={AlertTriangle} label="Pre-Scrub Catches" value="7" sub="All auto-corrected" subColor="text-amber-500" />
        <KpiCard icon={CheckCircle} label="Clean Claim Rate" value="97.1%" subColor="text-emerald-500" />
        <KpiCard icon={DollarSign} label="ERA Posted" value="$38,200" sub="Auto-reconciled" subColor="text-emerald-500" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Claims Queue</div>
            {CLAIMS_QUEUE.map((c, i) => (
              <div key={i} className="py-2 border-b last:border-0" data-testid={`claim-${i}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold">{c.patient}</span>
                  <StatusBadge status={c.status} />
                </div>
                <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                  <span>{c.proc} \u00B7 {c.payer}</span>
                  <span className="font-bold text-foreground font-mono">{c.fee}</span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">AI Pre-Scrub Catches</div>
            {CLAIMS_SCRUB_CATCHES.map((c, i) => (
              <div key={i} className={`mb-3 p-3 border-l-4 rounded-r-md ${c.severity === "high" ? "border-red-500 bg-red-500/5" : c.severity === "warning" ? "border-amber-500 bg-amber-500/5" : "border-purple-500 bg-purple-500/5"}`} data-testid={`scrub-catch-${i}`}>
                <div className="flex items-center gap-2 mb-1">
                  <AlertTriangle className={`h-3.5 w-3.5 ${c.severity === "high" ? "text-red-500" : c.severity === "warning" ? "text-amber-500" : "text-purple-500"}`} />
                  <span className="text-xs font-bold">{c.issue}</span>
                </div>
                <div className="text-[10px] text-muted-foreground">{c.fix}</div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function CrosscodeModule() {
  return (
    <div>
      <SectionHeader title="CDT-to-CPT Cross-Coding Engine" subtitle="Auto-detect medical billing opportunities" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={ArrowLeftRight} label="Cross-Coded MTD" value="34" sub="$28,400 medical revenue" subColor="text-purple-500" />
        <KpiCard icon={DollarSign} label="Avg Per Patient" value="$835" sub="Additional revenue" subColor="text-emerald-500" />
        <KpiCard icon={CheckCircle} label="Approval Rate" value="78%" subColor="text-emerald-500" />
        <KpiCard icon={FileCheck} label="CMS-1500 Generated" value="34" subColor="text-blue-500" />
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="text-sm font-bold mb-3">Cross-Coding Opportunities</div>
          <div className="grid grid-cols-7 gap-2 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
            <div className="col-span-2">Procedure</div><div>CDT</div><div>ICD-10</div><div>CPT</div><div>Medical Fee</div><div>Status</div>
          </div>
          {CROSSCODE_OPPS.map((c, i) => (
            <div key={i} className="grid grid-cols-7 gap-2 py-2 border-b last:border-0 items-center text-xs" data-testid={`crosscode-${i}`}>
              <span className="font-bold col-span-2">{c.proc}</span>
              <span className="font-mono text-blue-500">{c.cdt}</span>
              <span className="font-mono text-orange-500">{c.icd}</span>
              <span className="font-mono text-purple-500">{c.cpt}</span>
              <span className="font-mono font-bold text-emerald-500">{c.medical}</span>
              <StatusBadge status={c.status} />
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function NecessityModule() {
  return (
    <div>
      <SectionHeader title="AI Medical Necessity Letter Generator" subtitle="One-click from chart data \u2014 auto-generate with clinical evidence" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={ScrollText} label="Letters MTD" value="18" sub="12 sec avg generation" subColor="text-indigo-500" />
        <KpiCard icon={CheckCircle} label="Approval Rate" value="91%" sub="vs 64% manual" subColor="text-emerald-500" />
        <KpiCard icon={DollarSign} label="Revenue Recovered" value="$42,800" subColor="text-emerald-500" />
        <KpiCard icon={BarChart3} label="Data Sources" value="6" sub="Notes, X-ray, perio, meds, hx, labs" subColor="text-blue-500" />
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="text-sm font-bold mb-3">Recent Necessity Letters</div>
          {NECESSITY_LETTERS.map((n, i) => (
            <div key={i} className="py-3 border-b last:border-0" data-testid={`necessity-letter-${i}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold">{n.patient}</span>
                <div className="flex items-center gap-2">
                  <StatusBadge status={n.status} />
                  <span className="text-xs font-extrabold text-emerald-500 font-mono">{n.val}</span>
                </div>
              </div>
              <div className="text-[10px] text-muted-foreground">{n.proc} \u00B7 {n.payer}</div>
              <div className="text-[10px] text-muted-foreground mt-1 flex items-center gap-1">
                <FileText className="h-3 w-3" />{n.evidence}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function DenialsModule() {
  return (
    <div>
      <SectionHeader title="AI Denial Management & Appeals" subtitle="Root cause analysis, auto-appeal with evidence" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={Swords} label="Open Denials" value="23" sub="$12,840 at risk" subColor="text-red-500" />
        <KpiCard icon={Bot} label="Auto-Appealed" value="18" sub="78% automated" subColor="text-blue-500" />
        <KpiCard icon={CheckCircle} label="Overturn Rate" value="68%" sub="vs 32% industry" subColor="text-emerald-500" />
        <KpiCard icon={DollarSign} label="Recovered MTD" value="$34,200" subColor="text-emerald-500" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Active Denials</div>
            {ACTIVE_DENIALS.map((d, i) => (
              <div key={i} className="py-3 border-b last:border-0" data-testid={`denial-${i}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold">{d.patient}</span>
                  <span className="text-xs font-extrabold text-red-500 font-mono">{d.val}</span>
                </div>
                <div className="text-[10px] text-muted-foreground">{d.proc} \u00B7 {d.payer} \u00B7 Reason: <span className="text-red-500">{d.reason}</span></div>
                <div className="text-[10px] text-emerald-500 mt-1 flex items-center gap-1">
                  <Bot className="h-3 w-3" />{d.action}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Denial Root Cause Analysis</div>
            {DENIAL_CAUSES.map((d, i) => (
              <div key={i} className="mb-3" data-testid={`denial-cause-${i}`}>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs">{d.reason}</span>
                  <span className={`text-xs font-bold font-mono ${d.color}`}>{d.pct}%</span>
                </div>
                <Progress value={d.pct} className="h-1" />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function PhoneModule() {
  return (
    <div>
      <SectionHeader title="AI Phone & Communication Agent" subtitle="24/7 AI receptionist \u2014 booking, verification, follow-up" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={Phone} label="Calls Today" value="67" sub="42 AI, 25 staff" subColor="text-blue-500" />
        <KpiCard icon={Bot} label="AI Resolution" value="84%" sub="No staff needed" subColor="text-emerald-500" />
        <KpiCard icon={Calendar} label="Appts Booked" value="18" sub="11 AI, 7 staff" subColor="text-cyan-500" />
        <KpiCard icon={DollarSign} label="Revenue Recovered" value="$4,200" sub="Missed call follow-up" subColor="text-emerald-500" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm font-bold">Live Call Feed</span>
              <Badge variant="secondary" className="text-[10px] bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 no-default-hover-elevate no-default-active-elevate">LIVE</Badge>
            </div>
            {PHONE_CALLS.map((c, i) => (
              <div key={i} className="py-2 border-b last:border-0" data-testid={`phone-call-${i}`}>
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <span className="text-xs font-bold">{c.caller}</span>
                    <span className="text-[10px] text-muted-foreground ml-2">{c.time} \u00B7 {c.dur}</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Badge variant="secondary" className={`text-[10px] no-default-hover-elevate no-default-active-elevate ${c.type === "AI" ? "bg-blue-500/15 text-blue-700 dark:text-blue-400" : "bg-teal-500/15 text-teal-700 dark:text-teal-400"}`}>{c.type}</Badge>
                    <StatusBadge status={c.status} />
                  </div>
                </div>
                <div className="text-[10px] text-muted-foreground mt-1">{c.action}</div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">AI Agent Capabilities</div>
            {AI_CAPABILITIES.map((cap, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 border-b last:border-0" data-testid={`ai-cap-${i}`}>
                <span className="text-xs">{cap}</span>
                <StatusBadge status="Active" />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function VoiceModule() {
  return (
    <div>
      <SectionHeader title="Voice-to-Code Pipeline" subtitle="Speak naturally \u2192 SOAP note \u2192 CDT codes \u2192 claim ready" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={Mic} label="Voice Notes Today" value="24" sub="6.8 hrs saved" subColor="text-cyan-500" />
        <KpiCard icon={Activity} label="Processing Speed" value="2.8 sec" subColor="text-emerald-500" />
        <KpiCard icon={CheckCircle} label="Auto-Coded" value="98.4%" subColor="text-emerald-500" />
        <KpiCard icon={FileCheck} label="Claims Generated" value="22" sub="From voice notes" subColor="text-blue-500" />
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="text-sm font-bold mb-3">Recent Voice Transcription</div>
          <div className="p-3 bg-cyan-500/5 border-l-4 border-cyan-500 rounded-r-md mb-4">
            <div className="text-xs font-extrabold text-cyan-600 dark:text-cyan-400 mb-3">Dr. Chen \u2014 Michael Torres \u2014 2:18 PM</div>
            {VOICE_SOAP.map((s, i) => (
              <div key={i} className={`mb-2 p-2 border-l-2 rounded-r-md ${s.color}`} data-testid={`voice-soap-${i}`}>
                <span className="text-[10px] font-extrabold">{s.label}: </span>
                <span className="text-[10px] text-muted-foreground">{s.text}</span>
              </div>
            ))}
            <div className="flex gap-1.5 mt-3 flex-wrap">
              <Badge variant="secondary" className="text-[10px] bg-blue-500/15 text-blue-700 dark:text-blue-400 no-default-hover-elevate no-default-active-elevate">D6058 \u2014 $950</Badge>
              <Badge variant="secondary" className="text-[10px] bg-purple-500/15 text-purple-700 dark:text-purple-400 no-default-hover-elevate no-default-active-elevate">D6065 \u2014 $1,650</Badge>
              <Badge variant="secondary" className="text-[10px] bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 no-default-hover-elevate no-default-active-elevate">AUTO-CODED</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function AcceptanceModule() {
  return (
    <div>
      <SectionHeader title="AI Case Acceptance Engine" subtitle="Visual treatment presentation, financing integration, AI follow-up sequences" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={Target} label="Acceptance Rate" value="74%" sub="Up from 58% pre-AI" subColor="text-emerald-500" />
        <KpiCard icon={DollarSign} label="Presented MTD" value="$186,400" subColor="text-blue-500" />
        <KpiCard icon={CheckCircle} label="Accepted MTD" value="$138,000" sub="74% of presented" subColor="text-emerald-500" />
        <KpiCard icon={Clock} label="Pending" value="$32,800" sub="18 pts \u2014 AI following up" subColor="text-amber-500" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Active Presentations</div>
            {ACCEPTANCE_PRESENTATIONS.map((p, i) => (
              <div key={i} className="py-3 border-b last:border-0" data-testid={`acceptance-${i}`}>
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <span className="text-xs font-extrabold">{p.patient}</span>
                    <span className="text-[10px] text-muted-foreground ml-2">{p.days}d ago</span>
                  </div>
                  <StatusBadge status={p.status} />
                </div>
                <div className="text-[10px] text-muted-foreground mb-2">{p.tx}</div>
                <div className="grid grid-cols-4 gap-2 text-[10px]">
                  <div><div className="text-muted-foreground">Total</div><div className="font-bold">{p.total}</div></div>
                  <div><div className="text-muted-foreground">Insurance</div><div className="font-bold text-emerald-500">{p.ins}</div></div>
                  <div><div className="text-muted-foreground">OOP</div><div className="font-bold text-amber-500">{p.oop}</div></div>
                  <div><div className="text-muted-foreground">Monthly</div><div className="font-bold text-cyan-500">{p.mo}</div></div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Objection Analysis</div>
            {OBJECTION_ANALYSIS.map((o, i) => (
              <div key={i} className="mb-3" data-testid={`objection-${i}`}>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs">{o.obj}</span>
                  <span className={`text-xs font-bold ${o.color}`}>{o.pct}%</span>
                </div>
                <Progress value={o.pct} className="h-1" />
                <div className="text-[10px] text-emerald-500 mt-1 flex items-center gap-1">
                  <Bot className="h-3 w-3" />{o.ai}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function FeesModule() {
  return (
    <div>
      <SectionHeader title="Fee Schedule Optimizer" subtitle="Compare your fees against UCR percentiles and PPO fee schedules" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={Receipt} label="Revenue Opportunity" value="$42,800" sub="Annual if raised to UCR" subColor="text-emerald-500" />
        <KpiCard icon={TrendingUp} label="Below UCR" value="34" sub="Procedures under 80th" subColor="text-amber-500" />
        <KpiCard icon={BarChart3} label="Fee vs UCR" value="88%" sub="Avg of UCR 80th" subColor="text-blue-500" />
        <KpiCard icon={FileText} label="PPO Contracts" value="8" sub="Active negotiations" subColor="text-purple-500" />
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="text-sm font-bold mb-3">Fee Schedule Analysis</div>
          <div className="grid grid-cols-7 gap-2 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
            <div>CDT</div><div className="col-span-2">Procedure</div><div>Your Fee</div><div>UCR 80th</div><div>Delta</div><div>Action</div>
          </div>
          {FEE_SCHEDULE.map((f, i) => (
            <div key={i} className="grid grid-cols-7 gap-2 py-2 border-b last:border-0 items-center text-xs" data-testid={`fee-row-${i}`}>
              <span className="font-mono text-blue-500">{f.cdt}</span>
              <span className="font-semibold col-span-2">{f.proc}</span>
              <span className="font-mono">{f.your}</span>
              <span className="font-mono text-emerald-500 font-bold">{f.ucr}</span>
              <span className="font-mono text-muted-foreground">{f.delta}</span>
              <Badge variant="secondary" className="text-[10px] bg-amber-500/15 text-amber-700 dark:text-amber-400 no-default-hover-elevate no-default-active-elevate">{f.action}</Badge>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ProviderModule() {
  return (
    <div>
      <SectionHeader title="Provider Performance Intelligence" subtitle="Production, case acceptance, and collections by provider" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={Stethoscope} label="Providers" value="3" subColor="text-blue-500" />
        <KpiCard icon={DollarSign} label="Production MTD" value="$198,200" subColor="text-emerald-500" />
        <KpiCard icon={TrendingUp} label="Avg Prod/Day" value="$8,260" subColor="text-blue-500" />
        <KpiCard icon={Target} label="Avg Acceptance" value="74%" subColor="text-emerald-500" />
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="text-sm font-bold mb-3">Provider Scorecard</div>
          <div className="grid grid-cols-8 gap-2 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
            <div>Provider</div><div>Production</div><div>Prod/Day</div><div>Patients</div><div>Accept</div><div>Avg Tx</div><div>Collect</div><div>Score</div>
          </div>
          {PROVIDER_SCORECARD.map((p, i) => (
            <div key={i} className="grid grid-cols-8 gap-2 py-2 border-b last:border-0 items-center text-xs" data-testid={`provider-${i}`}>
              <span className="font-bold">{p.name}</span>
              <span className="font-mono text-emerald-500 font-bold">{p.prod}</span>
              <span className="font-mono">{p.perDay}</span>
              <span>{p.patients}</span>
              <span className="font-bold">{p.accept}</span>
              <span className="font-mono">{p.avgTx}</span>
              <span className="text-emerald-500">{p.collections}</span>
              <div className="flex items-center gap-1">
                <Progress value={p.score} className="h-1.5 flex-1" />
                <span className="text-[10px] font-bold">{p.score}</span>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function PayerModule() {
  return (
    <div>
      <SectionHeader title="Payer Intelligence Dashboard" subtitle="Approval rates, payment speed, denial patterns by payer" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={Landmark} label="Payer Profiles" value="340+" subColor="text-blue-500" />
        <KpiCard icon={FileCheck} label="Claims Analyzed" value="12,400+" subColor="text-purple-500" />
        <KpiCard icon={Clock} label="Avg Days to Pay" value="14.2" subColor="text-blue-500" />
        <KpiCard icon={DollarSign} label="Opportunities" value="$18,400" subColor="text-emerald-500" />
      </div>
      <Card>
        <CardContent className="p-4">
          <div className="text-sm font-bold mb-3">Top Payer Scorecard</div>
          <div className="grid grid-cols-7 gap-2 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
            <div className="col-span-2">Payer</div><div>Approval</div><div>Days</div><div>Denial</div><div>Reimb.</div><div>Score</div>
          </div>
          {PAYER_SCORECARD.map((p, i) => (
            <div key={i} className="grid grid-cols-7 gap-2 py-2 border-b last:border-0 items-center text-xs" data-testid={`payer-${i}`}>
              <span className="font-bold col-span-2">{p.payer}</span>
              <span className="text-emerald-500 font-bold">{p.approval}</span>
              <span className="font-mono">{p.days}</span>
              <span className="text-red-500">{p.denial}</span>
              <span>{p.reimburse}</span>
              <div className="flex items-center gap-1">
                <Progress value={p.score} className="h-1.5 flex-1" />
                <span className="text-[10px] font-bold">{p.score}</span>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function ComplianceModule() {
  return (
    <div>
      <SectionHeader title="Compliance & Coding Audit" subtitle="AI-powered chart auditing, documentation completeness, risk detection" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={ShieldCheck} label="Compliance Score" value="96.4%" subColor="text-emerald-500" />
        <KpiCard icon={FileText} label="Charts Audited" value="342" subColor="text-blue-500" />
        <KpiCard icon={AlertTriangle} label="Issues Found" value="12" subColor="text-amber-500" />
        <KpiCard icon={DollarSign} label="Risk Avoided" value="$28,400" subColor="text-emerald-500" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Coding Audit Issues</div>
            <div className="grid grid-cols-5 gap-2 py-2 border-b text-[10px] font-bold tracking-wider uppercase text-muted-foreground">
              <div className="col-span-2">Issue</div><div>Provider</div><div>Risk</div><div>Action</div>
            </div>
            {COMPLIANCE_ISSUES.map((c, i) => (
              <div key={i} className="grid grid-cols-5 gap-2 py-2 border-b last:border-0 items-center text-xs" data-testid={`compliance-issue-${i}`}>
                <span className="col-span-2">{c.issue} <span className="text-muted-foreground">({c.cases} cases)</span></span>
                <span className="text-muted-foreground">{c.provider}</span>
                <span className="font-mono text-red-500 font-bold">{c.risk}</span>
                <span className="text-[10px] text-emerald-500">{c.action}</span>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Documentation Completeness</div>
            {DOC_COMPLETENESS.map((d, i) => (
              <div key={i} className="mb-3" data-testid={`doc-complete-${i}`}>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs">{d.label}</span>
                  <span className={`text-xs font-bold font-mono ${d.color}`}>{d.pct}%</span>
                </div>
                <Progress value={d.pct} className="h-1.5" />
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function BiModule() {
  return (
    <div>
      <SectionHeader title="Business Intelligence Dashboard" subtitle="Practice-wide KPIs, trend analysis, AI-powered recommendations" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <KpiCard icon={PieChart} label="Practice Score" value="94" sub="Top 6% nationally" subColor="text-emerald-500" />
        <KpiCard icon={TrendingUp} label="Revenue Growth" value="18%" sub="vs prior year" subColor="text-emerald-500" />
        <KpiCard icon={Users} label="Patient Growth" value="12%" sub="38 new pts/mo avg" subColor="text-blue-500" />
        <KpiCard icon={Bot} label="AI ROI" value="14.2x" sub="$284K saved annually" subColor="text-purple-500" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <CardContent className="p-4">
            <div className="text-sm font-bold mb-3">Key Metrics Overview</div>
            {BI_METRICS.map((m, i) => (
              <div key={i} className="mb-3" data-testid={`bi-metric-${i}`}>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-xs">{m.label}</span>
                  <span className={`text-xs font-bold font-mono ${m.color}`}>{m.value}</span>
                </div>
                <Progress value={m.pct > 100 ? 100 : m.pct} className="h-1.5" />
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Brain className="h-4 w-4 text-purple-500" />
              <span className="text-sm font-bold">AI Strategic Recommendations</span>
            </div>
            {BI_RECOMMENDATIONS.map((r, i) => (
              <div key={i} className="flex items-start gap-2 py-2 border-b last:border-0" data-testid={`bi-rec-${i}`}>
                <TrendingUp className="h-3.5 w-3.5 text-emerald-500 mt-0.5 flex-shrink-0" />
                <span className="text-xs text-muted-foreground">{r}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

const MODULE_COMPONENTS: Record<ModuleId, () => JSX.Element> = {
  intake: IntakeModule,
  perio: PerioModule,
  soap: SoapModule,
  aiimaging: AIImagingModule,
  consent: ConsentModule,
  erx: ErxModule,
  aiclinical: AiClinicalModule,
  ortho: OrthoModule,
  implant: ImplantModule,
  lab: LabModule,
  referral: ReferralModule,
  inventory: InventoryModule,
  hr: HrModule,
  sterilization: SterilizationModule,
  schedule: ScheduleModule,
  rcm: RcmModule,
  verify: VerifyModule,
  claims: ClaimsModule,
  crosscode: CrosscodeModule,
  necessity: NecessityModule,
  denials: DenialsModule,
  phone: PhoneModule,
  voice: VoiceModule,
  txplan: AiTreatmentModule,
  acceptance: AcceptanceModule,
  telehealth: TelehealthModule,
  financial: FinancialModule,
  financing: FinancingModule,
  marketing: MarketingModule,
  nps: NpsModule,
  fees: FeesModule,
  provider: ProviderModule,
  payer: PayerModule,
  multiloc: MultilocModule,
  compliance: ComplianceModule,
  bi: BiModule,
};

export default function AdvancedModulesPage() {
  const [activeTab, setActiveTab] = useState<ModuleId>("aiimaging");

  const ActiveModule = MODULE_COMPONENTS[activeTab];

  return (
    <div className="flex h-full" data-testid="advanced-modules-page">
      <div className="w-56 bg-card border-r p-3 flex-shrink-0">
        <ScrollArea className="h-full">
          {GROUPS.map((group) => (
            <div key={group} className="mb-3">
              <div className="text-[9px] font-bold tracking-widest uppercase text-muted-foreground px-2 py-1">{group}</div>
              {MODULES.filter((m) => m.group === group).map((m) => {
                const Icon = m.icon;
                const isActive = activeTab === m.id;
                return (
                  <button
                    key={m.id}
                    onClick={() => setActiveTab(m.id)}
                    className={`flex items-center gap-2 w-full px-2 py-1.5 rounded-md text-left text-xs transition-colors ${
                      isActive
                        ? "bg-primary/10 text-primary font-bold"
                        : "text-muted-foreground hover-elevate"
                    }`}
                    data-testid={`tab-${m.id}`}
                  >
                    <Icon className="h-3.5 w-3.5 flex-shrink-0" />
                    <span>{m.label}</span>
                  </button>
                );
              })}
            </div>
          ))}
        </ScrollArea>
      </div>
      <div className="flex-1 overflow-auto p-6">
        <ActiveModule />
      </div>
    </div>
  );
}
