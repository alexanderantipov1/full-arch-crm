import { useState, useEffect } from "react";

// ═══════════════════════════════════════════════════════════════
// DENTAI SaaS PLATFORM — Multi-Tenant Practice Management
// Landing Page → Onboarding → Practice Dashboard → Admin
// ═══════════════════════════════════════════════════════════════

const C = {
  bg: "#FAFBFC", card: "#FFFFFF", border: "#E8ECF1", text: "#0F1729", muted: "#6C7A8D",
  accent: "#1a6bff", accentDark: "#0A4FD6", success: "#059669", warning: "#D97706",
  danger: "#DC2626", purple: "#7C3AED", pink: "#DB2777", teal: "#0D9488",
  orange: "#EA580C", navy: "#0B1222", navyLight: "#111D35",
};

// ═══ PRICING DATA ═══
const PLANS = [
  { id: "starter", name: "Starter", price: 297, period: "/mo", tagline: "Solo practice essentials", features: ["1 practice location", "Up to 5 users", "Patient CRM (unlimited patients)", "Appointment scheduling", "Digital charting", "Basic insurance claims", "SMS reminders (500/mo)", "Email support", "DentBot AI assistant"], highlight: false, cta: "Start Free Trial" },
  { id: "growth", name: "Growth", price: 497, period: "/mo", tagline: "For practices ready to scale", features: ["1-3 practice locations", "Up to 15 users", "Everything in Starter, plus:", "AI phone receptionist (24/7)", "Smart scheduling optimizer", "Auto insurance verification", "SMS collections engine", "Automated recall campaigns", "AI treatment presentations", "Review generation bot", "Google Ads integration", "Analytics dashboard", "Priority support + onboarding"], highlight: true, cta: "Start Free Trial", badge: "Most Popular" },
  { id: "enterprise", name: "Enterprise", price: 997, period: "/mo", tagline: "DSO & multi-location powerhouse", features: ["Unlimited locations", "Unlimited users", "Everything in Growth, plus:", "Multi-location dashboard", "Provider performance scorecards", "Custom AI agent workflows", "EDI claims clearinghouse", "API access & integrations", "HIPAA BAA included", "Custom onboarding (60-day)", "Dedicated success manager", "White-label option", "SLA 99.9% uptime"], highlight: false, cta: "Contact Sales" },
];

// ═══ FEATURES ═══
const FEATURES = [
  { icon: "🤖", title: "AI-Native from Day 1", desc: "Every module is powered by Claude AI — from phone calls to treatment plans to collections. Not an afterthought, it's the foundation." },
  { icon: "📞", title: "AI Phone Receptionist", desc: "Never miss a call. Our AI answers after-hours, books appointments, triages emergencies, and texts follow-ups — automatically." },
  { icon: "💬", title: "SMS Collections Engine", desc: "Patients pay via text. Automated payment links, smart reminder sequences, and auto-generated payment plans recover 35%+ more revenue." },
  { icon: "🦷", title: "Full Digital Charting", desc: "32-tooth interactive chart with CDT codes, treatment history, and AI-assisted condition detection. Dentrix-grade, cloud-native." },
  { icon: "📋", title: "Smart Claims Processing", desc: "Auto-verify insurance, submit claims electronically, track payments, and follow up on pending claims — all AI-automated." },
  { icon: "📊", title: "DEO-Grade Analytics", desc: "Real-time KPIs: production, collections, case acceptance, overhead, provider scorecards. The numbers that actually drive profit." },
  { icon: "🎯", title: "Patient Acquisition AI", desc: "Built-in Google Ads manager, lead nurture sequences, review generation, and referral tracking. Your marketing team in a box." },
  { icon: "📅", title: "Intelligent Scheduling", desc: "Predicts no-shows, auto-fills cancellations from waitlist, optimizes block scheduling for maximum chair utilization." },
];

// ═══ TESTIMONIALS ═══
const TESTIMONIALS = [
  { name: "Dr. Sarah Park", role: "Park Family Dentistry — Roseville, CA", quote: "We went from 28 to 52 new patients per month in 90 days. The AI phone system alone captured 20+ calls we were missing weekly.", metric: "+86% new patients", avatar: "SP" },
  { name: "Dr. Marcus Johnson", role: "Johnson Implant Center — Sacramento, CA", quote: "Case acceptance jumped from 48% to 74% once we started using the AI treatment presentations. Patients literally see their future smile.", metric: "+54% case acceptance", avatar: "MJ" },
  { name: "Dr. Lisa Chen", role: "Bright Smiles DSO — 4 locations", quote: "Managing 4 locations used to require 3 office managers full-time. DentAI automated 70% of what they did. We reallocated them to patient care.", metric: "$340K saved/year", avatar: "LC" },
];

// ═══ ONBOARDING STEPS ═══
const ONBOARD_STEPS = [
  { id: 1, title: "Practice Info", icon: "🏥", fields: ["Practice Name", "Number of Locations", "Number of Operatories", "Practice Management System (current)", "Specialty Focus"] },
  { id: 2, title: "Team Setup", icon: "👥", fields: ["Owner/Admin Name", "Owner Email", "Number of Providers", "Number of Staff", "Office Manager Name & Email"] },
  { id: 3, title: "Integrations", icon: "🔗", fields: ["Current PMS (Dentrix/Eaglesoft/Open Dental/Other)", "Phone System", "Payment Processor", "Insurance Clearinghouse", "Email Provider"] },
  { id: 4, title: "AI Configuration", icon: "🤖", fields: ["Enable AI Phone Receptionist?", "Enable SMS Collections?", "Enable Auto Review Requests?", "Enable Recall Campaigns?", "AI Personality Tone (Professional/Friendly/Warm)"] },
  { id: 5, title: "Go Live", icon: "🚀", fields: ["Import Patient Data (CSV/API)", "Set Business Hours", "Configure Appointment Types", "Add Insurance Plans", "Invite Team Members"] },
];

