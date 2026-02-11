import { useState, useEffect, useRef, useCallback } from "react";

// ═══════════════════════════════════════════════════════════════
// DENTAI CRM — AI-POWERED PRACTICE MANAGEMENT SYSTEM
// ═══════════════════════════════════════════════════════════════

const C = { bg: "#F6F7F9", card: "#FFFFFF", border: "#E5E7EB", text: "#111827", muted: "#6B7280", accent: "#2563EB", success: "#059669", warning: "#D97706", danger: "#DC2626", purple: "#7C3AED", pink: "#DB2777", cyan: "#0891B2", teal: "#0D9488", orange: "#EA580C", indigo: "#4F46E5", sidebar: "#0F172A", sideHover: "#1E293B", sideText: "#94A3B8", sideActive: "#3B82F6" };

// ═══ PATIENT DATABASE ═══
const PATIENTS = [
  { id: 1, fn: "Margaret", ln: "Sullivan", dob: "1965-03-14", gender: "F", phone: "(555) 234-8901", email: "msullivan@email.com", addr: "1425 Oak Drive, Suite 3", city: "Auburn", state: "CA", zip: "95603", ssn: "***-**-4521", insurance: { primary: "Delta Dental PPO", memberId: "DDN-849201", group: "GRP-7742", employer: "State Farm Insurance", copay: 25, deductible: 1500, used: 420, annual_max: 2000 }, provider: "Dr. Chen", hygienist: "Sarah M.", status: "active", lastVisit: "2026-01-28", nextAppt: "2026-02-18 09:00", balance: 1250.00, totalProd: 28450, alert: "Penicillin allergy", medHx: ["Hypertension", "Penicillin allergy", "Bisphosphonate use"], chart: { 3: "crown", 14: "implant", 19: "filling", 30: "missing" }, treatments: [
    { date: "2026-01-28", cdt: "D6010", desc: "Implant body — #14", fee: 2200, ins: 1100, pat: 1100, status: "completed", provider: "Dr. Chen" },
    { date: "2026-01-28", cdt: "D0367", desc: "CBCT — limited FOV", fee: 250, ins: 175, pat: 75, status: "completed", provider: "Dr. Chen" },
    { date: "2025-11-15", cdt: "D2740", desc: "Crown porcelain — #3", fee: 1450, ins: 870, pat: 580, status: "completed", provider: "Dr. Chen" },
    { date: "2025-09-20", cdt: "D1110", desc: "Prophylaxis — adult", fee: 175, ins: 175, pat: 0, status: "completed", provider: "Sarah M." },
  ], ledger: [
    { date: "2026-01-28", desc: "Implant body #14 + CBCT", charge: 2450, payment: 0, adj: 0, ins: 1275, bal: 1175 },
    { date: "2026-01-30", desc: "Insurance payment — Delta", charge: 0, payment: 1275, adj: 0, ins: 0, bal: -100 },
    { date: "2025-11-15", desc: "Crown #3", charge: 1450, payment: 580, adj: 0, ins: 870, bal: 0 },
  ], comms: [
    { date: "2026-02-10", type: "sms", dir: "out", msg: "Hi Margaret! Reminder: your appointment is Feb 18 at 9:00 AM with Dr. Chen. Reply C to confirm.", status: "delivered" },
    { date: "2026-02-10", type: "sms", dir: "in", msg: "C", status: "received" },
    { date: "2026-01-29", type: "call", dir: "out", msg: "Post-op follow-up call. Patient reports mild soreness, no complications. Taking ibuprofen as directed.", status: "completed", duration: "3:42" },
    { date: "2026-01-28", type: "email", dir: "out", msg: "Post-procedure care instructions sent for implant #14", status: "delivered" },
    { date: "2026-01-20", type: "sms", dir: "out", msg: "Balance reminder: $1,250.00 due. Pay securely: pay.dentai.com/ms4521. Reply PLAN for payment options.", status: "delivered" },
  ], txPlans: [
    { id: "TP-001", name: "Implant Restoration Phase 2", status: "pending", presented: "2026-01-28", items: [
      { tooth: 14, cdt: "D6058", desc: "Abutment — implant supported", fee: 950, ins_est: 475 },
      { tooth: 14, cdt: "D6065", desc: "Crown — implant supported porcelain", fee: 1650, ins_est: 825 },
    ]},
    { id: "TP-002", name: "Perio Maintenance", status: "accepted", presented: "2025-09-20", items: [
      { tooth: null, cdt: "D4910", desc: "Periodontal maintenance", fee: 195, ins_est: 175 },
    ]},
  ]},
  { id: 2, fn: "Robert", ln: "Kim", dob: "1978-07-22", gender: "M", phone: "(555) 345-6789", email: "rkim@email.com", addr: "892 Pine Street", city: "Roseville", state: "CA", zip: "95678", ssn: "***-**-8834", insurance: { primary: "MetLife DPPO", memberId: "MLF-332847", group: "GRP-5501", employer: "Wells Fargo", copay: 30, deductible: 1000, used: 280, annual_max: 1500 }, provider: "Dr. Chen", hygienist: "Jamie L.", status: "active", lastVisit: "2026-02-05", nextAppt: "2026-02-22 14:00", balance: 0, totalProd: 4800, alert: "", medHx: ["None reported"], chart: { 14: "decay", 19: "filling", 31: "filling" }, treatments: [
    { date: "2026-02-05", cdt: "D0150", desc: "Comprehensive oral evaluation", fee: 125, ins: 100, pat: 25, status: "completed", provider: "Dr. Chen" },
    { date: "2026-02-05", cdt: "D0210", desc: "Full mouth X-rays", fee: 195, ins: 156, pat: 39, status: "completed", provider: "Dr. Chen" },
  ], ledger: [
    { date: "2026-02-05", desc: "New patient exam + FMX", charge: 320, payment: 64, adj: 0, ins: 256, bal: 0 },
  ], comms: [
    { date: "2026-02-09", type: "sms", dir: "out", msg: "Hi Robert! Your treatment plan is ready. View & accept online: plan.dentai.com/rk8834", status: "delivered" },
  ], txPlans: [
    { id: "TP-003", name: "Single Implant #14", status: "presented", presented: "2026-02-05", items: [
      { tooth: 14, cdt: "D6010", desc: "Implant body — endosteal", fee: 2200, ins_est: 880 },
      { tooth: 14, cdt: "D6058", desc: "Abutment — implant supported", fee: 950, ins_est: 380 },
      { tooth: 14, cdt: "D6065", desc: "Crown — implant supported", fee: 1650, ins_est: 660 },
    ]},
  ]},
  { id: 3, fn: "Diana", ln: "Patel", dob: "1992-11-03", gender: "F", phone: "(555) 456-7890", email: "dpatel@email.com", addr: "2301 Elm Way", city: "Folsom", state: "CA", zip: "95630", ssn: "***-**-2917", insurance: { primary: "Cigna DHMO", memberId: "CIG-119374", group: "GRP-8823", employer: "Google", copay: 20, deductible: 0, used: 0, annual_max: 2500 }, provider: "Dr. Park", hygienist: "Sarah M.", status: "active", lastVisit: "2026-01-15", nextAppt: "2026-02-20 10:30", balance: 350.00, totalProd: 3200, alert: "Latex allergy", medHx: ["Latex allergy", "Asthma"], chart: {}, treatments: [
    { date: "2026-01-15", cdt: "D0150", desc: "Comprehensive oral evaluation", fee: 125, ins: 100, pat: 25, status: "completed", provider: "Dr. Park" },
    { date: "2026-01-15", cdt: "D8090", desc: "Comprehensive orthodontic — adult", fee: 5800, ins: 2500, pat: 3300, status: "in_progress", provider: "Dr. Park" },
  ], ledger: [
    { date: "2026-01-15", desc: "Ortho consult + Invisalign start", charge: 5925, payment: 2950, adj: 0, ins: 2625, bal: 350 },
  ], comms: [], txPlans: []},
  { id: 4, fn: "James", ln: "Okafor", dob: "1985-05-30", gender: "M", phone: "(555) 567-8901", email: "jokafor@email.com", addr: "4410 Maple Court", city: "Auburn", state: "CA", zip: "95603", ssn: "***-**-6103", insurance: { primary: "Aetna PPO", memberId: "AET-556201", group: "GRP-3317", employer: "Kaiser Permanente", copay: 25, deductible: 1500, used: 1200, annual_max: 2000 }, provider: "Dr. Park", hygienist: "Jamie L.", status: "active", lastVisit: "2026-02-03", nextAppt: "2026-03-05 11:00", balance: 0, totalProd: 6800, alert: "", medHx: ["Type 2 Diabetes"], chart: { 2: "filling", 15: "filling", 18: "crown", 31: "root_canal" }, treatments: [
    { date: "2026-02-03", cdt: "D4341", desc: "Scaling & root planing — 1-3 teeth per quad", fee: 285, ins: 228, pat: 57, status: "completed", provider: "Dr. Park" },
  ], ledger: [], comms: [], txPlans: []},
  { id: 5, fn: "Sarah", ln: "Chen", dob: "2000-09-17", gender: "F", phone: "(555) 678-9012", email: "schen@email.com", addr: "118 Birch Lane", city: "Rocklin", state: "CA", zip: "95677", ssn: "***-**-7750", insurance: { primary: "United Healthcare", memberId: "UHC-884502", group: "GRP-2209", employer: "Self", copay: 35, deductible: 2000, used: 0, annual_max: 1500 }, provider: "Unassigned", hygienist: "", status: "lead", lastVisit: "—", nextAppt: "Pending", balance: 0, totalProd: 0, alert: "", medHx: [], chart: {}, treatments: [], ledger: [], comms: [
    { date: "2026-02-11", type: "webform", dir: "in", msg: "New patient inquiry via website: interested in dental implants. Submitted online form at 2:34 PM.", status: "new_lead" },
  ], txPlans: []},
  { id: 6, fn: "Michael", ln: "Torres", dob: "1970-01-08", gender: "M", phone: "(555) 789-0123", email: "mtorres@email.com", addr: "3055 Riverside Dr", city: "Auburn", state: "CA", zip: "95603", ssn: "***-**-3381", insurance: { primary: "Guardian DentalGuard", memberId: "GDN-770318", group: "GRP-1145", employer: "Retired — COBRA", copay: 20, deductible: 1000, used: 950, annual_max: 1500 }, provider: "Dr. Okafor", hygienist: "Sarah M.", status: "active", lastVisit: "2026-01-10", nextAppt: "2026-07-15 08:00", balance: 475.00, totalProd: 18700, alert: "Blood thinner — Warfarin", medHx: ["Warfarin use", "Heart murmur", "Hip replacement 2023"], chart: { 1: "missing", 16: "missing", 17: "bridge", 32: "missing" }, treatments: [
    { date: "2026-01-10", cdt: "D7210", desc: "Extraction — surgical (#17 remnant)", fee: 385, ins: 308, pat: 77, status: "completed", provider: "Dr. Okafor" },
    { date: "2026-01-10", cdt: "D7953", desc: "Bone graft — socket preservation", fee: 650, ins: 325, pat: 325, status: "completed", provider: "Dr. Okafor" },
  ], ledger: [
    { date: "2026-01-10", desc: "Surgical extraction + bone graft", charge: 1035, payment: 560, adj: 0, ins: 0, bal: 475 },
  ], comms: [
    { date: "2026-02-08", type: "sms", dir: "out", msg: "Hi Michael, you have a balance of $475.00. Pay now: pay.dentai.com/mt3381 or reply PLAN for monthly payments.", status: "delivered" },
    { date: "2026-02-08", type: "sms", dir: "in", msg: "PLAN", status: "received" },
    { date: "2026-02-08", type: "sms", dir: "out", msg: "Great! We've set you up on 3 payments of $158.33/mo. First charge on 2/15. Reply STOP to cancel anytime.", status: "delivered" },
  ], txPlans: []},
];

