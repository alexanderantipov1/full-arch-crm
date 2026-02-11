import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { BarChart, Bar, LineChart, Line, AreaChart, Area, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Legend, ComposedChart, FunnelChart, Funnel, LabelList } from "recharts";

// ═══════════════════════════════════════
// DATA LAYER
// ═══════════════════════════════════════

const MONTHS = ["Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb"];
const REVENUE_TREND = [
  { month: "Jul", implants: 310000, ortho: 245000, perio: 120000, surgery: 190000, total: 865000 },
  { month: "Aug", implants: 345000, ortho: 260000, perio: 135000, surgery: 205000, total: 945000 },
  { month: "Sep", implants: 380000, ortho: 275000, perio: 128000, surgery: 218000, total: 1001000 },
  { month: "Oct", implants: 410000, ortho: 290000, perio: 145000, surgery: 230000, total: 1075000 },
  { month: "Nov", implants: 395000, ortho: 310000, perio: 155000, surgery: 245000, total: 1105000 },
  { month: "Dec", implants: 365000, ortho: 285000, perio: 138000, surgery: 210000, total: 998000 },
  { month: "Jan", implants: 440000, ortho: 320000, perio: 162000, surgery: 260000, total: 1182000 },
  { month: "Feb", implants: 485000, ortho: 348000, perio: 178000, surgery: 285000, total: 1296000 },
];

const PIPELINE_STAGES = [
  { stage: "New Lead", count: 234, value: 1870000, color: "#64748B" },
  { stage: "Consultation Booked", count: 187, value: 1496000, color: "#6366F1" },
  { stage: "Consult Completed", count: 142, value: 1136000, color: "#0EA5E9" },
  { stage: "Treatment Plan Sent", count: 98, value: 784000, color: "#F59E0B" },
  { stage: "Plan Accepted", count: 67, value: 536000, color: "#10B981" },
  { stage: "In Treatment", count: 89, value: 712000, color: "#00E6B4" },
  { stage: "Completed", count: 156, value: 1248000, color: "#22D3EE" },
];

const FUNNEL_DATA = [
  { name: "Website Visitors", value: 14200, fill: "#6366F1" },
  { name: "Form Submissions", value: 3800, fill: "#0EA5E9" },
  { name: "Consultations", value: 1420, fill: "#10B981" },
  { name: "Treatment Plans", value: 890, fill: "#F59E0B" },
  { name: "Cases Started", value: 534, fill: "#00E6B4" },
];

const SPECIALTY_MIX = [
  { name: "Implants", value: 38, color: "#00E6B4" },
  { name: "Ortho", value: 27, color: "#6366F1" },
  { name: "Perio", value: 14, color: "#F59E0B" },
  { name: "Surgery", value: 21, color: "#EF4444" },
];

const PATIENT_SOURCE = [
  { name: "Google Ads", value: 32, color: "#4285F4" },
  { name: "Referrals", value: 24, color: "#00E6B4" },
  { name: "Organic SEO", value: 18, color: "#10B981" },
  { name: "Meta Ads", value: 14, color: "#6366F1" },
  { name: "Direct", value: 8, color: "#F59E0B" },
  { name: "Other", value: 4, color: "#64748B" },
];

const PROVIDER_PERFORMANCE = [
  { name: "Dr. Chen", production: 185000, collections: 172000, acceptance: 82, patients: 134, specialty: "Implants" },
  { name: "Dr. Park", production: 148000, collections: 141000, acceptance: 76, patients: 198, specialty: "Ortho" },
  { name: "Dr. Rivera", production: 125000, collections: 118000, acceptance: 71, patients: 89, specialty: "Perio" },
  { name: "Dr. Okafor", production: 162000, collections: 155000, acceptance: 79, patients: 112, specialty: "Surgery" },
  { name: "Dr. Nguyen", production: 138000, collections: 131000, acceptance: 74, patients: 156, specialty: "Implants" },
];

const RADAR_DATA = [
  { metric: "Revenue Growth", current: 92, benchmark: 65 },
  { metric: "Case Accept.", current: 72, benchmark: 55 },
  { metric: "Patient Retention", current: 85, benchmark: 70 },
  { metric: "Chair Utilization", current: 87, benchmark: 75 },
  { metric: "New Patients", current: 78, benchmark: 60 },
  { metric: "Collections", current: 94, benchmark: 80 },
];

const DAILY_PRODUCTION = Array.from({ length: 20 }, (_, i) => ({
  day: i + 1,
  actual: Math.round(38000 + Math.random() * 28000 + (i > 14 ? 8000 : 0)),
  goal: 52000,
}));

const HOURLY_PATIENTS = [
  { hour: "7AM", count: 4 },{ hour: "8AM", count: 12 },{ hour: "9AM", count: 18 },
  { hour: "10AM", count: 22 },{ hour: "11AM", count: 20 },{ hour: "12PM", count: 8 },
  { hour: "1PM", count: 16 },{ hour: "2PM", count: 21 },{ hour: "3PM", count: 19 },
  { hour: "4PM", count: 14 },{ hour: "5PM", count: 6 },
];

// CRM Contacts
const PATIENTS = [
  { id: 1, name: "Margaret Sullivan", email: "msullivan@email.com", phone: "(555) 234-8901", stage: "In Treatment", specialty: "Implants", provider: "Dr. Chen", ltv: 24500, lastVisit: "Feb 7, 2026", nextAppt: "Feb 18, 2026", treatmentPlan: "Full Arch Implants (Upper)", status: "active", source: "Google Ads", notes: "All-on-4 upper arch. Phase 1 complete. Healing well.", score: 95, avatar: "MS" },
  { id: 2, name: "Robert Kim", email: "rkim@email.com", phone: "(555) 345-6789", stage: "Treatment Plan Sent", specialty: "Implants", provider: "Dr. Chen", ltv: 8200, lastVisit: "Feb 3, 2026", nextAppt: "Pending", treatmentPlan: "Single Implant #14 + Crown", status: "warm", source: "Referral", notes: "Comparing pricing. Sent finance options. Follow up Feb 12.", score: 72, avatar: "RK" },
  { id: 3, name: "Diana Patel", email: "dpatel@email.com", phone: "(555) 456-7890", stage: "Consult Completed", specialty: "Ortho", provider: "Dr. Park", ltv: 3200, lastVisit: "Jan 28, 2026", nextAppt: "Pending", treatmentPlan: "Invisalign Comprehensive", status: "warm", source: "Meta Ads", notes: "Interested but concerned about treatment time. Send before/after gallery.", score: 65, avatar: "DP" },
  { id: 4, name: "James Okafor", email: "jokafor@email.com", phone: "(555) 567-8901", stage: "In Treatment", specialty: "Ortho", provider: "Dr. Park", ltv: 6800, lastVisit: "Feb 5, 2026", nextAppt: "Mar 5, 2026", treatmentPlan: "Invisalign + Whitening Bundle", status: "active", source: "Organic SEO", notes: "Tray 12 of 24. On track. Great compliance.", score: 88, avatar: "JO" },
  { id: 5, name: "Sarah Chen", email: "schen@email.com", phone: "(555) 678-9012", stage: "New Lead", specialty: "Implants", provider: "Unassigned", ltv: 0, lastVisit: "Never", nextAppt: "Pending", treatmentPlan: "TBD — Inquiry for implant consultation", status: "new", source: "Google Ads", notes: "Submitted form 2 hours ago. Missing 2 lower molars. Has insurance.", score: 45, avatar: "SC" },
  { id: 6, name: "Michael Torres", email: "mtorres@email.com", phone: "(555) 789-0123", stage: "Completed", specialty: "Surgery", provider: "Dr. Okafor", ltv: 18700, lastVisit: "Jan 15, 2026", nextAppt: "Jul 15, 2026", treatmentPlan: "Wisdom Teeth Extraction + Bone Graft", status: "completed", source: "Referral", notes: "Recovery complete. NPS: 10. Request testimonial video. Referral program enrolled.", score: 98, avatar: "MT" },
  { id: 7, name: "Lisa Wang", email: "lwang@email.com", phone: "(555) 890-1234", stage: "Plan Accepted", specialty: "Implants", provider: "Dr. Nguyen", ltv: 4100, lastVisit: "Feb 1, 2026", nextAppt: "Feb 14, 2026", treatmentPlan: "2 Implants #19 #30 + Crowns", status: "active", source: "Google Ads", notes: "Financing approved through Proceed. Surgery scheduled Valentine's Day.", score: 82, avatar: "LW" },
  { id: 8, name: "Carlos Mendez", email: "cmendez@email.com", phone: "(555) 901-2345", stage: "Consultation Booked", specialty: "Perio", provider: "Dr. Rivera", ltv: 1200, lastVisit: "Nov 10, 2025", nextAppt: "Feb 12, 2026", treatmentPlan: "Scaling & Root Planing Evaluation", status: "warm", source: "Direct", notes: "Referred by hygienist for deep pockets. Insurance verified. Stage 3 perio likely.", score: 58, avatar: "CM" },
];