// ═══ SAMPLE TENANTS (for admin view) ═══
const TENANTS = [
  { id: 1, name: "Auburn Dental Group", plan: "growth", locations: 1, users: 8, mrr: 497, patients: 3105, status: "active", joined: "2025-11-15", lastActive: "2026-02-11", usage: { sms: 847, calls_ai: 142, claims: 187, reviews: 12 } },
  { id: 2, name: "Park Family Dentistry", plan: "growth", locations: 1, users: 6, mrr: 497, patients: 2340, status: "active", joined: "2025-12-01", lastActive: "2026-02-11", usage: { sms: 612, calls_ai: 98, claims: 143, reviews: 18 } },
  { id: 3, name: "Johnson Implant Center", plan: "enterprise", locations: 2, users: 14, mrr: 997, patients: 4820, status: "active", joined: "2025-10-20", lastActive: "2026-02-11", usage: { sms: 1420, calls_ai: 234, claims: 312, reviews: 24 } },
  { id: 4, name: "Bright Smiles DSO", plan: "enterprise", locations: 4, users: 32, mrr: 997, patients: 12400, status: "active", joined: "2025-09-05", lastActive: "2026-02-10", usage: { sms: 4200, calls_ai: 580, claims: 890, reviews: 67 } },
  { id: 5, name: "Sierra Dental Care", plan: "starter", locations: 1, users: 3, mrr: 297, patients: 890, status: "active", joined: "2026-01-10", lastActive: "2026-02-11", usage: { sms: 234, calls_ai: 0, claims: 56, reviews: 4 } },
  { id: 6, name: "Dr. Kim Solo Practice", plan: "starter", locations: 1, users: 2, mrr: 297, patients: 620, status: "trial", joined: "2026-02-01", lastActive: "2026-02-09", usage: { sms: 45, calls_ai: 0, claims: 12, reviews: 1 } },
  { id: 7, name: "Valley Oral Surgery", plan: "growth", locations: 1, users: 7, mrr: 497, patients: 1870, status: "active", joined: "2025-12-15", lastActive: "2026-02-11", usage: { sms: 510, calls_ai: 112, claims: 178, reviews: 9 } },
  { id: 8, name: "Smile Design Studio", plan: "growth", locations: 2, users: 11, mrr: 497, patients: 3400, status: "churned", joined: "2025-08-20", lastActive: "2026-01-15", usage: { sms: 0, calls_ai: 0, claims: 0, reviews: 0 } },
];

// ═══ COMPONENTS ═══
const Badge = ({ children, color = C.accent, variant = "subtle" }) => <span style={{ background: variant === "solid" ? color : `${color}14`, color: variant === "solid" ? "#FFF" : color, padding: "3px 10px", borderRadius: 6, fontSize: 10, fontWeight: 700, letterSpacing: 0.3, textTransform: "uppercase" }}>{children}</span>;

const KpiCard = ({ label, value, sub, color = C.accent, icon }) => (
  <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "16px 18px" }}>
    <div style={{ fontSize: 10, color: C.muted, letterSpacing: 1.2, textTransform: "uppercase", fontWeight: 600, marginBottom: 4, display: "flex", alignItems: "center", gap: 4 }}>{icon && <span style={{ fontSize: 13 }}>{icon}</span>}{label}</div>
    <div style={{ fontSize: 26, fontWeight: 900, color: C.text }}>{value}</div>
    {sub && <div style={{ fontSize: 11, color, fontWeight: 600, marginTop: 2 }}>{sub}</div>}
  </div>
);