// ═══ SCHEDULE DATA ═══
const SCHEDULE = [
  { time: "08:00", duration: 60, patient: "Margaret Sullivan", procedure: "Implant Follow-up", provider: "Dr. Chen", type: "implant", status: "confirmed" },
  { time: "09:00", duration: 90, patient: "Robert Kim", procedure: "Implant Consult + CBCT", provider: "Dr. Chen", type: "implant", status: "confirmed" },
  { time: "08:00", duration: 60, patient: "James Okafor", procedure: "Perio Maintenance", provider: "Dr. Park", type: "perio", status: "confirmed" },
  { time: "09:00", duration: 30, patient: "Diana Patel", procedure: "Invisalign Check", provider: "Dr. Park", type: "ortho", status: "unconfirmed" },
  { time: "10:00", duration: 60, patient: "New Patient — Web Lead", procedure: "Comprehensive Exam", provider: "Dr. Chen", type: "exam", status: "unconfirmed" },
  { time: "10:30", duration: 90, patient: "Michael Torres", procedure: "Implant Surgery #17", provider: "Dr. Okafor", type: "implant", status: "confirmed" },
  { time: "11:00", duration: 60, patient: "Emily Watson", procedure: "Crown Prep #12", provider: "Dr. Park", type: "restorative", status: "confirmed" },
  { time: "13:00", duration: 60, patient: "Sarah M. — Hygiene", procedure: "Prophy + Exam", provider: "Hygiene 1", type: "hygiene", status: "confirmed" },
  { time: "13:00", duration: 90, patient: "OPEN", procedure: "— Available —", provider: "Dr. Chen", type: "open", status: "open" },
  { time: "14:00", duration: 60, patient: "Jamie L. — Hygiene", procedure: "SRP Quad 1", provider: "Hygiene 2", type: "perio", status: "confirmed" },
  { time: "14:00", duration: 60, patient: "Walk-In Emergency", procedure: "Emergency Exam", provider: "Dr. Okafor", type: "emergency", status: "pending" },
];

const TYPE_COLORS = { implant: C.accent, perio: C.teal, ortho: C.purple, restorative: C.orange, hygiene: C.success, exam: C.cyan, emergency: C.danger, open: "#D1D5DB" };

// ═══ AI INSIGHTS ═══
const AI_INSIGHTS = [
  { type: "revenue", icon: "💰", title: "Unscheduled treatment: $847K", desc: "234 patients have accepted but unscheduled treatment plans totaling $847,200. AI recommends automated 3-touch SMS sequence.", priority: "high", action: "Activate Sequence" },
  { type: "recall", icon: "📅", title: "187 patients overdue for recall", desc: "These patients are 6+ months past their recall date. Reactivation campaign could recover $112K in hygiene production.", priority: "high", action: "Launch Campaign" },
  { type: "billing", icon: "💳", title: "A/R over 90 days: $23,400", desc: "14 accounts are 90+ days past due. AI recommends escalating to payment plan offers via SMS before collections.", priority: "medium", action: "Send SMS Offers" },
  { type: "insurance", icon: "📋", title: "12 claims pending >30 days", desc: "Claims worth $18,600 have been pending with insurers for 30+ days. Auto-follow-up can recover 85% within 2 weeks.", priority: "medium", action: "Auto Follow-Up" },
  { type: "schedule", icon: "📊", title: "Tomorrow: 3 unconfirmed appointments", desc: "3 patients haven't confirmed for tomorrow. AI will send final confirmation SMS at 6 PM tonight + auto-fill from waitlist if no response.", priority: "low", action: "Auto-Confirm" },
  { type: "lead", icon: "🌐", title: "New web lead: Sarah Chen — implant inquiry", desc: "Submitted form 2 hours ago. AI recommends immediate phone call (85% conversion within 5 minutes) followed by consult booking.", priority: "high", action: "Call Now" },
];

// ═══ TOOTH DATA ═══
const UPPER_TEETH = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16];
const LOWER_TEETH = [32,31,30,29,28,27,26,25,24,23,22,21,20,19,18,17];
const TOOTH_STATUS_COLORS = { healthy: "#E5E7EB", crown: C.accent, filling: C.warning, implant: C.purple, decay: C.danger, missing: "#374151", root_canal: C.orange, bridge: C.teal };

