import { useState } from "react";
import {
  ClipboardList, BarChart3, FileText, Eye, Pen, Pill, CircleDot, Wrench,
  FlaskConical, RefreshCcw, Package, Users, TestTube, DollarSign, CreditCard,
  Megaphone, Star, Building2, Video, Brain, Bot, AlertTriangle, CheckCircle,
  Clock, Activity, Search, Camera, Shield, TrendingUp, AlertCircle,
  ArrowRight, Send, Mic, Hash,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";

type ModuleId = "intake" | "perio" | "soap" | "imaging" | "consent" | "erx" |
  "ortho" | "implant" | "lab" | "referral" | "inventory" | "hr" | "sterilization" |
  "financial" | "financing" | "marketing" | "nps" | "multiloc" |
  "telehealth" | "aitreatment" | "aiclinical";

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
  { id: "imaging", label: "Imaging Viewer", icon: Eye, group: "Clinical" },
  { id: "consent", label: "Consent Forms", icon: Pen, group: "Clinical" },
  { id: "erx", label: "E-Prescribing", icon: Pill, group: "Clinical" },
  { id: "ortho", label: "Ortho Tracker", icon: CircleDot, group: "Specialty" },
  { id: "implant", label: "Implant Tracker", icon: Wrench, group: "Specialty" },
  { id: "lab", label: "Lab Cases", icon: FlaskConical, group: "Specialty" },
  { id: "referral", label: "Referrals", icon: RefreshCcw, group: "Specialty" },
  { id: "inventory", label: "Inventory", icon: Package, group: "Operations" },
  { id: "hr", label: "HR & Time Clock", icon: Users, group: "Operations" },
  { id: "sterilization", label: "Sterilization", icon: TestTube, group: "Operations" },
  { id: "financial", label: "Financial Center", icon: DollarSign, group: "Business" },
  { id: "financing", label: "Patient Financing", icon: CreditCard, group: "Business" },
  { id: "marketing", label: "Marketing Suite", icon: Megaphone, group: "Business" },
  { id: "nps", label: "Patient Satisfaction", icon: Star, group: "Business" },
  { id: "multiloc", label: "Multi-Location", icon: Building2, group: "Business" },
  { id: "telehealth", label: "Teledentistry", icon: Video, group: "AI Modules" },
  { id: "aitreatment", label: "AI Tx Planning", icon: Brain, group: "AI Modules" },
  { id: "aiclinical", label: "AI Decision Support", icon: Bot, group: "AI Modules" },
];

const GROUPS = ["Clinical", "Specialty", "Operations", "Business", "AI Modules"];

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
    due_soon: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
    medium: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
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

function ImagingModule() {
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

const MODULE_COMPONENTS: Record<ModuleId, () => JSX.Element> = {
  intake: IntakeModule,
  perio: PerioModule,
  soap: SoapModule,
  imaging: ImagingModule,
  consent: ConsentModule,
  erx: ErxModule,
  ortho: OrthoModule,
  implant: ImplantModule,
  lab: LabModule,
  referral: ReferralModule,
  inventory: InventoryModule,
  hr: HrModule,
  sterilization: SterilizationModule,
  financial: FinancialModule,
  financing: FinancingModule,
  marketing: MarketingModule,
  nps: NpsModule,
  multiloc: MultilocModule,
  telehealth: TelehealthModule,
  aitreatment: AiTreatmentModule,
  aiclinical: AiClinicalModule,
};

export default function AdvancedModulesPage() {
  const [activeTab, setActiveTab] = useState<ModuleId>("intake");

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