// ═══ MAIN APP ═══
export default function DentAISaaS() {
  const [view, setView] = useState("landing"); // landing, onboarding, app, admin
  const [onboardStep, setOnboardStep] = useState(1);
  const [selTenant, setSelTenant] = useState(null);
  const [appTab, setAppTab] = useState("practices");
  const [adminTab, setAdminTab] = useState("overview");

  // ═══════════════════════════════════════════
  // LANDING PAGE
  // ═══════════════════════════════════════════
  if (view === "landing") return (
    <div style={{ background: "#FAFBFC", color: C.text, fontFamily: "'Outfit', 'DM Sans', sans-serif", minHeight: "100vh" }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Newsreader:ital,wght@0,400;0,700;1,400&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet" />

      {/* NAV */}
      <nav style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 40px", borderBottom: `1px solid ${C.border}`, background: "rgba(255,255,255,0.85)", backdropFilter: "blur(12px)", position: "sticky", top: 0, zIndex: 100 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 9, background: `linear-gradient(135deg, ${C.accent}, #06B6D4)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15 }}>🦷</div>
          <span style={{ fontSize: 20, fontWeight: 900, color: C.navy }}>DentAI</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
          {["Features", "Pricing", "Testimonials"].map(l => <a key={l} href="#" style={{ fontSize: 14, fontWeight: 500, color: C.muted, textDecoration: "none" }}>{l}</a>)}
          <button onClick={() => setView("app")} style={{ background: "none", border: `1px solid ${C.border}`, borderRadius: 8, padding: "7px 18px", fontSize: 13, fontWeight: 600, cursor: "pointer", color: C.text }}>Log In</button>
          <button onClick={() => setView("onboarding")} style={{ background: C.accent, color: "#FFF", border: "none", borderRadius: 8, padding: "7px 18px", fontSize: 13, fontWeight: 700, cursor: "pointer" }}>Start Free Trial</button>
        </div>
      </nav>

      {/* HERO */}
      <section style={{ padding: "80px 40px 60px", textAlign: "center", position: "relative", overflow: "hidden" }}>
        <div style={{ position: "absolute", top: -100, left: "50%", transform: "translateX(-50%)", width: 800, height: 800, background: `radial-gradient(circle, ${C.accent}06, transparent 70%)`, borderRadius: "50%", pointerEvents: "none" }} />
        <div style={{ position: "relative" }}>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 6, background: `${C.accent}08`, border: `1px solid ${C.accent}15`, borderRadius: 20, padding: "5px 16px", marginBottom: 20 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.success, boxShadow: `0 0 8px ${C.success}` }} />
            <span style={{ fontSize: 12, fontWeight: 700, color: C.accent }}>AI-powered dental practice management</span>
          </div>
          <h1 style={{ fontSize: "clamp(36px, 6vw, 64px)", fontWeight: 900, lineHeight: 1.05, maxWidth: 850, margin: "0 auto", color: C.navy }}>
            The operating system<br />for modern dental practices
          </h1>
          <p style={{ fontSize: 18, color: C.muted, maxWidth: 600, margin: "16px auto 0", lineHeight: 1.6, fontFamily: "'Newsreader', serif", fontStyle: "italic" }}>
            AI receptionist. Smart scheduling. SMS collections. Digital charting. Insurance automation. Analytics. Everything your practice needs — powered by intelligence, not just software.
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center", marginTop: 32 }}>
            <button onClick={() => setView("onboarding")} style={{ background: C.accent, color: "#FFF", border: "none", borderRadius: 10, padding: "14px 32px", fontSize: 16, fontWeight: 800, cursor: "pointer", boxShadow: `0 4px 20px ${C.accent}30` }}>Start 14-Day Free Trial →</button>
            <button style={{ background: C.card, color: C.text, border: `1px solid ${C.border}`, borderRadius: 10, padding: "14px 32px", fontSize: 16, fontWeight: 600, cursor: "pointer" }}>Watch Demo</button>
          </div>
          <div style={{ display: "flex", gap: 32, justifyContent: "center", marginTop: 32 }}>
            {[["3,100+", "Active practices"], ["$2.4M", "Collected via SMS"], ["47K", "AI calls handled"], ["98.2%", "Uptime SLA"]].map(([v, l], i) => (
              <div key={i}><div style={{ fontSize: 22, fontWeight: 900, color: C.navy }}>{v}</div><div style={{ fontSize: 11, color: C.muted }}>{l}</div></div>
            ))}
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section style={{ padding: "60px 40px", maxWidth: 1100, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: C.accent, letterSpacing: 3, textTransform: "uppercase", marginBottom: 6 }}>Built Different</div>
          <h2 style={{ fontSize: 36, fontWeight: 900, color: C.navy }}>AI-native. Not AI-bolted-on.</h2>
          <p style={{ fontSize: 16, color: C.muted, marginTop: 8, fontFamily: "'Newsreader', serif" }}>Every module was designed with intelligence at its core — not added as an afterthought.</p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 16 }}>
          {FEATURES.map((f, i) => (
            <div key={i} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: "24px 22px", transition: "0.2s", cursor: "default" }} onMouseOver={e => { e.currentTarget.style.borderColor = C.accent + "30"; e.currentTarget.style.transform = "translateY(-2px)"; }} onMouseOut={e => { e.currentTarget.style.borderColor = C.border; e.currentTarget.style.transform = "none"; }}>
              <div style={{ fontSize: 32, marginBottom: 10 }}>{f.icon}</div>
              <div style={{ fontSize: 16, fontWeight: 800, marginBottom: 6, color: C.navy }}>{f.title}</div>
              <div style={{ fontSize: 13, color: C.muted, lineHeight: 1.6 }}>{f.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* PRICING */}
      <section style={{ padding: "60px 40px", background: "#F3F5F8" }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: C.accent, letterSpacing: 3, textTransform: "uppercase", marginBottom: 6 }}>Simple Pricing</div>
          <h2 style={{ fontSize: 36, fontWeight: 900, color: C.navy }}>One platform. Three tiers. No surprises.</h2>
          <p style={{ fontSize: 16, color: C.muted, marginTop: 8, fontFamily: "'Newsreader', serif" }}>14-day free trial on every plan. No credit card required.</p>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 20, maxWidth: 1050, margin: "0 auto" }}>
          {PLANS.map(plan => (
            <div key={plan.id} style={{ background: C.card, border: plan.highlight ? `2px solid ${C.accent}` : `1px solid ${C.border}`, borderRadius: 20, padding: "28px 26px", position: "relative", transform: plan.highlight ? "scale(1.03)" : "none", boxShadow: plan.highlight ? `0 8px 40px ${C.accent}15` : "none" }}>
              {plan.badge && <div style={{ position: "absolute", top: -12, left: "50%", transform: "translateX(-50%)", background: C.accent, color: "#FFF", padding: "4px 18px", borderRadius: 20, fontSize: 11, fontWeight: 800 }}>{plan.badge}</div>}
              <div style={{ fontSize: 12, fontWeight: 700, color: C.accent, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 4 }}>{plan.name}</div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 4, marginBottom: 4 }}>
                <span style={{ fontSize: 42, fontWeight: 900, color: C.navy }}>${plan.price}</span>
                <span style={{ fontSize: 14, color: C.muted }}>{plan.period}</span>
              </div>
              <div style={{ fontSize: 13, color: C.muted, marginBottom: 18, fontFamily: "'Newsreader', serif", fontStyle: "italic" }}>{plan.tagline}</div>
              <button onClick={() => plan.id !== "enterprise" ? setView("onboarding") : null} style={{ width: "100%", background: plan.highlight ? C.accent : C.card, color: plan.highlight ? "#FFF" : C.text, border: plan.highlight ? "none" : `1px solid ${C.border}`, borderRadius: 10, padding: "12px 20px", fontSize: 14, fontWeight: 800, cursor: "pointer", marginBottom: 18 }}>{plan.cta}</button>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {plan.features.map((f, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: 13, color: f.includes("Everything") ? C.accent : "#4B5563", fontWeight: f.includes("Everything") ? 700 : 400 }}>
                    {!f.includes("Everything") && <span style={{ color: C.success, fontSize: 13, flexShrink: 0, marginTop: 1 }}>✓</span>}
                    {f}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* TESTIMONIALS */}
      <section style={{ padding: "60px 40px", maxWidth: 1050, margin: "0 auto" }}>
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <h2 style={{ fontSize: 36, fontWeight: 900, color: C.navy }}>Practices love DentAI</h2>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
          {TESTIMONIALS.map((t, i) => (
            <div key={i} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: "24px 22px" }}>
              <div style={{ fontSize: 22, fontWeight: 900, color: C.accent, marginBottom: 10 }}>{t.metric}</div>
              <div style={{ fontSize: 14, color: "#4B5563", lineHeight: 1.6, fontFamily: "'Newsreader', serif", fontStyle: "italic", marginBottom: 14 }}>"{t.quote}"</div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, paddingTop: 12, borderTop: `1px solid ${C.border}` }}>
                <div style={{ width: 36, height: 36, borderRadius: 9, background: `${C.accent}10`, color: C.accent, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 12 }}>{t.avatar}</div>
                <div><div style={{ fontSize: 13, fontWeight: 700 }}>{t.name}</div><div style={{ fontSize: 11, color: C.muted }}>{t.role}</div></div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section style={{ padding: "60px 40px", background: C.navy, textAlign: "center" }}>
        <h2 style={{ fontSize: 32, fontWeight: 900, color: "#F8FAFC", marginBottom: 8 }}>Ready to transform your practice?</h2>
        <p style={{ fontSize: 16, color: "#94A3B8", marginBottom: 24 }}>14-day free trial · No credit card · Setup in 15 minutes</p>
        <button onClick={() => setView("onboarding")} style={{ background: "#FFF", color: C.navy, border: "none", borderRadius: 10, padding: "14px 36px", fontSize: 16, fontWeight: 800, cursor: "pointer" }}>Get Started Free →</button>
      </section>

      {/* FOOTER */}
      <footer style={{ padding: "30px 40px", borderTop: `1px solid ${C.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 13, color: C.muted }}>© 2026 DentAI, Inc. · HIPAA Compliant · SOC 2 Type II</div>
        <div style={{ display: "flex", gap: 16, fontSize: 13, color: C.muted }}>{["Privacy", "Terms", "HIPAA", "Security", "API Docs"].map(l => <a key={l} href="#" style={{ color: C.muted, textDecoration: "none" }}>{l}</a>)}</div>
      </footer>
      <style>{`*{box-sizing:border-box;margin:0;padding:0} a:hover{color:${C.accent} !important} button{transition:0.15s} button:hover{filter:brightness(0.95)}`}</style>
    </div>
  );

  // ═══════════════════════════════════════════
  // ONBOARDING WIZARD
  // ═══════════════════════════════════════════
  if (view === "onboarding") return (
    <div style={{ minHeight: "100vh", background: "#F3F5F8", fontFamily: "'Outfit', sans-serif", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 32 }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Newsreader:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet" />

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 32 }}>
        <div style={{ width: 28, height: 28, borderRadius: 8, background: `linear-gradient(135deg, ${C.accent}, #06B6D4)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13 }}>🦷</div>
        <span style={{ fontSize: 18, fontWeight: 900, color: C.navy }}>DentAI</span>
      </div>

      {/* Progress Steps */}
      <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 32, maxWidth: 600, width: "100%" }}>
        {ONBOARD_STEPS.map((s, i) => (
          <div key={s.id} style={{ display: "flex", alignItems: "center", flex: 1 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, flex: "0 0 auto" }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: onboardStep >= s.id ? C.accent : "#E5E7EB", color: onboardStep >= s.id ? "#FFF" : C.muted, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 800, transition: "0.3s" }}>{onboardStep > s.id ? "✓" : s.id}</div>
              <span style={{ fontSize: 10, fontWeight: 600, color: onboardStep >= s.id ? C.accent : C.muted }}>{s.title}</span>
            </div>
            {i < ONBOARD_STEPS.length - 1 && <div style={{ flex: 1, height: 2, background: onboardStep > s.id ? C.accent : "#E5E7EB", transition: "0.3s", margin: "0 6px", marginBottom: 16 }} />}
          </div>
        ))}
      </div>

      {/* Form Card */}
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 20, padding: "36px 40px", maxWidth: 520, width: "100%", boxShadow: "0 4px 30px rgba(0,0,0,0.06)" }}>
        <div style={{ fontSize: 28, marginBottom: 4 }}>{ONBOARD_STEPS[onboardStep - 1].icon}</div>
        <div style={{ fontSize: 22, fontWeight: 900, color: C.navy, marginBottom: 4 }}>Step {onboardStep}: {ONBOARD_STEPS[onboardStep - 1].title}</div>
        <div style={{ fontSize: 13, color: C.muted, marginBottom: 20 }}>
          {onboardStep === 1 && "Tell us about your practice so we can configure everything perfectly."}
          {onboardStep === 2 && "Set up your team accounts and permissions."}
          {onboardStep === 3 && "Connect your existing tools — we'll sync everything."}
          {onboardStep === 4 && "Choose which AI automations to activate on day one."}
          {onboardStep === 5 && "Final setup — import your data and go live."}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {ONBOARD_STEPS[onboardStep - 1].fields.map((field, i) => (
            <div key={i}>
              <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 4 }}>{field}</label>
              {field.includes("?") ? (
                <div style={{ display: "flex", gap: 8 }}>
                  <button style={{ flex: 1, padding: "10px 16px", borderRadius: 8, border: `2px solid ${C.accent}20`, background: `${C.accent}06`, color: C.accent, fontWeight: 700, fontSize: 13, cursor: "pointer" }}>✓ Yes</button>
                  <button style={{ flex: 1, padding: "10px 16px", borderRadius: 8, border: `1px solid ${C.border}`, background: C.card, color: C.muted, fontWeight: 600, fontSize: 13, cursor: "pointer" }}>No</button>
                </div>
              ) : (
                <input placeholder={field} style={{ width: "100%", padding: "10px 14px", borderRadius: 8, border: `1px solid ${C.border}`, fontSize: 14, outline: "none", background: "#FAFBFC" }} />
              )}
            </div>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24 }}>
          <button onClick={() => onboardStep > 1 ? setOnboardStep(onboardStep - 1) : setView("landing")} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: "10px 22px", fontSize: 14, fontWeight: 600, cursor: "pointer", color: C.muted }}>← {onboardStep > 1 ? "Back" : "Cancel"}</button>
          <button onClick={() => onboardStep < 5 ? setOnboardStep(onboardStep + 1) : setView("app")} style={{ background: C.accent, color: "#FFF", border: "none", borderRadius: 10, padding: "10px 28px", fontSize: 14, fontWeight: 800, cursor: "pointer" }}>{onboardStep < 5 ? "Continue →" : "🚀 Launch DentAI"}</button>
        </div>
      </div>
      <style>{`*{box-sizing:border-box;margin:0;padding:0} input:focus{border-color:${C.accent};box-shadow:0 0 0 3px ${C.accent}18} button{transition:0.15s} button:hover{filter:brightness(0.95)}`}</style>
    </div>
  );

  // ═══════════════════════════════════════════
  // TENANT DASHBOARD (post-login)
  // ═══════════════════════════════════════════
  if (view === "app") return (
    <div style={{ minHeight: "100vh", background: C.bg, fontFamily: "'Outfit', sans-serif", display: "flex", flexDirection: "column" }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Newsreader:ital,wght@0,400;0,700;1,400&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet" />

      {/* App Nav */}
      <nav style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 28px", borderBottom: `1px solid ${C.border}`, background: C.card }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 30, height: 30, borderRadius: 8, background: `linear-gradient(135deg, ${C.accent}, #06B6D4)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>🦷</div>
          <span style={{ fontSize: 18, fontWeight: 900 }}>DentAI</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {[{ id: "practices", l: "My Practices" }, { id: "billing", l: "Billing" }, { id: "settings", l: "Settings" }].map(t => (
            <button key={t.id} onClick={() => setAppTab(t.id)} style={{ padding: "6px 16px", borderRadius: 7, border: "none", background: appTab === t.id ? `${C.accent}10` : "transparent", color: appTab === t.id ? C.accent : C.muted, fontWeight: 700, fontSize: 13, cursor: "pointer" }}>{t.l}</button>
          ))}
          <div style={{ width: 1, height: 20, background: C.border, margin: "0 8px" }} />
          <button onClick={() => setView("admin")} style={{ padding: "6px 16px", borderRadius: 7, border: `1px solid ${C.border}`, background: "transparent", color: C.muted, fontSize: 12, fontWeight: 600, cursor: "pointer" }}>⚙️ Admin</button>
          <div style={{ width: 30, height: 30, borderRadius: 8, background: `${C.accent}12`, color: C.accent, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800, cursor: "pointer" }}>AC</div>
        </div>
      </nav>

      <div style={{ padding: "24px 32px", flex: 1 }}>
        {appTab === "practices" && (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <div><div style={{ fontSize: 26, fontWeight: 900 }}>My Practices</div><div style={{ fontSize: 13, color: C.muted }}>Select a practice to open its management dashboard</div></div>
              <button style={{ background: C.accent, color: "#FFF", border: "none", borderRadius: 10, padding: "10px 22px", fontSize: 13, fontWeight: 700, cursor: "pointer" }}>+ Add Practice</button>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 16 }}>
              {TENANTS.filter(t => t.status !== "churned").slice(0, 4).map(t => (
                <div key={t.id} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, padding: "22px 24px", cursor: "pointer", transition: "0.2s" }} onMouseOver={e => { e.currentTarget.style.borderColor = C.accent + "40"; e.currentTarget.style.transform = "translateY(-2px)"; }} onMouseOut={e => { e.currentTarget.style.borderColor = C.border; e.currentTarget.style.transform = "none"; }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                    <div>
                      <div style={{ fontSize: 18, fontWeight: 800, color: C.navy }}>{t.name}</div>
                      <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>{t.locations} location{t.locations > 1 ? "s" : ""} · {t.users} users</div>
                    </div>
                    <Badge color={t.status === "active" ? C.success : C.warning} variant="subtle">{t.status === "trial" ? "14-day trial" : t.plan}</Badge>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 14 }}>
                    {[
                      { l: "Patients", v: t.patients.toLocaleString() },
                      { l: "SMS Sent", v: t.usage.sms.toLocaleString() },
                      { l: "AI Calls", v: t.usage.calls_ai.toLocaleString() },
                      { l: "Claims", v: t.usage.claims.toLocaleString() },
                    ].map((m, i) => <div key={i}><div style={{ fontSize: 10, color: C.muted, textTransform: "uppercase", fontWeight: 600, letterSpacing: 0.5 }}>{m.l}</div><div style={{ fontSize: 16, fontWeight: 800 }}>{m.v}</div></div>)}
                  </div>
                  <button style={{ width: "100%", background: `${C.accent}08`, color: C.accent, border: `1px solid ${C.accent}20`, borderRadius: 10, padding: "10px 20px", fontWeight: 700, fontSize: 13, cursor: "pointer" }}>Open Dashboard →</button>
                </div>
              ))}
            </div>
          </>
        )}

        {appTab === "billing" && (
          <>
            <div style={{ fontSize: 26, fontWeight: 900, marginBottom: 20 }}>Billing & Subscription</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12, marginBottom: 24 }}>
              <KpiCard icon="💳" label="Current MRR" value="$1,788" sub="4 active subscriptions" color={C.accent} />
              <KpiCard icon="📦" label="Plan" value="Mixed" sub="2 Growth + 1 Starter + 1 Trial" color={C.purple} />
              <KpiCard icon="📅" label="Next Invoice" value="Mar 1" sub="$1,491.00" color={C.warning} />
              <KpiCard icon="📊" label="Usage This Month" value="68%" sub="Within plan limits" color={C.success} />
            </div>
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
              <div style={{ padding: "14px 18px", borderBottom: `1px solid ${C.border}`, fontSize: 13, fontWeight: 800 }}>Subscription Details</div>
              {TENANTS.filter(t => t.status !== "churned").slice(0, 4).map(t => (
                <div key={t.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px", borderBottom: `1px solid ${C.border}` }}>
                  <div><div style={{ fontSize: 14, fontWeight: 700 }}>{t.name}</div><div style={{ fontSize: 11, color: C.muted }}>Since {t.joined}</div></div>
                  <Badge color={t.plan === "enterprise" ? C.purple : t.plan === "growth" ? C.accent : C.muted}>{t.plan}</Badge>
                  <div style={{ fontSize: 18, fontWeight: 800, fontFamily: "'JetBrains Mono'" }}>${t.mrr}/mo</div>
                  <button style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: "6px 14px", fontSize: 11, fontWeight: 600, cursor: "pointer" }}>{t.plan === "starter" ? "⬆ Upgrade" : "Manage"}</button>
                </div>
              ))}
            </div>
          </>
        )}

        {appTab === "settings" && (
          <>
            <div style={{ fontSize: 26, fontWeight: 900, marginBottom: 20 }}>Account Settings</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {[
                { title: "Organization", fields: [["Organization Name", "Auburn Dental Group"], ["Owner", "Dr. Alex Chen"], ["Email", "alex@auburndental.com"], ["Phone", "(530) 555-0100"]] },
                { title: "Security", fields: [["Two-Factor Auth", "Enabled ✓"], ["Session Timeout", "30 minutes"], ["Password Policy", "Strong (12+ chars)"], ["Last Password Change", "2026-01-15"]] },
                { title: "HIPAA Compliance", fields: [["BAA Status", "Signed ✓"], ["Encryption", "AES-256 at rest"], ["Audit Logging", "Enabled"], ["Data Retention", "7 years"]] },
                { title: "API & Integrations", fields: [["API Key", "sk-dent-****-****-7x9a"], ["Webhook URL", "https://..."], ["Rate Limit", "1,000 req/min"], ["API Version", "v2.1"]] },
              ].map((section, i) => (
                <div key={i} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "20px 22px" }}>
                  <div style={{ fontSize: 13, fontWeight: 800, color: C.navy, marginBottom: 14 }}>{section.title}</div>
                  {section.fields.map(([l, v], j) => (
                    <div key={j} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: j < section.fields.length - 1 ? `1px solid ${C.border}` : "none" }}>
                      <span style={{ fontSize: 13, color: C.muted }}>{l}</span>
                      <span style={{ fontSize: 13, fontWeight: 600 }}>{v}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
      <style>{`*{box-sizing:border-box;margin:0;padding:0} button{transition:0.15s} button:hover{filter:brightness(0.95)}`}</style>
    </div>
  );

  // ═══════════════════════════════════════════
  // ADMIN PANEL (platform owner view)
  // ═══════════════════════════════════════════
  if (view === "admin") return (
    <div style={{ minHeight: "100vh", background: C.bg, fontFamily: "'Outfit', sans-serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet" />

      <nav style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 28px", borderBottom: `1px solid ${C.border}`, background: C.navy }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 28, height: 28, borderRadius: 7, background: "#FFF", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13 }}>🦷</div>
          <span style={{ fontSize: 16, fontWeight: 900, color: "#F8FAFC" }}>DentAI Admin</span>
          <Badge color={C.danger} variant="solid">Internal</Badge>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {[{ id: "overview", l: "Overview" }, { id: "tenants", l: "Tenants" }, { id: "revenue", l: "Revenue" }, { id: "infra", l: "Infrastructure" }].map(t => (
            <button key={t.id} onClick={() => setAdminTab(t.id)} style={{ padding: "5px 14px", borderRadius: 6, border: "none", background: adminTab === t.id ? "rgba(255,255,255,0.1)" : "transparent", color: adminTab === t.id ? "#FFF" : "#94A3B8", fontWeight: 600, fontSize: 12, cursor: "pointer" }}>{t.l}</button>
          ))}
          <div style={{ width: 1, height: 20, background: "rgba(255,255,255,0.1)", margin: "0 6px" }} />
          <button onClick={() => setView("app")} style={{ padding: "5px 14px", borderRadius: 6, border: `1px solid rgba(255,255,255,0.15)`, background: "transparent", color: "#94A3B8", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>← Back to App</button>
        </div>
      </nav>

      <div style={{ padding: "24px 32px" }}>
        {adminTab === "overview" && (
          <>
            <div style={{ fontSize: 26, fontWeight: 900, marginBottom: 20 }}>Platform Overview</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12, marginBottom: 24 }}>
              <KpiCard icon="🏥" label="Active Tenants" value={TENANTS.filter(t=>t.status==="active").length.toString()} sub="+2 this month" color={C.accent} />
              <KpiCard icon="🧪" label="Trial Accounts" value={TENANTS.filter(t=>t.status==="trial").length.toString()} sub="1 converting soon" color={C.purple} />
              <KpiCard icon="💰" label="MRR" value={`$${TENANTS.filter(t=>t.status!=="churned").reduce((s,t)=>s+t.mrr,0).toLocaleString()}`} sub="↑ 18% MoM" color={C.success} />
              <KpiCard icon="📈" label="ARR" value={`$${(TENANTS.filter(t=>t.status!=="churned").reduce((s,t)=>s+t.mrr,0)*12).toLocaleString()}`} color={C.teal} />
              <KpiCard icon="👥" label="Total Users" value={TENANTS.reduce((s,t)=>s+t.users,0).toString()} color={C.warning} />
              <KpiCard icon="🦷" label="Total Patients" value={TENANTS.reduce((s,t)=>s+t.patients,0).toLocaleString()} color={C.orange} />
              <KpiCard icon="💬" label="SMS Sent (MTD)" value={TENANTS.reduce((s,t)=>s+t.usage.sms,0).toLocaleString()} color={C.pink} />
              <KpiCard icon="📞" label="AI Calls (MTD)" value={TENANTS.reduce((s,t)=>s+t.usage.calls_ai,0).toLocaleString()} color={C.accent} />
            </div>

            {/* Churn alert */}
            {TENANTS.filter(t => t.status === "churned").length > 0 && (
              <div style={{ background: `${C.danger}06`, border: `1px solid ${C.danger}18`, borderRadius: 12, padding: "14px 18px", marginBottom: 16, display: "flex", alignItems: "center", gap: 12 }}>
                <span style={{ fontSize: 20 }}>⚠️</span>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: C.danger }}>1 Churned Account</div>
                  <div style={{ fontSize: 12, color: C.muted }}>Smile Design Studio — last active Jan 15. Revenue impact: -$497/mo. Trigger win-back sequence?</div>
                </div>
                <button style={{ marginLeft: "auto", background: C.danger, color: "#FFF", border: "none", borderRadius: 8, padding: "7px 16px", fontSize: 12, fontWeight: 700, cursor: "pointer", whiteSpace: "nowrap" }}>Launch Win-Back</button>
              </div>
            )}
          </>
        )}

        {adminTab === "tenants" && (
          <>
            <div style={{ fontSize: 26, fontWeight: 900, marginBottom: 20 }}>All Tenants</div>
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
              <div style={{ display: "grid", gridTemplateColumns: "2fr 80px 70px 70px 90px 80px 80px 80px 100px", padding: "10px 18px", borderBottom: `2px solid ${C.border}` }}>
                {["Practice", "Plan", "Locs", "Users", "Patients", "MRR", "SMS", "AI Calls", "Status"].map(h => <div key={h} style={{ fontSize: 10, fontWeight: 700, color: C.muted, letterSpacing: 0.8, textTransform: "uppercase" }}>{h}</div>)}
              </div>
              {TENANTS.map(t => (
                <div key={t.id} style={{ display: "grid", gridTemplateColumns: "2fr 80px 70px 70px 90px 80px 80px 80px 100px", padding: "12px 18px", borderBottom: `1px solid ${C.border}`, alignItems: "center", cursor: "pointer" }} onMouseOver={e => e.currentTarget.style.background = "#F8FAFC"} onMouseOut={e => e.currentTarget.style.background = "transparent"}>
                  <div><div style={{ fontSize: 13, fontWeight: 700 }}>{t.name}</div><div style={{ fontSize: 10, color: C.muted }}>Since {t.joined}</div></div>
                  <Badge color={t.plan === "enterprise" ? C.purple : t.plan === "growth" ? C.accent : C.muted}>{t.plan}</Badge>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>{t.locations}</div>
                  <div style={{ fontSize: 13 }}>{t.users}</div>
                  <div style={{ fontSize: 12, fontFamily: "'JetBrains Mono'" }}>{t.patients.toLocaleString()}</div>
                  <div style={{ fontSize: 13, fontWeight: 700, fontFamily: "'JetBrains Mono'" }}>${t.mrr}</div>
                  <div style={{ fontSize: 12, fontFamily: "'JetBrains Mono'" }}>{t.usage.sms.toLocaleString()}</div>
                  <div style={{ fontSize: 12, fontFamily: "'JetBrains Mono'" }}>{t.usage.calls_ai}</div>
                  <Badge color={t.status === "active" ? C.success : t.status === "trial" ? C.warning : C.danger}>{t.status}</Badge>
                </div>
              ))}
            </div>
          </>
        )}

        {adminTab === "revenue" && (
          <>
            <div style={{ fontSize: 26, fontWeight: 900, marginBottom: 20 }}>Revenue Metrics</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12, marginBottom: 24 }}>
              <KpiCard icon="💰" label="MRR" value={`$${TENANTS.filter(t=>t.status!=="churned").reduce((s,t)=>s+t.mrr,0).toLocaleString()}`} sub="↑ $994 from last month" color={C.success} />
              <KpiCard icon="📈" label="ARR (Projected)" value={`$${(TENANTS.filter(t=>t.status!=="churned").reduce((s,t)=>s+t.mrr,0)*12).toLocaleString()}`} color={C.accent} />
              <KpiCard icon="📊" label="ARPU" value={`$${Math.round(TENANTS.filter(t=>t.status!=="churned").reduce((s,t)=>s+t.mrr,0)/TENANTS.filter(t=>t.status!=="churned").length)}`} sub="per tenant/month" color={C.purple} />
              <KpiCard icon="🔄" label="Churn Rate" value="2.1%" sub="1 churned / 47 total" color={C.warning} />
              <KpiCard icon="⏰" label="LTV" value="$13,400" sub="avg 27-month retention" color={C.teal} />
              <KpiCard icon="🎯" label="CAC" value="$1,200" sub="LTV:CAC = 11.2x" color={C.orange} />
            </div>
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "20px 22px" }}>
              <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 14 }}>Revenue by Plan</div>
              {[
                { plan: "Starter", count: TENANTS.filter(t=>t.plan==="starter"&&t.status!=="churned").length, mrr: TENANTS.filter(t=>t.plan==="starter"&&t.status!=="churned").reduce((s,t)=>s+t.mrr,0), color: C.muted, pct: 0 },
                { plan: "Growth", count: TENANTS.filter(t=>t.plan==="growth"&&t.status!=="churned").length, mrr: TENANTS.filter(t=>t.plan==="growth"&&t.status!=="churned").reduce((s,t)=>s+t.mrr,0), color: C.accent, pct: 0 },
                { plan: "Enterprise", count: TENANTS.filter(t=>t.plan==="enterprise"&&t.status!=="churned").length, mrr: TENANTS.filter(t=>t.plan==="enterprise"&&t.status!=="churned").reduce((s,t)=>s+t.mrr,0), color: C.purple, pct: 0 },
              ].map(r => { r.pct = Math.round(r.mrr / TENANTS.filter(t=>t.status!=="churned").reduce((s,t)=>s+t.mrr,0) * 100); return r; }).map((r, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
                  <div style={{ width: 80, fontSize: 13, fontWeight: 700, color: r.color }}>{r.plan}</div>
                  <div style={{ width: 50, fontSize: 12, color: C.muted }}>{r.count} accts</div>
                  <div style={{ flex: 1, height: 24, background: "#F3F4F6", borderRadius: 6, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${r.pct}%`, background: `${r.color}25`, borderRadius: 6, display: "flex", alignItems: "center", paddingLeft: 8, fontSize: 11, fontWeight: 700, color: r.color }}>{r.pct}%</div>
                  </div>
                  <div style={{ width: 80, textAlign: "right", fontSize: 14, fontWeight: 800, fontFamily: "'JetBrains Mono'" }}>${r.mrr.toLocaleString()}</div>
                </div>
              ))}
            </div>
          </>
        )}

        {adminTab === "infra" && (
          <>
            <div style={{ fontSize: 26, fontWeight: 900, marginBottom: 20 }}>Infrastructure & Compliance</div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              {[
                { title: "🏗️ Architecture (Replit Deploy)", items: [
                  ["Frontend", "Next.js 14 on Replit Deployments"],
                  ["Database", "Supabase PostgreSQL (multi-tenant RLS)"],
                  ["Auth", "Supabase Auth + Row Level Security"],
                  ["AI Engine", "Anthropic Claude API (Sonnet 4.5)"],
                  ["SMS/Voice", "Twilio (SMS, Voice, AI receptionist)"],
                  ["Payments", "Stripe (subscriptions + patient payments)"],
                  ["Email", "SendGrid (transactional + marketing)"],
                  ["Claims EDI", "DentalXChange / Tesia clearinghouse API"],
                  ["File Storage", "Supabase Storage (HIPAA bucket)"],
                  ["CDN", "Cloudflare (global edge)"],
                ]},
                { title: "🔒 HIPAA & Security", items: [
                  ["Encryption at Rest", "AES-256 ✓"],
                  ["Encryption in Transit", "TLS 1.3 ✓"],
                  ["BAA", "Signed with all sub-processors ✓"],
                  ["Audit Logging", "All PHI access logged ✓"],
                  ["Access Controls", "RBAC + Row Level Security ✓"],
                  ["Backup", "Daily encrypted backups, 30-day retention ✓"],
                  ["Penetration Testing", "Annual (last: Dec 2025) ✓"],
                  ["SOC 2 Type II", "In progress (target: Q2 2026)"],
                  ["Uptime SLA", "99.9% (current: 99.97%)"],
                  ["Incident Response", "< 1 hour for P1 ✓"],
                ]},
                { title: "📊 Database Schema (Multi-Tenant)", items: [
                  ["organizations", "Tenant accounts, plan, settings"],
                  ["users", "Auth, roles, permissions per org"],
                  ["patients", "Demographics, medical hx, alerts"],
                  ["appointments", "Scheduling, providers, status"],
                  ["treatment_plans", "CDT items, fees, insurance est."],
                  ["ledger", "Charges, payments, adjustments"],
                  ["insurance_claims", "EDI submission, tracking, ERA"],
                  ["communications", "SMS, calls, emails, web forms"],
                  ["dental_charts", "Tooth-level conditions, history"],
                  ["ai_automations", "Workflows, triggers, sequences"],
                ]},
                { title: "🔌 API Endpoints", items: [
                  ["POST /api/patients", "Create / update patient"],
                  ["GET /api/schedule", "Get appointments by date/provider"],
                  ["POST /api/claims/submit", "Submit insurance claim (EDI)"],
                  ["POST /api/sms/send", "Send SMS via Twilio"],
                  ["POST /api/ai/phone", "AI receptionist webhook"],
                  ["GET /api/analytics", "Dashboard KPI data"],
                  ["POST /api/billing/charge", "Process patient payment"],
                  ["POST /api/treatment-plans", "Create treatment plan"],
                  ["GET /api/insurance/verify", "Real-time eligibility check"],
                  ["POST /api/webhooks/stripe", "Subscription events"],
                ]},
              ].map((section, i) => (
                <div key={i} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "20px 22px" }}>
                  <div style={{ fontSize: 14, fontWeight: 800, marginBottom: 14 }}>{section.title}</div>
                  {section.items.map(([l, v], j) => (
                    <div key={j} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: j < section.items.length - 1 ? `1px solid ${C.border}` : "none", gap: 12 }}>
                      <span style={{ fontSize: 12, color: C.muted, fontFamily: "'JetBrains Mono'", flexShrink: 0 }}>{l}</span>
                      <span style={{ fontSize: 12, fontWeight: 600, textAlign: "right" }}>{v}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
      <style>{`*{box-sizing:border-box;margin:0;padding:0} button{transition:0.15s} button:hover{filter:brightness(0.95)}`}</style>
    </div>
  );

  return null;
}