// ═══ COMPONENTS ═══
const Badge = ({ children, color = C.accent, variant = "subtle" }) => {
  const bg = variant === "solid" ? color : `${color}15`;
  const fg = variant === "solid" ? "#FFF" : color;
  return <span style={{ background: bg, color: fg, padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 700, letterSpacing: 0.3, textTransform: "uppercase", whiteSpace: "nowrap" }}>{children}</span>;
};
const Pbar = ({ v, color = C.accent, h = 6 }) => <div style={{ height: h, background: "#F3F4F6", borderRadius: h, overflow: "hidden", flex: 1 }}><div style={{ height: "100%", width: `${Math.min(v,100)}%`, background: color, borderRadius: h, transition: "width 0.6s" }}/></div>;

const KpiCard = ({ label, value, sub, color = C.accent, icon }) => (
  <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "16px 18px", position: "relative", overflow: "hidden" }}>
    <div style={{ position: "absolute", top: -10, right: -10, width: 60, height: 60, background: `${color}08`, borderRadius: "50%" }} />
    <div style={{ fontSize: 10, color: C.muted, letterSpacing: 1.2, textTransform: "uppercase", fontWeight: 600, marginBottom: 4, display: "flex", alignItems: "center", gap: 4 }}>{icon && <span style={{ fontSize: 13 }}>{icon}</span>}{label}</div>
    <div style={{ fontSize: 24, fontWeight: 900, color: C.text, fontFamily: "'Tabular Nums', 'JetBrains Mono', monospace" }}>{value}</div>
    {sub && <div style={{ fontSize: 11, color, fontWeight: 600, marginTop: 2 }}>{sub}</div>}
  </div>
);