const ACTIVITIES = [
  { time: "2 min ago", type: "ai", text: "AI detected: Robert Kim opened treatment plan email 3x. Recommend immediate call.", icon: "🤖" },
  { time: "18 min ago", type: "call", text: "Maria L. called Sarah Chen — voicemail left. Auto follow-up SMS scheduled.", icon: "📞" },
  { time: "34 min ago", type: "booking", text: "Lisa Wang confirmed surgery appointment for Feb 14 via online portal.", icon: "📅" },
  { time: "1 hr ago", type: "payment", text: "Margaret Sullivan — payment of $4,200 processed (Phase 2 deposit).", icon: "💳" },
  { time: "1.5 hr ago", type: "ai", text: "AI: 12 patients overdue for perio recall. Campaign auto-launched to 234 contacts.", icon: "🤖" },
  { time: "2 hr ago", type: "review", text: "Michael Torres left 5-star Google review. Referral bonus email auto-sent.", icon: "⭐" },
  { time: "3 hr ago", type: "form", text: "New lead: Sarah Chen submitted implant inquiry form from Google Ads landing page.", icon: "📝" },
  { time: "4 hr ago", type: "ai", text: "AI analysis: Tuesday PM slots 23% underbooked. Recommend targeted recall for ortho check-ins.", icon: "🤖" },
];

const TASKS_CRM = [
  { id: 1, task: "Call Robert Kim — he opened treatment plan 3x today", assignee: "Maria L.", due: "Today", priority: "critical", type: "follow-up", aiGen: true },
  { id: 2, task: "Send Diana Patel before/after Invisalign gallery", assignee: "Jake R.", due: "Today", priority: "high", type: "nurture", aiGen: true },
  { id: 3, task: "Confirm Margaret Sullivan's Feb 18 appointment", assignee: "Front Desk", due: "Feb 14", priority: "medium", type: "admin", aiGen: false },
  { id: 4, task: "Request video testimonial from Michael Torres", assignee: "Dr. Okafor", due: "Feb 12", priority: "high", type: "marketing", aiGen: true },
  { id: 5, task: "Schedule Carlos Mendez CBCT scan before consult", assignee: "Sarah M.", due: "Feb 11", priority: "high", type: "clinical", aiGen: false },
  { id: 6, task: "Process Lisa Wang's insurance pre-auth for implants", assignee: "Billing", due: "Feb 12", priority: "critical", type: "billing", aiGen: false },
];

// ═══════════════════════════════════════
// UTILITY COMPONENTS
// ═══════════════════════════════════════

const fmt = (n) => n >= 1000000 ? `$${(n/1000000).toFixed(1)}M` : n >= 1000 ? `$${(n/1000).toFixed(0)}K` : `$${n}`;

