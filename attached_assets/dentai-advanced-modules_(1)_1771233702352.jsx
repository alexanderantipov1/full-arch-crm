import { useState, useEffect } from "react";

// ═══════════════════════════════════════════════════════════════
// DENTAI ADVANCED MODULES — 21 Complete Clinical & Business Modules
// ═══════════════════════════════════════════════════════════════

const C = { bg: "#F6F7F9", card: "#FFFFFF", border: "#E5E7EB", text: "#111827", muted: "#6B7280", accent: "#2563EB", success: "#059669", warning: "#D97706", danger: "#DC2626", purple: "#7C3AED", pink: "#DB2777", cyan: "#0891B2", teal: "#0D9488", orange: "#EA580C", indigo: "#4F46E5", sidebar: "#0F172A", sideText: "#94A3B8", sideActive: "#3B82F6" };

// ═══ SHARED COMPONENTS ═══
const Badge = ({ children, color = C.accent, solid }) => <span style={{ background: solid ? color : `${color}14`, color: solid ? "#FFF" : color, padding: "2px 9px", borderRadius: 6, fontSize: 10, fontWeight: 700, letterSpacing: 0.3, textTransform: "uppercase", whiteSpace: "nowrap" }}>{children}</span>;
const Pbar = ({ v, color = C.accent, h = 6 }) => <div style={{ height: h, background: "#F3F4F6", borderRadius: h, overflow: "hidden", flex: 1 }}><div style={{ height: "100%", width: `${Math.min(v,100)}%`, background: color, borderRadius: h, transition: "width 0.6s" }}/></div>;
const Kpi = ({ label, value, sub, color = C.accent, icon }) => (
  <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "14px 16px", position: "relative", overflow: "hidden" }}>
    <div style={{ position: "absolute", top: -8, right: -8, width: 50, height: 50, background: `${color}06`, borderRadius: "50%" }} />
    <div style={{ fontSize: 10, color: C.muted, letterSpacing: 1.2, textTransform: "uppercase", fontWeight: 600, marginBottom: 3 }}>{icon} {label}</div>
    <div style={{ fontSize: 22, fontWeight: 900 }}>{value}</div>
    {sub && <div style={{ fontSize: 11, color, fontWeight: 600, marginTop: 1 }}>{sub}</div>}
  </div>
);
const Table = ({ headers, rows, onRowClick }) => (
  <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${headers.length}, 1fr)`, padding: "9px 16px", borderBottom: `2px solid ${C.border}` }}>
      {headers.map(h => <div key={h} style={{ fontSize: 10, fontWeight: 700, color: C.muted, letterSpacing: 0.8, textTransform: "uppercase" }}>{h}</div>)}
    </div>
    {rows.map((row, i) => (
      <div key={i} onClick={() => onRowClick?.(i)} style={{ display: "grid", gridTemplateColumns: `repeat(${headers.length}, 1fr)`, padding: "10px 16px", borderBottom: `1px solid ${C.border}`, alignItems: "center", cursor: onRowClick ? "pointer" : "default", transition: "0.1s" }} onMouseOver={e => { if (onRowClick) e.currentTarget.style.background = "#F8FAFC"; }} onMouseOut={e => e.currentTarget.style.background = "transparent"}>
        {row.map((cell, j) => <div key={j} style={{ fontSize: 12 }}>{cell}</div>)}
      </div>
    ))}
  </div>
);
const Section = ({ title, sub, action, actionLabel, children }) => (
  <div style={{ marginBottom: 20 }}>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
      <div><div style={{ fontSize: 22, fontWeight: 900 }}>{title}</div>{sub && <div style={{ fontSize: 13, color: C.muted }}>{sub}</div>}</div>
      {action && <button onClick={action} style={{ background: C.accent, color: "#FFF", border: "none", borderRadius: 9, padding: "8px 18px", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>{actionLabel || "+ New"}</button>}
    </div>
    {children}
  </div>
);

// ═══ MODULE DEFINITIONS ═══
const MODULES = [
  { id: "intake", label: "Patient Intake", icon: "📝", group: "Clinical" },
  { id: "perio", label: "Perio Charting", icon: "📊", group: "Clinical" },
  { id: "soap", label: "Clinical Notes", icon: "📄", group: "Clinical" },
  { id: "imaging", label: "Imaging Viewer", icon: "🔬", group: "Clinical" },
  { id: "consent", label: "Consent Forms", icon: "✍️", group: "Clinical" },
  { id: "erx", label: "E-Prescribing", icon: "💊", group: "Clinical" },
  { id: "ortho", label: "Ortho Tracker", icon: "🦷", group: "Specialty" },
  { id: "implant", label: "Implant Tracker", icon: "🔩", group: "Specialty" },
  { id: "lab", label: "Lab Cases", icon: "🔬", group: "Specialty" },
  { id: "referral", label: "Referrals", icon: "🔄", group: "Specialty" },
  { id: "inventory", label: "Inventory", icon: "📦", group: "Operations" },
  { id: "hr", label: "HR & Time Clock", icon: "👥", group: "Operations" },
  { id: "sterilization", label: "Sterilization", icon: "🧪", group: "Operations" },
  { id: "financial", label: "Financial Center", icon: "💰", group: "Business" },
  { id: "financing", label: "Patient Financing", icon: "💳", group: "Business" },
  { id: "marketing", label: "Marketing Suite", icon: "📣", group: "Business" },
  { id: "nps", label: "Patient Satisfaction", icon: "⭐", group: "Business" },
  { id: "multiloc", label: "Multi-Location", icon: "🏢", group: "Business" },
  { id: "telehealth", label: "Teledentistry", icon: "📹", group: "AI Modules" },
  { id: "aitreatment", label: "AI Tx Planning", icon: "🧠", group: "AI Modules" },
  { id: "aiclinical", label: "AI Decision Support", icon: "🤖", group: "AI Modules" },
];

// ═══ MAIN APP ═══
export default function DentAIAdvanced() {
  const [tab, setTab] = useState("intake");

  const groups = [...new Set(MODULES.map(m => m.group))];

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: C.bg, fontFamily: "'Outfit', 'DM Sans', system-ui", color: C.text }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet" />

      {/* SIDEBAR */}
      <div style={{ width: 210, background: C.sidebar, padding: "14px 8px", display: "flex", flexDirection: "column", flexShrink: 0, overflowY: "auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 10px", marginBottom: 14 }}>
          <div style={{ width: 30, height: 30, borderRadius: 8, background: "linear-gradient(135deg, #3B82F6, #06B6D4)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>🦷</div>
          <div><div style={{ fontSize: 14, fontWeight: 900, color: "#F8FAFC" }}>DentAI</div><div style={{ fontSize: 8, color: C.sideText, letterSpacing: 2.5, textTransform: "uppercase" }}>Advanced Modules</div></div>
        </div>
        {groups.map(g => (
          <div key={g}>
            <div style={{ fontSize: 9, color: "#475569", letterSpacing: 2, textTransform: "uppercase", fontWeight: 700, padding: "10px 12px 4px" }}>{g}</div>
            {MODULES.filter(m => m.group === g).map(m => (
              <button key={m.id} onClick={() => setTab(m.id)} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 10px", borderRadius: 7, border: "none", background: tab === m.id ? `${C.sideActive}18` : "transparent", cursor: "pointer", width: "100%", transition: "0.1s" }}>
                <span style={{ fontSize: 13 }}>{m.icon}</span>
                <span style={{ fontSize: 11, fontWeight: tab === m.id ? 700 : 500, color: tab === m.id ? C.sideActive : C.sideText }}>{m.label}</span>
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* MAIN */}
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px", minWidth: 0 }}>

        {/* ═══ 1. DIGITAL INTAKE & PATIENT PORTAL ═══ */}
        {tab === "intake" && (
          <Section title="📝 Digital Intake & Patient Portal" sub="Online forms, e-signatures, insurance card capture, patient self-service">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="📋" label="Forms Submitted Today" value="12" sub="8 new patients" color={C.accent} />
              <Kpi icon="✍️" label="E-Signatures" value="34" sub="100% HIPAA compliant" color={C.success} />
              <Kpi icon="📸" label="Insurance Cards Captured" value="11" sub="Auto-verified" color={C.purple} />
              <Kpi icon="⏱️" label="Avg Intake Time" value="4.2 min" sub="↓ from 18 min paper" color={C.teal} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 16 }}>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 12 }}>📋 Active Intake Forms</div>
                {[
                  { name: "New Patient Registration", fields: 24, completion: "98%", status: "active" },
                  { name: "Medical History Questionnaire", fields: 42, completion: "96%", status: "active" },
                  { name: "HIPAA Privacy Acknowledgment", fields: 3, completion: "100%", status: "active" },
                  { name: "Financial Policy Agreement", fields: 5, completion: "99%", status: "active" },
                  { name: "Insurance Card Upload", fields: 2, completion: "94%", status: "active" },
                  { name: "Consent for Treatment (General)", fields: 4, completion: "100%", status: "active" },
                  { name: "Orthodontic Consent & Agreement", fields: 12, completion: "97%", status: "active" },
                  { name: "Implant Surgical Consent", fields: 8, completion: "95%", status: "active" },
                ].map((f, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0", borderBottom: i < 7 ? `1px solid ${C.border}` : "none" }}>
                    <div><div style={{ fontSize: 12, fontWeight: 600 }}>{f.name}</div><div style={{ fontSize: 10, color: C.muted }}>{f.fields} fields</div></div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 11, color: C.success, fontWeight: 600 }}>{f.completion}</span>
                      <Badge color={C.success}>Active</Badge>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 12 }}>🌐 Patient Portal Features</div>
                {[
                  { feat: "View & manage appointments", icon: "📅", status: "live" },
                  { feat: "Pay bills & view statements", icon: "💳", status: "live" },
                  { feat: "Message practice securely", icon: "💬", status: "live" },
                  { feat: "View treatment plans & accept", icon: "📋", status: "live" },
                  { feat: "Download receipts & EOBs", icon: "📄", status: "live" },
                  { feat: "Update medical history", icon: "🏥", status: "live" },
                  { feat: "Upload insurance card photos", icon: "📸", status: "live" },
                  { feat: "Request prescription refills", icon: "💊", status: "live" },
                  { feat: "View X-rays & treatment photos", icon: "🔬", status: "beta" },
                  { feat: "Book teledentistry consult", icon: "📹", status: "beta" },
                ].map((f, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", borderBottom: i < 9 ? `1px solid ${C.border}` : "none" }}>
                    <span style={{ fontSize: 14 }}>{f.icon}</span>
                    <span style={{ fontSize: 12, flex: 1 }}>{f.feat}</span>
                    <Badge color={f.status === "live" ? C.success : C.warning}>{f.status}</Badge>
                  </div>
                ))}
              </div>
            </div>
            <div style={{ background: `${C.accent}05`, border: `1px solid ${C.accent}15`, borderRadius: 14, padding: "16px 20px" }}>
              <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 6 }}>🤖 AI Intake Automation Flow</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 10, fontSize: 12, color: "#4B5563" }}>
                <div><strong style={{ color: C.accent }}>1. Pre-Visit (48hr):</strong> SMS sent with intake link → patient completes forms on phone → insurance card auto-OCR extracts plan info</div>
                <div><strong style={{ color: C.purple }}>2. Auto-Verify:</strong> Insurance eligibility checked instantly → benefits breakdown populated → copay/deductible calculated → treatment estimates ready</div>
                <div><strong style={{ color: C.success }}>3. Day-Of:</strong> Patient checks in via QR code → med hx flagged for provider review → allergies/alerts populated in chart → zero clipboard time</div>
                <div><strong style={{ color: C.orange }}>4. Post-Visit:</strong> Portal access activated → treatment plan viewable → payment link sent → next appointment booking → recall scheduled</div>
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 2. PERIO CHARTING ═══ */}
        {tab === "perio" && (() => {
          const teeth = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16];
          const lowerTeeth = [32,31,30,29,28,27,26,25,24,23,22,21,20,19,18,17];
          const probing = { 3: [3,2,3,4,5,3], 8: [2,2,2,2,3,2], 14: [5,6,4,4,5,6], 19: [4,3,3,3,4,4], 30: [6,7,5,5,6,7] };
          return (
            <Section title="📊 Periodontal Charting" sub="6-point probing, BOP, recession, furcation, mobility — full perio record">
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10, marginBottom: 16 }}>
                <Kpi icon="📏" label="Avg Probing Depth" value="3.2mm" sub="Previous: 3.8mm ↓" color={C.success} />
                <Kpi icon="🩸" label="BOP Sites" value="18%" sub="Target: <10%" color={C.danger} />
                <Kpi icon="📉" label="Sites >4mm" value="24" sub="Previous: 31 ↓" color={C.warning} />
                <Kpi icon="🦷" label="Perio Diagnosis" value="Stage III" sub="Grade B — generalized" color={C.purple} />
              </div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "20px 24px", marginBottom: 16 }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 14 }}>Probing Chart — Margaret Sullivan — 2026-02-11</div>
                {[{ label: "Facial — Upper", teeth, side: "F" }, { label: "Lingual — Upper", teeth, side: "L" }, { label: "Facial — Lower", teeth: lowerTeeth, side: "F" }, { label: "Lingual — Lower", teeth: lowerTeeth, side: "L" }].map((row, ri) => (
                  <div key={ri} style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 10, color: C.muted, fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase", marginBottom: 4 }}>{row.label}</div>
                    <div style={{ display: "flex", gap: 2 }}>
                      {row.teeth.map(t => {
                        const p = probing[t] || [2,2,2,2,2,2];
                        const vals = row.side === "F" ? p.slice(0,3) : p.slice(3,6);
                        return (
                          <div key={t} style={{ flex: 1, textAlign: "center" }}>
                            <div style={{ display: "flex", justifyContent: "center", gap: 1, marginBottom: 2 }}>
                              {vals.map((v, vi) => (
                                <div key={vi} style={{ width: 14, height: 18, borderRadius: 3, background: v >= 6 ? `${C.danger}20` : v >= 4 ? `${C.warning}20` : "#F3F4F6", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 9, fontWeight: 800, color: v >= 6 ? C.danger : v >= 4 ? C.warning : C.success, fontFamily: "'JetBrains Mono'" }}>{v}</div>
                              ))}
                            </div>
                            <div style={{ fontSize: 8, fontWeight: 700, color: C.muted }}>{t}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
                <div style={{ display: "flex", gap: 16, paddingTop: 10, borderTop: `1px solid ${C.border}`, marginTop: 8 }}>
                  {[["1-3mm", C.success, "Healthy"], ["4-5mm", C.warning, "Moderate"], ["6mm+", C.danger, "Severe"]].map(([r, c, l]) => (
                    <div key={r} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                      <div style={{ width: 12, height: 12, borderRadius: 3, background: `${c}20`, border: `1px solid ${c}` }} />
                      <span style={{ fontSize: 10, color: C.muted }}>{r} — {l}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div style={{ background: `${C.purple}06`, border: `1px solid ${C.purple}15`, borderRadius: 12, padding: "14px 18px" }}>
                <div style={{ fontSize: 12, fontWeight: 800, color: C.purple, marginBottom: 4 }}>🤖 AI Perio Assessment</div>
                <div style={{ fontSize: 12, color: "#4B5563", lineHeight: 1.6 }}>Diagnosis: <strong>Periodontitis Stage III, Grade B, Generalized</strong>. 24 sites ≥4mm (improved from 31). BOP at 18% (target &lt;10%). Recommend: continued SRP remaining quadrants, 3-month perio maintenance intervals, consider localized antibiotic therapy (Arestin) for sites ≥5mm. Insurance narrative auto-generated for D4341/D4342 with clinical justification.</div>
              </div>
            </Section>
          );
        })()}

        {/* ═══ 3. CLINICAL NOTES / SOAP ═══ */}
        {tab === "soap" && (
          <Section title="📄 Clinical Notes — AI-Assisted SOAP" sub="Voice-to-text, AI expansion, CDT auto-coding, template library">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 16 }}>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>Today's Notes</div>
                {[
                  { patient: "Margaret Sullivan", proc: "Implant Follow-up #14", time: "8:00 AM", status: "signed", provider: "Dr. Chen" },
                  { patient: "Robert Kim", proc: "Implant Consult + CBCT", time: "9:00 AM", status: "draft", provider: "Dr. Chen" },
                  { patient: "James Okafor", proc: "Perio Maintenance", time: "8:00 AM", status: "signed", provider: "Dr. Park" },
                  { patient: "Diana Patel", proc: "Invisalign Check #8", time: "9:00 AM", status: "pending", provider: "Dr. Park" },
                ].map((n, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 0", borderBottom: i < 3 ? `1px solid ${C.border}` : "none" }}>
                    <div><div style={{ fontSize: 12, fontWeight: 700 }}>{n.patient}</div><div style={{ fontSize: 10, color: C.muted }}>{n.proc} · {n.time} · {n.provider}</div></div>
                    <Badge color={n.status === "signed" ? C.success : n.status === "draft" ? C.warning : C.muted}>{n.status}</Badge>
                  </div>
                ))}
              </div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>📋 SOAP Note — Margaret Sullivan</div>
                {[
                  { label: "S — Subjective", text: "Patient reports mild sensitivity at implant site #14 when chewing. No spontaneous pain. Ibuprofen provides relief. Denies numbness, swelling, or drainage.", color: C.accent },
                  { label: "O — Objective", text: "Implant #14 stable, no mobility. Tissue healthy, pink, stippled. No suppuration. Probing: 3mm circumferential. CBCT confirms osseointegration progressing normally at 6 weeks. Occlusion checked — no premature contacts.", color: C.teal },
                  { label: "A — Assessment", text: "Implant #14 healing within normal parameters. Sensitivity consistent with early loading adaptation. No signs of peri-implantitis or failure.", color: C.purple },
                  { label: "P — Plan", text: "Continue soft diet for 2 more weeks. Return in 8 weeks for final impression (D6058 abutment + D6065 implant crown). Continue home care instructions. Patient educated and consented to next phase.", color: C.orange },
                ].map((s, i) => (
                  <div key={i} style={{ marginBottom: 10, padding: "10px 12px", background: `${s.color}05`, borderLeft: `3px solid ${s.color}30`, borderRadius: "0 8px 8px 0" }}>
                    <div style={{ fontSize: 10, fontWeight: 800, color: s.color, letterSpacing: 1, textTransform: "uppercase", marginBottom: 3 }}>{s.label}</div>
                    <div style={{ fontSize: 12, color: "#4B5563", lineHeight: 1.5 }}>{s.text}</div>
                  </div>
                ))}
                <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
                  <button style={{ background: C.success, color: "#FFF", border: "none", borderRadius: 8, padding: "6px 14px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>✓ Sign Note</button>
                  <button style={{ background: `${C.accent}10`, color: C.accent, border: `1px solid ${C.accent}20`, borderRadius: 8, padding: "6px 14px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>🎤 Voice-to-Text</button>
                  <button style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: "6px 14px", fontSize: 11, fontWeight: 600, cursor: "pointer" }}>🤖 AI Expand</button>
                </div>
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 4. IMAGING VIEWER ═══ */}
        {tab === "imaging" && (
          <Section title="🔬 Digital Imaging Viewer" sub="X-ray viewer, CBCT, intraoral photos, AI pathology detection">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="📸" label="Images Today" value="28" sub="12 periapical, 8 CBCT, 8 photos" color={C.accent} />
              <Kpi icon="🤖" label="AI Detections" value="6" sub="3 caries, 2 perio, 1 periapical" color={C.danger} />
              <Kpi icon="💾" label="Storage Used" value="124 GB" sub="of 500 GB" color={C.muted} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14, marginBottom: 16 }}>
              <div style={{ background: "#1a1a2e", borderRadius: 14, padding: "20px", minHeight: 300, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                <div style={{ width: "100%", height: 200, background: "#0a0a1a", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid #333", marginBottom: 12, position: "relative" }}>
                  <div style={{ color: "#666", fontSize: 40 }}>🦷</div>
                  <div style={{ position: "absolute", top: 10, left: 10, display: "flex", gap: 4 }}>
                    <Badge color={C.accent} solid>PA #14</Badge>
                    <Badge color={C.success} solid>2026-02-11</Badge>
                  </div>
                  <div style={{ position: "absolute", bottom: 10, right: 10 }}>
                    <Badge color={C.danger} solid>🤖 AI: Radiolucency detected</Badge>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  {["Brightness", "Contrast", "Invert", "Zoom", "Measure", "Annotate", "Compare", "AI Detect"].map(t => (
                    <button key={t} style={{ background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 6, padding: "5px 10px", color: "#94A3B8", fontSize: 10, fontWeight: 600, cursor: "pointer" }}>{t}</button>
                  ))}
                </div>
              </div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "16px 18px" }}>
                <div style={{ fontSize: 12, fontWeight: 800, marginBottom: 10 }}>🤖 AI Pathology Detection</div>
                {[
                  { finding: "Caries — Tooth #14 mesial", confidence: "94%", severity: "moderate", color: C.danger },
                  { finding: "Caries — Tooth #3 distal", confidence: "87%", severity: "early", color: C.warning },
                  { finding: "Caries — Tooth #19 occlusal", confidence: "91%", severity: "moderate", color: C.danger },
                  { finding: "Bone loss — #14 mesial", confidence: "88%", severity: "moderate", color: C.purple },
                  { finding: "Bone loss — #30 distal", confidence: "82%", severity: "severe", color: C.danger },
                  { finding: "Periapical radiolucency — #31", confidence: "79%", severity: "needs eval", color: C.orange },
                ].map((f, i) => (
                  <div key={i} style={{ padding: "6px 0", borderBottom: i < 5 ? `1px solid ${C.border}` : "none" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontSize: 11, fontWeight: 600 }}>{f.finding}</span>
                      <Badge color={f.color}>{f.severity}</Badge>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
                      <Pbar v={parseInt(f.confidence)} color={f.color} h={3} />
                      <span style={{ fontSize: 10, color: f.color, fontWeight: 700 }}>{f.confidence}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 5. CONSENT FORMS ═══ */}
        {tab === "consent" && (
          <Section title="✍️ Consent Form Builder" sub="Digital consents with e-signature, procedure-specific templates, legally defensible">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
              {[
                { name: "General Treatment Consent", sigs: 1240, fields: 6, procedures: "All", status: "active" },
                { name: "Implant Surgical Consent", sigs: 342, fields: 12, procedures: "D6010, D6040, D6050", status: "active" },
                { name: "Extraction Consent", sigs: 567, fields: 8, procedures: "D7140, D7210, D7220, D7230", status: "active" },
                { name: "Orthodontic Agreement", sigs: 189, fields: 15, procedures: "D8010-D8090", status: "active" },
                { name: "Endodontic Consent", sigs: 234, fields: 10, procedures: "D3310-D3330", status: "active" },
                { name: "Sedation/Anesthesia Consent", sigs: 156, fields: 14, procedures: "D9220-D9243", status: "active" },
                { name: "HIPAA Privacy Notice", sigs: 3105, fields: 3, procedures: "All patients", status: "active" },
                { name: "Financial Responsibility Agreement", sigs: 3105, fields: 5, procedures: "All patients", status: "active" },
                { name: "Whitening Consent", sigs: 98, fields: 6, procedures: "D9972-D9975", status: "active" },
                { name: "Periodontal Surgery Consent", sigs: 78, fields: 11, procedures: "D4210-D4274", status: "active" },
              ].map((f, i) => (
                <div key={i} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: "14px 16px" }}>
                  <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 4 }}>{f.name}</div>
                  <div style={{ fontSize: 11, color: C.muted, marginBottom: 8 }}>{f.fields} fields · {f.procedures} · {f.sigs.toLocaleString()} signatures collected</div>
                  <div style={{ display: "flex", gap: 4 }}>
                    <Badge color={C.success}>Active</Badge>
                    <Badge color={C.accent}>E-Signature</Badge>
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* ═══ 6. E-PRESCRIBING ═══ */}
        {tab === "erx" && (
          <Section title="💊 E-Prescribing (eRx)" sub="EPCS-compliant, drug interaction checking, pharmacy integration">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="💊" label="Rx Sent Today" value="8" sub="6 antibiotics, 2 analgesics" color={C.accent} />
              <Kpi icon="⚠️" label="Interactions Flagged" value="2" sub="Both resolved" color={C.danger} />
              <Kpi icon="🏪" label="Pharmacies Connected" value="47" sub="CVS, Walgreens, Rite Aid +" color={C.success} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>Recent Prescriptions</div>
                {[
                  { patient: "Margaret Sullivan", drug: "Amoxicillin 500mg", sig: "#21 — 1 cap TID x 7 days", pharmacy: "CVS Auburn", status: "sent", alert: "⚠️ Penicillin allergy — BLOCKED" },
                  { patient: "Robert Kim", drug: "Ibuprofen 600mg", sig: "#20 — 1 tab Q6H PRN pain", pharmacy: "Walgreens Roseville", status: "sent", alert: "" },
                  { patient: "Michael Torres", drug: "Clindamycin 300mg", sig: "#28 — 1 cap QID x 7 days", pharmacy: "CVS Auburn", status: "sent", alert: "⚠️ Check Warfarin interaction" },
                  { patient: "James Okafor", drug: "Chlorhexidine 0.12%", sig: "#1 — Rinse BID x 14 days", pharmacy: "Rite Aid Folsom", status: "sent", alert: "" },
                ].map((rx, i) => (
                  <div key={i} style={{ padding: "8px 0", borderBottom: i < 3 ? `1px solid ${C.border}` : "none" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <div style={{ fontSize: 12, fontWeight: 700 }}>{rx.patient}</div>
                      <Badge color={C.success}>Sent</Badge>
                    </div>
                    <div style={{ fontSize: 11, color: C.muted }}>{rx.drug} — {rx.sig}</div>
                    <div style={{ fontSize: 10, color: C.muted }}>{rx.pharmacy}</div>
                    {rx.alert && <div style={{ fontSize: 10, color: C.danger, fontWeight: 700, marginTop: 2 }}>{rx.alert}</div>}
                  </div>
                ))}
              </div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>🤖 AI Drug Interaction Engine</div>
                <div style={{ background: `${C.danger}06`, border: `1px solid ${C.danger}18`, borderRadius: 10, padding: "12px 14px", marginBottom: 10 }}>
                  <div style={{ fontSize: 11, fontWeight: 800, color: C.danger }}>⛔ BLOCKED: Margaret Sullivan — Penicillin Allergy</div>
                  <div style={{ fontSize: 11, color: "#4B5563", marginTop: 4 }}>Amoxicillin is a penicillin-class antibiotic. Patient has documented penicillin allergy. AI auto-substituted: <strong>Clindamycin 300mg QID x 7d</strong> or <strong>Azithromycin 500mg Day 1 then 250mg x 4d</strong>.</div>
                </div>
                <div style={{ background: `${C.warning}06`, border: `1px solid ${C.warning}18`, borderRadius: 10, padding: "12px 14px" }}>
                  <div style={{ fontSize: 11, fontWeight: 800, color: C.warning }}>⚠️ WARNING: Michael Torres — Warfarin + Clindamycin</div>
                  <div style={{ fontSize: 11, color: "#4B5563", marginTop: 4 }}>Clindamycin may increase INR in patients on Warfarin. Recommend: notify patient's cardiologist, consider INR check at Day 3-5, reduce Warfarin dose if INR &gt;3.5. AI flagged and documented.</div>
                </div>
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 7. ORTHO TRACKER ═══ */}
        {tab === "ortho" && (
          <Section title="🦷 Orthodontic Tracker" sub="Invisalign tray tracking, bracket charting, progress photos, compliance">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="🦷" label="Active Ortho Cases" value="34" sub="28 Invisalign, 6 brackets" color={C.purple} />
              <Kpi icon="📅" label="Check-ins This Week" value="12" color={C.accent} />
              <Kpi icon="✅" label="On-Track Rate" value="91%" sub="3 patients behind" color={C.success} />
              <Kpi icon="💰" label="Ortho Revenue MTD" value="$48,200" color={C.teal} />
            </div>
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: `1px solid ${C.border}`, fontSize: 13, fontWeight: 800 }}>Active Invisalign Cases</div>
              {[
                { patient: "Diana Patel", trays: "8/22", start: "2026-01-15", est_end: "2026-08-20", compliance: "95%", status: "on_track", next: "2026-02-20" },
                { patient: "Emma Rodriguez", trays: "14/30", start: "2025-09-01", est_end: "2026-06-15", compliance: "88%", status: "on_track", next: "2026-02-25" },
                { patient: "Tyler Nguyen", trays: "3/18", start: "2026-02-01", est_end: "2026-10-01", compliance: "100%", status: "on_track", next: "2026-03-01" },
                { patient: "Sophia Adams", trays: "18/24", start: "2025-06-10", est_end: "2026-03-30", compliance: "72%", status: "behind", next: "2026-02-14" },
              ].map((c, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "1.5fr 80px 1fr 80px 80px 80px", padding: "10px 16px", borderBottom: `1px solid ${C.border}`, alignItems: "center" }}>
                  <div style={{ fontSize: 13, fontWeight: 700 }}>{c.patient}</div>
                  <div style={{ fontWeight: 800, color: C.purple, fontFamily: "'JetBrains Mono'", fontSize: 13 }}>{c.trays}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}><Pbar v={parseInt(c.trays) / parseInt(c.trays.split("/")[1]) * 100} color={C.purple} h={4} /></div>
                  <div style={{ fontSize: 11, fontWeight: 600, color: parseInt(c.compliance) >= 90 ? C.success : C.warning }}>{c.compliance}</div>
                  <Badge color={c.status === "on_track" ? C.success : C.warning}>{c.status === "on_track" ? "On Track" : "Behind"}</Badge>
                  <div style={{ fontSize: 11, color: C.muted }}>{c.next}</div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* ═══ 8. IMPLANT TRACKER ═══ */}
        {tab === "implant" && (
          <Section title="🔩 Implant Case Tracker" sub="Stage-based workflow from consult through final restoration">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="🔩" label="Active Implant Cases" value="18" sub="6 healing, 8 restoring, 4 new" color={C.accent} />
              <Kpi icon="💰" label="Implant Revenue MTD" value="$87,400" color={C.success} />
              <Kpi icon="✅" label="Success Rate" value="98.4%" sub="1 complication in 62 cases" color={C.teal} />
            </div>
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
              <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 14 }}>Implant Pipeline</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
                {[
                  { stage: "Consult", icon: "🎯", count: 4, patients: ["Robert Kim #14", "Sarah Chen #30", "Lisa Park #8,9", "Tom Davis #19"], color: C.accent },
                  { stage: "Surgery", icon: "🔪", count: 3, patients: ["Michael Torres #17", "John Wu #3", "Amy Lee #14,15"], color: C.purple },
                  { stage: "Healing", icon: "⏳", count: 6, patients: ["Margaret Sullivan #14", "David Park #5", "Karen Brown #18", "Pete Hall #30", "Raj Patel #3", "Nina Fox #10"], color: C.warning },
                  { stage: "Impression", icon: "📸", count: 3, patients: ["Jim Lee #14", "Maria Garcia #19", "Steve Chen #3"], color: C.teal },
                  { stage: "Restoration", icon: "👑", count: 2, patients: ["Emily Watson #12", "Frank Morris #8"], color: C.success },
                ].map(s => (
                  <div key={s.stage} style={{ background: `${s.color}05`, border: `1px solid ${s.color}15`, borderRadius: 12, padding: "12px 14px" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                      <span style={{ fontSize: 12, fontWeight: 800, color: s.color }}>{s.icon} {s.stage}</span>
                      <span style={{ fontSize: 18, fontWeight: 900, color: s.color }}>{s.count}</span>
                    </div>
                    {s.patients.map((p, i) => <div key={i} style={{ fontSize: 11, color: "#4B5563", padding: "3px 0", borderBottom: i < s.patients.length - 1 ? `1px solid ${C.border}` : "none" }}>{p}</div>)}
                  </div>
                ))}
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 9. LAB CASES ═══ */}
        {tab === "lab" && (
          <Section title="🔬 Lab Case Manager" sub="Track every case from scan to delivery — crowns, bridges, aligners, implant components">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="📦" label="Active Lab Cases" value="23" sub="8 overdue" color={C.accent} />
              <Kpi icon="💰" label="Lab Costs MTD" value="$14,200" sub="7.1% of production" color={C.warning} />
              <Kpi icon="⏱️" label="Avg Turnaround" value="8.2 days" sub="Target: 7 days" color={C.orange} />
            </div>
            <Table headers={["Patient", "Case Type", "Lab", "Shade", "Sent", "Due", "Status"]} rows={[
              [<span style={{ fontWeight: 700 }}>Margaret Sullivan</span>, "Crown PFM #3", "Burbank Dental Lab", "A2", "Jan 28", "Feb 8", <Badge color={C.danger}>Overdue</Badge>],
              [<span style={{ fontWeight: 700 }}>Emily Watson</span>, "Crown e.max #12", "Glidewell", "B1", "Feb 5", "Feb 14", <Badge color={C.warning}>In Progress</Badge>],
              [<span style={{ fontWeight: 700 }}>Robert Kim</span>, "Implant Abutment #14", "Straumann Lab", "—", "Feb 10", "Feb 24", <Badge color={C.accent}>Submitted</Badge>],
              [<span style={{ fontWeight: 700 }}>Diana Patel</span>, "Invisalign Trays 9-12", "Align Technology", "—", "Feb 8", "Feb 18", <Badge color={C.accent}>Fabricating</Badge>],
              [<span style={{ fontWeight: 700 }}>Frank Morris</span>, "Implant Crown #8", "Burbank Dental Lab", "A1", "Feb 1", "Feb 11", <Badge color={C.success}>Ready</Badge>],
            ]} />
          </Section>
        )}

        {/* ═══ 10. REFERRAL MANAGEMENT ═══ */}
        {tab === "referral" && (
          <Section title="🔄 Referral Management" sub="Track inbound/outbound referrals, specialist network, revenue attribution">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="📤" label="Referrals Out (MTD)" value="14" sub="8 perio, 4 OS, 2 endo" color={C.accent} />
              <Kpi icon="📥" label="Referrals In (MTD)" value="22" sub="$186K referred revenue" color={C.success} />
              <Kpi icon="🔗" label="Network Specialists" value="12" sub="Active relationships" color={C.purple} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "16px 18px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>Top Referring Doctors (Inbound)</div>
                {[
                  { name: "Dr. Anderson (GP)", referred: 8, revenue: "$68,400", trend: "↑" },
                  { name: "Dr. Williams (GP)", referred: 5, revenue: "$42,100", trend: "↑" },
                  { name: "Dr. Garcia (Pedo)", referred: 4, revenue: "$34,800", trend: "→" },
                  { name: "Dr. Lee (Endo)", referred: 3, revenue: "$24,200", trend: "↑" },
                  { name: "Dr. Brown (Ortho)", referred: 2, revenue: "$16,500", trend: "→" },
                ].map((d, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: i < 4 ? `1px solid ${C.border}` : "none" }}>
                    <div style={{ fontSize: 12, fontWeight: 600 }}>{d.name}</div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span style={{ fontSize: 11, color: C.muted }}>{d.referred} pts</span>
                      <span style={{ fontSize: 11, fontWeight: 700, color: C.success }}>{d.revenue}</span>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "16px 18px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>Outbound Referral Status</div>
                {[
                  { patient: "James Okafor", to: "Dr. Park (Perio)", reason: "SRP + possible surgery", status: "seen", color: C.success },
                  { patient: "Michael Torres", to: "Dr. Smith (Cardio)", reason: "Warfarin management pre-surgery", status: "pending", color: C.warning },
                  { patient: "Sarah Chen", to: "Dr. Okafor (OS)", reason: "Wisdom tooth extraction", status: "scheduled", color: C.accent },
                ].map((r, i) => (
                  <div key={i} style={{ padding: "8px 0", borderBottom: i < 2 ? `1px solid ${C.border}` : "none" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 12, fontWeight: 700 }}>{r.patient}</span>
                      <Badge color={r.color}>{r.status}</Badge>
                    </div>
                    <div style={{ fontSize: 11, color: C.muted }}>→ {r.to} · {r.reason}</div>
                  </div>
                ))}
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 11. INVENTORY ═══ */}
        {tab === "inventory" && (
          <Section title="📦 Inventory & Supply Management" sub="Auto-reorder, vendor comparison, expiration tracking, usage analytics">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="📦" label="Total SKUs" value="342" color={C.accent} />
              <Kpi icon="⚠️" label="Low Stock Alerts" value="8" sub="3 critical" color={C.danger} />
              <Kpi icon="📅" label="Expiring Soon" value="12" sub="Within 90 days" color={C.warning} />
              <Kpi icon="💰" label="Monthly Spend" value="$11,400" sub="5.7% of production" color={C.teal} />
            </div>
            <Table headers={["Item", "Category", "Stock", "Reorder At", "Vendor", "Unit Cost", "Status"]} rows={[
              [<span style={{ fontWeight: 700 }}>Composite A2 (4g syringe)</span>, "Restorative", "12", "10", "Henry Schein", "$42.50", <Badge color={C.warning}>Low</Badge>],
              [<span style={{ fontWeight: 700 }}>Implant Body 4.1x10mm</span>, "Implant", "3", "5", "Straumann", "$285.00", <Badge color={C.danger}>Critical</Badge>],
              [<span style={{ fontWeight: 700 }}>Nitrile Gloves (M)</span>, "PPE", "24 boxes", "10", "Amazon Business", "$12.99", <Badge color={C.success}>OK</Badge>],
              [<span style={{ fontWeight: 700 }}>Anesthetic Lidocaine 2%</span>, "Anesthesia", "48 carp", "20", "Patterson", "$28.50/box", <Badge color={C.success}>OK</Badge>],
              [<span style={{ fontWeight: 700 }}>Bite Registration Material</span>, "Impression", "6", "8", "Dentsply Sirona", "$34.00", <Badge color={C.warning}>Low</Badge>],
              [<span style={{ fontWeight: 700 }}>Sterilization Pouches (lg)</span>, "Infection Ctrl", "2 boxes", "5", "Crosstex", "$18.50", <Badge color={C.danger}>Critical</Badge>],
            ]} />
          </Section>
        )}

        {/* ═══ 12. HR & TIME CLOCK ═══ */}
        {tab === "hr" && (
          <Section title="👥 HR & Employee Management" sub="Time clock, PTO, scheduling, payroll, CE tracking, license alerts">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="👥" label="Total Staff" value="14" sub="3 providers, 11 team" color={C.accent} />
              <Kpi icon="⏰" label="Clocked In Now" value="12" sub="2 off today" color={C.success} />
              <Kpi icon="📅" label="PTO Requests" value="3" sub="2 pending approval" color={C.warning} />
              <Kpi icon="🎓" label="CE Expiring <90d" value="2" sub="Sarah M, Jamie L" color={C.danger} />
            </div>
            <Table headers={["Employee", "Role", "Status", "Clock In", "Hours Today", "PTO Balance", "License Exp"]} rows={[
              [<span style={{ fontWeight: 700 }}>Dr. Chen</span>, "Implantologist", <Badge color={C.success}>In</Badge>, "7:45 AM", "8.2h", "15 days", "Dec 2026"],
              [<span style={{ fontWeight: 700 }}>Dr. Park</span>, "Orthodontist", <Badge color={C.success}>In</Badge>, "7:50 AM", "8.1h", "12 days", "Mar 2027"],
              [<span style={{ fontWeight: 700 }}>Dr. Okafor</span>, "Oral Surgeon", <Badge color={C.success}>In</Badge>, "8:00 AM", "8.0h", "18 days", "Jun 2026"],
              [<span style={{ fontWeight: 700 }}>Sarah M. RDH</span>, "Hygienist", <Badge color={C.success}>In</Badge>, "7:55 AM", "8.1h", "8 days", <span style={{ color: C.danger, fontWeight: 700 }}>Apr 2026 ⚠️</span>],
              [<span style={{ fontWeight: 700 }}>Jamie L. RDH</span>, "Hygienist/Perio", <Badge color={C.success}>In</Badge>, "8:00 AM", "8.0h", "6 days", <span style={{ color: C.danger, fontWeight: 700 }}>May 2026 ⚠️</span>],
              [<span style={{ fontWeight: 700 }}>Maria G.</span>, "Office Manager", <Badge color={C.success}>In</Badge>, "7:30 AM", "8.5h", "10 days", "—"],
              [<span style={{ fontWeight: 700 }}>Tom R.</span>, "Front Desk", <Badge color={C.muted}>Off</Badge>, "—", "—", "5 days", "—"],
            ]} />
          </Section>
        )}

        {/* ═══ 13. STERILIZATION & COMPLIANCE ═══ */}
        {tab === "sterilization" && (
          <Section title="🧪 Sterilization & OSHA Compliance" sub="Autoclave logs, biological indicators, compliance checklists, safety records">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="🧪" label="Autoclave Cycles Today" value="8" sub="All passed ✓" color={C.success} />
              <Kpi icon="🦠" label="Last Spore Test" value="Pass" sub="Feb 10, 2026" color={C.success} />
              <Kpi icon="📋" label="OSHA Compliance" value="98%" sub="1 item due renewal" color={C.warning} />
              <Kpi icon="☢️" label="Radiation Badges" value="Current" sub="Next reading: Mar 1" color={C.teal} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "16px 18px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>Today's Autoclave Log</div>
                {[1,2,3,4,5,6,7,8].map(i => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: i < 8 ? `1px solid ${C.border}` : "none", fontSize: 12 }}>
                    <span>Cycle #{i} — {`${7 + Math.floor(i/2)}:${i%2 === 0 ? "00" : "30"} AM`}</span>
                    <div style={{ display: "flex", gap: 8 }}>
                      <span style={{ color: C.muted }}>270°F / 30 min</span>
                      <Badge color={C.success}>Pass</Badge>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "16px 18px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>OSHA Compliance Checklist</div>
                {[
                  { item: "Exposure Control Plan", due: "Annual", last: "Jan 2026", status: "current" },
                  { item: "Hazard Communication Program", due: "Annual", last: "Jan 2026", status: "current" },
                  { item: "Bloodborne Pathogen Training", due: "Annual", last: "Dec 2025", status: "current" },
                  { item: "Fire Safety Inspection", due: "Annual", last: "Nov 2025", status: "current" },
                  { item: "Radiation Safety Certificate", due: "Biennial", last: "Mar 2024", status: "due_soon" },
                  { item: "Emergency Eyewash Testing", due: "Weekly", last: "Feb 10", status: "current" },
                  { item: "SDS Binder Updated", due: "Ongoing", last: "Feb 2026", status: "current" },
                ].map((c, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: i < 6 ? `1px solid ${C.border}` : "none" }}>
                    <div style={{ fontSize: 12 }}>{c.item}</div>
                    <Badge color={c.status === "current" ? C.success : C.warning}>{c.status === "current" ? "Current" : "Due Soon"}</Badge>
                  </div>
                ))}
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 14. FINANCIAL COMMAND CENTER ═══ */}
        {tab === "financial" && (
          <Section title="💰 Financial Command Center" sub="P&L, cash flow, budgets, tax prep, provider compensation, overhead breakdown">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="💵" label="YTD Revenue" value="$498,240" sub="↑ 18% vs LY" color={C.success} />
              <Kpi icon="💰" label="Net Income MTD" value="$86,400" sub="43.2% margin" color={C.accent} />
              <Kpi icon="📊" label="Overhead %" value="57.3%" sub="Target: <59%" color={C.teal} />
              <Kpi icon="💳" label="A/P Outstanding" value="$18,200" sub="3 vendors due" color={C.warning} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 12 }}>P&L Summary — February 2026</div>
                {[
                  { cat: "Production (Gross)", val: "$206,400", pct: "", color: C.text, bold: true },
                  { cat: "Adjustments/Write-offs", val: "($7,200)", pct: "3.5%", color: C.muted },
                  { cat: "Net Production", val: "$199,200", pct: "", color: C.accent, bold: true },
                  { cat: "Collections", val: "$198,240", pct: "99.5%", color: C.success, bold: true },
                  { cat: "─ Staff Costs", val: "($52,800)", pct: "26.6%", color: C.muted },
                  { cat: "─ Facility", val: "($14,400)", pct: "7.3%", color: C.muted },
                  { cat: "─ Supplies & Lab", val: "($25,600)", pct: "12.9%", color: C.muted },
                  { cat: "─ Marketing", val: "($8,200)", pct: "4.1%", color: C.muted },
                  { cat: "─ Admin & Other", val: "($12,800)", pct: "6.5%", color: C.muted },
                  { cat: "Total Overhead", val: "($113,800)", pct: "57.3%", color: C.warning, bold: true },
                  { cat: "NET INCOME", val: "$84,440", pct: "42.6%", color: C.success, bold: true },
                ].map((r, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: r.bold ? `1px solid ${C.border}` : "none" }}>
                    <span style={{ fontSize: 12, fontWeight: r.bold ? 800 : 400, color: r.color }}>{r.cat}</span>
                    <div style={{ display: "flex", gap: 12 }}>
                      {r.pct && <span style={{ fontSize: 11, color: C.muted }}>{r.pct}</span>}
                      <span style={{ fontSize: 12, fontWeight: r.bold ? 800 : 600, fontFamily: "'JetBrains Mono'", color: r.color }}>{r.val}</span>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 12 }}>Overhead Breakdown</div>
                {[
                  { cat: "Staff (salaries + benefits)", pct: 26.6, target: 28, color: C.success },
                  { cat: "Supplies & Lab", pct: 12.9, target: 14, color: C.success },
                  { cat: "Facility (rent + utilities)", pct: 7.3, target: 8, color: C.success },
                  { cat: "Admin & Technology", pct: 6.5, target: 4, color: C.danger },
                  { cat: "Marketing", pct: 4.1, target: 5, color: C.success },
                ].map((o, i) => (
                  <div key={i} style={{ marginBottom: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                      <span style={{ fontSize: 12 }}>{o.cat}</span>
                      <span style={{ fontSize: 12, fontWeight: 700, color: o.color }}>{o.pct}% <span style={{ color: C.muted, fontWeight: 400 }}>/ {o.target}%</span></span>
                    </div>
                    <Pbar v={o.pct / o.target * 100} color={o.color} h={5} />
                  </div>
                ))}
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 15. PATIENT FINANCING ═══ */}
        {tab === "financing" && (
          <Section title="💳 Patient Financing Engine" sub="In-house payment plans, auto-charge, application & approval, no third-party fees">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="💳" label="Active Plans" value="47" sub="$284K outstanding" color={C.accent} />
              <Kpi icon="✅" label="On-Time Rate" value="94%" sub="3 past due" color={C.success} />
              <Kpi icon="💰" label="Collected via Plans (MTD)" value="$42,800" color={C.teal} />
              <Kpi icon="📊" label="Avg Plan Size" value="$3,240" sub="12-month avg" color={C.purple} />
            </div>
            <Table headers={["Patient", "Treatment", "Total", "Monthly", "Remaining", "Payments", "Status"]} rows={[
              [<span style={{ fontWeight: 700 }}>Margaret Sullivan</span>, "Implant #14 restoration", "$2,600", "$216.67/mo", "$1,950", "3/12", <Badge color={C.success}>Current</Badge>],
              [<span style={{ fontWeight: 700 }}>Diana Patel</span>, "Invisalign", "$3,300", "$275.00/mo", "$2,475", "3/12", <Badge color={C.success}>Current</Badge>],
              [<span style={{ fontWeight: 700 }}>Michael Torres</span>, "Bone graft + implant", "$475", "$158.33/mo", "$316.67", "1/3", <Badge color={C.success}>Current</Badge>],
              [<span style={{ fontWeight: 700 }}>Tom Davis</span>, "Full arch restoration", "$12,400", "$516.67/mo", "$9,300", "6/24", <Badge color={C.warning}>Late 5 days</Badge>],
            ]} />
            <div style={{ background: `${C.accent}05`, border: `1px solid ${C.accent}15`, borderRadius: 14, padding: "16px 20px", marginTop: 12 }}>
              <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 6 }}>🤖 Auto-Financing Flow</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10, fontSize: 12, color: "#4B5563" }}>
                <div><strong>1. Present:</strong> Treatment plan shown with "Monthly Payment" option alongside full price. $4,800 implant = "$200/mo for 24 months"</div>
                <div><strong>2. Apply:</strong> Patient taps "Apply" → soft credit check → instant approval (85% approval rate) → terms presented</div>
                <div><strong>3. Sign:</strong> Digital agreement signed on tablet/phone → first payment collected → card on file for auto-charge</div>
                <div><strong>4. Collect:</strong> Monthly auto-charge → SMS receipt → past-due auto-reminders → payment plan dashboard for tracking</div>
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 16. MARKETING SUITE ═══ */}
        {tab === "marketing" && (
          <Section title="📣 Marketing Suite" sub="Content calendar, ad management, review monitoring, referral tracking, ROI attribution">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="👤" label="New Patients (Feb)" value="38" sub="Target: 45" color={C.accent} />
              <Kpi icon="💰" label="Marketing Spend" value="$8,200" sub="4.1% of revenue" color={C.warning} />
              <Kpi icon="📊" label="Cost Per Patient" value="$216" sub="Target: <$300" color={C.success} />
              <Kpi icon="⭐" label="Google Rating" value="4.9" sub="234 reviews" color={C.teal} />
              <Kpi icon="📱" label="Social Followers" value="2,840" sub="↑ 340 this month" color={C.purple} />
              <Kpi icon="🔗" label="Referral Revenue" value="$186K" sub="22 referred patients" color={C.orange} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "16px 18px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>📊 Channel Performance</div>
                {[
                  { channel: "Google Ads", spend: "$3,200", patients: 14, cpa: "$229", roi: "8.2x", color: C.accent },
                  { channel: "Meta/Instagram", spend: "$2,100", patients: 8, cpa: "$263", roi: "5.4x", color: C.purple },
                  { channel: "Google Organic (SEO)", spend: "$800", patients: 6, cpa: "$133", roi: "12.1x", color: C.success },
                  { channel: "Patient Referrals", spend: "$1,500", patients: 6, cpa: "$250", roi: "9.8x", color: C.teal },
                  { channel: "Direct Mail", spend: "$600", patients: 2, cpa: "$300", roi: "4.2x", color: C.muted },
                  { channel: "Walk-ins / Other", spend: "$0", patients: 2, cpa: "$0", roi: "∞", color: C.orange },
                ].map((ch, i) => (
                  <div key={i} style={{ display: "grid", gridTemplateColumns: "1.5fr 70px 50px 60px 50px", padding: "6px 0", borderBottom: i < 5 ? `1px solid ${C.border}` : "none", alignItems: "center" }}>
                    <span style={{ fontSize: 12, fontWeight: 600 }}>{ch.channel}</span>
                    <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono'" }}>{ch.spend}</span>
                    <span style={{ fontSize: 11, fontWeight: 700 }}>{ch.patients}</span>
                    <span style={{ fontSize: 11, fontFamily: "'JetBrains Mono'" }}>{ch.cpa}</span>
                    <span style={{ fontSize: 11, fontWeight: 800, color: ch.color }}>{ch.roi}</span>
                  </div>
                ))}
              </div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "16px 18px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>📅 Content Calendar (This Week)</div>
                {[
                  { day: "Mon", content: "Before/After implant transformation", platform: "IG + FB", type: "photo", status: "posted" },
                  { day: "Tue", content: "\"3 Signs You Need a Root Canal\" video", platform: "TikTok + YT", type: "video", status: "scheduled" },
                  { day: "Wed", content: "Patient testimonial — Diana P. (Invisalign)", platform: "IG + FB", type: "video", status: "scheduled" },
                  { day: "Thu", content: "Blog: \"Dental Implants vs Bridges\" (SEO)", platform: "Website", type: "article", status: "draft" },
                  { day: "Fri", content: "Team Friday BTS + fun reel", platform: "IG + TikTok", type: "video", status: "idea" },
                ].map((c, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 0", borderBottom: i < 4 ? `1px solid ${C.border}` : "none" }}>
                    <span style={{ fontSize: 11, fontWeight: 800, color: C.accent, width: 30 }}>{c.day}</span>
                    <div style={{ flex: 1 }}><div style={{ fontSize: 11, fontWeight: 600 }}>{c.content}</div><div style={{ fontSize: 10, color: C.muted }}>{c.platform}</div></div>
                    <Badge color={c.status === "posted" ? C.success : c.status === "scheduled" ? C.accent : c.status === "draft" ? C.warning : C.muted}>{c.status}</Badge>
                  </div>
                ))}
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 17. NPS / PATIENT SATISFACTION ═══ */}
        {tab === "nps" && (
          <Section title="⭐ Patient Satisfaction & NPS" sub="Post-visit surveys, NPS tracking, sentiment analysis, review routing">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="⭐" label="NPS Score" value="78" sub="Excellent (target: 70+)" color={C.success} />
              <Kpi icon="😊" label="Promoters" value="82%" sub="Score 9-10" color={C.success} />
              <Kpi icon="😐" label="Passives" value="14%" sub="Score 7-8" color={C.warning} />
              <Kpi icon="😞" label="Detractors" value="4%" sub="Score 0-6 — 3 patients" color={C.danger} />
              <Kpi icon="📊" label="Response Rate" value="64%" sub="Industry avg: 25%" color={C.purple} />
              <Kpi icon="⭐" label="Avg Rating" value="4.87" sub="Out of 5.0" color={C.teal} />
            </div>
            <div style={{ background: `${C.success}06`, border: `1px solid ${C.success}15`, borderRadius: 14, padding: "14px 18px", marginBottom: 12 }}>
              <div style={{ fontSize: 12, fontWeight: 800, color: C.success, marginBottom: 4 }}>🤖 AI Review Routing</div>
              <div style={{ fontSize: 12, color: "#4B5563" }}>Patients scoring 9-10 automatically receive Google review link. Patients scoring ≤6 route to office manager for personal follow-up. AI generates draft response for each Google review within 30 minutes of posting.</div>
            </div>
          </Section>
        )}

        {/* ═══ 18. MULTI-LOCATION ═══ */}
        {tab === "multiloc" && (
          <Section title="🏢 Multi-Location Command Center" sub="Side-by-side performance, centralized management, location benchmarking">
            <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, overflow: "hidden" }}>
              <div style={{ padding: "12px 16px", borderBottom: `2px solid ${C.border}`, display: "grid", gridTemplateColumns: "1.5fr repeat(6, 1fr)", fontSize: 10, fontWeight: 700, color: C.muted, letterSpacing: 0.8, textTransform: "uppercase" }}>
                {["Location", "MTD Production", "Collections %", "New Patients", "Case Accept", "Overhead", "Net Margin"].map(h => <div key={h}>{h}</div>)}
              </div>
              {[
                { loc: "Auburn Main", prod: "$198,200", coll: "96.2%", np: 38, accept: "72%", overhead: "57.3%", margin: "42.7%", trend: "↑" },
                { loc: "Roseville", prod: "$142,800", coll: "94.8%", np: 28, accept: "68%", overhead: "61.2%", margin: "33.6%", trend: "→" },
                { loc: "Folsom", prod: "$168,400", coll: "97.1%", np: 34, accept: "74%", overhead: "55.8%", margin: "41.3%", trend: "↑" },
                { loc: "Rocklin (New)", prod: "$84,200", coll: "92.4%", np: 22, accept: "64%", overhead: "68.4%", margin: "24.0%", trend: "↑" },
              ].map((l, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "1.5fr repeat(6, 1fr)", padding: "12px 16px", borderBottom: `1px solid ${C.border}`, alignItems: "center" }}>
                  <div style={{ fontSize: 13, fontWeight: 800 }}>{l.loc} <span style={{ color: C.success }}>{l.trend}</span></div>
                  <div style={{ fontWeight: 700, fontFamily: "'JetBrains Mono'", fontSize: 13 }}>{l.prod}</div>
                  <div style={{ color: parseFloat(l.coll) >= 96 ? C.success : C.warning, fontWeight: 700 }}>{l.coll}</div>
                  <div style={{ fontWeight: 700 }}>{l.np}</div>
                  <div style={{ color: parseInt(l.accept) >= 70 ? C.success : C.warning, fontWeight: 700 }}>{l.accept}</div>
                  <div style={{ color: parseFloat(l.overhead) < 60 ? C.success : C.danger, fontWeight: 700 }}>{l.overhead}</div>
                  <div style={{ fontWeight: 800, color: parseFloat(l.margin) >= 40 ? C.success : parseFloat(l.margin) >= 30 ? C.warning : C.danger }}>{l.margin}</div>
                </div>
              ))}
              <div style={{ display: "grid", gridTemplateColumns: "1.5fr repeat(6, 1fr)", padding: "12px 16px", background: "#F9FAFB", fontWeight: 800 }}>
                <div>TOTAL (4 Locations)</div>
                <div style={{ fontFamily: "'JetBrains Mono'" }}>$593,600</div>
                <div>95.4%</div><div>122</div><div>70%</div><div>58.7%</div><div style={{ color: C.success }}>37.9%</div>
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 19. TELEDENTISTRY ═══ */}
        {tab === "telehealth" && (
          <Section title="📹 Teledentistry Module" sub="HIPAA-compliant video consults, photo triage, post-op check-ins, remote monitoring">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10, marginBottom: 16 }}>
              <Kpi icon="📹" label="Video Consults (MTD)" value="24" sub="$4,800 billed (D9995/D9996)" color={C.accent} />
              <Kpi icon="📸" label="Photo Triage" value="18" sub="12 → in-office, 6 → advice only" color={C.purple} />
              <Kpi icon="✅" label="Post-Op Checks" value="34" sub="0 complications flagged" color={C.success} />
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>📅 Today's Telehealth Queue</div>
                {[
                  { patient: "Sarah Chen", reason: "Implant consult (new lead)", time: "11:00 AM", type: "video", status: "waiting" },
                  { patient: "Tom Davis", reason: "Post-op check (extraction)", time: "1:00 PM", type: "video", status: "scheduled" },
                  { patient: "Nina Fox", reason: "Photo triage (swelling)", time: "ASAP", type: "photo", status: "urgent" },
                ].map((a, i) => (
                  <div key={i} style={{ padding: "8px 0", borderBottom: i < 2 ? `1px solid ${C.border}` : "none" }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 12, fontWeight: 700 }}>{a.patient}</span>
                      <Badge color={a.status === "urgent" ? C.danger : a.status === "waiting" ? C.warning : C.accent}>{a.status}</Badge>
                    </div>
                    <div style={{ fontSize: 11, color: C.muted }}>{a.reason} · {a.time} · {a.type}</div>
                  </div>
                ))}
              </div>
              <div style={{ background: "#1a1a2e", borderRadius: 14, padding: "20px", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 200 }}>
                <div style={{ fontSize: 48, marginBottom: 10 }}>📹</div>
                <div style={{ color: "#94A3B8", fontSize: 14, fontWeight: 600, marginBottom: 16 }}>HIPAA-Compliant Video Room</div>
                <button style={{ background: C.success, color: "#FFF", border: "none", borderRadius: 10, padding: "10px 28px", fontWeight: 800, fontSize: 14, cursor: "pointer" }}>Start Video Consult</button>
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 20. AI TREATMENT PLANNING ═══ */}
        {tab === "aitreatment" && (
          <Section title="🧠 AI Treatment Planning Assistant" sub="Upload imaging → AI suggests diagnosis + CDT codes + fee estimates + insurance predictions">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 12 }}>🧠 AI Analysis — Robert Kim</div>
                <div style={{ fontSize: 11, color: C.muted, marginBottom: 10 }}>Based on: CBCT scan, periapical #14, full mouth X-rays, clinical notes</div>
                {[
                  { finding: "Missing tooth #14 — moderate bone loss mesial", dx: "K08.1", confidence: "98%", color: C.danger },
                  { finding: "Sufficient bone height for implant (12mm)", dx: "Favorable anatomy", confidence: "94%", color: C.success },
                  { finding: "Adjacent teeth #13, #15 — healthy", dx: "No contraindication", confidence: "96%", color: C.success },
                  { finding: "Sinus proximity — 3mm clearance", dx: "No sinus lift needed", confidence: "87%", color: C.warning },
                ].map((f, i) => (
                  <div key={i} style={{ padding: "8px 10px", background: `${f.color}05`, borderLeft: `3px solid ${f.color}`, borderRadius: "0 8px 8px 0", marginBottom: 6 }}>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 11, fontWeight: 600 }}>{f.finding}</span>
                      <span style={{ fontSize: 10, fontWeight: 700, color: f.color }}>{f.confidence}</span>
                    </div>
                    <div style={{ fontSize: 10, color: C.muted }}>{f.dx}</div>
                  </div>
                ))}
              </div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 12 }}>📋 AI-Generated Treatment Plan</div>
                {[
                  { phase: "Phase 1 — Implant Placement", items: [{ cdt: "D6010", desc: "Implant body #14", fee: 2200, ins: 880 }, { cdt: "D0367", desc: "CBCT (if not already taken)", fee: 250, ins: 175 }] },
                  { phase: "Phase 2 — Restoration (after healing)", items: [{ cdt: "D6058", desc: "Abutment placement", fee: 950, ins: 380 }, { cdt: "D6065", desc: "Implant crown — porcelain", fee: 1650, ins: 660 }] },
                ].map((p, pi) => (
                  <div key={pi} style={{ marginBottom: 12 }}>
                    <div style={{ fontSize: 11, fontWeight: 800, color: C.purple, marginBottom: 4 }}>{p.phase}</div>
                    {p.items.map((item, ii) => (
                      <div key={ii} style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", fontSize: 11, borderBottom: `1px solid ${C.border}` }}>
                        <span style={{ color: C.accent, fontFamily: "'JetBrains Mono'" }}>{item.cdt}</span>
                        <span style={{ flex: 1, marginLeft: 8 }}>{item.desc}</span>
                        <span style={{ fontWeight: 700, fontFamily: "'JetBrains Mono'" }}>${item.fee}</span>
                      </div>
                    ))}
                  </div>
                ))}
                <div style={{ background: "#F9FAFB", borderRadius: 8, padding: "10px 12px", marginTop: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, fontWeight: 900 }}>
                    <span>Total</span><span>$5,050</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: C.success }}>
                    <span>Est. Insurance</span><span>$2,095</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, fontWeight: 900, color: C.danger }}>
                    <span>Patient Responsibility</span><span>$2,955</span>
                  </div>
                  <div style={{ fontSize: 11, color: C.muted, marginTop: 6 }}>💳 Payment option: $123.13/mo for 24 months</div>
                </div>
              </div>
            </div>
          </Section>
        )}

        {/* ═══ 21. AI CLINICAL DECISION SUPPORT ═══ */}
        {tab === "aiclinical" && (
          <Section title="🤖 AI Clinical Decision Support" sub="Drug interactions, treatment contraindications, risk assessments, protocol recommendations">
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 12 }}>⚠️ Active Patient Alerts</div>
                {[
                  { patient: "Margaret Sullivan", alert: "Bisphosphonate use — implant healing risk", severity: "high", action: "Monitor osseointegration closely. Consider BRONJ risk assessment. Document informed consent.", color: C.danger },
                  { patient: "Michael Torres", alert: "Warfarin + upcoming implant surgery", severity: "high", action: "Contact cardiologist for INR management. Target INR <2.5 pre-surgery. Consider bridging protocol. Have hemostatic agents ready.", color: C.danger },
                  { patient: "James Okafor", alert: "Type 2 Diabetes — A1C check recommended", severity: "medium", action: "Request recent A1C from PCP. If >8%, consider delaying elective procedures. Perio treatment may improve glycemic control.", color: C.warning },
                  { patient: "Diana Patel", alert: "Latex allergy — ensure latex-free supplies", severity: "medium", action: "Flag all appointments. Verify: nitrile gloves, latex-free prophy cups, non-latex dam if needed.", color: C.warning },
                  { patient: "Sarah Chen", alert: "New patient — no medical history on file", severity: "low", action: "Intake forms pending. Do not proceed with treatment until medical history reviewed.", color: C.accent },
                ].map((a, i) => (
                  <div key={i} style={{ padding: "10px 12px", background: `${a.color}05`, borderLeft: `3px solid ${a.color}`, borderRadius: "0 10px 10px 0", marginBottom: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 2 }}>
                      <span style={{ fontSize: 12, fontWeight: 800 }}>{a.patient}</span>
                      <Badge color={a.color}>{a.severity}</Badge>
                    </div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: a.color, marginBottom: 3 }}>{a.alert}</div>
                    <div style={{ fontSize: 11, color: "#4B5563", lineHeight: 1.5 }}>{a.action}</div>
                  </div>
                ))}
              </div>
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "18px 20px" }}>
                <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 12 }}>🧠 AI Protocol Recommendations</div>
                {[
                  { title: "Pre-Surgical Antibiotic Protocol", desc: "Based on AHA guidelines: patients with prosthetic heart valves, history of endocarditis, or certain congenital conditions require prophylaxis. Amoxicillin 2g PO 30-60 min pre-op (or Clindamycin 600mg if penicillin allergy).", icon: "💊" },
                  { title: "Perio-Systemic Risk Assessment", desc: "AI cross-references medical history for: diabetes (perio bidirectional), cardiovascular disease, pregnancy, immunosuppression. Auto-adjusts recall interval recommendations.", icon: "🔗" },
                  { title: "Radiograph Interval Guidelines", desc: "Based on ADA/FDA guidelines: new patients need FMX or pano + BWX. Recall BWX every 6-18 months based on caries risk. CBCT only when 2D insufficient. AI tracks and alerts when imaging is due.", icon: "📸" },
                  { title: "Emergency Protocol Auto-Activation", desc: "If clinical notes mention: syncope, chest pain, allergic reaction, seizure, aspiration — AI automatically pulls emergency protocol card with step-by-step response and 911 guidance.", icon: "🚨" },
                ].map((p, i) => (
                  <div key={i} style={{ padding: "10px 0", borderBottom: i < 3 ? `1px solid ${C.border}` : "none" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                      <span style={{ fontSize: 16 }}>{p.icon}</span>
                      <span style={{ fontSize: 12, fontWeight: 800 }}>{p.title}</span>
                    </div>
                    <div style={{ fontSize: 11, color: "#4B5563", lineHeight: 1.5 }}>{p.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          </Section>
        )}
      </div>

      <style>{`*{box-sizing:border-box;margin:0;padding:0} button{transition:0.15s} button:hover{filter:brightness(0.95)} ::-webkit-scrollbar{width:5px} ::-webkit-scrollbar-thumb{background:#D1D5DB;border-radius:3px}`}</style>
    </div>
  );
}