// ═══ MAIN APP ═══
export default function DentAI() {
  const [tab, setTab] = useState("dashboard");
  const [selPatient, setSelPatient] = useState(null);
  const [patSearch, setPatSearch] = useState("");
  const [patTab, setPatTab] = useState("overview");
  const [schedDate] = useState("Tuesday, Feb 11, 2026");

  const tabs = [
    { id: "dashboard", label: "Dashboard", icon: "📊" },
    { id: "patients", label: "Patients", icon: "👥" },
    { id: "schedule", label: "Schedule", icon: "📅" },
    { id: "charting", label: "Charting", icon: "🦷" },
    { id: "treatment", label: "Tx Plans", icon: "📋" },
    { id: "insurance", label: "Insurance", icon: "🏥" },
    { id: "billing", label: "Billing", icon: "💰" },
    { id: "comms", label: "Comms Hub", icon: "💬" },
    { id: "ai", label: "AI Engine", icon: "🤖" },
    { id: "analytics", label: "Analytics", icon: "📈" },
  ];

  const filteredPatients = PATIENTS.filter(p => {
    const q = patSearch.toLowerCase();
    return !q || `${p.fn} ${p.ln}`.toLowerCase().includes(q) || p.phone.includes(q) || p.email.toLowerCase().includes(q);
  });

  const patient = selPatient ? PATIENTS.find(p => p.id === selPatient) : null;

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: C.bg, fontFamily: "'Outfit', 'DM Sans', system-ui, -apple-system, sans-serif", color: C.text }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet" />

      {/* ═══ SIDEBAR ═══ */}
      <div style={{ width: 220, background: C.sidebar, padding: "16px 10px", display: "flex", flexDirection: "column", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "4px 10px", marginBottom: 20 }}>
          <div style={{ width: 34, height: 34, borderRadius: 10, background: "linear-gradient(135deg, #3B82F6, #06B6D4)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>🦷</div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 900, color: "#F8FAFC" }}>DentAI</div>
            <div style={{ fontSize: 9, color: C.sideText, letterSpacing: 2.5, textTransform: "uppercase" }}>Practice Management</div>
          </div>
        </div>

        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 2 }}>
          {tabs.map(t => (
            <button key={t.id} onClick={() => { setTab(t.id); if (t.id !== "patients" && t.id !== "charting" && t.id !== "treatment" && t.id !== "billing" && t.id !== "comms") setSelPatient(null); }} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 12px", borderRadius: 8, border: "none", background: tab === t.id ? C.sideActive + "18" : "transparent", cursor: "pointer", transition: "0.15s", width: "100%" }}>
              <span style={{ fontSize: 16, width: 24, textAlign: "center" }}>{t.icon}</span>
              <span style={{ fontSize: 13, fontWeight: tab === t.id ? 700 : 500, color: tab === t.id ? C.sideActive : C.sideText }}>{t.label}</span>
              {t.id === "ai" && <span style={{ marginLeft: "auto", width: 6, height: 6, borderRadius: "50%", background: "#22C55E", boxShadow: "0 0 6px #22C55E" }} />}
            </button>
          ))}
        </div>

        <div style={{ borderTop: "1px solid rgba(255,255,255,0.06)", paddingTop: 12, marginTop: 8 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 12px" }}>
            <div style={{ width: 28, height: 28, borderRadius: 7, background: "#334155", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, color: "#94A3B8", fontWeight: 700 }}>AC</div>
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: "#E2E8F0" }}>Auburn Dental</div>
              <div style={{ fontSize: 10, color: C.sideText }}>Multi-Specialty</div>
            </div>
          </div>
        </div>
      </div>

      {/* ═══ MAIN CONTENT ═══ */}
      <div style={{ flex: 1, overflowY: "auto", minWidth: 0 }}>

        {/* ═══ DASHBOARD ═══ */}
        {tab === "dashboard" && (
          <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div><div style={{ fontSize: 24, fontWeight: 900 }}>Good morning, Doctor</div><div style={{ fontSize: 13, color: C.muted }}>{schedDate} · 14 patients today · 2 surgeries</div></div>
              <div style={{ display: "flex", gap: 6 }}>
                <button style={{ background: C.accent, color: "#FFF", border: "none", borderRadius: 9, padding: "8px 16px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>+ New Patient</button>
                <button style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 9, padding: "8px 16px", fontSize: 12, fontWeight: 600, cursor: "pointer", color: C.text }}>Morning Huddle</button>
              </div>
            </div>

            {/* KPIs */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
              <KpiCard icon="💵" label="Today's Production" value="$18,450" sub="↑ 12% vs avg" color={C.success} />
              <KpiCard icon="📥" label="MTD Collections" value="$198,240" sub="96.2% rate" color={C.accent} />
              <KpiCard icon="👤" label="New Patients (Feb)" value="38" sub="Target: 45" color={C.purple} />
              <KpiCard icon="✅" label="Case Acceptance" value="72%" sub="↑ 4% this month" color={C.teal} />
              <KpiCard icon="⏰" label="Chair Utilization" value="87%" sub="3 open slots today" color={C.warning} />
              <KpiCard icon="⚠️" label="Outstanding A/R" value="$34,200" sub="$23.4K over 90 days" color={C.danger} />
            </div>

            {/* AI Insights */}
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>🤖 AI Insights & Actions <span style={{ background: `${C.danger}12`, color: C.danger, padding: "1px 8px", borderRadius: 10, fontSize: 10, fontWeight: 700 }}>{AI_INSIGHTS.filter(i=>i.priority==="high").length} urgent</span></div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {AI_INSIGHTS.map((ins, i) => (
                  <div key={i} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: "14px 16px", display: "flex", alignItems: "flex-start", gap: 12 }}>
                    <span style={{ fontSize: 22 }}>{ins.icon}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
                        <span style={{ fontSize: 14, fontWeight: 700 }}>{ins.title}</span>
                        <Badge color={ins.priority === "high" ? C.danger : ins.priority === "medium" ? C.warning : C.success}>{ins.priority}</Badge>
                      </div>
                      <div style={{ fontSize: 12, color: C.muted, lineHeight: 1.5 }}>{ins.desc}</div>
                    </div>
                    <button style={{ background: `${C.accent}10`, color: C.accent, border: `1px solid ${C.accent}25`, borderRadius: 8, padding: "6px 14px", fontSize: 11, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0 }}>{ins.action}</button>
                  </div>
                ))}
              </div>
            </div>

            {/* Today's Schedule Preview */}
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 10 }}>📅 Today's Schedule</div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
                <div style={{ display: "grid", gridTemplateColumns: "70px 1fr 1fr 120px 90px", borderBottom: `1px solid ${C.border}`, padding: "8px 16px" }}>
                  {["Time", "Patient", "Procedure", "Provider", "Status"].map(h => <div key={h} style={{ fontSize: 10, fontWeight: 700, color: C.muted, letterSpacing: 1, textTransform: "uppercase" }}>{h}</div>)}
                </div>
                {SCHEDULE.filter(s => s.type !== "open").slice(0, 8).map((s, i) => (
                  <div key={i} style={{ display: "grid", gridTemplateColumns: "70px 1fr 1fr 120px 90px", padding: "10px 16px", borderBottom: `1px solid ${C.border}`, alignItems: "center" }}>
                    <div style={{ fontSize: 13, fontWeight: 700, fontFamily: "'JetBrains Mono'" }}>{s.time}</div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{s.patient}</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}><div style={{ width: 8, height: 8, borderRadius: "50%", background: TYPE_COLORS[s.type] }} /><span style={{ fontSize: 12, color: C.muted }}>{s.procedure}</span></div>
                    <div style={{ fontSize: 12, color: C.muted }}>{s.provider}</div>
                    <Badge color={s.status === "confirmed" ? C.success : s.status === "pending" ? C.warning : C.danger}>{s.status}</Badge>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ═══ PATIENTS ═══ */}
        {tab === "patients" && !selPatient && (
          <div style={{ padding: "20px 24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div style={{ fontSize: 24, fontWeight: 900 }}>Patients</div>
              <button style={{ background: C.accent, color: "#FFF", border: "none", borderRadius: 9, padding: "8px 18px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>+ New Patient</button>
            </div>
            <input value={patSearch} onChange={e => setPatSearch(e.target.value)} placeholder="Search by name, phone, or email..." style={{ width: "100%", padding: "10px 16px", borderRadius: 10, border: `1px solid ${C.border}`, fontSize: 14, marginBottom: 16, background: C.card, outline: "none" }} />
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
              <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 100px 80px", padding: "10px 16px", borderBottom: `2px solid ${C.border}` }}>
                {["Patient", "Phone", "Provider", "Next Appt", "Balance", "Status"].map(h => <div key={h} style={{ fontSize: 10, fontWeight: 700, color: C.muted, letterSpacing: 1, textTransform: "uppercase" }}>{h}</div>)}
              </div>
              {filteredPatients.map(p => (
                <div key={p.id} onClick={() => { setSelPatient(p.id); setPatTab("overview"); }} style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr 100px 80px", padding: "12px 16px", borderBottom: `1px solid ${C.border}`, cursor: "pointer", alignItems: "center", transition: "0.1s" }} onMouseOver={e => e.currentTarget.style.background = "#F8FAFC"} onMouseOut={e => e.currentTarget.style.background = "transparent"}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 34, height: 34, borderRadius: 8, background: p.status === "lead" ? `${C.purple}12` : `${C.accent}10`, color: p.status === "lead" ? C.purple : C.accent, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 800 }}>{p.fn[0]}{p.ln[0]}</div>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 700 }}>{p.fn} {p.ln}</div>
                      <div style={{ fontSize: 11, color: C.muted }}>{p.email}</div>
                    </div>
                    {p.alert && <span title={p.alert} style={{ fontSize: 14, cursor: "help" }}>⚠️</span>}
                  </div>
                  <div style={{ fontSize: 13, color: C.muted, fontFamily: "'JetBrains Mono'" }}>{p.phone}</div>
                  <div style={{ fontSize: 13, color: C.muted }}>{p.provider}</div>
                  <div style={{ fontSize: 12, color: C.muted }}>{p.nextAppt}</div>
                  <div style={{ fontSize: 13, fontWeight: 700, fontFamily: "'JetBrains Mono'", color: p.balance > 0 ? C.danger : C.success }}>{p.balance > 0 ? `$${p.balance.toFixed(2)}` : "—"}</div>
                  <Badge color={p.status === "active" ? C.success : p.status === "lead" ? C.purple : C.muted}>{p.status}</Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ═══ PATIENT DETAIL ═══ */}
        {(tab === "patients" || tab === "charting" || tab === "treatment" || tab === "billing" || tab === "comms") && selPatient && patient && (
          <div style={{ padding: "20px 24px" }}>
            {/* Patient Header */}
            <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 16 }}>
              <button onClick={() => setSelPatient(null)} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: "5px 10px", cursor: "pointer", fontSize: 14, color: C.muted }}>←</button>
              <div style={{ width: 48, height: 48, borderRadius: 12, background: `${C.accent}12`, color: C.accent, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, fontWeight: 900 }}>{patient.fn[0]}{patient.ln[0]}</div>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 22, fontWeight: 900 }}>{patient.fn} {patient.ln}</span>
                  <Badge color={patient.status === "active" ? C.success : C.purple}>{patient.status}</Badge>
                  {patient.alert && <Badge color={C.danger}>⚠️ {patient.alert}</Badge>}
                </div>
                <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>DOB: {patient.dob} · {patient.gender} · {patient.insurance.primary} · ID: {patient.insurance.memberId}</div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                {["📞 Call", "💬 SMS", "📧 Email", "📅 Book"].map((a, i) => <button key={i} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: "6px 12px", fontSize: 11, fontWeight: 600, cursor: "pointer", color: C.text }}>{a}</button>)}
              </div>
            </div>

            {/* Patient Tabs */}
            <div style={{ display: "flex", gap: 4, marginBottom: 16, borderBottom: `2px solid ${C.border}`, paddingBottom: 2 }}>
              {[{ id: "overview", l: "Overview" }, { id: "chart", l: "Dental Chart" }, { id: "tx", l: "Treatment Plans" }, { id: "ledger", l: "Billing & Ledger" }, { id: "comms", l: "Communications" }, { id: "insurance", l: "Insurance" }].map(t => (
                <button key={t.id} onClick={() => setPatTab(t.id)} style={{ padding: "8px 16px", borderRadius: "8px 8px 0 0", border: "none", borderBottom: patTab === t.id ? `2px solid ${C.accent}` : "2px solid transparent", background: patTab === t.id ? `${C.accent}08` : "transparent", color: patTab === t.id ? C.accent : C.muted, fontWeight: 700, fontSize: 13, cursor: "pointer" }}>{t.l}</button>
              ))}
            </div>

            {/* OVERVIEW TAB */}
            {patTab === "overview" && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, letterSpacing: 1, textTransform: "uppercase", marginBottom: 12 }}>Contact Information</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    {[["Phone", patient.phone], ["Email", patient.email], ["Address", `${patient.addr}`], ["City/State", `${patient.city}, ${patient.state} ${patient.zip}`]].map(([l,v], i) => (
                      <div key={i}><div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", fontWeight: 600 }}>{l}</div><div style={{ fontSize: 13, fontWeight: 600, marginTop: 1 }}>{v}</div></div>
                    ))}
                  </div>
                </div>
                <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, letterSpacing: 1, textTransform: "uppercase", marginBottom: 12 }}>Financial Summary</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    {[["Balance Due", `$${patient.balance.toFixed(2)}`, patient.balance > 0 ? C.danger : C.success], ["Total Production", `$${patient.totalProd.toLocaleString()}`, C.accent], ["Insurance Used", `$${patient.insurance.used} / $${patient.insurance.annual_max}`, C.warning], ["Deductible", `$${patient.insurance.deductible}`, C.muted]].map(([l,v,c], i) => (
                      <div key={i}><div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", fontWeight: 600 }}>{l}</div><div style={{ fontSize: 15, fontWeight: 800, color: c, marginTop: 1 }}>{v}</div></div>
                    ))}
                  </div>
                </div>
                <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, letterSpacing: 1, textTransform: "uppercase", marginBottom: 12 }}>Medical History</div>
                  {patient.medHx.length ? patient.medHx.map((m, i) => <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}><span style={{ color: m.toLowerCase().includes("allergy") ? C.danger : C.warning, fontSize: 12 }}>●</span><span style={{ fontSize: 13 }}>{m}</span></div>) : <div style={{ fontSize: 13, color: C.muted }}>No medical history reported</div>}
                </div>
                <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, letterSpacing: 1, textTransform: "uppercase", marginBottom: 12 }}>Treatment History</div>
                  {patient.treatments.slice(0, 4).map((tx, i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: i < 3 ? `1px solid ${C.border}` : "none" }}>
                      <div><div style={{ fontSize: 12, fontWeight: 600 }}>{tx.desc}</div><div style={{ fontSize: 10, color: C.muted }}>{tx.date} · {tx.cdt}</div></div>
                      <div style={{ fontSize: 12, fontWeight: 700, fontFamily: "'JetBrains Mono'" }}>${tx.fee}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* DENTAL CHART TAB */}
            {patTab === "chart" && (
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "24px 28px" }}>
                <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 16 }}>Dental Chart — {patient.fn} {patient.ln}</div>
                {[{ label: "Upper", teeth: UPPER_TEETH }, { label: "Lower", teeth: LOWER_TEETH }].map(row => (
                  <div key={row.label} style={{ marginBottom: 20 }}>
                    <div style={{ fontSize: 10, color: C.muted, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 8 }}>{row.label}</div>
                    <div style={{ display: "flex", gap: 4, justifyContent: "center" }}>
                      {row.teeth.map(t => {
                        const status = patient.chart[t];
                        const color = status ? TOOTH_STATUS_COLORS[status] : TOOTH_STATUS_COLORS.healthy;
                        return (
                          <div key={t} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
                            <div style={{ width: 32, height: 36, borderRadius: 6, background: status === "missing" ? "transparent" : `${color}20`, border: `2px solid ${status === "missing" ? "#9CA3AF" : color}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 800, color: status === "missing" ? "#9CA3AF" : color, cursor: "pointer", transition: "0.15s", borderStyle: status === "missing" ? "dashed" : "solid" }}>
                              {status === "missing" ? "✕" : status === "implant" ? "⬡" : status === "crown" ? "♛" : status === "filling" ? "●" : status === "root_canal" ? "◉" : status === "decay" ? "!" : ""}
                            </div>
                            <span style={{ fontSize: 9, fontWeight: 700, color: C.muted }}>{t}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
                <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginTop: 8, paddingTop: 12, borderTop: `1px solid ${C.border}` }}>
                  {Object.entries(TOOTH_STATUS_COLORS).filter(([k]) => k !== "healthy").map(([k, c]) => (
                    <div key={k} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                      <div style={{ width: 12, height: 12, borderRadius: 3, background: k === "missing" ? "transparent" : `${c}30`, border: `2px solid ${c}`, borderStyle: k === "missing" ? "dashed" : "solid" }} />
                      <span style={{ fontSize: 11, color: C.muted, textTransform: "capitalize" }}>{k.replace("_", " ")}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* TX PLANS TAB */}
            {patTab === "tx" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {patient.txPlans.length ? patient.txPlans.map(tp => (
                  <div key={tp.id} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
                    <div style={{ padding: "14px 18px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: `1px solid ${C.border}` }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}><span style={{ fontSize: 14, fontWeight: 800 }}>{tp.name}</span><Badge color={tp.status === "accepted" ? C.success : tp.status === "pending" ? C.warning : C.accent}>{tp.status}</Badge></div>
                        <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>Presented: {tp.presented} · {tp.id}</div>
                      </div>
                      <div style={{ display: "flex", gap: 6 }}>
                        <button style={{ background: `${C.success}10`, color: C.success, border: `1px solid ${C.success}25`, borderRadius: 8, padding: "6px 14px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>✓ Accept</button>
                        <button style={{ background: `${C.accent}10`, color: C.accent, border: `1px solid ${C.accent}25`, borderRadius: 8, padding: "6px 14px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>📤 Send to Patient</button>
                      </div>
                    </div>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                      <thead><tr style={{ borderBottom: `1px solid ${C.border}` }}>{["Tooth", "CDT Code", "Description", "Fee", "Ins Est.", "Patient Est."].map(h => <th key={h} style={{ padding: "8px 16px", textAlign: "left", fontSize: 10, fontWeight: 700, color: C.muted, letterSpacing: 1, textTransform: "uppercase" }}>{h}</th>)}</tr></thead>
                      <tbody>
                        {tp.items.map((item, i) => (
                          <tr key={i} style={{ borderBottom: `1px solid ${C.border}` }}>
                            <td style={{ padding: "10px 16px", fontWeight: 700 }}>#{item.tooth || "—"}</td>
                            <td style={{ padding: "10px 16px", fontFamily: "'JetBrains Mono'", fontSize: 12, color: C.accent }}>{item.cdt}</td>
                            <td style={{ padding: "10px 16px", fontSize: 13 }}>{item.desc}</td>
                            <td style={{ padding: "10px 16px", fontWeight: 700, fontFamily: "'JetBrains Mono'" }}>${item.fee.toLocaleString()}</td>
                            <td style={{ padding: "10px 16px", color: C.success, fontFamily: "'JetBrains Mono'", fontSize: 12 }}>${item.ins_est}</td>
                            <td style={{ padding: "10px 16px", fontWeight: 700, fontFamily: "'JetBrains Mono'" }}>${(item.fee - item.ins_est).toLocaleString()}</td>
                          </tr>
                        ))}
                        <tr style={{ background: "#F9FAFB" }}>
                          <td colSpan={3} style={{ padding: "10px 16px", fontWeight: 800, textAlign: "right" }}>TOTAL</td>
                          <td style={{ padding: "10px 16px", fontWeight: 900, fontFamily: "'JetBrains Mono'" }}>${tp.items.reduce((s, i) => s + i.fee, 0).toLocaleString()}</td>
                          <td style={{ padding: "10px 16px", color: C.success, fontWeight: 700, fontFamily: "'JetBrains Mono'" }}>${tp.items.reduce((s, i) => s + i.ins_est, 0).toLocaleString()}</td>
                          <td style={{ padding: "10px 16px", fontWeight: 900, fontFamily: "'JetBrains Mono'", color: C.danger }}>${tp.items.reduce((s, i) => s + (i.fee - i.ins_est), 0).toLocaleString()}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                )) : <div style={{ padding: 40, textAlign: "center", color: C.muted, background: C.card, borderRadius: 14, border: `1px solid ${C.border}` }}>No treatment plans on file. <button style={{ color: C.accent, background: "none", border: "none", fontWeight: 700, cursor: "pointer", textDecoration: "underline" }}>+ Create Treatment Plan</button></div>}
              </div>
            )}

            {/* LEDGER TAB */}
            {patTab === "ledger" && (
              <div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 16 }}>
                  <KpiCard label="Balance Due" value={`$${patient.balance.toFixed(2)}`} color={patient.balance > 0 ? C.danger : C.success} />
                  <KpiCard label="Total Production" value={`$${patient.totalProd.toLocaleString()}`} color={C.accent} />
                  <KpiCard label="Insurance Used" value={`$${patient.insurance.used}`} sub={`of $${patient.insurance.annual_max} max`} color={C.warning} />
                  <KpiCard label="Remaining Benefits" value={`$${patient.insurance.annual_max - patient.insurance.used}`} color={C.success} />
                </div>
                {patient.balance > 0 && (
                  <div style={{ background: `${C.danger}06`, border: `1px solid ${C.danger}18`, borderRadius: 12, padding: "14px 18px", marginBottom: 16, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div><div style={{ fontSize: 14, fontWeight: 700, color: C.danger }}>Outstanding Balance: ${patient.balance.toFixed(2)}</div><div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>AI can send SMS payment link or set up auto payment plan</div></div>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button style={{ background: C.danger, color: "#FFF", border: "none", borderRadius: 8, padding: "8px 16px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>💬 SMS Pay Link</button>
                      <button style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: "8px 16px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>📅 Payment Plan</button>
                    </div>
                  </div>
                )}
                <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
                  <div style={{ display: "grid", gridTemplateColumns: "90px 2fr 90px 90px 90px 90px 90px", padding: "10px 16px", borderBottom: `2px solid ${C.border}` }}>
                    {["Date", "Description", "Charges", "Payment", "Adjust", "Insurance", "Balance"].map(h => <div key={h} style={{ fontSize: 10, fontWeight: 700, color: C.muted, letterSpacing: 1, textTransform: "uppercase" }}>{h}</div>)}
                  </div>
                  {patient.ledger.map((l, i) => (
                    <div key={i} style={{ display: "grid", gridTemplateColumns: "90px 2fr 90px 90px 90px 90px 90px", padding: "10px 16px", borderBottom: `1px solid ${C.border}`, alignItems: "center" }}>
                      <div style={{ fontSize: 12, color: C.muted, fontFamily: "'JetBrains Mono'" }}>{l.date}</div>
                      <div style={{ fontSize: 13 }}>{l.desc}</div>
                      <div style={{ fontSize: 12, fontWeight: 600, fontFamily: "'JetBrains Mono'", color: l.charge > 0 ? C.text : "" }}>{l.charge > 0 ? `$${l.charge}` : "—"}</div>
                      <div style={{ fontSize: 12, fontWeight: 600, fontFamily: "'JetBrains Mono'", color: l.payment > 0 ? C.success : "" }}>{l.payment > 0 ? `($${l.payment})` : "—"}</div>
                      <div style={{ fontSize: 12, fontFamily: "'JetBrains Mono'" }}>{l.adj > 0 ? `($${l.adj})` : "—"}</div>
                      <div style={{ fontSize: 12, fontFamily: "'JetBrains Mono'", color: C.accent }}>{l.ins > 0 ? `($${l.ins})` : "—"}</div>
                      <div style={{ fontSize: 12, fontWeight: 700, fontFamily: "'JetBrains Mono'", color: l.bal > 0 ? C.danger : C.success }}>{l.bal > 0 ? `$${l.bal}` : l.bal < 0 ? `($${Math.abs(l.bal)})` : "$0"}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* COMMUNICATIONS TAB */}
            {patTab === "comms" && (
              <div>
                <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
                  <button style={{ background: C.accent, color: "#FFF", border: "none", borderRadius: 8, padding: "8px 16px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>💬 Send SMS</button>
                  <button style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: "8px 16px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>📧 Send Email</button>
                  <button style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: "8px 16px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>📞 Log Call</button>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {patient.comms.length ? patient.comms.map((comm, i) => {
                    const icons = { sms: "💬", call: "📞", email: "📧", webform: "🌐" };
                    const dirColor = comm.dir === "in" ? C.success : C.accent;
                    return (
                      <div key={i} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: "14px 18px", display: "flex", alignItems: "flex-start", gap: 12 }}>
                        <div style={{ width: 36, height: 36, borderRadius: 10, background: `${dirColor}10`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, flexShrink: 0 }}>{icons[comm.type]}</div>
                        <div style={{ flex: 1 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
                            <Badge color={dirColor}>{comm.dir === "in" ? "↙ Inbound" : "↗ Outbound"}</Badge>
                            <Badge color={C.muted}>{comm.type}</Badge>
                            <span style={{ fontSize: 11, color: C.muted }}>{comm.date}</span>
                            {comm.duration && <span style={{ fontSize: 11, color: C.muted }}>· {comm.duration}</span>}
                          </div>
                          <div style={{ fontSize: 13, lineHeight: 1.5, color: "#4B5563", marginTop: 4 }}>{comm.msg}</div>
                        </div>
                        <Badge color={comm.status === "delivered" || comm.status === "completed" ? C.success : comm.status === "new_lead" ? C.purple : C.warning}>{comm.status}</Badge>
                      </div>
                    );
                  }) : <div style={{ padding: 40, textAlign: "center", color: C.muted, background: C.card, borderRadius: 14 }}>No communication history yet.</div>}
                </div>
              </div>
            )}

            {/* INSURANCE TAB */}
            {patTab === "insurance" && (
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "20px 22px" }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, letterSpacing: 1, textTransform: "uppercase", marginBottom: 14 }}>Primary Insurance</div>
                  {[["Plan", patient.insurance.primary], ["Member ID", patient.insurance.memberId], ["Group #", patient.insurance.group], ["Employer", patient.insurance.employer], ["Copay", `$${patient.insurance.copay}`], ["Deductible", `$${patient.insurance.deductible}`]].map(([l,v], i) => (
                    <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: i < 5 ? `1px solid ${C.border}` : "none" }}>
                      <span style={{ fontSize: 12, color: C.muted }}>{l}</span>
                      <span style={{ fontSize: 13, fontWeight: 700 }}>{v}</span>
                    </div>
                  ))}
                </div>
                <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "20px 22px" }}>
                  <div style={{ fontSize: 12, fontWeight: 700, color: C.muted, letterSpacing: 1, textTransform: "uppercase", marginBottom: 14 }}>Benefits Usage</div>
                  <div style={{ fontSize: 28, fontWeight: 900, color: C.accent, marginBottom: 4 }}>${patient.insurance.used} <span style={{ fontSize: 14, color: C.muted, fontWeight: 500 }}>/ ${patient.insurance.annual_max}</span></div>
                  <Pbar v={(patient.insurance.used / patient.insurance.annual_max) * 100} color={C.accent} h={8} />
                  <div style={{ fontSize: 12, color: C.success, fontWeight: 600, marginTop: 8 }}>${patient.insurance.annual_max - patient.insurance.used} remaining this year</div>
                  <div style={{ marginTop: 16, display: "flex", gap: 6 }}>
                    <button style={{ background: `${C.accent}10`, color: C.accent, border: `1px solid ${C.accent}25`, borderRadius: 8, padding: "8px 14px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>🔄 Verify Eligibility</button>
                    <button style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: "8px 14px", fontSize: 11, fontWeight: 600, cursor: "pointer" }}>📋 View Breakdown</button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ═══ SCHEDULE ═══ */}
        {tab === "schedule" && (
          <div style={{ padding: "20px 24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <div><div style={{ fontSize: 24, fontWeight: 900 }}>Schedule</div><div style={{ fontSize: 13, color: C.muted }}>{schedDate} · 14 appointments · 2 open slots</div></div>
              <div style={{ display: "flex", gap: 6 }}>
                <button style={{ background: C.accent, color: "#FFF", border: "none", borderRadius: 9, padding: "8px 18px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>+ Book Appointment</button>
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
              {["Dr. Chen", "Dr. Park", "Dr. Okafor", "Hygiene"].map(prov => (
                <div key={prov} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
                  <div style={{ padding: "10px 14px", background: "#F9FAFB", borderBottom: `1px solid ${C.border}`, fontSize: 13, fontWeight: 800 }}>{prov}</div>
                  <div style={{ padding: "8px" }}>
                    {SCHEDULE.filter(s => s.provider.includes(prov.split(" ").pop()) || (prov === "Hygiene" && s.provider.includes("Hygiene"))).map((s, i) => (
                      <div key={i} style={{ padding: "8px 10px", borderRadius: 8, marginBottom: 4, background: s.type === "open" ? "#F9FAFB" : `${TYPE_COLORS[s.type]}08`, borderLeft: `3px solid ${TYPE_COLORS[s.type]}`, cursor: "pointer" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontSize: 11, fontWeight: 700, fontFamily: "'JetBrains Mono'" }}>{s.time}</span>
                          <span style={{ fontSize: 9, fontWeight: 600, color: TYPE_COLORS[s.type] }}>{s.duration}m</span>
                        </div>
                        <div style={{ fontSize: 12, fontWeight: 700, marginTop: 2, color: s.type === "open" ? C.muted : C.text }}>{s.patient}</div>
                        <div style={{ fontSize: 10, color: C.muted }}>{s.procedure}</div>
                        {s.status !== "open" && <div style={{ marginTop: 3 }}><Badge color={s.status === "confirmed" ? C.success : s.status === "pending" ? C.warning : C.danger}>{s.status}</Badge></div>}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ═══ AI ENGINE ═══ */}
        {tab === "ai" && (
          <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
            <div><div style={{ fontSize: 24, fontWeight: 900 }}>🤖 AI Automation Engine</div><div style={{ fontSize: 13, color: C.muted }}>Active automations running 24/7 across all modules</div></div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
              {[
                { name: "AI Phone Receptionist", status: "active", desc: "Answering after-hours calls, booking appointments, triaging emergencies", calls: "142 calls handled", color: C.success },
                { name: "Smart Scheduling", status: "active", desc: "Auto-filling cancellations from waitlist, predicting no-shows, optimizing blocks", calls: "23 slots auto-filled this month", color: C.accent },
                { name: "Insurance Verification", status: "active", desc: "Batch-verifying eligibility for tomorrow's patients every evening at 6 PM", calls: "98.2% auto-verified", color: C.purple },
                { name: "Recall Engine", status: "active", desc: "Automated SMS + email sequences for 3/6/9/12 month recall campaigns", calls: "38 reactivated this month", color: C.teal },
                { name: "Collections Bot", status: "active", desc: "SMS payment links, auto payment plans, escalation sequences for overdue accounts", calls: "$18.4K collected via SMS", color: C.warning },
                { name: "Review Generator", status: "active", desc: "Post-appointment SMS review request with direct Google review link", calls: "12 new reviews this month", color: C.orange },
                { name: "Treatment Follow-Up", status: "active", desc: "Post-op check sequences, unaccepted treatment nurture campaigns, re-engagement", calls: "24 plans re-engaged", color: C.pink },
                { name: "Lead Nurture", status: "active", desc: "Web form auto-response, 7-touch nurture sequence, consult booking automation", calls: "67% form-to-booked rate", color: C.indigo },
              ].map((a, i) => (
                <div key={i} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "16px 18px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 800 }}>{a.name}</span>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: C.success, boxShadow: `0 0 6px ${C.success}` }} />
                  </div>
                  <div style={{ fontSize: 11, color: C.muted, lineHeight: 1.5, marginBottom: 8 }}>{a.desc}</div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: a.color }}>{a.calls}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ═══ ANALYTICS ═══ */}
        {tab === "analytics" && (
          <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
            <div><div style={{ fontSize: 24, fontWeight: 900 }}>Practice Analytics</div><div style={{ fontSize: 13, color: C.muted }}>Real-time performance metrics — DEO framework</div></div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
              {[
                { l: "YTD Revenue", v: "$498,240", sub: "↑ 18% vs LY", c: C.success },
                { l: "Avg Prod/Day", v: "$52,400", sub: "Target: $55K", c: C.accent },
                { l: "Collections %", v: "96.2%", sub: "Target: 98%", c: C.warning },
                { l: "New Pts/Mo", v: "38", sub: "Target: 45", c: C.purple },
                { l: "Case Accept %", v: "72%", sub: "↑ 4% MoM", c: C.teal },
                { l: "Overhead %", v: "57.3%", sub: "Target: <59%", c: C.orange },
              ].map((k, i) => <KpiCard key={i} label={k.l} value={k.v} sub={k.sub} color={k.c} />)}
            </div>
            {/* Provider Scorecard */}
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
              <div style={{ padding: "14px 18px", borderBottom: `1px solid ${C.border}`, fontSize: 13, fontWeight: 800 }}>Provider Performance Scorecard</div>
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead><tr style={{ borderBottom: `2px solid ${C.border}` }}>{["Provider", "Specialty", "MTD Production", "Collections %", "Case Accept %", "Pts Seen", "Prod/Day"].map(h => <th key={h} style={{ padding: "10px 14px", textAlign: "left", fontSize: 10, fontWeight: 700, color: C.muted, letterSpacing: 1, textTransform: "uppercase" }}>{h}</th>)}</tr></thead>
                <tbody>
                  {[
                    { name: "Dr. Chen", spec: "Implants/Prostho", prod: "$148,200", coll: "97.8%", accept: "78%", pts: 89, ppd: "$7,410" },
                    { name: "Dr. Park", spec: "Ortho/General", prod: "$92,400", coll: "95.1%", accept: "68%", pts: 124, ppd: "$4,620" },
                    { name: "Dr. Okafor", spec: "Oral Surgery", prod: "$76,800", coll: "98.2%", accept: "82%", pts: 56, ppd: "$6,400" },
                    { name: "Sarah M. RDH", spec: "Hygiene", prod: "$24,200", coll: "99.1%", accept: "—", pts: 142, ppd: "$1,210" },
                    { name: "Jamie L. RDH", spec: "Hygiene/Perio", prod: "$21,800", coll: "98.8%", accept: "—", pts: 128, ppd: "$1,090" },
                  ].map((p, i) => (
                    <tr key={i} style={{ borderBottom: `1px solid ${C.border}` }}>
                      <td style={{ padding: "12px 14px", fontWeight: 700, fontSize: 13 }}>{p.name}</td>
                      <td style={{ padding: "12px 14px", fontSize: 12, color: C.muted }}>{p.spec}</td>
                      <td style={{ padding: "12px 14px", fontWeight: 700, fontFamily: "'JetBrains Mono'", fontSize: 13 }}>{p.prod}</td>
                      <td style={{ padding: "12px 14px" }}><span style={{ color: parseFloat(p.coll) >= 98 ? C.success : C.warning, fontWeight: 700, fontSize: 13 }}>{p.coll}</span></td>
                      <td style={{ padding: "12px 14px", fontWeight: 700, fontSize: 13 }}>{p.accept}</td>
                      <td style={{ padding: "12px 14px", fontSize: 13 }}>{p.pts}</td>
                      <td style={{ padding: "12px 14px", fontWeight: 700, fontFamily: "'JetBrains Mono'", fontSize: 13 }}>{p.ppd}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ═══ INSURANCE MODULE (standalone) ═══ */}
        {tab === "insurance" && !selPatient && (
          <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
            <div><div style={{ fontSize: 24, fontWeight: 900 }}>Insurance & Claims</div><div style={{ fontSize: 13, color: C.muted }}>AI-powered claims processing, verification, and follow-up</div></div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
              <KpiCard icon="📤" label="Claims Submitted (MTD)" value="187" color={C.accent} />
              <KpiCard icon="✅" label="Claims Paid" value="164" sub="$142,800" color={C.success} />
              <KpiCard icon="⏳" label="Pending >30 Days" value="12" sub="$18,600" color={C.warning} />
              <KpiCard icon="❌" label="Denied" value="8" sub="$6,200 — 3 appealable" color={C.danger} />
            </div>
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
              <div style={{ padding: "14px 18px", borderBottom: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 13, fontWeight: 800 }}>Recent Claims</span>
                <button style={{ background: `${C.accent}10`, color: C.accent, border: `1px solid ${C.accent}20`, borderRadius: 8, padding: "6px 14px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>🤖 Auto Follow-Up All Pending</button>
              </div>
              {[
                { patient: "Margaret Sullivan", cdt: "D6010", desc: "Implant body #14", fee: 2200, ins: "Delta Dental", submitted: "2026-01-29", status: "paid", paid: 1100 },
                { patient: "Robert Kim", cdt: "D0210", desc: "Full mouth X-rays", fee: 195, ins: "MetLife", submitted: "2026-02-06", status: "paid", paid: 156 },
                { patient: "Diana Patel", cdt: "D8090", desc: "Comprehensive ortho", fee: 5800, ins: "Cigna", submitted: "2026-01-16", status: "pending", paid: 0 },
                { patient: "Michael Torres", cdt: "D7210", desc: "Surgical extraction", fee: 385, ins: "Guardian", submitted: "2026-01-11", status: "pending", paid: 0 },
                { patient: "Emily Watson", cdt: "D2750", desc: "Crown — porcelain/metal", fee: 1380, ins: "Aetna", submitted: "2026-01-22", status: "denied", paid: 0 },
              ].map((c, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "1.5fr 80px 1.5fr 90px 1fr 90px 90px", padding: "10px 18px", borderBottom: `1px solid ${C.border}`, alignItems: "center", fontSize: 12 }}>
                  <div style={{ fontWeight: 600 }}>{c.patient}</div>
                  <div style={{ fontFamily: "'JetBrains Mono'", color: C.accent, fontSize: 11 }}>{c.cdt}</div>
                  <div style={{ color: C.muted }}>{c.desc}</div>
                  <div style={{ fontWeight: 700, fontFamily: "'JetBrains Mono'" }}>${c.fee}</div>
                  <div style={{ color: C.muted }}>{c.ins}</div>
                  <div style={{ fontFamily: "'JetBrains Mono'", fontSize: 11, color: C.muted }}>{c.submitted}</div>
                  <Badge color={c.status === "paid" ? C.success : c.status === "pending" ? C.warning : C.danger}>{c.status === "paid" ? `✓ $${c.paid}` : c.status}</Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ═══ BILLING MODULE (standalone) ═══ */}
        {tab === "billing" && !selPatient && (
          <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
            <div><div style={{ fontSize: 24, fontWeight: 900 }}>Billing & Collections</div><div style={{ fontSize: 13, color: C.muted }}>AI-powered payment collection via SMS, email, and auto payment plans</div></div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
              <KpiCard icon="💰" label="MTD Collections" value="$198,240" color={C.success} />
              <KpiCard icon="📊" label="Collection Rate" value="96.2%" sub="Target: 98%" color={C.accent} />
              <KpiCard icon="⚠️" label="Total A/R" value="$34,200" color={C.warning} />
              <KpiCard icon="💬" label="SMS Payments (MTD)" value="$18,400" sub="47 payments via text" color={C.purple} />
            </div>
            <div style={{ background: `${C.accent}04`, border: `1px solid ${C.accent}15`, borderRadius: 14, padding: "16px 20px" }}>
              <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 6 }}>🤖 AI Collections Engine — How It Works</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12, fontSize: 12, color: "#4B5563", lineHeight: 1.6 }}>
                <div><strong style={{ color: C.accent }}>Day 1:</strong> Invoice generated → SMS payment link sent automatically: "Pay securely: pay.dentai.com/[id]"</div>
                <div><strong style={{ color: C.warning }}>Day 7:</strong> Friendly reminder SMS: "Hi [Name], just a reminder about your $X balance. Tap to pay: [link]"</div>
                <div><strong style={{ color: C.orange }}>Day 14:</strong> Email statement + SMS: "Reply PLAN to set up easy monthly payments."</div>
                <div><strong style={{ color: C.danger }}>Day 30:</strong> Final notice + offer auto payment plan. If patient replies "PLAN" → auto-generates 3/6/12 month plan.</div>
              </div>
            </div>
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
              <div style={{ padding: "14px 18px", borderBottom: `1px solid ${C.border}`, fontSize: 13, fontWeight: 800 }}>Outstanding Balances</div>
              {PATIENTS.filter(p => p.balance > 0).map(p => (
                <div key={p.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 18px", borderBottom: `1px solid ${C.border}` }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div style={{ width: 32, height: 32, borderRadius: 8, background: `${C.danger}10`, color: C.danger, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800 }}>{p.fn[0]}{p.ln[0]}</div>
                    <div><div style={{ fontSize: 13, fontWeight: 700 }}>{p.fn} {p.ln}</div><div style={{ fontSize: 11, color: C.muted }}>{p.phone} · {p.insurance.primary}</div></div>
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 900, color: C.danger, fontFamily: "'JetBrains Mono'" }}>${p.balance.toFixed(2)}</div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button style={{ background: C.accent, color: "#FFF", border: "none", borderRadius: 8, padding: "6px 14px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>💬 SMS Pay Link</button>
                    <button style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: "6px 14px", fontSize: 11, fontWeight: 600, cursor: "pointer" }}>📅 Payment Plan</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ═══ COMMS HUB (standalone) ═══ */}
        {tab === "comms" && !selPatient && (
          <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 18 }}>
            <div><div style={{ fontSize: 24, fontWeight: 900 }}>Communications Hub</div><div style={{ fontSize: 13, color: C.muted }}>All patient touchpoints — calls, SMS, emails, forms — in one place</div></div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
              <KpiCard icon="📞" label="Calls Today" value="23" sub="4 missed" color={C.accent} />
              <KpiCard icon="💬" label="SMS Sent (MTD)" value="1,847" sub="94% delivered" color={C.success} />
              <KpiCard icon="📧" label="Emails Sent" value="423" sub="32% open rate" color={C.purple} />
              <KpiCard icon="🌐" label="Web Forms" value="18" sub="12 new leads" color={C.orange} />
            </div>
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
              <div style={{ padding: "14px 18px", borderBottom: `1px solid ${C.border}`, fontSize: 13, fontWeight: 800 }}>Recent Activity Feed</div>
              {[...PATIENTS.flatMap(p => p.comms.map(c => ({ ...c, patient: `${p.fn} ${p.ln}`, patId: p.id })))].sort((a, b) => b.date.localeCompare(a.date)).slice(0, 10).map((c, i) => {
                const icons = { sms: "💬", call: "📞", email: "📧", webform: "🌐" };
                return (
                  <div key={i} onClick={() => { setSelPatient(c.patId); setPatTab("comms"); }} style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 18px", borderBottom: `1px solid ${C.border}`, cursor: "pointer", transition: "0.1s" }} onMouseOver={e => e.currentTarget.style.background = "#F8FAFC"} onMouseOut={e => e.currentTarget.style.background = "transparent"}>
                    <span style={{ fontSize: 16 }}>{icons[c.type]}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ fontSize: 13, fontWeight: 700 }}>{c.patient}</span>
                        <Badge color={c.dir === "in" ? C.success : C.accent}>{c.dir === "in" ? "IN" : "OUT"}</Badge>
                      </div>
                      <div style={{ fontSize: 12, color: C.muted, marginTop: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: 500 }}>{c.msg}</div>
                    </div>
                    <span style={{ fontSize: 11, color: C.muted }}>{c.date}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ═══ CHARTING / TREATMENT / standalone tabs redirect ═══ */}
        {tab === "charting" && !selPatient && (
          <div style={{ padding: "20px 24px" }}>
            <div style={{ fontSize: 24, fontWeight: 900, marginBottom: 8 }}>Clinical Charting</div>
            <div style={{ fontSize: 13, color: C.muted, marginBottom: 16 }}>Select a patient to view their dental chart</div>
            {PATIENTS.filter(p => p.status === "active").map(p => (
              <div key={p.id} onClick={() => { setSelPatient(p.id); setPatTab("chart"); }} style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, marginBottom: 6, cursor: "pointer" }} onMouseOver={e => e.currentTarget.style.background = "#F8FAFC"} onMouseOut={e => e.currentTarget.style.background = C.card}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: `${C.accent}10`, color: C.accent, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800 }}>{p.fn[0]}{p.ln[0]}</div>
                <div><div style={{ fontSize: 14, fontWeight: 700 }}>{p.fn} {p.ln}</div><div style={{ fontSize: 11, color: C.muted }}>{p.provider} · Last visit: {p.lastVisit}</div></div>
                {p.alert && <Badge color={C.danger}>⚠️ {p.alert}</Badge>}
              </div>
            ))}
          </div>
        )}
        {tab === "treatment" && !selPatient && (
          <div style={{ padding: "20px 24px" }}>
            <div style={{ fontSize: 24, fontWeight: 900, marginBottom: 8 }}>Treatment Plans</div>
            <div style={{ fontSize: 13, color: C.muted, marginBottom: 16 }}>All active treatment plans across patients</div>
            {PATIENTS.filter(p => p.txPlans.length > 0).flatMap(p => p.txPlans.map(tp => ({ ...tp, patient: `${p.fn} ${p.ln}`, patId: p.id }))).map(tp => (
              <div key={tp.id} onClick={() => { setSelPatient(tp.patId); setPatTab("tx"); }} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, marginBottom: 8, cursor: "pointer" }}>
                <div><div style={{ fontSize: 14, fontWeight: 700 }}>{tp.patient} — {tp.name}</div><div style={{ fontSize: 11, color: C.muted }}>{tp.id} · Presented: {tp.presented}</div></div>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span style={{ fontSize: 16, fontWeight: 800, fontFamily: "'JetBrains Mono'" }}>${tp.items.reduce((s,i) => s + i.fee, 0).toLocaleString()}</span>
                  <Badge color={tp.status === "accepted" ? C.success : tp.status === "pending" ? C.warning : C.accent}>{tp.status}</Badge>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <style>{`* { box-sizing:border-box; margin:0; padding:0; } button { transition:0.15s; } button:hover { filter:brightness(0.96); } input:focus { border-color: ${C.accent}; box-shadow: 0 0 0 3px ${C.accent}18; } ::-webkit-scrollbar { width:6px; } ::-webkit-scrollbar-thumb { background:#D1D5DB; border-radius:3px; }`}</style>
    </div>
  );
}