const Spark = ({ data, color = "#00E6B4", w = 80, h = 28 }) => {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const points = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / range) * (h - 4) - 2}`).join(" ");
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={(data.length - 1) / (data.length - 1) * w} cy={h - ((data[data.length - 1] - min) / range) * (h - 4) - 2} r="2.5" fill={color} />
    </svg>
  );
};

const Badge = ({ children, color = "#00E6B4", size = "sm" }) => (
  <span style={{ background: `${color}15`, color, padding: size === "sm" ? "2px 9px" : "4px 14px", borderRadius: 20, fontSize: size === "sm" ? 10 : 12, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", whiteSpace: "nowrap", border: `1px solid ${color}20` }}>{children}</span>
);

const KPI = ({ label, value, change, spark, color, icon }) => (
  <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 14, padding: "18px 20px", position: "relative", overflow: "hidden" }}>
    <div style={{ position: "absolute", top: -8, right: -4, fontSize: 36, opacity: 0.05 }}>{icon}</div>
    <div style={{ fontSize: 10, color: "var(--muted)", letterSpacing: 1.4, textTransform: "uppercase", fontWeight: 600, marginBottom: 6 }}>{label}</div>
    <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
      <div>
        <div style={{ fontSize: 26, fontWeight: 800, color: "var(--text)", fontFamily: "var(--font-display)" }}>{value}</div>
        {change && <div style={{ fontSize: 12, color: change.startsWith("+") || change.startsWith("↑") ? "#00E6B4" : "#EF4444", fontWeight: 600, marginTop: 2 }}>{change}</div>}
      </div>
      {spark && <Spark data={spark} color={color || "#00E6B4"} />}
    </div>
  </div>
);

const Avatar = ({ initials, color = "#6366F1", size = 36 }) => (
  <div style={{ width: size, height: size, borderRadius: 10, background: `${color}18`, color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: size * 0.35, fontWeight: 800, flexShrink: 0, border: `1px solid ${color}25` }}>{initials}</div>
);

const Toggle = ({ active }) => (
  <div style={{ width: 38, height: 20, borderRadius: 10, background: active ? "#00E6B4" : "rgba(255,255,255,0.08)", position: "relative", cursor: "pointer", transition: "0.3s", flexShrink: 0 }}>
    <div style={{ width: 14, height: 14, borderRadius: "50%", background: "#fff", position: "absolute", top: 3, left: active ? 21 : 3, transition: "0.3s", boxShadow: "0 1px 3px rgba(0,0,0,0.3)" }} />
  </div>
);

const TabBar = ({ tabs, active, onChange, size = "md" }) => (
  <div style={{ display: "flex", gap: 3, background: "rgba(255,255,255,0.02)", borderRadius: 10, padding: 3, border: "1px solid var(--border)", overflowX: "auto" }}>
    {tabs.map((t) => (
      <button key={t.id} onClick={() => onChange(t.id)} style={{
        background: active === t.id ? "rgba(0,230,180,0.1)" : "transparent",
        border: active === t.id ? "1px solid rgba(0,230,180,0.18)" : "1px solid transparent",
        color: active === t.id ? "#00E6B4" : "var(--muted)",
        borderRadius: 8, padding: size === "sm" ? "5px 12px" : "7px 16px", fontSize: size === "sm" ? 11 : 13,
        fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap", transition: "0.2s", display: "flex", alignItems: "center", gap: 6
      }}>
        {t.icon && <span style={{ fontSize: size === "sm" ? 12 : 14 }}>{t.icon}</span>}{t.label}
        {t.count != null && <span style={{ background: active === t.id ? "rgba(0,230,180,0.15)" : "rgba(255,255,255,0.06)", padding: "1px 7px", borderRadius: 8, fontSize: 10, fontWeight: 800 }}>{t.count}</span>}
      </button>
    ))}
  </div>
);

const Section = ({ title, sub, children, action }) => (
  <div>
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14, flexWrap: "wrap", gap: 8 }}>
      <div>
        <div style={{ fontSize: 15, fontWeight: 800, color: "var(--text)" }}>{title}</div>
        {sub && <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 1 }}>{sub}</div>}
      </div>
      {action}
    </div>
    {children}
  </div>
);

const ChartCard = ({ title, children, span = 1, height }) => (
  <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 16, padding: "18px 20px", gridColumn: `span ${span}`, minWidth: 0 }}>
    {title && <div style={{ fontSize: 12, fontWeight: 700, color: "var(--muted)", letterSpacing: 1.2, textTransform: "uppercase", marginBottom: 14 }}>{title}</div>}
    <div style={{ height: height || 220 }}>{children}</div>
  </div>
);

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: "#151B24", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, padding: "10px 14px", fontSize: 12 }}>
      <div style={{ fontWeight: 700, marginBottom: 4, color: "#E8EDF2" }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, color: p.color, marginBottom: 2 }}>
          <div style={{ width: 8, height: 8, borderRadius: 2, background: p.color }} />
          <span style={{ color: "#8899AA" }}>{p.name}:</span>
          <span style={{ fontWeight: 700 }}>{typeof p.value === "number" && p.value > 999 ? fmt(p.value) : p.value}</span>
        </div>
      ))}
    </div>
  );
};

// ═══════════════════════════════════════
// NEURAL NETWORK VISUALIZATION
// ═══════════════════════════════════════

const NeuralBG = () => {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d");
    c.width = c.offsetWidth * 2; c.height = c.offsetHeight * 2;
    let t = 0, af;
    const nodes = Array.from({ length: 40 }, () => ({ x: Math.random() * c.width, y: Math.random() * c.height, vx: (Math.random() - 0.5) * 0.8, vy: (Math.random() - 0.5) * 0.8, r: Math.random() * 2 + 1 }));
    const draw = () => {
      t += 0.008; ctx.clearRect(0, 0, c.width, c.height);
      nodes.forEach((n) => { n.x += n.vx; n.y += n.vy; if (n.x < 0 || n.x > c.width) n.vx *= -1; if (n.y < 0 || n.y > c.height) n.vy *= -1; });
      nodes.forEach((a, i) => nodes.slice(i + 1).forEach((b) => {
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        if (d < 160) { ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.strokeStyle = `rgba(0,230,180,${0.06 * (1 - d / 160)})`; ctx.lineWidth = 0.8; ctx.stroke(); }
      }));
      nodes.forEach((n) => { const p = Math.sin(t * 2 + n.x * 0.01) * 0.5 + 0.5; ctx.beginPath(); ctx.arc(n.x, n.y, n.r + p * 1.5, 0, Math.PI * 2); ctx.fillStyle = `rgba(0,230,180,${0.15 + p * 0.2})`; ctx.fill(); });
      af = requestAnimationFrame(draw);
    };
    draw(); return () => cancelAnimationFrame(af);
  }, []);
  return <canvas ref={ref} style={{ width: "100%", height: "100%", position: "absolute", inset: 0, opacity: 0.7 }} />;
};

// ═══════════════════════════════════════
// MAIN APPLICATION
// ═══════════════════════════════════════

export default function DentalNexus() {
  const [mainTab, setMainTab] = useState("dashboard");
  const [crmTab, setCrmTab] = useState("pipeline");
  const [biTab, setBiTab] = useState("overview");
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [pipelineView, setPipelineView] = useState("kanban");
  const [chartPeriod, setChartPeriod] = useState("8mo");
  const [insightIdx, setInsightIdx] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    const iv = setInterval(() => setInsightIdx((p) => (p + 1) % ACTIVITIES.length), 4000);
    return () => clearInterval(iv);
  }, []);

  const mainTabs = [
    { id: "dashboard", label: "Dashboard", icon: "⚡" },
    { id: "crm", label: "CRM", icon: "👥" },
    { id: "analytics", label: "Analytics", icon: "📊" },
    { id: "pipeline", label: "Pipeline", icon: "🔀" },
    { id: "growth", label: "Growth Engine", icon: "🚀" },
  ];

  const stageColors = { "New Lead": "#64748B", "Consultation Booked": "#6366F1", "Consult Completed": "#0EA5E9", "Treatment Plan Sent": "#F59E0B", "Plan Accepted": "#10B981", "In Treatment": "#00E6B4", "Completed": "#22D3EE" };
  const statusColors = { new: "#6366F1", warm: "#F59E0B", active: "#00E6B4", completed: "#22D3EE" };
  const priorityColors = { critical: "#EF4444", high: "#F59E0B", medium: "#0EA5E9", low: "#64748B" };

  // ── Patient Detail Panel ──
  const PatientDetail = ({ patient, onClose }) => (
    <div style={{ position: "fixed", inset: 0, zIndex: 100, display: "flex", justifyContent: "flex-end" }}>
      <div onClick={onClose} style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }} />
      <div style={{ width: "min(520px, 95vw)", background: "#0D1117", borderLeft: "1px solid var(--border)", position: "relative", zIndex: 1, overflowY: "auto", animation: "slideIn 0.3s ease" }}>
        <div style={{ padding: "24px 28px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
            <Avatar initials={patient.avatar} color={stageColors[patient.stage]} size={48} />
            <div>
              <div style={{ fontSize: 20, fontWeight: 800 }}>{patient.name}</div>
              <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
                <Badge color={stageColors[patient.stage]}>{patient.stage}</Badge>
                <Badge color={statusColors[patient.status]}>{patient.status}</Badge>
              </div>
            </div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "var(--muted)", fontSize: 22, cursor: "pointer", padding: 4 }}>✕</button>
        </div>

        <div style={{ padding: "20px 28px", display: "flex", flexDirection: "column", gap: 20 }}>
          {/* Contact Info */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {[
              { l: "Email", v: patient.email },
              { l: "Phone", v: patient.phone },
              { l: "Provider", v: patient.provider },
              { l: "Specialty", v: patient.specialty },
              { l: "Source", v: patient.source },
              { l: "Lead Score", v: `${patient.score}/100` },
            ].map((f, i) => (
              <div key={i} style={{ background: "var(--card)", borderRadius: 10, padding: "10px 14px", border: "1px solid var(--border)" }}>
                <div style={{ fontSize: 10, color: "var(--muted)", letterSpacing: 1, textTransform: "uppercase", fontWeight: 600, marginBottom: 2 }}>{f.l}</div>
                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text)" }}>{f.v}</div>
              </div>
            ))}
          </div>

          {/* LTV & Financials */}
          <div style={{ background: "rgba(0,230,180,0.04)", borderRadius: 14, padding: 18, border: "1px solid rgba(0,230,180,0.1)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#00E6B4", letterSpacing: 1, textTransform: "uppercase" }}>Lifetime Value</div>
              <div style={{ fontSize: 28, fontWeight: 800, color: "#00E6B4", fontFamily: "var(--font-display)" }}>${patient.ltv.toLocaleString()}</div>
            </div>
            <div style={{ height: 4, background: "rgba(0,230,180,0.1)", borderRadius: 2, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${Math.min((patient.ltv / 25000) * 100, 100)}%`, background: "linear-gradient(90deg, #00E6B4, #00D4A8)", borderRadius: 2 }} />
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 6, textAlign: "right" }}>Target LTV: $25,000</div>
          </div>

          {/* Treatment Plan */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--muted)", letterSpacing: 1, textTransform: "uppercase", marginBottom: 8 }}>Treatment Plan</div>
            <div style={{ background: "var(--card)", borderRadius: 12, padding: 16, border: "1px solid var(--border)", fontSize: 14, fontWeight: 600, lineHeight: 1.5 }}>{patient.treatmentPlan}</div>
          </div>

          {/* Notes */}
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--muted)", letterSpacing: 1, textTransform: "uppercase", marginBottom: 8 }}>AI Notes</div>
            <div style={{ background: "var(--card)", borderRadius: 12, padding: 16, border: "1px solid var(--border)", fontSize: 13, color: "#8899AA", lineHeight: 1.6 }}>
              {patient.notes}
            </div>
          </div>

          {/* Appointments */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div style={{ background: "var(--card)", borderRadius: 12, padding: 14, border: "1px solid var(--border)" }}>
              <div style={{ fontSize: 10, color: "var(--muted)", letterSpacing: 1, textTransform: "uppercase", fontWeight: 600, marginBottom: 4 }}>Last Visit</div>
              <div style={{ fontSize: 14, fontWeight: 700 }}>{patient.lastVisit}</div>
            </div>
            <div style={{ background: "var(--card)", borderRadius: 12, padding: 14, border: "1px solid var(--border)" }}>
              <div style={{ fontSize: 10, color: "var(--muted)", letterSpacing: 1, textTransform: "uppercase", fontWeight: 600, marginBottom: 4 }}>Next Appointment</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: patient.nextAppt === "Pending" ? "#F59E0B" : "#00E6B4" }}>{patient.nextAppt}</div>
            </div>
          </div>

          {/* Quick Actions */}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {["📞 Call", "📧 Email", "💬 SMS", "📅 Schedule", "📄 Treatment Plan", "💳 Payment"].map((a, i) => (
              <button key={i} style={{ background: "var(--card)", border: "1px solid var(--border)", color: "var(--text)", borderRadius: 8, padding: "7px 14px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>{a}</button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div style={{ "--bg": "#0A0E14", "--card": "rgba(255,255,255,0.02)", "--border": "rgba(255,255,255,0.06)", "--text": "#E8EDF2", "--muted": "#6B7B8D", "--accent": "#00E6B4", "--font-display": "'Outfit', sans-serif", "--font-body": "'Geist', 'DM Sans', system-ui, sans-serif", "--font-mono": "'JetBrains Mono', 'Fira Code', monospace", minHeight: "100vh", background: "var(--bg)", color: "var(--text)", fontFamily: "var(--font-body)" }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet" />

      {/* ═══ HEADER ═══ */}
      <div style={{ background: "rgba(255,255,255,0.015)", borderBottom: "1px solid var(--border)", padding: "10px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", position: "sticky", top: 0, zIndex: 50, backdropFilter: "blur(12px)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 34, height: 34, borderRadius: 9, background: "linear-gradient(135deg, #00E6B4, #0EA5E9)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 17 }}>🦷</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 900, letterSpacing: -0.5, fontFamily: "var(--font-display)", background: "linear-gradient(90deg, #F0F4F8, #00E6B4)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>DENTAL NEXUS</div>
            <div style={{ fontSize: 9, color: "var(--muted)", letterSpacing: 2.5, textTransform: "uppercase", fontWeight: 600 }}>Salesforce + Power BI + Neural AI</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(0,230,180,0.06)", padding: "4px 12px", borderRadius: 16, border: "1px solid rgba(0,230,180,0.12)" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00E6B4", boxShadow: "0 0 8px #00E6B4", animation: "pulse 2s infinite" }} />
            <span style={{ fontSize: 10, color: "#00E6B4", fontWeight: 700, letterSpacing: 0.5 }}>AI LIVE</span>
          </div>
          <div style={{ fontSize: 11, color: "var(--muted)", fontFamily: "var(--font-mono)" }}>Feb 10, 2026</div>
        </div>
      </div>

      {/* ═══ MAIN NAV ═══ */}
      <div style={{ borderBottom: "1px solid var(--border)", padding: "8px 24px" }}>
        <TabBar tabs={mainTabs.map((t) => ({ ...t }))} active={mainTab} onChange={setMainTab} />
      </div>

      <div style={{ padding: "20px 24px", maxWidth: 1500, margin: "0 auto" }}>

        {/* ════════════════════════════════
            DASHBOARD (Executive Command)
           ════════════════════════════════ */}
        {mainTab === "dashboard" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
            {/* AI Neural Banner */}
            <div style={{ position: "relative", height: 140, borderRadius: 18, overflow: "hidden", border: "1px solid rgba(0,230,180,0.08)", background: "linear-gradient(135deg, rgba(0,230,180,0.02), rgba(14,165,233,0.02))" }}>
              <NeuralBG />
              <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "flex-end", padding: "18px 24px", background: "linear-gradient(transparent 20%, rgba(10,14,20,0.92))" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1 }}>
                  <span style={{ fontSize: 20 }}>{ACTIVITIES[insightIdx].icon}</span>
                  <div>
                    <div style={{ fontSize: 10, color: "#00E6B4", letterSpacing: 1.5, textTransform: "uppercase", fontWeight: 700, marginBottom: 2 }}>Neural AI • {ACTIVITIES[insightIdx].time}</div>
                    <div style={{ fontSize: 14, fontWeight: 700, maxWidth: 700 }}>{ACTIVITIES[insightIdx].text}</div>
                  </div>
                </div>
                <button style={{ background: "linear-gradient(135deg, #00E6B4, #0EA5E9)", color: "#0A0E14", border: "none", borderRadius: 8, padding: "8px 18px", fontWeight: 800, fontSize: 12, cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0 }}>Take Action →</button>
              </div>
            </div>

            {/* KPI Row */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
              <KPI label="Monthly Revenue" value="$1.29M" change="↑ 23% MoM" spark={REVENUE_TREND.map((r) => r.total)} color="#00E6B4" icon="💰" />
              <KPI label="Active Pipeline" value="$4.78M" change="234 opportunities" spark={PIPELINE_STAGES.map((s) => s.value)} color="#6366F1" icon="🔀" />
              <KPI label="Patients (Active)" value="3,105" change="+342 this month" spark={[2400,2520,2680,2750,2840,2920,3010,3105]} color="#0EA5E9" icon="👥" />
              <KPI label="Case Acceptance" value="72%" change="↑ 8pts (AI scripts)" spark={[54,58,62,64,66,68,70,72]} color="#F59E0B" icon="✅" />
              <KPI label="Collections Rate" value="96.2%" change="↑ 1.4pts" spark={[92,93,93.5,94,94.8,95,95.5,96.2]} color="#10B981" icon="💳" />
            </div>

            {/* Charts Row */}
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14 }}>
              <ChartCard title="Revenue by Specialty — 8 Month Trend">
                <ResponsiveContainer>
                  <AreaChart data={REVENUE_TREND} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
                    <defs>
                      {[["#00E6B4","implants"],["#6366F1","ortho"],["#F59E0B","perio"],["#EF4444","surgery"]].map(([c,k]) => (
                        <linearGradient key={k} id={`g_${k}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={c} stopOpacity={0.3} /><stop offset="100%" stopColor={c} stopOpacity={0} /></linearGradient>
                      ))}
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                    <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#6B7B8D" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: "#6B7B8D" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v/1000}K`} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="implants" name="Implants" stroke="#00E6B4" fill="url(#g_implants)" strokeWidth={2} />
                    <Area type="monotone" dataKey="ortho" name="Ortho" stroke="#6366F1" fill="url(#g_ortho)" strokeWidth={2} />
                    <Area type="monotone" dataKey="surgery" name="Surgery" stroke="#EF4444" fill="url(#g_surgery)" strokeWidth={2} />
                    <Area type="monotone" dataKey="perio" name="Perio" stroke="#F59E0B" fill="url(#g_perio)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </ChartCard>

              <ChartCard title="Specialty Revenue Mix">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={SPECIALTY_MIX} cx="50%" cy="50%" innerRadius="55%" outerRadius="80%" paddingAngle={3} dataKey="value" stroke="none">
                      {SPECIALTY_MIX.map((s, i) => <Cell key={i} fill={s.color} />)}
                    </Pie>
                    <Tooltip content={<CustomTooltip />} />
                    <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} formatter={(v) => <span style={{ color: "#8899AA" }}>{v}</span>} />
                  </PieChart>
                </ResponsiveContainer>
              </ChartCard>
            </div>

            {/* Pipeline + Activity */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <ChartCard title="Conversion Funnel" height={240}>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, height: "100%", justifyContent: "center" }}>
                  {FUNNEL_DATA.map((f, i) => {
                    const widthPct = (f.value / FUNNEL_DATA[0].value) * 100;
                    return (
                      <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{ width: 110, fontSize: 11, color: "var(--muted)", textAlign: "right", flexShrink: 0 }}>{f.name}</div>
                        <div style={{ flex: 1, position: "relative" }}>
                          <div style={{ height: 28, borderRadius: 6, background: `${f.fill}18`, overflow: "hidden" }}>
                            <div style={{ height: "100%", width: `${widthPct}%`, background: `linear-gradient(90deg, ${f.fill}, ${f.fill}99)`, borderRadius: 6, display: "flex", alignItems: "center", paddingLeft: 10, transition: "width 1s ease" }}>
                              <span style={{ fontSize: 11, fontWeight: 800, color: "#fff" }}>{f.value.toLocaleString()}</span>
                            </div>
                          </div>
                        </div>
                        {i > 0 && <div style={{ fontSize: 10, color: "#00E6B4", fontWeight: 700, width: 40, textAlign: "right" }}>{Math.round((f.value / FUNNEL_DATA[i - 1].value) * 100)}%</div>}
                      </div>
                    );
                  })}
                </div>
              </ChartCard>

              <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 16, padding: "18px 20px", overflow: "hidden" }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: "var(--muted)", letterSpacing: 1.2, textTransform: "uppercase", marginBottom: 14 }}>Live Activity Feed</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 230, overflowY: "auto" }}>
                  {ACTIVITIES.map((a, i) => (
                    <div key={i} style={{ display: "flex", gap: 10, padding: "8px 0", borderBottom: i < ACTIVITIES.length - 1 ? "1px solid var(--border)" : "none" }}>
                      <span style={{ fontSize: 16, flexShrink: 0 }}>{a.icon}</span>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 600, lineHeight: 1.4, color: a.type === "ai" ? "#00E6B4" : "var(--text)" }}>{a.text}</div>
                        <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 2 }}>{a.time}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ════════════════════════════════
            CRM (Salesforce-style)
           ════════════════════════════════ */}
        {mainTab === "crm" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
              <div>
                <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "var(--font-display)" }}>Patient CRM</div>
                <div style={{ fontSize: 13, color: "var(--muted)" }}>Salesforce-grade contact management with AI-powered lead scoring</div>
              </div>
              <button style={{ background: "linear-gradient(135deg, #00E6B4, #0EA5E9)", color: "#0A0E14", border: "none", borderRadius: 10, padding: "9px 20px", fontWeight: 800, fontSize: 13, cursor: "pointer" }}>+ New Patient</button>
            </div>

            {/* CRM Stats */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}>
              <KPI label="Total Contacts" value="3,105" icon="👥" />
              <KPI label="New Leads (30d)" value="234" change="+18% vs last month" icon="🆕" />
              <KPI label="Open Opps" value="$4.78M" icon="🔀" />
              <KPI label="Avg Lead Score" value="68/100" icon="🎯" />
              <KPI label="Avg LTV" value="$8,740" icon="💰" />
            </div>

            {/* Patient Table */}
            <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 16, overflow: "hidden" }}>
              <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ fontSize: 13, fontWeight: 700 }}>All Patients</div>
                <div style={{ display: "flex", gap: 6 }}>
                  {["All", "New", "Warm", "Active", "Completed"].map((f) => (
                    <button key={f} style={{ background: "transparent", border: "1px solid var(--border)", color: "var(--muted)", borderRadius: 6, padding: "3px 10px", fontSize: 11, fontWeight: 600, cursor: "pointer" }}>{f}</button>
                  ))}
                </div>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--border)" }}>
                      {["Patient", "Stage", "Specialty", "Provider", "LTV", "Score", "Next Appt", ""].map((h, i) => (
                        <th key={i} style={{ padding: "10px 14px", textAlign: "left", fontSize: 10, color: "var(--muted)", letterSpacing: 1.2, textTransform: "uppercase", fontWeight: 700, whiteSpace: "nowrap" }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {PATIENTS.map((p) => (
                      <tr key={p.id} onClick={() => setSelectedPatient(p)} style={{ borderBottom: "1px solid var(--border)", cursor: "pointer", transition: "0.15s" }} onMouseOver={(e) => e.currentTarget.style.background = "rgba(0,230,180,0.03)"} onMouseOut={(e) => e.currentTarget.style.background = "transparent"}>
                        <td style={{ padding: "12px 14px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <Avatar initials={p.avatar} color={stageColors[p.stage]} size={32} />
                            <div>
                              <div style={{ fontWeight: 700, fontSize: 13 }}>{p.name}</div>
                              <div style={{ fontSize: 11, color: "var(--muted)" }}>{p.email}</div>
                            </div>
                          </div>
                        </td>
                        <td style={{ padding: "12px 14px" }}><Badge color={stageColors[p.stage]}>{p.stage}</Badge></td>
                        <td style={{ padding: "12px 14px", fontSize: 12, fontWeight: 600 }}>{p.specialty}</td>
                        <td style={{ padding: "12px 14px", fontSize: 12, color: "var(--muted)" }}>{p.provider}</td>
                        <td style={{ padding: "12px 14px", fontWeight: 800, fontFamily: "var(--font-mono)", fontSize: 13, color: p.ltv > 10000 ? "#00E6B4" : "var(--text)" }}>${p.ltv.toLocaleString()}</td>
                        <td style={{ padding: "12px 14px" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <div style={{ width: 36, height: 5, borderRadius: 3, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                              <div style={{ height: "100%", width: `${p.score}%`, background: p.score > 80 ? "#00E6B4" : p.score > 60 ? "#F59E0B" : "#EF4444", borderRadius: 3 }} />
                            </div>
                            <span style={{ fontSize: 11, fontWeight: 700, color: p.score > 80 ? "#00E6B4" : p.score > 60 ? "#F59E0B" : "#EF4444" }}>{p.score}</span>
                          </div>
                        </td>
                        <td style={{ padding: "12px 14px", fontSize: 12, color: p.nextAppt === "Pending" ? "#F59E0B" : "var(--text)", fontWeight: 600 }}>{p.nextAppt}</td>
                        <td style={{ padding: "12px 14px" }}>
                          <button style={{ background: "none", border: "1px solid var(--border)", color: "var(--muted)", borderRadius: 6, padding: "4px 10px", fontSize: 11, cursor: "pointer", fontWeight: 600 }}>View</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* CRM Tasks */}
            <Section title="AI-Generated Tasks" sub="Neural network detected these action items">
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {TASKS_CRM.map((t) => (
                  <div key={t.id} style={{ background: "var(--card)", border: `1px solid ${t.priority === "critical" ? "rgba(239,68,68,0.12)" : "var(--border)"}`, borderRadius: 12, padding: "12px 18px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1, minWidth: 200 }}>
                      <div style={{ width: 20, height: 20, borderRadius: 5, border: "2px solid var(--border)", flexShrink: 0, cursor: "pointer" }} />
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 700, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                          {t.task}
                          {t.aiGen && <span style={{ background: "rgba(0,230,180,0.08)", color: "#00E6B4", padding: "1px 7px", borderRadius: 4, fontSize: 9, fontWeight: 800, letterSpacing: 0.4 }}>AI</span>}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>👤 {t.assignee} · Due: {t.due}</div>
                      </div>
                    </div>
                    <Badge color={priorityColors[t.priority]} size="sm">{t.priority}</Badge>
                  </div>
                ))}
              </div>
            </Section>
          </div>
        )}

        {/* ════════════════════════════════
            ANALYTICS (Power BI-style)
           ════════════════════════════════ */}
        {mainTab === "analytics" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
              <div>
                <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "var(--font-display)" }}>Analytics Studio</div>
                <div style={{ fontSize: 13, color: "var(--muted)" }}>Power BI-grade interactive dashboards and drill-down analytics</div>
              </div>
              <TabBar tabs={[
                { id: "overview", label: "Overview" },
                { id: "production", label: "Production" },
                { id: "marketing", label: "Marketing" },
                { id: "providers", label: "Providers" },
              ]} active={biTab} onChange={setBiTab} size="sm" />
            </div>

            {biTab === "overview" && (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
                  <KPI label="YTD Revenue" value="$2.48M" change="+31% YoY" icon="💰" spark={REVENUE_TREND.map((r) => r.total)} />
                  <KPI label="Avg Production/Day" value="$52.4K" change="+12% target" icon="📈" />
                  <KPI label="Collections Rate" value="96.2%" change="+1.4pts" icon="💳" spark={[92,93,93.5,94,94.8,95,95.5,96.2]} color="#10B981" />
                  <KPI label="New Patients/Mo" value="342" change="+28% vs goal" icon="🆕" spark={[210,235,260,278,295,310,325,342]} color="#6366F1" />
                  <KPI label="Avg Procedure Value" value="$2,840" change="+$320 from upsells" icon="🦷" />
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr", gap: 14 }}>
                  <ChartCard title="Revenue Trend — All Specialties" height={260}>
                    <ResponsiveContainer>
                      <ComposedChart data={REVENUE_TREND} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                        <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#6B7B8D" }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 10, fill: "#6B7B8D" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v/1000}K`} />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar dataKey="implants" name="Implants" fill="#00E6B4" radius={[3,3,0,0]} />
                        <Bar dataKey="ortho" name="Ortho" fill="#6366F1" radius={[3,3,0,0]} />
                        <Bar dataKey="perio" name="Perio" fill="#F59E0B" radius={[3,3,0,0]} />
                        <Bar dataKey="surgery" name="Surgery" fill="#EF4444" radius={[3,3,0,0]} />
                        <Line type="monotone" dataKey="total" name="Total" stroke="#22D3EE" strokeWidth={2.5} dot={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </ChartCard>

                  <ChartCard title="Practice vs. Benchmark" height={260}>
                    <ResponsiveContainer>
                      <RadarChart data={RADAR_DATA} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
                        <PolarGrid stroke="rgba(255,255,255,0.06)" />
                        <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10, fill: "#8899AA" }} />
                        <PolarRadiusAxis tick={false} axisLine={false} domain={[0, 100]} />
                        <Radar name="Your Practice" dataKey="current" stroke="#00E6B4" fill="#00E6B4" fillOpacity={0.15} strokeWidth={2} />
                        <Radar name="Industry Avg" dataKey="benchmark" stroke="#6366F1" fill="#6366F1" fillOpacity={0.08} strokeWidth={1.5} strokeDasharray="4 4" />
                        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
                      </RadarChart>
                    </ResponsiveContainer>
                  </ChartCard>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
                  <ChartCard title="Patient Source Breakdown">
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={PATIENT_SOURCE} cx="50%" cy="50%" innerRadius="50%" outerRadius="78%" paddingAngle={2} dataKey="value" stroke="none">
                          {PATIENT_SOURCE.map((s, i) => <Cell key={i} fill={s.color} />)}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                        <Legend iconType="circle" iconSize={7} wrapperStyle={{ fontSize: 10, fontWeight: 600 }} formatter={(v) => <span style={{ color: "#8899AA" }}>{v}</span>} />
                      </PieChart>
                    </ResponsiveContainer>
                  </ChartCard>

                  <ChartCard title="Patient Volume by Hour">
                    <ResponsiveContainer>
                      <BarChart data={HOURLY_PATIENTS} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                        <XAxis dataKey="hour" tick={{ fontSize: 9, fill: "#6B7B8D" }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 10, fill: "#6B7B8D" }} axisLine={false} tickLine={false} />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar dataKey="count" name="Patients" fill="#0EA5E9" radius={[4,4,0,0]}>
                          {HOURLY_PATIENTS.map((_, i) => <Cell key={i} fill={HOURLY_PATIENTS[i].count > 18 ? "#00E6B4" : HOURLY_PATIENTS[i].count > 12 ? "#0EA5E9" : "#64748B"} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </ChartCard>

                  <ChartCard title="Daily Production vs Goal">
                    <ResponsiveContainer>
                      <ComposedChart data={DAILY_PRODUCTION} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                        <XAxis dataKey="day" tick={{ fontSize: 10, fill: "#6B7B8D" }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fontSize: 10, fill: "#6B7B8D" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v/1000}K`} />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar dataKey="actual" name="Actual" fill="#00E6B4" radius={[3,3,0,0]} fillOpacity={0.7} />
                        <Line type="monotone" dataKey="goal" name="Goal" stroke="#EF4444" strokeWidth={2} strokeDasharray="6 4" dot={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </ChartCard>
                </div>
              </>
            )}

            {biTab === "providers" && (
              <>
                <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 16, overflow: "hidden" }}>
                  <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--border)", fontSize: 12, fontWeight: 700, color: "var(--muted)", letterSpacing: 1.2, textTransform: "uppercase" }}>Provider Performance Scorecard</div>
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                      <thead>
                        <tr style={{ borderBottom: "1px solid var(--border)" }}>
                          {["Provider", "Specialty", "Production", "Collections", "Col. Rate", "Acceptance", "Patients"].map((h, i) => (
                            <th key={i} style={{ padding: "10px 14px", textAlign: i > 1 ? "right" : "left", fontSize: 10, color: "var(--muted)", letterSpacing: 1.2, textTransform: "uppercase", fontWeight: 700, whiteSpace: "nowrap" }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {PROVIDER_PERFORMANCE.map((p, i) => (
                          <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                            <td style={{ padding: "14px", fontWeight: 700 }}>{p.name}</td>
                            <td style={{ padding: "14px" }}><Badge color={p.specialty === "Implants" ? "#00E6B4" : p.specialty === "Ortho" ? "#6366F1" : p.specialty === "Perio" ? "#F59E0B" : "#EF4444"}>{p.specialty}</Badge></td>
                            <td style={{ padding: "14px", textAlign: "right", fontFamily: "var(--font-mono)", fontWeight: 700 }}>{fmt(p.production)}</td>
                            <td style={{ padding: "14px", textAlign: "right", fontFamily: "var(--font-mono)" }}>{fmt(p.collections)}</td>
                            <td style={{ padding: "14px", textAlign: "right", fontWeight: 700, color: (p.collections / p.production) > 0.95 ? "#00E6B4" : "#F59E0B" }}>{Math.round((p.collections / p.production) * 100)}%</td>
                            <td style={{ padding: "14px", textAlign: "right" }}>
                              <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 6 }}>
                                <div style={{ width: 40, height: 5, borderRadius: 3, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                                  <div style={{ height: "100%", width: `${p.acceptance}%`, background: p.acceptance > 75 ? "#00E6B4" : "#F59E0B", borderRadius: 3 }} />
                                </div>
                                <span style={{ fontWeight: 700, fontSize: 12 }}>{p.acceptance}%</span>
                              </div>
                            </td>
                            <td style={{ padding: "14px", textAlign: "right", fontWeight: 600 }}>{p.patients}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <ChartCard title="Provider Production Comparison" height={280}>
                  <ResponsiveContainer>
                    <BarChart data={PROVIDER_PERFORMANCE} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 60 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                      <XAxis type="number" tick={{ fontSize: 10, fill: "#6B7B8D" }} axisLine={false} tickLine={false} tickFormatter={(v) => fmt(v)} />
                      <YAxis type="category" dataKey="name" tick={{ fontSize: 12, fill: "#8899AA", fontWeight: 600 }} axisLine={false} tickLine={false} width={70} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="production" name="Production" fill="#00E6B4" radius={[0,4,4,0]} barSize={16} />
                      <Bar dataKey="collections" name="Collections" fill="#0EA5E9" radius={[0,4,4,0]} barSize={16} />
                    </BarChart>
                  </ResponsiveContainer>
                </ChartCard>
              </>
            )}

            {biTab === "production" && (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
                  <KPI label="MTD Production" value="$1.08M" change="83% of goal" icon="📈" />
                  <KPI label="Procedures Today" value="47" change="6 implants, 12 ortho" icon="🦷" />
                  <KPI label="Chair Utilization" value="87%" change="Target: 92%" icon="🪑" />
                  <KPI label="Avg Production/Chair" value="$6,580" change="+14% QoQ" icon="💰" />
                </div>
                <ChartCard title="Daily Production — February 2026" height={300}>
                  <ResponsiveContainer>
                    <ComposedChart data={DAILY_PRODUCTION} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                      <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#6B7B8D" }} axisLine={false} tickLine={false} label={{ value: "Day of Month", position: "insideBottom", offset: -2, fontSize: 10, fill: "#6B7B8D" }} />
                      <YAxis tick={{ fontSize: 10, fill: "#6B7B8D" }} axisLine={false} tickLine={false} tickFormatter={(v) => `$${v / 1000}K`} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="actual" name="Actual" radius={[4, 4, 0, 0]}>
                        {DAILY_PRODUCTION.map((d, i) => <Cell key={i} fill={d.actual >= d.goal ? "#00E6B4" : d.actual >= d.goal * 0.8 ? "#F59E0B" : "#EF4444"} fillOpacity={0.75} />)}
                      </Bar>
                      <Line type="monotone" dataKey="goal" name="Daily Goal" stroke="#EF4444" strokeWidth={2} strokeDasharray="8 4" dot={false} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </ChartCard>
              </>
            )}

            {biTab === "marketing" && (
              <>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10 }}>
                  <KPI label="Marketing Spend" value="$42K" change="$287 CAC" icon="📣" />
                  <KPI label="Leads Generated" value="234" change="+18% MoM" icon="🎯" />
                  <KPI label="Lead-to-Patient" value="23%" icon="📈" />
                  <KPI label="ROAS" value="8.4x" change="+2.1x from AI optim." icon="💰" />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                  <ChartCard title="Patient Acquisition Source" height={260}>
                    <ResponsiveContainer>
                      <PieChart>
                        <Pie data={PATIENT_SOURCE} cx="50%" cy="50%" innerRadius="45%" outerRadius="80%" paddingAngle={3} dataKey="value" stroke="none">
                          {PATIENT_SOURCE.map((s, i) => <Cell key={i} fill={s.color} />)}
                        </Pie>
                        <Tooltip content={<CustomTooltip />} />
                        <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, fontWeight: 600 }} formatter={(v) => <span style={{ color: "#8899AA" }}>{v}</span>} />
                      </PieChart>
                    </ResponsiveContainer>
                  </ChartCard>
                  <ChartCard title="Conversion Funnel" height={260}>
                    <div style={{ display: "flex", flexDirection: "column", gap: 8, height: "100%", justifyContent: "center" }}>
                      {FUNNEL_DATA.map((f, i) => {
                        const w = (f.value / FUNNEL_DATA[0].value) * 100;
                        return (
                          <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <div style={{ width: 100, fontSize: 11, color: "var(--muted)", textAlign: "right", flexShrink: 0 }}>{f.name}</div>
                            <div style={{ flex: 1, height: 26, borderRadius: 5, background: `${f.fill}12`, overflow: "hidden" }}>
                              <div style={{ height: "100%", width: `${w}%`, background: f.fill, borderRadius: 5, display: "flex", alignItems: "center", paddingLeft: 8 }}>
                                <span style={{ fontSize: 10, fontWeight: 800, color: "#fff" }}>{f.value.toLocaleString()}</span>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </ChartCard>
                </div>
              </>
            )}
          </div>
        )}

        {/* ════════════════════════════════
            PIPELINE (Kanban)
           ════════════════════════════════ */}
        {mainTab === "pipeline" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
              <div>
                <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "var(--font-display)" }}>Opportunity Pipeline</div>
                <div style={{ fontSize: 13, color: "var(--muted)" }}>$4.78M in active pipeline across 7 stages</div>
              </div>
            </div>

            {/* Pipeline Summary */}
            <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 4 }}>
              {PIPELINE_STAGES.map((s) => (
                <div key={s.stage} style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, padding: "12px 16px", minWidth: 150, flex: "0 0 auto" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: s.color }} />
                    <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", letterSpacing: 0.4, textTransform: "uppercase" }}>{s.stage}</div>
                  </div>
                  <div style={{ fontSize: 20, fontWeight: 800, fontFamily: "var(--font-display)" }}>{s.count}</div>
                  <div style={{ fontSize: 12, color: s.color, fontWeight: 700 }}>{fmt(s.value)}</div>
                </div>
              ))}
            </div>

            {/* Kanban Board */}
            <div style={{ display: "flex", gap: 10, overflowX: "auto", paddingBottom: 12 }}>
              {["New Lead", "Consultation Booked", "Treatment Plan Sent", "Plan Accepted", "In Treatment"].map((stage) => {
                const patients = PATIENTS.filter((p) => p.stage === stage);
                return (
                  <div key={stage} style={{ minWidth: 260, flex: "0 0 260px", background: "var(--card)", border: "1px solid var(--border)", borderRadius: 14, overflow: "hidden" }}>
                    <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ width: 8, height: 8, borderRadius: "50%", background: stageColors[stage] }} />
                        <div style={{ fontSize: 12, fontWeight: 700 }}>{stage}</div>
                      </div>
                      <span style={{ fontSize: 11, color: "var(--muted)", fontWeight: 700 }}>{patients.length}</span>
                    </div>
                    <div style={{ padding: 8, display: "flex", flexDirection: "column", gap: 6, minHeight: 120 }}>
                      {patients.map((p) => (
                        <div key={p.id} onClick={() => setSelectedPatient(p)} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: 10, padding: "10px 12px", cursor: "pointer", transition: "0.15s" }} onMouseOver={(e) => e.currentTarget.style.borderColor = stageColors[stage] + "50"} onMouseOut={(e) => e.currentTarget.style.borderColor = "var(--border)"}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                            <Avatar initials={p.avatar} color={stageColors[stage]} size={28} />
                            <div style={{ fontSize: 13, fontWeight: 700 }}>{p.name}</div>
                          </div>
                          <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 6 }}>{p.treatmentPlan}</div>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                            <span style={{ fontSize: 12, fontWeight: 800, color: p.ltv > 0 ? "#00E6B4" : "var(--muted)" }}>${p.ltv.toLocaleString()}</span>
                            <span style={{ fontSize: 10, color: "var(--muted)" }}>{p.provider}</span>
                          </div>
                        </div>
                      ))}
                      {patients.length === 0 && <div style={{ padding: 20, textAlign: "center", fontSize: 12, color: "var(--muted)" }}>No patients</div>}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Pipeline Analytics */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <ChartCard title="Pipeline Value by Stage" height={240}>
                <ResponsiveContainer>
                  <BarChart data={PIPELINE_STAGES} margin={{ top: 5, right: 5, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                    <XAxis dataKey="stage" tick={{ fontSize: 9, fill: "#6B7B8D" }} axisLine={false} tickLine={false} interval={0} angle={-20} textAnchor="end" height={50} />
                    <YAxis tick={{ fontSize: 10, fill: "#6B7B8D" }} axisLine={false} tickLine={false} tickFormatter={(v) => fmt(v)} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="value" name="Value" radius={[6, 6, 0, 0]}>
                      {PIPELINE_STAGES.map((s, i) => <Cell key={i} fill={s.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
              <ChartCard title="Leads by Stage Count" height={240}>
                <ResponsiveContainer>
                  <BarChart data={PIPELINE_STAGES} layout="vertical" margin={{ top: 5, right: 20, bottom: 5, left: 80 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.03)" />
                    <XAxis type="number" tick={{ fontSize: 10, fill: "#6B7B8D" }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="stage" tick={{ fontSize: 10, fill: "#8899AA" }} axisLine={false} tickLine={false} width={90} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="count" name="Contacts" radius={[0, 6, 6, 0]} barSize={14}>
                      {PIPELINE_STAGES.map((s, i) => <Cell key={i} fill={s.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </ChartCard>
            </div>
          </div>
        )}

        {/* ════════════════════════════════
            GROWTH ENGINE (Hormozi)
           ════════════════════════════════ */}
        {mainTab === "growth" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
            <div style={{ background: "linear-gradient(135deg, rgba(0,230,180,0.04), rgba(99,102,241,0.04))", border: "1px solid rgba(0,230,180,0.08)", borderRadius: 18, padding: 24 }}>
              <div style={{ fontSize: 10, color: "#00E6B4", letterSpacing: 2, textTransform: "uppercase", fontWeight: 700, marginBottom: 4 }}>acquisition.com Framework</div>
              <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "var(--font-display)", marginBottom: 4 }}>$100M Dental Empire Playbook</div>
              <div style={{ fontSize: 13, color: "var(--muted)" }}>Grand Slam Offer × Value Ladder × Acquisition Roll-Up — all AI-orchestrated.</div>
            </div>

            {/* Hormozi Metrics */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10 }}>
              {[
                { l: "Patient LTV", v: "$8,740", t: "$12K target", pct: 73, c: "#00E6B4" },
                { l: "CAC", v: "$287", t: "$150 target", pct: 52, c: "#F59E0B" },
                { l: "LTV:CAC", v: "30.5x", t: "80x target", pct: 38, c: "#6366F1" },
                { l: "Churn", v: "8.2%", t: "5% target", pct: 61, c: "#EF4444" },
                { l: "Ascension", v: "34%", t: "60% target", pct: 57, c: "#0EA5E9" },
                { l: "Referral Rate", v: "22%", t: "40% target", pct: 55, c: "#10B981" },
              ].map((m, i) => (
                <div key={i} style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 14, padding: "16px 18px", textAlign: "center" }}>
                  <div style={{ fontSize: 24, fontWeight: 900, color: m.c, fontFamily: "var(--font-display)", marginBottom: 2 }}>{m.v}</div>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text)", marginBottom: 4 }}>{m.l}</div>
                  <div style={{ height: 5, background: "rgba(255,255,255,0.04)", borderRadius: 3, overflow: "hidden", marginBottom: 4 }}>
                    <div style={{ height: "100%", width: `${m.pct}%`, background: m.c, borderRadius: 3 }} />
                  </div>
                  <div style={{ fontSize: 10, color: "var(--muted)" }}>{m.t}</div>
                </div>
              ))}
            </div>

            {/* Value Equation */}
            <div style={{ background: "var(--card)", border: "1px solid rgba(0,230,180,0.08)", borderRadius: 16, padding: 22 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#00E6B4", letterSpacing: 1, textTransform: "uppercase", marginBottom: 16 }}>Grand Slam Offer — Value Equation</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 14, textAlign: "center" }}>
                {[
                  { l: "Dream Outcome", v: "9.2", d: "Perfect smile, zero pain", c: "#00E6B4", op: "×" },
                  { l: "Likelihood of Success", v: "8.5", d: "3D preview, guarantees", c: "#6366F1", op: "÷" },
                  { l: "Time Delay", v: "2.1", d: "Same-day teeth option", c: "#F59E0B", op: "÷" },
                  { l: "Effort & Sacrifice", v: "1.8", d: "Sedation + financing", c: "#EF4444", op: "=" },
                ].map((v, i) => (
                  <div key={i} style={{ position: "relative" }}>
                    <div style={{ fontSize: 32, fontWeight: 900, color: v.c, fontFamily: "var(--font-display)" }}>{v.v}</div>
                    <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 2 }}>{v.l}</div>
                    <div style={{ fontSize: 10, color: "var(--muted)" }}>{v.d}</div>
                  </div>
                ))}
              </div>
              <div style={{ textAlign: "center", marginTop: 18, padding: "10px 18px", background: "rgba(0,230,180,0.05)", borderRadius: 10, fontSize: 14 }}>
                <span style={{ fontWeight: 900, color: "#00E6B4", fontFamily: "var(--font-display)" }}>Offer Score: 21.8</span>
                <span style={{ color: "var(--muted)", marginLeft: 8 }}>→ "Free CBCT + Consult + 3D Smile Preview + Lifetime Warranty"</span>
              </div>
            </div>

            {/* Growth Levers */}
            <Section title="Growth Levers" sub="Active scaling strategies from the Hormozi playbook">
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {[
                  { lever: "Grand Slam Offer", status: "active", impact: "10x", desc: "Free CBCT + consultation + 3D preview. Zero-risk entry point.", progress: 78, color: "#00E6B4" },
                  { lever: "Value Ladder", status: "active", impact: "3x", desc: "Cleaning → Whitening → Invisalign → Implants → Full Mouth Rehab", progress: 65, color: "#6366F1" },
                  { lever: "Practice Acquisitions", status: "scouting", impact: "10x", desc: "Roll-up: acquire underperforming practices, inject AI + SOPs", progress: 30, color: "#0EA5E9" },
                  { lever: "Referral Engine", status: "building", impact: "3x", desc: "$500 referral bonus + automated post-treatment ask sequence", progress: 38, color: "#F59E0B" },
                  { lever: "Paid Acquisition", status: "optimizing", impact: "4x", desc: "Meta + Google + YouTube funnel with AI-optimized creative", progress: 56, color: "#EF4444" },
                  { lever: "Lead Magnets", status: "building", impact: "5x", desc: "Free Smile Quiz + Implant Cost Calculator + Before/After Gallery", progress: 42, color: "#10B981" },
                ].map((g, i) => (
                  <div key={i} style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, padding: "16px 20px" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8, flexWrap: "wrap", gap: 6 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{ fontSize: 15, fontWeight: 800 }}>{g.lever}</div>
                        <Badge color={g.status === "active" ? "#00E6B4" : g.status === "optimizing" ? "#6366F1" : "#F59E0B"}>{g.status}</Badge>
                      </div>
                      <div style={{ background: `${g.color}12`, color: g.color, padding: "2px 10px", borderRadius: 6, fontSize: 12, fontWeight: 800 }}>{g.impact} impact</div>
                    </div>
                    <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 10 }}>{g.desc}</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ flex: 1, height: 5, background: "rgba(255,255,255,0.04)", borderRadius: 3, overflow: "hidden" }}>
                        <div style={{ height: "100%", width: `${g.progress}%`, background: g.color, borderRadius: 3, transition: "width 1s" }} />
                      </div>
                      <div style={{ fontSize: 12, fontWeight: 800, color: g.color, minWidth: 36, textAlign: "right" }}>{g.progress}%</div>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          </div>
        )}
      </div>

      {/* Patient Detail Slideout */}
      {selectedPatient && <PatientDetail patient={selectedPatient} onClose={() => setSelectedPatient(null)} />}

      <style>{`
        @keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: 0.4 } }
        @keyframes slideIn { from { transform: translateX(100%) } to { transform: translateX(0) } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 5px; height: 5px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 3px; }
        button { transition: all 0.15s; }
        button:hover { filter: brightness(1.12); transform: translateY(-0.5px); }
        table tr:hover { background: rgba(0,230,180,0.02); }
      `}</style>
    </div>
  );
}
