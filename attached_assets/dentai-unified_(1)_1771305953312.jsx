import { useState } from "react";

// ═══════════════════════════════════════════════════════════════════════════
// DENTAI UNIFIED PLATFORM — 37-Module Complete Dental Practice OS
// End-to-End: Clinical · Specialty · Operations · Revenue Cycle · AI · BI
// Replaces: Dentrix + CareStack + Overjet + Pearl + Weave + DentalRobot +
//           Vyne + BastionGPT + Nexus + DataRovers + Dental Intelligence
// ═══════════════════════════════════════════════════════════════════════════

const C = { bg: "#08090E", card: "#0F1118", card2: "#141720", border: "#1C1F2E", text: "#E8ECF4", muted: "#5C6478", accent: "#6C5CE7", success: "#00C48C", warning: "#FFB020", danger: "#FF4757", purple: "#A855F7", pink: "#F472B6", cyan: "#22D3EE", teal: "#2DD4BF", orange: "#FB923C", indigo: "#818CF8", emerald: "#34D399", lime: "#A3E635", rose: "#FB7185", sky: "#38BDF8", gold: "#F5C542", sidebar: "#060710", sideText: "#4A5068", sideActive: "#6C5CE7", glow: "rgba(108,92,231,0.12)" };

// ═══ SHARED COMPONENTS ═══
const Badge = ({ children, color = C.accent, solid, pulse }) => (
  <span style={{ background: solid ? color : `${color}15`, color: solid ? "#FFF" : color, padding: "2px 9px", borderRadius: 6, fontSize: 10, fontWeight: 700, letterSpacing: 0.3, textTransform: "uppercase", whiteSpace: "nowrap", display: "inline-flex", alignItems: "center", gap: 4 }}>
    {pulse && <span style={{ width: 5, height: 5, borderRadius: "50%", background: solid ? "#FFF" : color, animation: "blink 2s infinite" }} />}
    {children}
  </span>
);
const Pbar = ({ v, color = C.accent, h = 5 }) => (
  <div style={{ height: h, background: "#1A1D2E", borderRadius: h, overflow: "hidden", flex: 1 }}>
    <div style={{ height: "100%", width: `${Math.min(v, 100)}%`, background: `linear-gradient(90deg, ${color}88, ${color})`, borderRadius: h, transition: "width 0.7s cubic-bezier(.4,0,.2,1)" }} />
  </div>
);
const Kpi = ({ label, value, sub, color = C.accent, icon }) => (
  <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "15px 17px", position: "relative", overflow: "hidden" }}>
    <div style={{ position: "absolute", top: -18, right: -18, width: 60, height: 60, background: `${color}08`, borderRadius: "50%", filter: "blur(14px)" }} />
    <div style={{ fontSize: 9, color: C.muted, letterSpacing: 1.4, textTransform: "uppercase", fontWeight: 600, marginBottom: 3 }}>{icon} {label}</div>
    <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "'JetBrains Mono', monospace" }}>{value}</div>
    {sub && <div style={{ fontSize: 10, color, fontWeight: 600, marginTop: 2 }}>{sub}</div>}
  </div>
);
const Section = ({ title, sub, children }) => (
  <div style={{ marginBottom: 22 }}>
    <div style={{ marginBottom: 13 }}>
      <div style={{ fontSize: 21, fontWeight: 900, letterSpacing: -0.4 }}>{title}</div>
      {sub && <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>{sub}</div>}
    </div>
    {children}
  </div>
);
const Card = ({ children, style: s }) => <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "16px 18px", ...s }}>{children}</div>;
const CardTitle = ({ children }) => <div style={{ fontSize: 13, fontWeight: 800, marginBottom: 10 }}>{children}</div>;
const Row = ({ children, bb, style: s }) => <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "6px 0", borderBottom: bb ? `1px solid ${C.border}` : "none", ...s }}>{children}</div>;
const Grid = ({ cols = 2, gap = 12, children, style: s }) => <div style={{ display: "grid", gridTemplateColumns: `repeat(auto-fit, minmax(${Math.floor(600/cols)}px, 1fr))`, gap, ...s }}>{children}</div>;
const Alert = ({ color, icon, title, children }) => (
  <div style={{ background: `${color}06`, borderLeft: `3px solid ${color}`, borderRadius: "0 10px 10px 0", padding: "10px 14px", marginBottom: 7 }}>
    <div style={{ fontSize: 11, fontWeight: 800, color, marginBottom: 2 }}>{icon} {title}</div>
    <div style={{ fontSize: 10, color: "#8892A8", lineHeight: 1.5 }}>{children}</div>
  </div>
);
const Metric = ({ label, value, color }) => <div><span style={{ fontSize: 10, color: C.muted }}>{label}: </span><span style={{ fontSize: 11, fontWeight: 700, color: color || C.text, fontFamily: "'JetBrains Mono'" }}>{value}</span></div>;

// ═══ ALL 37 MODULES ═══
const MODULES = [
  // Clinical
  { id: "intake", label: "Patient Intake", icon: "📋", group: "Clinical" },
  { id: "perio", label: "Perio Charting", icon: "📊", group: "Clinical" },
  { id: "soap", label: "Clinical Notes", icon: "📝", group: "Clinical" },
  { id: "imaging", label: "AI Diagnostics", icon: "🔬", group: "Clinical" },
  { id: "consent", label: "Consent Forms", icon: "✍️", group: "Clinical" },
  { id: "erx", label: "E-Prescribing", icon: "💊", group: "Clinical" },
  { id: "aiclinical", label: "Decision Support", icon: "🧠", group: "Clinical" },
  // Specialty
  { id: "ortho", label: "Ortho Tracker", icon: "🦷", group: "Specialty" },
  { id: "implant", label: "Implant Tracker", icon: "🔩", group: "Specialty" },
  { id: "lab", label: "Lab Cases", icon: "🔬", group: "Specialty" },
  { id: "referral", label: "Referrals", icon: "🔄", group: "Specialty" },
  // Operations
  { id: "inventory", label: "Inventory", icon: "📦", group: "Operations" },
  { id: "hr", label: "HR & Payroll", icon: "👥", group: "Operations" },
  { id: "sterilization", label: "Sterilization", icon: "🧪", group: "Operations" },
  { id: "schedule", label: "Smart Schedule", icon: "📅", group: "Operations" },
  // Revenue Cycle AI
  { id: "rcm", label: "Revenue Command", icon: "🎛️", group: "Revenue AI" },
  { id: "verify", label: "Insurance Verify", icon: "🔍", group: "Revenue AI" },
  { id: "claims", label: "Claims Engine", icon: "📋", group: "Revenue AI" },
  { id: "crosscode", label: "Cross-Coding", icon: "🔀", group: "Revenue AI" },
  { id: "necessity", label: "Necessity Letters", icon: "📄", group: "Revenue AI" },
  { id: "denials", label: "Denial Appeals", icon: "⚔️", group: "Revenue AI" },
  // AI Engines
  { id: "phone", label: "AI Phone Agent", icon: "📞", group: "AI Engines" },
  { id: "voice", label: "Voice-to-Code", icon: "🎤", group: "AI Engines" },
  { id: "txplan", label: "AI Tx Planning", icon: "🧠", group: "AI Engines" },
  { id: "acceptance", label: "Case Acceptance", icon: "🎯", group: "AI Engines" },
  { id: "telehealth", label: "Teledentistry", icon: "📹", group: "AI Engines" },
  // Business Intelligence
  { id: "financial", label: "Financial Center", icon: "💰", group: "Intelligence" },
  { id: "financing", label: "Patient Finance", icon: "💳", group: "Intelligence" },
  { id: "marketing", label: "Marketing Suite", icon: "📣", group: "Intelligence" },
  { id: "nps", label: "Patient NPS", icon: "⭐", group: "Intelligence" },
  { id: "fees", label: "Fee Optimizer", icon: "💲", group: "Intelligence" },
  { id: "provider", label: "Provider Intel", icon: "👨‍⚕️", group: "Intelligence" },
  { id: "payer", label: "Payer Intel", icon: "🏦", group: "Intelligence" },
  { id: "multiloc", label: "Multi-Location", icon: "🏢", group: "Intelligence" },
  { id: "compliance", label: "Compliance Audit", icon: "🛡️", group: "Intelligence" },
  { id: "bi", label: "Business Intel", icon: "📊", group: "Intelligence" },
];

export default function DentAIUnified() {
  const [tab, setTab] = useState("rcm");
  const groups = [...new Set(MODULES.map(m => m.group))];
  const groupIcons = { "Clinical": "💉", "Specialty": "🦷", "Operations": "⚙️", "Revenue AI": "💰", "AI Engines": "🤖", "Intelligence": "📊" };

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: C.bg, fontFamily: "'Outfit', system-ui, sans-serif", color: C.text }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet" />

      {/* ═══ SIDEBAR ═══ */}
      <div style={{ width: 215, background: C.sidebar, padding: "12px 8px", display: "flex", flexDirection: "column", flexShrink: 0, borderRight: `1px solid ${C.border}`, overflowY: "auto" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9, padding: "6px 10px", marginBottom: 12 }}>
          <div style={{ width: 32, height: 32, borderRadius: 9, background: "linear-gradient(135deg, #6C5CE7, #00C48C, #FFB020)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15, boxShadow: "0 0 20px rgba(108,92,231,0.4)" }}>🦷</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 900, color: "#F0F2F8", letterSpacing: -0.3 }}>DentAI</div>
            <div style={{ fontSize: 7, color: C.sideText, letterSpacing: 3, textTransform: "uppercase" }}>Unified Platform</div>
          </div>
        </div>

        <div style={{ background: `${C.accent}08`, border: `1px solid ${C.accent}15`, borderRadius: 9, padding: "8px 11px", margin: "0 4px 10px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: C.success, boxShadow: `0 0 6px ${C.success}` }} />
            <span style={{ fontSize: 10, color: C.success, fontWeight: 700 }}>36 Modules · All Active</span>
          </div>
          <div style={{ fontSize: 9, color: C.sideText, marginTop: 3 }}>Replaces $4,200+/mo in software</div>
        </div>

        {groups.map(g => (
          <div key={g}>
            <div style={{ fontSize: 8, color: "#2A2E3E", letterSpacing: 2.2, textTransform: "uppercase", fontWeight: 800, padding: "10px 11px 3px" }}>{groupIcons[g]} {g}</div>
            {MODULES.filter(m => m.group === g).map(m => (
              <button key={m.id} onClick={() => setTab(m.id)} style={{ display: "flex", alignItems: "center", gap: 7, padding: "6px 10px", borderRadius: 7, border: "none", background: tab === m.id ? `${C.sideActive}12` : "transparent", cursor: "pointer", width: "100%", transition: "0.12s", borderLeft: tab === m.id ? `2px solid ${C.sideActive}` : "2px solid transparent" }}>
                <span style={{ fontSize: 12 }}>{m.icon}</span>
                <span style={{ fontSize: 10.5, fontWeight: tab === m.id ? 700 : 500, color: tab === m.id ? C.sideActive : C.sideText }}>{m.label}</span>
              </button>
            ))}
          </div>
        ))}
      </div>

      {/* ═══ MAIN CONTENT ═══ */}
      <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px", minWidth: 0 }}>

{/* ═══════════════════════════════════════ */}
{/* ═══ 1. PATIENT INTAKE & PORTAL ════════ */}
{/* ═══════════════════════════════════════ */}
{tab === "intake" && (
  <Section title="📋 Digital Intake & Patient Portal" sub="Online forms, e-signatures, insurance card capture, patient self-service">
    <Grid cols={4} style={{ marginBottom: 14 }}>
      <Kpi icon="📋" label="Forms Today" value="12" sub="8 new patients" color={C.accent} />
      <Kpi icon="✍️" label="E-Signatures" value="34" sub="100% HIPAA compliant" color={C.success} />
      <Kpi icon="📸" label="Insurance Cards" value="11" sub="Auto-verified OCR" color={C.purple} />
      <Kpi icon="⏱️" label="Avg Intake Time" value="4.2m" sub="↓ from 18m paper" color={C.teal} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>📋 Active Intake Forms</CardTitle>
        {["New Patient Registration|24|98%","Medical History Questionnaire|42|96%","HIPAA Privacy Acknowledgment|3|100%","Financial Policy Agreement|5|99%","Insurance Card Upload|2|94%","Consent for Treatment|4|100%","Orthodontic Consent|12|97%","Implant Surgical Consent|8|95%"].map((f,i) => {
          const [name,fields,comp] = f.split("|");
          return <Row key={i} bb={i<7}><div><div style={{fontSize:12,fontWeight:600}}>{name}</div><div style={{fontSize:10,color:C.muted}}>{fields} fields</div></div><div style={{display:"flex",gap:6,alignItems:"center"}}><span style={{fontSize:11,color:C.success,fontWeight:600}}>{comp}</span><Badge color={C.success}>Active</Badge></div></Row>;
        })}
      </Card>
      <Card>
        <CardTitle>🌐 Patient Portal Features</CardTitle>
        {["📅 View & manage appointments|live","💳 Pay bills & view statements|live","💬 Message practice securely|live","📋 View treatment plans & accept|live","📄 Download receipts & EOBs|live","🏥 Update medical history|live","📸 Upload insurance card photos|live","💊 Request prescription refills|live","🔬 View X-rays & photos|beta","📹 Book teledentistry consult|beta"].map((f,i) => {
          const [feat,status] = f.split("|");
          return <Row key={i} bb={i<9}><span style={{fontSize:12}}>{feat}</span><Badge color={status==="live"?C.success:C.warning}>{status}</Badge></Row>;
        })}
      </Card>
    </Grid>
    <div style={{ background: `${C.accent}05`, border: `1px solid ${C.accent}12`, borderRadius: 12, padding: "14px 18px", marginTop: 12 }}>
      <div style={{ fontSize: 12, fontWeight: 800, marginBottom: 6 }}>🤖 AI Intake Automation Flow</div>
      <Grid cols={4} gap={8}>
        {[["1. Pre-Visit (48hr)","SMS sent → patient fills forms on phone → insurance card OCR extracts plan info",C.accent],["2. Auto-Verify","Eligibility checked instantly → benefits populated → copay calculated → estimates ready",C.purple],["3. Day-Of","QR code check-in → med hx flagged → allergies populated → zero clipboard time",C.success],["4. Post-Visit","Portal activated → treatment plan viewable → payment link → next appt booked",C.orange]].map(([t,d,c],i) => (
          <div key={i} style={{fontSize:11,color:"#7A8298"}}><strong style={{color:c}}>{t}:</strong> {d}</div>
        ))}
      </Grid>
    </div>
  </Section>
)}

{/* ═══════════════════════════════════════ */}
{/* ═══ 2. PERIO CHARTING ═════════════════ */}
{/* ═══════════════════════════════════════ */}
{tab === "perio" && (() => {
  const teeth = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16];
  const lower = [32,31,30,29,28,27,26,25,24,23,22,21,20,19,18,17];
  const probing = {3:[3,2,3,4,5,3],8:[2,2,2,2,3,2],14:[5,6,4,4,5,6],19:[4,3,3,3,4,4],30:[6,7,5,5,6,7]};
  return (
    <Section title="📊 Periodontal Charting" sub="6-point probing, BOP, recession, furcation, mobility — full perio record">
      <Grid cols={4} style={{marginBottom:14}}>
        <Kpi icon="📏" label="Avg Probing" value="3.2mm" sub="Previous: 3.8mm ↓" color={C.success} />
        <Kpi icon="🩸" label="BOP Sites" value="18%" sub="Target: <10%" color={C.danger} />
        <Kpi icon="📉" label="Sites >4mm" value="24" sub="Previous: 31 ↓" color={C.warning} />
        <Kpi icon="🦷" label="Perio Dx" value="Stage III" sub="Grade B — generalized" color={C.purple} />
      </Grid>
      <Card style={{marginBottom:14}}>
        <CardTitle>Probing Chart — Margaret Sullivan — 2026-02-11</CardTitle>
        {[{label:"Facial — Upper",t:teeth,s:"F"},{label:"Lingual — Upper",t:teeth,s:"L"},{label:"Facial — Lower",t:lower,s:"F"},{label:"Lingual — Lower",t:lower,s:"L"}].map((row,ri) => (
          <div key={ri} style={{marginBottom:10}}>
            <div style={{fontSize:9,color:C.muted,fontWeight:700,letterSpacing:1.5,textTransform:"uppercase",marginBottom:3}}>{row.label}</div>
            <div style={{display:"flex",gap:2}}>
              {row.t.map(t => {
                const p = probing[t]||[2,2,2,2,2,2];
                const vals = row.s==="F"?p.slice(0,3):p.slice(3,6);
                return (
                  <div key={t} style={{flex:1,textAlign:"center"}}>
                    <div style={{display:"flex",justifyContent:"center",gap:1,marginBottom:2}}>
                      {vals.map((v,vi) => (
                        <div key={vi} style={{width:13,height:17,borderRadius:3,background:v>=6?`${C.danger}18`:v>=4?`${C.warning}18`:"#1A1D2E",display:"flex",alignItems:"center",justifyContent:"center",fontSize:9,fontWeight:800,color:v>=6?C.danger:v>=4?C.warning:C.success,fontFamily:"'JetBrains Mono'"}}>{v}</div>
                      ))}
                    </div>
                    <div style={{fontSize:8,fontWeight:700,color:C.muted}}>{t}</div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
        <div style={{display:"flex",gap:14,paddingTop:8,borderTop:`1px solid ${C.border}`,marginTop:6}}>
          {[["1-3mm",C.success,"Healthy"],["4-5mm",C.warning,"Moderate"],["6mm+",C.danger,"Severe"]].map(([r,c,l]) => (
            <div key={r} style={{display:"flex",alignItems:"center",gap:4}}>
              <div style={{width:10,height:10,borderRadius:3,background:`${c}18`,border:`1px solid ${c}`}} />
              <span style={{fontSize:9,color:C.muted}}>{r} — {l}</span>
            </div>
          ))}
        </div>
      </Card>
      <Alert color={C.purple} icon="🤖" title="AI Perio Assessment">
        Diagnosis: <strong>Periodontitis Stage III, Grade B, Generalized</strong>. 24 sites ≥4mm (improved from 31). BOP at 18%. Recommend: continued SRP, 3-month perio maintenance, consider Arestin for sites ≥5mm. Insurance narrative auto-generated for D4341/D4342.
      </Alert>
    </Section>
  );
})()}

{/* ═══════════════════════════════════════ */}
{/* ═══ 3. CLINICAL NOTES / SOAP ══════════ */}
{/* ═══════════════════════════════════════ */}
{tab === "soap" && (
  <Section title="📝 Clinical Notes — AI-Assisted SOAP" sub="Voice-to-text, AI expansion, CDT auto-coding, template library">
    <Grid cols={2}>
      <Card>
        <CardTitle>Today's Notes</CardTitle>
        {[["Margaret Sullivan","Implant Follow-up #14","8:00 AM","signed","Dr. Chen"],["Robert Kim","Implant Consult + CBCT","9:00 AM","draft","Dr. Chen"],["James Okafor","Perio Maintenance","8:00 AM","signed","Dr. Park"],["Diana Patel","Invisalign Check #8","9:00 AM","pending","Dr. Park"]].map(([p,proc,t,st,prov],i) => (
          <Row key={i} bb={i<3}><div><div style={{fontSize:12,fontWeight:700}}>{p}</div><div style={{fontSize:10,color:C.muted}}>{proc} · {t} · {prov}</div></div><Badge color={st==="signed"?C.success:st==="draft"?C.warning:C.muted}>{st}</Badge></Row>
        ))}
      </Card>
      <Card>
        <CardTitle>📋 SOAP Note — Margaret Sullivan</CardTitle>
        {[["S — Subjective","Patient reports mild sensitivity at implant site #14 when chewing. No spontaneous pain. Ibuprofen provides relief.",C.accent],["O — Objective","Implant #14 stable, no mobility. Tissue healthy. Probing: 3mm circumferential. CBCT confirms osseointegration at 6 weeks.",C.teal],["A — Assessment","Implant #14 healing within normal parameters. Sensitivity consistent with early loading adaptation.",C.purple],["P — Plan","Continue soft diet 2 weeks. Return 8 weeks for final impression (D6058 + D6065). Home care instructions given.",C.orange]].map(([label,text,color],i) => (
          <div key={i} style={{marginBottom:8,padding:"8px 10px",background:`${color}05`,borderLeft:`3px solid ${color}25`,borderRadius:"0 8px 8px 0"}}>
            <div style={{fontSize:9,fontWeight:800,color,letterSpacing:1,textTransform:"uppercase",marginBottom:2}}>{label}</div>
            <div style={{fontSize:11,color:"#8892A8",lineHeight:1.5}}>{text}</div>
          </div>
        ))}
        <div style={{display:"flex",gap:5,marginTop:6}}>
          <button style={{background:C.success,color:"#FFF",border:"none",borderRadius:7,padding:"5px 12px",fontSize:10,fontWeight:700,cursor:"pointer"}}>✓ Sign</button>
          <button style={{background:`${C.accent}12`,color:C.accent,border:`1px solid ${C.accent}20`,borderRadius:7,padding:"5px 12px",fontSize:10,fontWeight:700,cursor:"pointer"}}>🎤 Voice</button>
          <button style={{background:C.card2,border:`1px solid ${C.border}`,borderRadius:7,padding:"5px 12px",fontSize:10,fontWeight:600,cursor:"pointer"}}>🤖 AI Expand</button>
        </div>
      </Card>
    </Grid>
  </Section>
)}

{/* ═══════════════════════════════════════ */}
{/* ═══ 4. AI DIAGNOSTIC IMAGING ══════════ */}
{/* ═══════════════════════════════════════ */}
{tab === "imaging" && (
  <Section title="🔬 AI Diagnostic Imaging Engine" sub="Real-time radiograph analysis, caries & bone loss detection — replaces Overjet + Pearl + VideaHealth">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="🔬" label="Scans Analyzed" value="42" sub="38 BWX, 4 CBCT" color={C.accent} />
      <Kpi icon="🦷" label="Pathologies Found" value="18" sub="12 caries, 4 bone, 2 other" color={C.danger} />
      <Kpi icon="📊" label="Detection Accuracy" value="96.2%" sub="Validated vs provider dx" color={C.success} />
      <Kpi icon="💰" label="Revenue Found" value="$8,400" sub="AI-detected treatment" color={C.emerald} />
    </Grid>
    <div style={{display:"grid",gridTemplateColumns:"5fr 3fr",gap:14}}>
      <div style={{background:"#0A0C14",borderRadius:14,padding:"18px",border:`1px solid ${C.border}`}}>
        <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:10}}>
          <span style={{fontSize:13,fontWeight:800}}>Margaret Sullivan — BWX R/L</span>
          <Badge color={C.success} solid>AI ANALYZED</Badge>
        </div>
        <Grid cols={2} gap={8} style={{marginBottom:10}}>
          {[{label:"BWX — Right",findings:[{tooth:"#3 Mesial",type:"Caries",conf:94,sev:"moderate",color:C.danger},{tooth:"#14 Mesial",type:"Bone Loss",conf:89,sev:"4.2mm",color:C.purple}]},{label:"BWX — Left",findings:[{tooth:"#19 Distal",type:"Caries",conf:87,sev:"early",color:C.warning},{tooth:"#30 Mesial",type:"Bone Loss",conf:91,sev:"5.8mm",color:C.danger},{tooth:"#31 Periapical",type:"Radiolucency",conf:78,sev:"eval",color:C.orange}]}].map((xr,xi) => (
            <div key={xi} style={{background:"#060810",borderRadius:10,padding:"12px",border:"1px solid #1A1D2E"}}>
              <div style={{fontSize:9,color:C.muted,letterSpacing:1.5,textTransform:"uppercase",fontWeight:700,marginBottom:8}}>{xr.label}</div>
              <div style={{display:"flex",justifyContent:"center",height:70,background:"#040608",borderRadius:7,marginBottom:8,alignItems:"center",position:"relative",border:"1px solid #141720"}}>
                <span style={{fontSize:28,opacity:0.15}}>🦷</span>
                {xr.findings.map((f,fi) => <div key={fi} style={{position:"absolute",top:4+fi*22,right:4,background:`${f.color}18`,border:`1px solid ${f.color}35`,borderRadius:5,padding:"2px 6px"}}><span style={{fontSize:8,color:f.color,fontWeight:700}}>⚠ {f.tooth}</span></div>)}
              </div>
              {xr.findings.map((f,fi) => (
                <div key={fi} style={{padding:"4px 0",borderBottom:fi<xr.findings.length-1?`1px solid ${C.border}`:"none"}}>
                  <Row><span style={{fontSize:10,fontWeight:700,color:f.color}}>{f.type} — {f.tooth}</span><Badge color={f.color}>{f.sev}</Badge></Row>
                  <div style={{display:"flex",alignItems:"center",gap:5,marginTop:2}}><Pbar v={f.conf} color={f.color} h={3} /><span style={{fontSize:9,color:f.color,fontWeight:700,fontFamily:"'JetBrains Mono'"}}>{f.conf}%</span></div>
                </div>
              ))}
            </div>
          ))}
        </Grid>
        <div style={{display:"flex",gap:4}}>
          {["AI Overlay","Bone Levels","Caries Map","Compare","Enhance","Annotate","Patient View","Export"].map(t => (
            <button key={t} style={{background:"rgba(255,255,255,0.03)",border:"1px solid rgba(255,255,255,0.06)",borderRadius:6,padding:"5px 8px",color:"#5C6478",fontSize:9,fontWeight:600,cursor:"pointer",flex:1}}>{t}</button>
          ))}
        </div>
      </div>
      <div style={{display:"flex",flexDirection:"column",gap:10}}>
        <Card>
          <CardTitle>🧠 AI Diagnostic Summary</CardTitle>
          <Alert color={C.danger} icon="🦷" title="3 Carious Lesions">#3M (94%), #19D (87%), #14M (82%)</Alert>
          <Alert color={C.purple} icon="📏" title="Bone Loss Quantified">#14M: 4.2mm (30%) · #30M: 5.8mm (45%). Stage III Perio.</Alert>
          <Alert color={C.orange} icon="⚠️" title="Periapical Finding">#31: Radiolucency 3×4mm — vitality test + PA recommended</Alert>
        </Card>
        <Card>
          <CardTitle>💰 AI Treatment Opportunity</CardTitle>
          {[["D2391 ×2 — Composite #3M, #19D","$480",C.accent],["D4341 ×4 — SRP all quadrants","$820",C.purple],["D0220 — PA #31 (diagnostic)","$35",C.teal],["D3310 — RCT #31 (if non-vital)","$980",C.orange]].map(([p,f,c],i) => (
            <Row key={i} bb><span style={{fontSize:10,color:"#8892A8"}}>{p}</span><span style={{fontWeight:700,color:c,fontFamily:"'JetBrains Mono'",fontSize:11}}>{f}</span></Row>
          ))}
          <Row style={{paddingTop:8,borderTop:`2px solid ${C.border}`,marginTop:4}}><span style={{fontSize:13,fontWeight:900}}>Potential Revenue</span><span style={{fontSize:15,fontWeight:900,color:C.emerald,fontFamily:"'JetBrains Mono'"}}>$2,315</span></Row>
        </Card>
      </div>
    </div>
  </Section>
)}

{/* ═══════════════════════════════════════ */}
{/* ═══ 5. CONSENT FORMS ══════════════════ */}
{/* ═══════════════════════════════════════ */}
{tab === "consent" && (
  <Section title="✍️ Consent Form Builder" sub="Digital consents with e-signature, procedure-specific templates">
    <Grid cols={3} gap={10}>
      {[["General Treatment Consent","6 fields","All","1,240"],["Implant Surgical Consent","12 fields","D6010-D6050","342"],["Extraction Consent","8 fields","D7140-D7230","567"],["Orthodontic Agreement","15 fields","D8010-D8090","189"],["Endodontic Consent","10 fields","D3310-D3330","234"],["Sedation Consent","14 fields","D9220-D9243","156"],["HIPAA Privacy Notice","3 fields","All patients","3,105"],["Financial Agreement","5 fields","All patients","3,105"],["Whitening Consent","6 fields","D9972-D9975","98"],["Perio Surgery Consent","11 fields","D4210-D4274","78"]].map(([name,fields,proc,sigs],i) => (
        <Card key={i}>
          <div style={{fontSize:12,fontWeight:700,marginBottom:3}}>{name}</div>
          <div style={{fontSize:10,color:C.muted,marginBottom:6}}>{fields} · {proc} · {sigs} signatures</div>
          <div style={{display:"flex",gap:4}}><Badge color={C.success}>Active</Badge><Badge color={C.accent}>E-Sign</Badge></div>
        </Card>
      ))}
    </Grid>
  </Section>
)}

{/* ═══════════════════════════════════════ */}
{/* ═══ 6. E-PRESCRIBING ══════════════════ */}
{/* ═══════════════════════════════════════ */}
{tab === "erx" && (
  <Section title="💊 E-Prescribing (eRx)" sub="EPCS-compliant, drug interaction checking, pharmacy integration">
    <Grid cols={3} style={{marginBottom:14}}>
      <Kpi icon="💊" label="Rx Sent Today" value="8" sub="6 antibiotics, 2 analgesics" color={C.accent} />
      <Kpi icon="⚠️" label="Interactions Flagged" value="2" sub="Both resolved" color={C.danger} />
      <Kpi icon="🏪" label="Pharmacies" value="47" sub="CVS, Walgreens, Rite Aid +" color={C.success} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>Recent Prescriptions</CardTitle>
        {[{p:"Margaret Sullivan",d:"Amoxicillin 500mg",s:"#21 — TID × 7d",ph:"CVS Auburn",alert:"⛔ Penicillin allergy — BLOCKED"},{p:"Robert Kim",d:"Ibuprofen 600mg",s:"#20 — Q6H PRN",ph:"Walgreens Roseville",alert:""},{p:"Michael Torres",d:"Clindamycin 300mg",s:"#28 — QID × 7d",ph:"CVS Auburn",alert:"⚠️ Check Warfarin interaction"},{p:"James Okafor",d:"Chlorhexidine 0.12%",s:"#1 — BID × 14d",ph:"Rite Aid Folsom",alert:""}].map((rx,i) => (
          <div key={i} style={{padding:"7px 0",borderBottom:i<3?`1px solid ${C.border}`:"none"}}>
            <Row><span style={{fontSize:12,fontWeight:700}}>{rx.p}</span><Badge color={C.success}>Sent</Badge></Row>
            <div style={{fontSize:10,color:C.muted}}>{rx.d} — {rx.s} · {rx.ph}</div>
            {rx.alert && <div style={{fontSize:10,color:C.danger,fontWeight:700,marginTop:2}}>{rx.alert}</div>}
          </div>
        ))}
      </Card>
      <Card>
        <CardTitle>🤖 AI Drug Interaction Engine</CardTitle>
        <Alert color={C.danger} icon="⛔" title="BLOCKED: Margaret Sullivan — Penicillin Allergy">Amoxicillin is penicillin-class. Auto-substituted: <strong>Clindamycin 300mg QID ×7d</strong> or <strong>Azithromycin 500mg then 250mg ×4d</strong>.</Alert>
        <Alert color={C.warning} icon="⚠️" title="WARNING: Michael Torres — Warfarin + Clindamycin">May increase INR. Notify cardiologist, INR check Day 3-5, reduce Warfarin if INR &gt;3.5. Documented.</Alert>
      </Card>
    </Grid>
  </Section>
)}

{/* ═══════════════════════════════════════ */}
{/* ═══ 7. AI DECISION SUPPORT ════════════ */}
{/* ═══════════════════════════════════════ */}
{tab === "aiclinical" && (
  <Section title="🧠 AI Clinical Decision Support" sub="Drug interactions, contraindications, risk assessments, protocol recommendations">
    <Grid cols={2}>
      <Card>
        <CardTitle>⚠️ Active Patient Alerts</CardTitle>
        {[{p:"Margaret Sullivan",alert:"Bisphosphonate use — implant healing risk",sev:"high",action:"Monitor osseointegration. Consider BRONJ risk. Document consent.",c:C.danger},{p:"Michael Torres",alert:"Warfarin + upcoming implant surgery",sev:"high",action:"Contact cardiologist for INR. Target <2.5 pre-surgery. Hemostatic agents ready.",c:C.danger},{p:"James Okafor",alert:"Type 2 Diabetes — A1C check recommended",sev:"med",action:"Request A1C from PCP. If >8%, delay elective procedures.",c:C.warning},{p:"Diana Patel",alert:"Latex allergy — ensure latex-free supplies",sev:"med",action:"Flag appointments. Nitrile gloves, latex-free prophy cups.",c:C.warning},{p:"Sarah Chen",alert:"New patient — no medical history on file",sev:"low",action:"Intake forms pending. Do not treat until reviewed.",c:C.accent}].map((a,i) => (
          <Alert key={i} color={a.c} icon="" title={<>{a.p} <Badge color={a.c}>{a.sev}</Badge></>}><strong style={{color:a.c}}>{a.alert}</strong><br/>{a.action}</Alert>
        ))}
      </Card>
      <Card>
        <CardTitle>🧠 AI Protocol Recommendations</CardTitle>
        {[{t:"Pre-Surgical Antibiotic Protocol",d:"AHA guidelines: prosthetic valves, endocarditis history → Amoxicillin 2g PO 30-60 min pre-op (Clindamycin 600mg if allergy).",icon:"💊"},{t:"Perio-Systemic Risk Assessment",d:"Cross-references: diabetes, CVD, pregnancy, immunosuppression. Auto-adjusts recall intervals.",icon:"🔗"},{t:"Radiograph Interval Guidelines",d:"ADA/FDA: new pts need FMX/pano+BWX. Recall BWX every 6-18mo based on caries risk. CBCT when 2D insufficient.",icon:"📸"},{t:"Emergency Protocol Auto-Activation",d:"Notes mentioning syncope, chest pain, allergic reaction → auto-pulls emergency protocol card with step-by-step.",icon:"🚨"}].map((p,i) => (
          <div key={i} style={{padding:"8px 0",borderBottom:i<3?`1px solid ${C.border}`:"none"}}>
            <div style={{display:"flex",alignItems:"center",gap:5,marginBottom:3}}><span style={{fontSize:14}}>{p.icon}</span><span style={{fontSize:11,fontWeight:800}}>{p.t}</span></div>
            <div style={{fontSize:10,color:"#7A8298",lineHeight:1.5}}>{p.d}</div>
          </div>
        ))}
      </Card>
    </Grid>
  </Section>
)}

{/* ═══════════════════════════════════════ */}
{/* ═══ 8. ORTHO TRACKER ══════════════════ */}
{/* ═══════════════════════════════════════ */}
{tab === "ortho" && (
  <Section title="🦷 Orthodontic Tracker" sub="Invisalign tray tracking, bracket charting, compliance monitoring">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="🦷" label="Active Cases" value="34" sub="28 Invisalign, 6 brackets" color={C.purple} />
      <Kpi icon="📅" label="Check-ins This Week" value="12" color={C.accent} />
      <Kpi icon="✅" label="On-Track Rate" value="91%" sub="3 patients behind" color={C.success} />
      <Kpi icon="💰" label="Ortho Revenue MTD" value="$48,200" color={C.teal} />
    </Grid>
    <Card>
      <CardTitle>Active Invisalign Cases</CardTitle>
      {[["Diana Patel","8/22","95%","on_track","2026-02-20"],["Emma Rodriguez","14/30","88%","on_track","2026-02-25"],["Tyler Nguyen","3/18","100%","on_track","2026-03-01"],["Sophia Adams","18/24","72%","behind","2026-02-14"]].map(([p,trays,comp,st,next],i) => (
        <div key={i} style={{display:"grid",gridTemplateColumns:"1.5fr 70px 1fr 70px 70px 80px",padding:"8px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:11}}>
          <span style={{fontWeight:700}}>{p}</span>
          <span style={{fontWeight:800,color:C.purple,fontFamily:"'JetBrains Mono'"}}>{trays}</span>
          <Pbar v={parseInt(trays)/parseInt(trays.split("/")[1])*100} color={C.purple} h={4} />
          <span style={{fontWeight:600,color:parseInt(comp)>=90?C.success:C.warning}}>{comp}</span>
          <Badge color={st==="on_track"?C.success:C.warning}>{st==="on_track"?"On Track":"Behind"}</Badge>
          <span style={{color:C.muted}}>{next}</span>
        </div>
      ))}
    </Card>
  </Section>
)}

{/* ═══════════════════════════════════════ */}
{/* ═══ 9. IMPLANT TRACKER ════════════════ */}
{/* ═══════════════════════════════════════ */}
{tab === "implant" && (
  <Section title="🔩 Implant Case Tracker" sub="Stage-based workflow from consult through final restoration">
    <Grid cols={3} style={{marginBottom:14}}>
      <Kpi icon="🔩" label="Active Cases" value="18" sub="6 healing, 8 restoring, 4 new" color={C.accent} />
      <Kpi icon="💰" label="Implant Revenue MTD" value="$87,400" color={C.success} />
      <Kpi icon="✅" label="Success Rate" value="98.4%" sub="1 complication in 62" color={C.teal} />
    </Grid>
    <Card>
      <CardTitle>Implant Pipeline</CardTitle>
      <Grid cols={5} gap={8}>
        {[{s:"Consult",icon:"🎯",c:4,pts:["Robert Kim #14","Sarah Chen #30","Lisa Park #8,9","Tom Davis #19"],color:C.accent},{s:"Surgery",icon:"🔪",c:3,pts:["Michael Torres #17","John Wu #3","Amy Lee #14,15"],color:C.purple},{s:"Healing",icon:"⏳",c:6,pts:["Margaret Sullivan #14","David Park #5","Karen Brown #18","Pete Hall #30","Raj Patel #3","Nina Fox #10"],color:C.warning},{s:"Impression",icon:"📸",c:3,pts:["Jim Lee #14","Maria Garcia #19","Steve Chen #3"],color:C.teal},{s:"Restoration",icon:"👑",c:2,pts:["Emily Watson #12","Frank Morris #8"],color:C.success}].map(st => (
          <div key={st.s} style={{background:`${st.color}05`,border:`1px solid ${st.color}12`,borderRadius:10,padding:"10px 12px"}}>
            <Row style={{marginBottom:6}}><span style={{fontSize:11,fontWeight:800,color:st.color}}>{st.icon} {st.s}</span><span style={{fontSize:16,fontWeight:900,color:st.color}}>{st.c}</span></Row>
            {st.pts.map((p,i) => <div key={i} style={{fontSize:10,color:"#7A8298",padding:"2px 0",borderBottom:i<st.pts.length-1?`1px solid ${C.border}`:"none"}}>{p}</div>)}
          </div>
        ))}
      </Grid>
    </Card>
  </Section>
)}

{/* ═══════════════════════════════════════ */}
{/* ═══ 10. LAB CASES ═════════════════════ */}
{/* ═══════════════════════════════════════ */}
{tab === "lab" && (
  <Section title="🔬 Lab Case Manager" sub="Track every case from scan to delivery">
    <Grid cols={3} style={{marginBottom:14}}>
      <Kpi icon="📦" label="Active Cases" value="23" sub="8 overdue" color={C.accent} />
      <Kpi icon="💰" label="Lab Costs MTD" value="$14,200" sub="7.1% of production" color={C.warning} />
      <Kpi icon="⏱️" label="Avg Turnaround" value="8.2 days" sub="Target: 7 days" color={C.orange} />
    </Grid>
    <Card>
      {[["Margaret Sullivan","Crown PFM #3","Burbank Lab","A2","Jan 28","Feb 8","Overdue",C.danger],["Emily Watson","Crown e.max #12","Glidewell","B1","Feb 5","Feb 14","In Progress",C.warning],["Robert Kim","Implant Abutment #14","Straumann","—","Feb 10","Feb 24","Submitted",C.accent],["Diana Patel","Invisalign Trays 9-12","Align Tech","—","Feb 8","Feb 18","Fabricating",C.accent],["Frank Morris","Implant Crown #8","Burbank Lab","A1","Feb 1","Feb 11","Ready",C.success]].map(([p,type,lab,shade,sent,due,st,color],i) => (
        <div key={i} style={{display:"grid",gridTemplateColumns:"1.2fr 1.2fr 1fr 40px 60px 60px 80px",padding:"7px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:11}}>
          <span style={{fontWeight:700}}>{p}</span><span style={{color:"#8892A8"}}>{type}</span><span style={{color:C.muted}}>{lab}</span><span>{shade}</span><span style={{color:C.muted}}>{sent}</span><span style={{color:C.muted}}>{due}</span><Badge color={color}>{st}</Badge>
        </div>
      ))}
    </Card>
  </Section>
)}

{/* ═══════════════════════════════════════ */}
{/* ═══ 11. REFERRAL MANAGEMENT ═══════════ */}
{/* ═══════════════════════════════════════ */}
{tab === "referral" && (
  <Section title="🔄 Referral Management" sub="Inbound/outbound referrals, specialist network, revenue attribution">
    <Grid cols={3} style={{marginBottom:14}}>
      <Kpi icon="📤" label="Referrals Out MTD" value="14" sub="8 perio, 4 OS, 2 endo" color={C.accent} />
      <Kpi icon="📥" label="Referrals In MTD" value="22" sub="$186K revenue" color={C.success} />
      <Kpi icon="🔗" label="Network Specialists" value="12" color={C.purple} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>Top Referring Doctors (Inbound)</CardTitle>
        {[["Dr. Anderson (GP)",8,"$68,400"],["Dr. Williams (GP)",5,"$42,100"],["Dr. Garcia (Pedo)",4,"$34,800"],["Dr. Lee (Endo)",3,"$24,200"],["Dr. Brown (Ortho)",2,"$16,500"]].map(([n,ref,rev],i) => (
          <Row key={i} bb={i<4}><span style={{fontSize:11,fontWeight:600}}>{n}</span><div style={{display:"flex",gap:8}}><span style={{fontSize:10,color:C.muted}}>{ref} pts</span><span style={{fontSize:10,fontWeight:700,color:C.success}}>{rev}</span></div></Row>
        ))}
      </Card>
      <Card>
        <CardTitle>Outbound Referral Status</CardTitle>
        {[["James Okafor","Dr. Park (Perio)","SRP + surgery","seen",C.success],["Michael Torres","Dr. Smith (Cardio)","Warfarin pre-surgery","pending",C.warning],["Sarah Chen","Dr. Okafor (OS)","Wisdom extraction","scheduled",C.accent]].map(([p,to,reason,st,color],i) => (
          <div key={i} style={{padding:"7px 0",borderBottom:i<2?`1px solid ${C.border}`:"none"}}>
            <Row><span style={{fontSize:11,fontWeight:700}}>{p}</span><Badge color={color}>{st}</Badge></Row>
            <div style={{fontSize:10,color:C.muted}}>→ {to} · {reason}</div>
          </div>
        ))}
      </Card>
    </Grid>
  </Section>
)}

{/* ═══════════════════════════════════════ */}
{/* ═══ 12. INVENTORY ═════════════════════ */}
{/* ═══════════════════════════════════════ */}
{tab === "inventory" && (
  <Section title="📦 Inventory & Supply Management" sub="Auto-reorder, vendor comparison, expiration tracking">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="📦" label="Total SKUs" value="342" color={C.accent} />
      <Kpi icon="⚠️" label="Low Stock" value="8" sub="3 critical" color={C.danger} />
      <Kpi icon="📅" label="Expiring <90d" value="12" color={C.warning} />
      <Kpi icon="💰" label="Monthly Spend" value="$11,400" sub="5.7% of production" color={C.teal} />
    </Grid>
    <Card>
      {[["Composite A2 (4g)","Restorative","12","10","Henry Schein","$42.50","Low",C.warning],["Implant Body 4.1×10","Implant","3","5","Straumann","$285","Critical",C.danger],["Nitrile Gloves (M)","PPE","24 boxes","10","Amazon","$12.99","OK",C.success],["Lidocaine 2%","Anesthesia","48 carp","20","Patterson","$28.50","OK",C.success],["Bite Registration","Impression","6","8","Dentsply","$34","Low",C.warning],["Sterilization Pouches","Infection Ctrl","2 boxes","5","Crosstex","$18.50","Critical",C.danger]].map(([item,cat,stock,reorder,vendor,cost,st,color],i) => (
        <div key={i} style={{display:"grid",gridTemplateColumns:"1.8fr 0.8fr 60px 60px 1fr 70px 70px",padding:"7px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:11}}>
          <span style={{fontWeight:700}}>{item}</span><span style={{color:C.muted}}>{cat}</span><span>{stock}</span><span style={{color:C.muted}}>{reorder}</span><span style={{color:C.muted}}>{vendor}</span><span style={{fontFamily:"'JetBrains Mono'"}}>{cost}</span><Badge color={color}>{st}</Badge>
        </div>
      ))}
    </Card>
  </Section>
)}

{/* ═══ 13. HR & PAYROLL ════════════════════ */}
{tab === "hr" && (
  <Section title="👥 HR & Employee Management" sub="Time clock, PTO, scheduling, payroll, CE tracking, license alerts">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="👥" label="Total Staff" value="14" sub="3 providers, 11 team" color={C.accent} />
      <Kpi icon="⏰" label="Clocked In" value="12" sub="2 off today" color={C.success} />
      <Kpi icon="📅" label="PTO Requests" value="3" sub="2 pending" color={C.warning} />
      <Kpi icon="🎓" label="CE Expiring <90d" value="2" sub="Sarah M, Jamie L" color={C.danger} />
    </Grid>
    <Card>
      {[["Dr. Chen","Implantologist","In",C.success,"7:45 AM","8.2h","15d","Dec 2026"],["Dr. Park","Orthodontist","In",C.success,"7:50 AM","8.1h","12d","Mar 2027"],["Dr. Okafor","Oral Surgeon","In",C.success,"8:00 AM","8.0h","18d","Jun 2026"],["Sarah M. RDH","Hygienist","In",C.success,"7:55 AM","8.1h","8d","Apr 2026 ⚠️"],["Jamie L. RDH","Hyg/Perio","In",C.success,"8:00 AM","8.0h","6d","May 2026 ⚠️"],["Maria G.","Office Mgr","In",C.success,"7:30 AM","8.5h","10d","—"],["Tom R.","Front Desk","Off",C.muted,"—","—","5d","—"]].map(([name,role,st,color,cin,hrs,pto,lic],i) => (
        <div key={i} style={{display:"grid",gridTemplateColumns:"1.3fr 1fr 55px 60px 55px 55px 75px",padding:"7px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:11}}>
          <span style={{fontWeight:700}}>{name}</span><span style={{color:C.muted}}>{role}</span><Badge color={color}>{st}</Badge><span style={{color:C.muted}}>{cin}</span><span>{hrs}</span><span>{pto}</span><span style={{color:lic.includes("⚠")?C.danger:C.muted,fontWeight:lic.includes("⚠")?700:400}}>{lic}</span>
        </div>
      ))}
    </Card>
  </Section>
)}

{/* ═══ 14. STERILIZATION ═════════════════ */}
{tab === "sterilization" && (
  <Section title="🧪 Sterilization & OSHA Compliance" sub="Autoclave logs, biological indicators, compliance checklists">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="🧪" label="Cycles Today" value="8" sub="All passed ✓" color={C.success} />
      <Kpi icon="🦠" label="Last Spore Test" value="Pass" sub="Feb 10, 2026" color={C.success} />
      <Kpi icon="📋" label="OSHA Compliance" value="98%" sub="1 item due" color={C.warning} />
      <Kpi icon="☢️" label="Radiation Badges" value="Current" sub="Next: Mar 1" color={C.teal} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>Today's Autoclave Log</CardTitle>
        {[1,2,3,4,5,6,7,8].map(i => (
          <Row key={i} bb={i<8}><span style={{fontSize:11}}>Cycle #{i} — {`${7+Math.floor(i/2)}:${i%2===0?"00":"30"} AM`}</span><div style={{display:"flex",gap:6}}><span style={{fontSize:10,color:C.muted}}>270°F / 30 min</span><Badge color={C.success}>Pass</Badge></div></Row>
        ))}
      </Card>
      <Card>
        <CardTitle>OSHA Compliance Checklist</CardTitle>
        {[["Exposure Control Plan","Annual","Jan 2026","current"],["Hazard Communication","Annual","Jan 2026","current"],["Bloodborne Pathogen Training","Annual","Dec 2025","current"],["Fire Safety Inspection","Annual","Nov 2025","current"],["Radiation Safety Certificate","Biennial","Mar 2024","due_soon"],["Emergency Eyewash Testing","Weekly","Feb 10","current"],["SDS Binder Updated","Ongoing","Feb 2026","current"]].map(([item,due,last,st],i) => (
          <Row key={i} bb={i<6}><span style={{fontSize:11}}>{item}</span><Badge color={st==="current"?C.success:C.warning}>{st==="current"?"Current":"Due Soon"}</Badge></Row>
        ))}
      </Card>
    </Grid>
  </Section>
)}

{/* ═══ 15. SMART SCHEDULING ══════════════ */}
{tab === "schedule" && (
  <Section title="📅 AI Scheduling & Capacity Optimizer" sub="Production-based scheduling, no-show prediction, same-day fill">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="📅" label="Chair Utilization" value="91%" sub="Target: 85%" color={C.success} />
      <Kpi icon="💰" label="Tomorrow's Production" value="$24,800" color={C.accent} />
      <Kpi icon="⚠️" label="No-Show Risk" value="3" sub="AI sending reminders" color={C.warning} />
      <Kpi icon="🔄" label="Same-Day Fills" value="4" sub="From AI waitlist" color={C.emerald} />
    </Grid>
    <div style={{display:"grid",gridTemplateColumns:"2fr 1fr",gap:14}}>
      <Card>
        <CardTitle>📅 Tomorrow's Schedule</CardTitle>
        {[["8:00","60m","Op 1","Dr. Chen","Robert Kim","Implant Consult + CBCT","$2,450","low"],["8:00","60m","Op 2","Dr. Park","Diana Patel","Invisalign Check #9","$280","low"],["8:00","60m","Hyg 1","Sarah RDH","James Okafor","Perio Maintenance","$180","med"],["8:00","60m","Hyg 2","Jamie RDH","New Pt — Garcia","NP Exam + BWX","$342","high"],["9:00","90m","Op 1","Dr. Chen","Margaret Sullivan","Crown Seat #14","$1,280","low"],["9:00","60m","Op 2","Dr. Park","Tyler Nguyen","Ortho Consult","$250","med"],["10:00","120m","Op 1","Dr. Chen","Michael Torres","Crown Prep #3","$1,840","low"]].map(([time,dur,chair,prov,pt,proc,prod,risk],i) => (
          <div key={i} style={{display:"grid",gridTemplateColumns:"45px 40px 50px 70px 1fr 1.2fr 70px 45px",padding:"6px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:10}}>
            <span style={{fontFamily:"'JetBrains Mono'",fontWeight:700,color:C.accent}}>{time}</span>
            <span style={{color:C.muted}}>{dur}</span>
            <span style={{color:C.muted}}>{chair}</span>
            <span style={{fontWeight:600,fontSize:9}}>{prov}</span>
            <span style={{fontWeight:700}}>{pt}</span>
            <span style={{color:"#7A8298",fontSize:9}}>{proc}</span>
            <span style={{fontWeight:800,color:C.emerald,fontFamily:"'JetBrains Mono'"}}>{prod}</span>
            <Badge color={risk==="high"?C.danger:risk==="med"?C.warning:C.success}>{risk}</Badge>
          </div>
        ))}
      </Card>
      <div style={{display:"flex",flexDirection:"column",gap:10}}>
        <Card>
          <CardTitle>⚠️ No-Show Risk</CardTitle>
          {[["Maria Garcia (New)","38%","New pt, no deposit",C.danger],["James Okafor","22%","Missed last 2 hyg",C.warning],["Tyler Nguyen","18%","History of reschedule",C.warning]].map(([p,risk,reason,color],i) => (
            <div key={i} style={{padding:"6px 8px",background:`${color}05`,borderRadius:7,marginBottom:5}}>
              <Row><span style={{fontSize:10,fontWeight:700}}>{p}</span><Badge color={color}>{risk}</Badge></Row>
              <div style={{fontSize:9,color:C.muted}}>{reason}</div>
            </div>
          ))}
        </Card>
        <Card>
          <CardTitle>🔄 AI Waitlist</CardTitle>
          {[["Frank Morris","Crown seat #8","$1,280","Any AM"],["Karen Brown","Filling #18","$240","Tue/Thu PM"],["Pete Hall","Implant F/U","$0","Flexible"]].map(([p,proc,prod,flex],i) => (
            <Row key={i} bb={i<2}><div><span style={{fontSize:10,fontWeight:700}}>{p}</span><br/><span style={{fontSize:9,color:C.muted}}>{proc}</span></div><div style={{textAlign:"right"}}><span style={{fontSize:10,fontWeight:700,color:C.emerald}}>{prod}</span><br/><span style={{fontSize:9,color:C.muted}}>{flex}</span></div></Row>
          ))}
          <div style={{fontSize:9,color:C.success,marginTop:4}}>🤖 Cancellation → AI contacts waitlist in 30 sec</div>
        </Card>
      </div>
    </div>
  </Section>
)}

{/* ═══ 16. REVENUE CYCLE COMMAND CENTER ═══ */}
{tab === "rcm" && (
  <Section title="🎛️ Revenue Cycle Command Center" sub="Real-time pipeline from verification → payment — entire revenue cycle at a glance">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="📋" label="Claims MTD" value="847" sub="94.2% first-pass rate" color={C.accent} />
      <Kpi icon="💰" label="Collections MTD" value="$198,240" sub="99.5% of net production" color={C.emerald} />
      <Kpi icon="⏱️" label="Days in A/R" value="18.4" sub="↓ from 32 days" color={C.success} />
      <Kpi icon="🔀" label="Cross-Coded" value="34" sub="$28,400 medical revenue" color={C.purple} />
    </Grid>
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="📄" label="Necessity Letters" value="18" sub="91% approval rate" color={C.indigo} />
      <Kpi icon="⚔️" label="Open Denials" value="$12,840" sub="68% overturn rate" color={C.warning} />
      <Kpi icon="🎤" label="Voice Notes" value="24" sub="6.8 hrs saved today" color={C.cyan} />
      <Kpi icon="🏦" label="Payer Connections" value="340+" sub="All major payers" color={C.teal} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>🔴 Live Revenue Activity</CardTitle>
        {[["2:42 PM","✅ Claim D2740 #3 — Margaret Sullivan auto-submitted to Delta","$1,280",C.success],["2:38 PM","🔍 Insurance verified — Robert Kim (Cigna PPO) implant benefits confirmed","—",C.accent],["2:31 PM","🔀 Cross-coded: Sleep appliance D5988 → G47.33 → E0486 for medical billing","$2,400",C.purple],["2:24 PM","📄 Medical necessity letter generated for SRP D4341 — James Okafor","—",C.indigo],["2:18 PM","⚔️ Appeal auto-submitted: Denied crown D2740 — MetLife — clinical narrative attached","$1,280",C.warning],["2:10 PM","🎤 Voice note → SOAP → CDT auto-coded: Dr. Chen — Michael Torres implant follow-up","—",C.cyan],["1:55 PM","💰 ERA auto-posted: Cigna batch $8,420 — 12 claims reconciled","$8,420",C.emerald]].map(([time,action,amt,color],i) => (
          <div key={i} style={{padding:"7px 10px",background:`${color}04`,borderLeft:`2px solid ${color}30`,borderRadius:"0 8px 8px 0",marginBottom:5}}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}>
              <span style={{fontSize:10,color:C.muted}}>{time}</span>
              {amt !== "—" && <span style={{fontSize:11,fontWeight:800,color,fontFamily:"'JetBrains Mono'"}}>{amt}</span>}
            </div>
            <div style={{fontSize:10,color:"#8892A8",marginTop:2}}>{action}</div>
          </div>
        ))}
      </Card>
      <Card>
        <CardTitle>📊 Engine Performance</CardTitle>
        {[["Claim Accuracy","97.8%",97.8,C.success],["Verification Speed","4.2 sec",95,C.accent],["Cross-Code Match","89%",89,C.purple],["Necessity Approval","91%",91,C.indigo],["Appeal Overturn","68%",68,C.warning],["Voice-to-Code","98.4%",98.4,C.cyan],["ERA Auto-Post","96%",96,C.teal],["First-Pass Rate","94.2%",94.2,C.emerald]].map(([label,val,pct,color],i) => (
          <div key={i} style={{marginBottom:8}}>
            <Row><span style={{fontSize:11}}>{label}</span><span style={{fontSize:11,fontWeight:700,color,fontFamily:"'JetBrains Mono'"}}>{val}</span></Row>
            <Pbar v={pct} color={color} h={4} />
          </div>
        ))}
      </Card>
    </Grid>
  </Section>
)}

{/* ═══ 17. AI INSURANCE VERIFICATION ═════ */}
{tab === "verify" && (
  <Section title="🔍 AI Insurance Verification Engine" sub="Real-time eligibility, benefits breakdown, auto-estimate — replaces DentalRobot + Vyne">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="🔍" label="Verified Today" value="48" sub="Tomorrow's schedule" color={C.accent} />
      <Kpi icon="⚡" label="Avg Speed" value="4.2 sec" sub="vs 12 min manual" color={C.success} />
      <Kpi icon="✅" label="Accuracy" value="98.6%" color={C.emerald} />
      <Kpi icon="🏦" label="Payers Connected" value="340+" color={C.teal} />
    </Grid>
    <Card>
      <CardTitle>🔍 Tomorrow's Verification Results</CardTitle>
      {[["Robert Kim","Cigna PPO","Active","50% major, $2K max, $1,450 remaining","✓",C.success],["Margaret Sullivan","Delta Premier","Active","80% basic, 50% major, $1,800 remaining","✓",C.success],["Diana Patel","MetLife PPO","Active","$2K ortho lifetime, $800 remaining","⚠",C.warning],["James Okafor","Aetna DMO","Active","100% prev, 80% basic, 50% major","✓",C.success],["New — Garcia","Delta PPO","Active","100% prev, 80% basic, 50% major, $2K max","✓",C.success],["Tom Davis","BCBS FEP","Active","50% implant, $2.5K max, $400 remaining","⚠",C.warning]].map(([p,plan,st,benefits,check,color],i) => (
        <div key={i} style={{padding:"8px 0",borderBottom:`1px solid ${C.border}`}}>
          <Row><span style={{fontSize:12,fontWeight:700}}>{p}</span><div style={{display:"flex",gap:5}}><Badge color={C.success}>{st}</Badge><Badge color={color}>{check}</Badge></div></Row>
          <div style={{fontSize:10,color:C.muted}}>{plan} — {benefits}</div>
        </div>
      ))}
    </Card>
  </Section>
)}

{/* ═══ 18. AI CLAIMS ENGINE ══════════════ */}
{tab === "claims" && (
  <Section title="📋 AI Claims Processing Engine" sub="Auto-code from notes, pre-submit scrubbing, ERA auto-posting">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="📋" label="Submitted Today" value="34" sub="$42,800 total" color={C.accent} />
      <Kpi icon="🔧" label="Pre-Scrub Catches" value="7" sub="All auto-corrected" color={C.warning} />
      <Kpi icon="✅" label="Clean Claim Rate" value="97.1%" color={C.success} />
      <Kpi icon="💰" label="ERA Posted" value="$38,200" sub="Auto-reconciled" color={C.emerald} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>📋 Claims Queue</CardTitle>
        {[["Margaret Sullivan","D2740 Crown #3","$1,280","Delta Premier","submitted",C.accent],["Robert Kim","D0367 CBCT","$250","Cigna PPO","submitted",C.accent],["James Okafor","D4910 Perio Maint","$180","Aetna DMO","pending",C.warning],["Diana Patel","D8040 Ortho Comprehensive","$280","MetLife","pre-auth",C.purple],["Michael Torres","D2950+D2740 #17","$1,620","UHC","scrubbing",C.orange]].map(([p,proc,fee,payer,st,color],i) => (
          <div key={i} style={{padding:"7px 0",borderBottom:`1px solid ${C.border}`}}>
            <Row><span style={{fontSize:11,fontWeight:700}}>{p}</span><Badge color={color}>{st}</Badge></Row>
            <div style={{display:"flex",justifyContent:"space-between",fontSize:10,color:C.muted}}><span>{proc} · {payer}</span><span style={{fontWeight:700,color:C.text,fontFamily:"'JetBrains Mono'"}}>{fee}</span></div>
          </div>
        ))}
      </Card>
      <Card>
        <CardTitle>🔧 AI Pre-Scrub Catches</CardTitle>
        {[["Missing tooth # on D2740","Auto-added from chart",C.warning],["D1110 frequency violation (Cigna)","Changed to D4910 — eligible",C.danger],["D2950 bundling risk","Attached narrative justification",C.warning],["Pre-auth required D8040","Auto-submitted to MetLife",C.purple],["Missing X-ray attachment D2740","Auto-attached PA from chart",C.warning]].map(([issue,fix,color],i) => (
          <Alert key={i} color={color} icon="🔧" title={issue}>{fix}</Alert>
        ))}
      </Card>
    </Grid>
  </Section>
)}

{/* ═══ 19. CDT-TO-CPT CROSS-CODING ══════ */}
{tab === "crosscode" && (
  <Section title="🔀 CDT-to-CPT Cross-Coding Engine" sub="Auto-detect medical billing opportunities — replaces Nexus">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="🔀" label="Cross-Coded MTD" value="34" sub="$28,400 medical revenue" color={C.purple} />
      <Kpi icon="💰" label="Avg Per Patient" value="$835" sub="Additional revenue" color={C.emerald} />
      <Kpi icon="✅" label="Approval Rate" value="78%" color={C.success} />
      <Kpi icon="📋" label="CMS-1500 Generated" value="34" color={C.accent} />
    </Grid>
    <Card>
      <CardTitle>🔀 Cross-Coding Opportunities</CardTitle>
      {[["Sleep Apnea Appliance","D5988","G47.33","E0486","$2,400","$1,680","approved",C.success],["TMJ Splint Therapy","D7880","M26.60","21085","$1,800","$1,260","approved",C.success],["Oral Biopsy","D7286","K13.1","40808","$450","$380","pending",C.warning],["Bone Graft (Implant)","D7953","M27.8","21210","$1,200","$840","submitted",C.accent],["CBCT — Pathology Eval","D0367","Z13.89","70553","$250","$220","approved",C.success]].map(([proc,cdt,icd,cpt,dental,medical,st,color],i) => (
        <div key={i} style={{display:"grid",gridTemplateColumns:"1.5fr 60px 65px 55px 70px 70px 75px",padding:"8px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:11}}>
          <span style={{fontWeight:700}}>{proc}</span>
          <span style={{fontFamily:"'JetBrains Mono'",color:C.accent}}>{cdt}</span>
          <span style={{fontFamily:"'JetBrains Mono'",color:C.orange}}>{icd}</span>
          <span style={{fontFamily:"'JetBrains Mono'",color:C.purple}}>{cpt}</span>
          <span style={{fontFamily:"'JetBrains Mono'"}}>{dental}</span>
          <span style={{fontFamily:"'JetBrains Mono'",color:C.emerald,fontWeight:700}}>{medical}</span>
          <Badge color={color}>{st}</Badge>
        </div>
      ))}
    </Card>
  </Section>
)}

{/* ═══ 20. AI NECESSITY LETTERS ══════════ */}
{tab === "necessity" && (
  <Section title="📄 AI Medical Necessity Letter Generator" sub="One-click from chart data — replaces BastionGPT">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="📄" label="Letters MTD" value="18" sub="12 sec avg generation" color={C.indigo} />
      <Kpi icon="✅" label="Approval Rate" value="91%" sub="vs 64% manual" color={C.success} />
      <Kpi icon="💰" label="Revenue Recovered" value="$42,800" color={C.emerald} />
      <Kpi icon="📊" label="Data Sources" value="6" sub="Notes, X-ray, perio, meds, hx, labs" color={C.accent} />
    </Grid>
    <Card>
      <CardTitle>📄 Recent Necessity Letters</CardTitle>
      {[["James Okafor","D4341 SRP — All Quads","Perio probing 4-7mm, 18% BOP, Stage III","Delta","approved","$820",C.success],["Margaret Sullivan","D2740 Crown #3","Fracture line visible, >50% tooth structure loss","MetLife","approved","$1,280",C.success],["Robert Kim","D6010 Implant #14","Missing tooth, bone sufficient per CBCT, adjacent teeth healthy","Cigna","pending","$2,200",C.warning],["Tom Davis","D6010-D6065 Full Arch","Complete edentulism, CBCT bone eval, medical necessity for function","BCBS","submitted","$24,800",C.accent],["Diana Patel","D8080 Comprehensive Ortho","Class II div 1 malocclusion, TMJ symptoms, functional impairment","MetLife","approved","$5,500",C.success]].map(([p,proc,evidence,payer,st,val,color],i) => (
        <div key={i} style={{padding:"8px 10px",borderLeft:`3px solid ${color}30`,borderRadius:"0 8px 8px 0",marginBottom:6,background:`${color}03`}}>
          <Row><span style={{fontSize:11,fontWeight:700}}>{p}</span><div style={{display:"flex",gap:4}}><Badge color={color}>{st}</Badge><span style={{fontSize:11,fontWeight:800,color:C.emerald,fontFamily:"'JetBrains Mono'"}}>{val}</span></div></Row>
          <div style={{fontSize:10,color:C.muted}}>{proc} · {payer}</div>
          <div style={{fontSize:10,color:"#7A8298",marginTop:2}}>📋 {evidence}</div>
        </div>
      ))}
    </Card>
  </Section>
)}

{/* ═══ 21. DENIAL MANAGEMENT ═════════════ */}
{tab === "denials" && (
  <Section title="⚔️ AI Denial Management & Appeals" sub="Root cause analysis → auto-appeal with evidence — replaces DataRovers + WhiteSpace">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="⚔️" label="Open Denials" value="23" sub="$12,840 at risk" color={C.danger} />
      <Kpi icon="🤖" label="Auto-Appealed" value="18" sub="78% automated" color={C.accent} />
      <Kpi icon="✅" label="Overturn Rate" value="68%" sub="vs 32% industry" color={C.success} />
      <Kpi icon="💰" label="Recovered MTD" value="$34,200" color={C.emerald} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>⚔️ Active Denials</CardTitle>
        {[["Margaret Sullivan","D2740 Crown #3","MetLife","Missing documentation","Appeal sent — narrative + X-ray attached","$1,280",C.warning],["Robert Kim","D0367 CBCT","Cigna","Not medically necessary","Appeal + medical necessity letter auto-generated","$250",C.warning],["Diana Patel","D8080 Ortho","MetLife","Frequency limitation","Appealing — prior auth was approved","$5,500",C.danger],["Tom Davis","D6010 Implant","BCBS","Pre-auth required","Pre-auth submitted retroactively + appeal","$2,200",C.warning]].map(([p,proc,payer,reason,action,val,color],i) => (
          <div key={i} style={{padding:"8px 10px",borderLeft:`3px solid ${color}`,borderRadius:"0 8px 8px 0",marginBottom:6,background:`${color}04`}}>
            <Row><span style={{fontSize:11,fontWeight:700}}>{p}</span><span style={{fontWeight:800,color:C.danger,fontFamily:"'JetBrains Mono'",fontSize:11}}>{val}</span></Row>
            <div style={{fontSize:10,color:C.muted}}>{proc} · {payer} · Reason: <span style={{color:C.danger}}>{reason}</span></div>
            <div style={{fontSize:10,color:C.success,marginTop:2}}>🤖 {action}</div>
          </div>
        ))}
      </Card>
      <Card>
        <CardTitle>📊 Denial Root Cause Analysis</CardTitle>
        {[["Missing documentation",35,C.danger],["Frequency limitations",22,C.warning],["Medical necessity",17,C.orange],["Pre-auth required",13,C.purple],["Not covered → cross-code",9,C.accent],["Coding errors",4,C.teal]].map(([reason,pct,color],i) => (
          <div key={i} style={{marginBottom:7}}>
            <Row><span style={{fontSize:11}}>{reason}</span><span style={{fontSize:11,fontWeight:700,color,fontFamily:"'JetBrains Mono'"}}>{pct}%</span></Row>
            <Pbar v={pct} color={color} h={4} />
          </div>
        ))}
      </Card>
    </Grid>
  </Section>
)}

{/* ═══ 22. AI PHONE AGENT ════════════════ */}
{tab === "phone" && (
  <Section title="📞 AI Phone & Communication Agent" sub="24/7 AI receptionist — replaces HeyGent + Weave AI">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="📞" label="Calls Today" value="67" sub="42 AI, 25 staff" color={C.accent} />
      <Kpi icon="🤖" label="AI Resolution" value="84%" sub="No staff needed" color={C.success} />
      <Kpi icon="📅" label="Appts Booked" value="18" sub="11 AI, 7 staff" color={C.cyan} />
      <Kpi icon="💰" label="Revenue Recovered" value="$4,200" sub="Missed call follow-up" color={C.emerald} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>📞 Live Call Feed <Badge color={C.success} solid pulse>LIVE</Badge></CardTitle>
        {[["2:42 PM","New — Maria Garcia","3:12","AI","Booked NP exam 02/18. Collected insurance (Delta PPO). Sent intake SMS.","resolved",C.success],["2:38 PM","Diana Patel","1:45","AI","Confirmed Invisalign check 02/14. Asked about whitening — offered consult.","resolved",C.success],["2:31 PM","Unknown 916-555-8821","2:08","AI","Insurance implant question. Explained benefits. Booked free consult.","resolved",C.success],["2:24 PM","Tom Davis","0:45","AI","Rx refill request. Flagged for Dr. Chen approval.","escalated",C.warning],["2:18 PM","Dr. Anderson's Office","2:30","Staff","Specialist referral — transferred to Maria G.","transferred",C.accent],["1:55 PM","Missed 916-555-3344","—","AI","Auto-callback <2 min. New patient booked 02/20 8AM.","recovered",C.emerald]].map(([time,caller,dur,type,action,st,color],i) => (
          <div key={i} style={{padding:"6px 8px",borderLeft:`2px solid ${color}30`,borderRadius:"0 7px 7px 0",marginBottom:5,background:`${color}03`}}>
            <Row><div><span style={{fontSize:10,fontWeight:700}}>{caller}</span><span style={{fontSize:9,color:C.muted,marginLeft:5}}>{time} · {dur}</span></div><div style={{display:"flex",gap:3}}><Badge color={type==="AI"?C.accent:C.teal}>{type}</Badge><Badge color={color}>{st}</Badge></div></Row>
            <div style={{fontSize:9,color:"#7A8298",marginTop:1}}>{action}</div>
          </div>
        ))}
      </Card>
      <Card>
        <CardTitle>🤖 AI Agent Capabilities</CardTitle>
        {["📞 Answer with practice greeting","📅 Book/reschedule/cancel appts","🔍 Verify insurance on call","📱 Send intake forms via SMS","❓ Answer FAQs (hours, services, pricing)","🚨 After-hours emergency triage","↩️ Auto-callback missed calls <2min","📲 Reactivation calls to overdue patients","💰 Collections reminder calls","🌐 Spanish/Mandarin/Vietnamese","👤 Escalate with full context","📝 Record & transcribe all calls"].map((c,i) => (
          <Row key={i} bb={i<11}><span style={{fontSize:10}}>{c}</span><Badge color={C.success}>Active</Badge></Row>
        ))}
      </Card>
    </Grid>
  </Section>
)}

{/* ═══ 23. VOICE-TO-CODE PIPELINE ════════ */}
{tab === "voice" && (
  <Section title="🎤 Voice-to-Code Pipeline" sub="Speak naturally → SOAP note → CDT codes → claim ready">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="🎤" label="Voice Notes Today" value="24" sub="6.8 hrs saved" color={C.cyan} />
      <Kpi icon="⚡" label="Processing Speed" value="2.8 sec" color={C.success} />
      <Kpi icon="✅" label="Auto-Coded" value="98.4%" color={C.emerald} />
      <Kpi icon="📋" label="Claims Generated" value="22" sub="From voice notes" color={C.accent} />
    </Grid>
    <Card>
      <CardTitle>🎤 Recent Voice Transcriptions</CardTitle>
      <div style={{padding:"12px 14px",background:`${C.cyan}05`,borderLeft:`3px solid ${C.cyan}`,borderRadius:"0 10px 10px 0",marginBottom:10}}>
        <div style={{fontSize:10,fontWeight:800,color:C.cyan,marginBottom:6}}>Dr. Chen — Michael Torres — 2:18 PM</div>
        {[["S","Patient presents for implant follow-up #17. Reports mild tenderness, no pain. Chewing carefully.",C.accent],["O","Implant #17 stable. Tissue healing well. No suppuration. Probing 2mm circumferential. Occlusion checked.",C.teal],["A","Implant #17 osseointegration progressing normally at 8 weeks.",C.purple],["P","Continue soft diet 2 weeks. Return 4 weeks for final impression. D6058 abutment + D6065 crown.",C.orange]].map(([label,text,color],i) => (
          <div key={i} style={{marginBottom:4,padding:"4px 8px",borderLeft:`2px solid ${color}30`,borderRadius:"0 6px 6px 0"}}>
            <span style={{fontSize:9,fontWeight:800,color}}>{label}: </span>
            <span style={{fontSize:10,color:"#8892A8"}}>{text}</span>
          </div>
        ))}
        <div style={{marginTop:6,display:"flex",gap:4}}>
          <Badge color={C.accent}>D6058 — $950</Badge>
          <Badge color={C.purple}>D6065 — $1,650</Badge>
          <Badge color={C.success} solid>AUTO-CODED</Badge>
        </div>
      </div>
    </Card>
  </Section>
)}

{/* ═══ 24. AI TREATMENT PLANNING ═════════ */}
{tab === "txplan" && (
  <Section title="🧠 AI Treatment Planning Assistant" sub="Upload imaging → AI suggests diagnosis + CDT codes + fee estimates + insurance predictions">
    <Grid cols={2}>
      <Card>
        <CardTitle>🧠 AI Analysis — Robert Kim</CardTitle>
        <div style={{fontSize:10,color:C.muted,marginBottom:8}}>Based on: CBCT, periapical #14, FMX, clinical notes</div>
        {[["Missing tooth #14 — moderate bone loss mesial","K08.1","98%",C.danger],["Sufficient bone for implant (12mm)","Favorable","94%",C.success],["Adjacent #13, #15 — healthy","No contraindication","96%",C.success],["Sinus proximity — 3mm clearance","No sinus lift needed","87%",C.warning]].map(([finding,dx,conf,color],i) => (
          <Alert key={i} color={color} icon="" title={finding}>{dx} · Confidence: <strong>{conf}</strong></Alert>
        ))}
      </Card>
      <Card>
        <CardTitle>📋 AI-Generated Treatment Plan</CardTitle>
        {[{phase:"Phase 1 — Implant Placement",items:[["D6010","Implant body #14",2200,880],["D0367","CBCT",250,175]]},{phase:"Phase 2 — Restoration",items:[["D6058","Abutment placement",950,380],["D6065","Implant crown — porcelain",1650,660]]}].map((p,pi) => (
          <div key={pi} style={{marginBottom:10}}>
            <div style={{fontSize:10,fontWeight:800,color:C.purple,marginBottom:4}}>{p.phase}</div>
            {p.items.map(([cdt,desc,fee,ins],ii) => (
              <Row key={ii} bb><span style={{color:C.accent,fontFamily:"'JetBrains Mono'",fontSize:10}}>{cdt}</span><span style={{flex:1,marginLeft:8,fontSize:10}}>{desc}</span><span style={{fontWeight:700,fontFamily:"'JetBrains Mono'",fontSize:10}}>${fee}</span></Row>
            ))}
          </div>
        ))}
        <div style={{background:`${C.card2}`,borderRadius:8,padding:"10px 12px",marginTop:8}}>
          <Row><span style={{fontSize:13,fontWeight:900}}>Total</span><span style={{fontSize:13,fontWeight:900,fontFamily:"'JetBrains Mono'"}}>$5,050</span></Row>
          <Row><span style={{fontSize:11,color:C.success}}>Est. Insurance</span><span style={{fontSize:11,color:C.success,fontFamily:"'JetBrains Mono'"}}>$2,095</span></Row>
          <Row><span style={{fontSize:12,fontWeight:900,color:C.danger}}>Patient Responsibility</span><span style={{fontSize:12,fontWeight:900,color:C.danger,fontFamily:"'JetBrains Mono'"}}>$2,955</span></Row>
          <div style={{fontSize:10,color:C.muted,marginTop:4}}>💳 Payment option: $123.13/mo × 24 months</div>
        </div>
      </Card>
    </Grid>
  </Section>
)}

{/* ═══ 25. CASE ACCEPTANCE ENGINE ══════════ */}
{tab === "acceptance" && (
  <Section title="🎯 AI Case Acceptance Engine" sub="Visual treatment presentation, financing integration, AI follow-up sequences">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="🎯" label="Acceptance Rate" value="74%" sub="↑ from 58% pre-AI" color={C.success} />
      <Kpi icon="💰" label="Presented MTD" value="$186,400" color={C.accent} />
      <Kpi icon="✅" label="Accepted MTD" value="$138,000" sub="74% of presented" color={C.emerald} />
      <Kpi icon="⏳" label="Pending" value="$32,800" sub="18 pts — AI following up" color={C.warning} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>🎯 Active Presentations</CardTitle>
        {[["Robert Kim","Implant #14","$5,050","$2,095","$2,955","$123/mo","pending",3,C.warning],["Margaret Sullivan","Crown #3 + SRP","$2,100","$1,240","$860","$143/mo","accepted",0,C.success],["Sophia Adams","Invisalign Full","$5,500","$2,000","$3,500","$291/mo","pending",7,C.warning],["Tom Davis","Full Arch","$24,800","$4,000","$20,800","$433/mo","pending",14,C.danger],["Emma Rodriguez","Veneers ×4","$6,400","$0","$6,400","$266/mo","declined",5,C.danger]].map(([p,tx,total,ins,oop,mo,st,days,color],i) => (
          <div key={i} style={{padding:"8px 10px",borderLeft:`3px solid ${color}25`,borderRadius:"0 8px 8px 0",marginBottom:6,background:`${color}03`}}>
            <Row><div><span style={{fontSize:11,fontWeight:800}}>{p}</span><span style={{fontSize:9,color:C.muted,marginLeft:5}}>{days}d ago</span></div><Badge color={color}>{st}</Badge></Row>
            <div style={{fontSize:10,color:"#8892A8",marginBottom:4}}>{tx}</div>
            <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:4,fontSize:9}}>
              <Metric label="Total" value={total} /><Metric label="Insurance" value={ins} color={C.success} /><Metric label="OOP" value={oop} color={C.warning} /><Metric label="Monthly" value={mo} color={C.cyan} />
            </div>
          </div>
        ))}
      </Card>
      <Card>
        <CardTitle>📊 Objection Analysis</CardTitle>
        {[["Too expensive",42,"Auto-show monthly payment",C.danger],["Need to think",28,"3-day follow-up w/ education",C.warning],["Not sure necessary",18,"Send AI X-ray overlay",C.orange],["Want 2nd opinion",8,"Share clinical guidelines",C.accent],["Dental anxiety",4,"Offer sedation + testimonials",C.purple]].map(([obj,pct,ai,color],i) => (
          <div key={i} style={{marginBottom:7}}>
            <Row><span style={{fontSize:10}}>{obj}</span><span style={{fontSize:10,fontWeight:700,color}}>{pct}%</span></Row>
            <Pbar v={pct} color={color} h={3} />
            <div style={{fontSize:9,color:C.success,marginTop:1}}>🤖 {ai}</div>
          </div>
        ))}
      </Card>
    </Grid>
  </Section>
)}

{/* ═══ 26. TELEDENTISTRY ═════════════════ */}
{tab === "telehealth" && (
  <Section title="📹 Teledentistry Module" sub="HIPAA video consults, photo triage, remote monitoring (D9995/D9996)">
    <Grid cols={3} style={{marginBottom:14}}>
      <Kpi icon="📹" label="Video Consults MTD" value="24" sub="$4,800 billed" color={C.accent} />
      <Kpi icon="📸" label="Photo Triage" value="18" sub="12 → in-office, 6 → advice" color={C.purple} />
      <Kpi icon="✅" label="Post-Op Checks" value="34" sub="0 complications" color={C.success} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>📅 Today's Telehealth Queue</CardTitle>
        {[["Sarah Chen","Implant consult (new lead)","11:00 AM","video","waiting",C.warning],["Tom Davis","Post-op check (extraction)","1:00 PM","video","scheduled",C.accent],["Nina Fox","Photo triage (swelling)","ASAP","photo","urgent",C.danger]].map(([p,reason,time,type,st,color],i) => (
          <div key={i} style={{padding:"7px 0",borderBottom:i<2?`1px solid ${C.border}`:"none"}}>
            <Row><span style={{fontSize:11,fontWeight:700}}>{p}</span><Badge color={color}>{st}</Badge></Row>
            <div style={{fontSize:10,color:C.muted}}>{reason} · {time} · {type}</div>
          </div>
        ))}
      </Card>
      <div style={{background:"#0A0C14",borderRadius:14,padding:20,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",minHeight:180,border:`1px solid ${C.border}`}}>
        <div style={{fontSize:40,marginBottom:8}}>📹</div>
        <div style={{color:C.muted,fontSize:13,fontWeight:600,marginBottom:14}}>HIPAA-Compliant Video Room</div>
        <button style={{background:C.success,color:"#FFF",border:"none",borderRadius:10,padding:"10px 28px",fontWeight:800,fontSize:13,cursor:"pointer"}}>Start Video Consult</button>
      </div>
    </Grid>
  </Section>
)}

{/* ═══ 27. FINANCIAL CENTER ══════════════ */}
{tab === "financial" && (
  <Section title="💰 Financial Command Center" sub="P&L, cash flow, budgets, overhead breakdown, tax prep">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="💵" label="YTD Revenue" value="$498,240" sub="↑ 18% vs LY" color={C.success} />
      <Kpi icon="💰" label="Net Income MTD" value="$86,400" sub="43.2% margin" color={C.accent} />
      <Kpi icon="📊" label="Overhead %" value="57.3%" sub="Target: <59%" color={C.teal} />
      <Kpi icon="💳" label="A/P Outstanding" value="$18,200" sub="3 vendors due" color={C.warning} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>P&L Summary — February 2026</CardTitle>
        {[["Production (Gross)","$206,400","",true,C.text],["Adjustments","($7,200)","3.5%",false,C.muted],["Net Production","$199,200","",true,C.accent],["Collections","$198,240","99.5%",true,C.success],["— Staff Costs","($52,800)","26.6%",false,C.muted],["— Facility","($14,400)","7.3%",false,C.muted],["— Supplies & Lab","($25,600)","12.9%",false,C.muted],["— Marketing","($8,200)","4.1%",false,C.muted],["— Admin & Other","($12,800)","6.5%",false,C.muted],["Total Overhead","($113,800)","57.3%",true,C.warning],["NET INCOME","$84,440","42.6%",true,C.success]].map(([cat,val,pct,bold,color],i) => (
          <Row key={i} style={{borderBottom:bold?`1px solid ${C.border}`:"none"}}><span style={{fontSize:11,fontWeight:bold?800:400,color}}>{cat}</span><div style={{display:"flex",gap:10}}>{pct&&<span style={{fontSize:10,color:C.muted}}>{pct}</span>}<span style={{fontSize:11,fontWeight:bold?800:600,fontFamily:"'JetBrains Mono'",color}}>{val}</span></div></Row>
        ))}
      </Card>
      <Card>
        <CardTitle>Overhead Breakdown</CardTitle>
        {[["Staff (salaries + benefits)",26.6,28,C.success],["Supplies & Lab",12.9,14,C.success],["Facility (rent + utilities)",7.3,8,C.success],["Admin & Technology",6.5,4,C.danger],["Marketing",4.1,5,C.success]].map(([cat,pct,target,color],i) => (
          <div key={i} style={{marginBottom:8}}>
            <Row><span style={{fontSize:11}}>{cat}</span><span style={{fontSize:11,fontWeight:700,color}}>{pct}% <span style={{color:C.muted,fontWeight:400}}>/ {target}%</span></span></Row>
            <Pbar v={pct/target*100} color={color} h={4} />
          </div>
        ))}
      </Card>
    </Grid>
  </Section>
)}

{/* ═══ 28. PATIENT FINANCING ═════════════ */}
{tab === "financing" && (
  <Section title="💳 Patient Financing Engine" sub="In-house payment plans, auto-charge, no third-party fees">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="💳" label="Active Plans" value="47" sub="$284K outstanding" color={C.accent} />
      <Kpi icon="✅" label="On-Time Rate" value="94%" sub="3 past due" color={C.success} />
      <Kpi icon="💰" label="Collected MTD" value="$42,800" color={C.teal} />
      <Kpi icon="📊" label="Avg Plan" value="$3,240" sub="12-month avg" color={C.purple} />
    </Grid>
    <Card>
      {[["Margaret Sullivan","Implant #14","$2,600","$216.67/mo","$1,950","3/12","Current",C.success],["Diana Patel","Invisalign","$3,300","$275/mo","$2,475","3/12","Current",C.success],["Michael Torres","Graft + implant","$475","$158.33/mo","$316.67","1/3","Current",C.success],["Tom Davis","Full arch","$12,400","$516.67/mo","$9,300","6/24","Late 5d",C.warning]].map(([p,tx,total,mo,rem,pmts,st,color],i) => (
        <div key={i} style={{display:"grid",gridTemplateColumns:"1.2fr 1fr 70px 80px 70px 50px 70px",padding:"7px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:11}}>
          <span style={{fontWeight:700}}>{p}</span><span style={{color:C.muted}}>{tx}</span><span style={{fontFamily:"'JetBrains Mono'"}}>{total}</span><span style={{fontFamily:"'JetBrains Mono'"}}>{mo}</span><span style={{fontFamily:"'JetBrains Mono'"}}>{rem}</span><span>{pmts}</span><Badge color={color}>{st}</Badge>
        </div>
      ))}
    </Card>
  </Section>
)}

{/* ═══ 29. MARKETING SUITE ═══════════════ */}
{tab === "marketing" && (
  <Section title="📣 Marketing Suite" sub="Content calendar, ad management, review monitoring, ROI attribution">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="👤" label="New Patients Feb" value="38" sub="Target: 45" color={C.accent} />
      <Kpi icon="💰" label="Marketing Spend" value="$8,200" sub="4.1% of revenue" color={C.warning} />
      <Kpi icon="📊" label="Cost/Patient" value="$216" sub="Target: <$300" color={C.success} />
      <Kpi icon="⭐" label="Google Rating" value="4.9" sub="234 reviews" color={C.teal} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>📊 Channel Performance</CardTitle>
        {[["Google Ads","$3,200",14,"$229","8.2x",C.accent],["Meta/Instagram","$2,100",8,"$263","5.4x",C.purple],["Google Organic","$800",6,"$133","12.1x",C.success],["Patient Referrals","$1,500",6,"$250","9.8x",C.teal],["Direct Mail","$600",2,"$300","4.2x",C.muted],["Walk-ins","$0",2,"$0","∞",C.orange]].map(([ch,spend,pts,cpa,roi,color],i) => (
          <div key={i} style={{display:"grid",gridTemplateColumns:"1.5fr 65px 40px 55px 45px",padding:"5px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:11}}>
            <span style={{fontWeight:600}}>{ch}</span><span style={{fontFamily:"'JetBrains Mono'"}}>{spend}</span><span style={{fontWeight:700}}>{pts}</span><span style={{fontFamily:"'JetBrains Mono'"}}>{cpa}</span><span style={{fontWeight:800,color}}>{roi}</span>
          </div>
        ))}
      </Card>
      <Card>
        <CardTitle>📅 Content Calendar</CardTitle>
        {[["Mon","Before/after implant photo","IG+FB","posted",C.success],["Tue","3 Signs You Need RCT video","TikTok","scheduled",C.accent],["Wed","Patient testimonial — Diana P.","IG+FB","scheduled",C.accent],["Thu","Blog: Implants vs Bridges","Website","draft",C.warning],["Fri","Team BTS reel","IG+TikTok","idea",C.muted]].map(([day,content,platform,st,color],i) => (
          <Row key={i} bb={i<4}><div style={{display:"flex",alignItems:"center",gap:6}}><span style={{fontSize:10,fontWeight:800,color:C.accent,width:25}}>{day}</span><div><div style={{fontSize:10,fontWeight:600}}>{content}</div><div style={{fontSize:9,color:C.muted}}>{platform}</div></div></div><Badge color={color}>{st}</Badge></Row>
        ))}
      </Card>
    </Grid>
  </Section>
)}

{/* ═══ 30. PATIENT NPS ═══════════════════ */}
{tab === "nps" && (
  <Section title="⭐ Patient Satisfaction & NPS" sub="Post-visit surveys, sentiment analysis, review routing">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="⭐" label="NPS Score" value="78" sub="Excellent (target: 70+)" color={C.success} />
      <Kpi icon="😊" label="Promoters" value="82%" sub="Score 9-10" color={C.success} />
      <Kpi icon="😐" label="Passives" value="14%" sub="Score 7-8" color={C.warning} />
      <Kpi icon="😞" label="Detractors" value="4%" sub="3 patients" color={C.danger} />
    </Grid>
    <Alert color={C.success} icon="🤖" title="AI Review Routing">Patients scoring 9-10 auto-receive Google review link. Scores ≤6 route to office manager. AI generates draft response for each review within 30 minutes.</Alert>
  </Section>
)}

{/* ═══ 31. FEE OPTIMIZER ═════════════════ */}
{tab === "fees" && (
  <Section title="💲 AI Fee Schedule Optimizer" sub="UCR analysis, PPO fee negotiation, procedure profitability">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="💲" label="Revenue Opportunity" value="$42,800" sub="From fee optimization" color={C.emerald} />
      <Kpi icon="📊" label="Below UCR" value="34" sub="Of 180 active codes" color={C.warning} />
      <Kpi icon="📈" label="Fee vs UCR" value="88%" sub="Target: 95%" color={C.accent} />
      <Kpi icon="🔄" label="PPO Contracts" value="8" sub="3 need renegotiation" color={C.purple} />
    </Grid>
    <Card>
      <CardTitle>Fee Schedule — Top Procedures</CardTitle>
      <div style={{display:"grid",gridTemplateColumns:"60px 2fr 80px 80px 80px 80px 70px",padding:"6px 0",borderBottom:`2px solid ${C.border}`,fontSize:9,fontWeight:700,color:C.muted,letterSpacing:0.5,textTransform:"uppercase"}}>
        {["CDT","Procedure","Your Fee","UCR 80th","Delta","Cigna","Action"].map(h => <div key={h}>{h}</div>)}
      </div>
      {[["D0120","Periodic Eval","$52","$65","$48","$45","↑20%",C.warning],["D1110","Adult Prophy","$110","$142","$95","$88","↑23%",C.warning],["D2391","Composite 1-surf","$195","$228","$165","$158","↑14%",C.warning],["D2740","Crown Porcelain","$1,280","$1,420","$980","$920","✓ Good",C.success],["D4341","SRP 4+ teeth","$245","$290","$205","$195","↑16%",C.warning],["D6010","Implant Body","$2,200","$2,480","$1,650","$1,580","✓ Good",C.success]].map(([code,desc,fee,ucr,delta,cigna,action,color],i) => (
        <div key={i} style={{display:"grid",gridTemplateColumns:"60px 2fr 80px 80px 80px 80px 70px",padding:"7px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:11}}>
          <span style={{fontFamily:"'JetBrains Mono'",fontWeight:700,color:C.purple}}>{code}</span>
          <span style={{color:"#8892A8"}}>{desc}</span>
          <span style={{fontWeight:700,fontFamily:"'JetBrains Mono'"}}>{fee}</span>
          <span style={{color:C.success,fontFamily:"'JetBrains Mono'"}}>{ucr}</span>
          <span style={{color:C.warning,fontFamily:"'JetBrains Mono'"}}>{delta}</span>
          <span style={{color:C.danger,fontFamily:"'JetBrains Mono'"}}>{cigna}</span>
          <Badge color={color}>{action}</Badge>
        </div>
      ))}
    </Card>
  </Section>
)}

{/* ═══ 32. PROVIDER INTEL ════════════════ */}
{tab === "provider" && (
  <Section title="👨‍⚕️ Provider Performance Intelligence" sub="Production, coding patterns, speed metrics, compensation modeling">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="👨‍⚕️" label="Providers" value="3" sub="+ 2 hygienists" color={C.accent} />
      <Kpi icon="💰" label="Production MTD" value="$198,200" color={C.emerald} />
      <Kpi icon="📊" label="Avg Prod/Day" value="$8,260" color={C.success} />
      <Kpi icon="🎯" label="Avg Acceptance" value="74%" sub="↑ 6% with AI" color={C.cyan} />
    </Grid>
    <Card>
      <CardTitle>Provider Scorecard</CardTitle>
      <div style={{display:"grid",gridTemplateColumns:"1.4fr repeat(7,1fr)",padding:"6px 0",borderBottom:`2px solid ${C.border}`,fontSize:9,fontWeight:700,color:C.muted,letterSpacing:0.5,textTransform:"uppercase"}}>
        {["Provider","Production","Prod/Day","Patients","Case Accept","Avg Tx","Collections","Score"].map(h => <div key={h}>{h}</div>)}
      </div>
      {[["Dr. Chen|Implantologist","$98,400","$8,200","142","78%","$2,840","$96,200","A+",C.success],["Dr. Park|Orthodontist","$62,800","$7,850","98","72%","$1,680","$61,400","A",C.success],["Dr. Okafor|Oral Surgeon","$37,000","$9,250","48","68%","$3,420","$36,200","A-",C.success],["Sarah M.|Hygienist","$18,400","$920","164","—","$112","$18,100","A",C.success],["Jamie L.|Hyg/Perio","$16,800","$840","148","—","$114","$16,500","B+",C.warning]].map(([name,prod,perDay,pts,accept,avgTx,coll,score,color],i) => (
        <div key={i} style={{display:"grid",gridTemplateColumns:"1.4fr repeat(7,1fr)",padding:"7px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:11}}>
          <div><div style={{fontWeight:800}}>{name.split("|")[0]}</div><div style={{fontSize:9,color:C.muted}}>{name.split("|")[1]}</div></div>
          <span style={{fontWeight:700,fontFamily:"'JetBrains Mono'"}}>{prod}</span>
          <span style={{fontFamily:"'JetBrains Mono'"}}>{perDay}</span>
          <span>{pts}</span>
          <span style={{fontWeight:700,color:parseInt(accept)>=75?C.success:parseInt(accept)>=65?C.warning:C.muted}}>{accept}</span>
          <span style={{fontFamily:"'JetBrains Mono'"}}>{avgTx}</span>
          <span style={{color:C.success,fontFamily:"'JetBrains Mono'"}}>{coll}</span>
          <span style={{fontWeight:900,color,fontSize:14}}>{score}</span>
        </div>
      ))}
    </Card>
  </Section>
)}

{/* ═══ 33. PAYER INTELLIGENCE ════════════ */}
{tab === "payer" && (
  <Section title="🏦 Payer Intelligence Dashboard" sub="AI learns from every claim — payer profiles, playbooks, revenue opportunities">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="🏦" label="Payer Profiles" value="340+" color={C.accent} />
      <Kpi icon="📊" label="Claims Analyzed" value="12,400+" color={C.purple} />
      <Kpi icon="⏱️" label="Avg Days to Pay" value="14.2" color={C.success} />
      <Kpi icon="💰" label="Opportunities" value="$18,400" sub="Revenue detected" color={C.emerald} />
    </Grid>
    <Card>
      <CardTitle>🏦 Top Payer Scorecard</CardTitle>
      {[["Delta Dental Premier","92%","12d","4%","94%","Medium","A+",C.success],["Cigna PPO","86%","18d","8%","88%","High","A",C.success],["MetLife PPO","81%","22d","12%","82%","High","B+",C.warning],["Aetna DMO","78%","16d","9%","75%","Low","B",C.warning],["UHC PPO","74%","28d","15%","71%","High","C+",C.danger],["BCBS FEP","88%","14d","6%","90%","Medium","A",C.success]].map(([payer,approve,days,denial,reimb,xcode,score,color],i) => (
        <div key={i} style={{display:"grid",gridTemplateColumns:"1.5fr 65px 50px 55px 60px 65px 45px",padding:"7px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:11}}>
          <span style={{fontWeight:700}}>{payer}</span>
          <span style={{color:C.success}}>{approve}</span>
          <span style={{fontFamily:"'JetBrains Mono'"}}>{days}</span>
          <span style={{color:parseFloat(denial)>10?C.danger:C.warning}}>{denial}</span>
          <span style={{fontFamily:"'JetBrains Mono'"}}>{reimb}</span>
          <span style={{color:xcode==="High"?C.purple:C.muted}}>{xcode}</span>
          <span style={{fontWeight:900,color,fontSize:13}}>{score}</span>
        </div>
      ))}
    </Card>
  </Section>
)}

{/* ═══ 34. MULTI-LOCATION ════════════════ */}
{tab === "multiloc" && (
  <Section title="🏢 Multi-Location Command Center" sub="Side-by-side performance, centralized management, location benchmarking">
    <Card>
      <div style={{display:"grid",gridTemplateColumns:"1.5fr repeat(6,1fr)",padding:"8px 0",borderBottom:`2px solid ${C.border}`,fontSize:9,fontWeight:700,color:C.muted,letterSpacing:0.6,textTransform:"uppercase"}}>
        {["Location","Production","Collections%","New Pts","Accept%","Overhead","Net Margin"].map(h => <div key={h}>{h}</div>)}
      </div>
      {[["Auburn Main","$198,200","96.2%","38","72%","57.3%","42.7%","↑"],["Roseville","$142,800","94.8%","28","68%","61.2%","33.6%","↑"],["Folsom","$168,400","97.1%","34","74%","55.8%","41.3%","↑"],["Rocklin (New)","$84,200","92.4%","22","64%","68.4%","24.0%","↑"]].map(([loc,prod,coll,np,accept,overhead,margin,trend],i) => (
        <div key={i} style={{display:"grid",gridTemplateColumns:"1.5fr repeat(6,1fr)",padding:"10px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:12}}>
          <span style={{fontWeight:800}}>{loc} <span style={{color:C.success}}>{trend}</span></span>
          <span style={{fontWeight:700,fontFamily:"'JetBrains Mono'"}}>{prod}</span>
          <span style={{color:parseFloat(coll)>=96?C.success:C.warning,fontWeight:700}}>{coll}</span>
          <span style={{fontWeight:700}}>{np}</span>
          <span style={{color:parseInt(accept)>=70?C.success:C.warning,fontWeight:700}}>{accept}</span>
          <span style={{color:parseFloat(overhead)<60?C.success:C.danger,fontWeight:700}}>{overhead}</span>
          <span style={{fontWeight:800,color:parseFloat(margin)>=40?C.success:parseFloat(margin)>=30?C.warning:C.danger}}>{margin}</span>
        </div>
      ))}
      <div style={{display:"grid",gridTemplateColumns:"1.5fr repeat(6,1fr)",padding:"10px 0",background:`${C.card2}`,fontWeight:800,fontSize:12}}>
        <span>TOTAL (4 Locations)</span>
        <span style={{fontFamily:"'JetBrains Mono'"}}>$593,600</span>
        <span>95.4%</span><span>122</span><span>70%</span><span>58.7%</span><span style={{color:C.success}}>37.9%</span>
      </div>
    </Card>
  </Section>
)}

{/* ═══ 35. COMPLIANCE AUDIT ══════════════ */}
{tab === "compliance" && (
  <Section title="🛡️ AI Compliance & Coding Audit" sub="Real-time audit, documentation completeness, HIPAA compliance">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="🛡️" label="Compliance Score" value="96.4%" sub="Excellent" color={C.success} />
      <Kpi icon="📋" label="Charts Audited" value="342" sub="100% auto-audited" color={C.accent} />
      <Kpi icon="⚠️" label="Issues Found" value="12" sub="8 resolved, 4 pending" color={C.warning} />
      <Kpi icon="💰" label="Risk Avoided" value="$28,400" color={C.emerald} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>🔍 Coding Audit — This Week</CardTitle>
        {[["D2950 without crown code","Dr. Chen","2 cases","high","Unbundling risk — D2740 attached",C.danger],["D0220 PA + D0330 Pano same day","Dr. Park","1 case","med","Modifier documentation added",C.warning],["D4341 SRP without perio chart","Sarah RDH","3 cases","high","Perio charts attached retroactively",C.danger],["Narrative missing D2740 >$1,200","Dr. Chen","2 cases","med","AI auto-generated narratives",C.warning]].map(([issue,prov,cases,risk,action,color],i) => (
          <Alert key={i} color={color} icon="🔍" title={<>{issue} <Badge color={color}>{risk}</Badge></>}>{prov} · {cases} — 🤖 {action}</Alert>
        ))}
      </Card>
      <Card>
        <CardTitle>📋 Documentation Completeness</CardTitle>
        {[["SOAP notes signed",98,C.success],["Perio charts with SRP",88,C.warning],["Consent forms on file",100,C.success],["X-rays attached to claims",95,C.success],["Medical history <12mo",82,C.warning],["Narratives on major procs",91,C.success],["Pre-auth documentation",96,C.success]].map(([doc,pct,color],i) => (
          <div key={i} style={{marginBottom:6}}>
            <Row><span style={{fontSize:10}}>{doc}</span><span style={{fontSize:10,fontWeight:700,color}}>{pct}%</span></Row>
            <Pbar v={pct} color={color} h={3} />
          </div>
        ))}
      </Card>
    </Grid>
  </Section>
)}

{/* ═══ 36. UNIFIED BUSINESS INTELLIGENCE ═ */}
{tab === "bi" && (
  <Section title="📊 Unified Business Intelligence" sub="Cross-module analytics, AI value attribution, competitive benchmarking, strategic recommendations">
    <Grid cols={4} style={{marginBottom:14}}>
      <Kpi icon="💰" label="Annualized Revenue" value="$2.38M" sub="Run rate" color={C.emerald} />
      <Kpi icon="📈" label="Growth Rate" value="+18%" sub="YoY" color={C.success} />
      <Kpi icon="🏆" label="Percentile" value="92nd" sub="vs national" color={C.accent} />
      <Kpi icon="🤖" label="AI Impact" value="$384K" sub="Annual value from AI" color={C.purple} />
    </Grid>
    <Grid cols={2}>
      <Card>
        <CardTitle>🤖 AI Value Attribution — Monthly</CardTitle>
        {[["🔬 AI Diagnostics","$8,400",C.accent],["📞 AI Phone Agent","$18,400",C.cyan],["📋 Claims Engine","$6,200",C.teal],["🔀 Cross-Coding","$28,400",C.purple],["⚔️ Denial Appeals","$34,200",C.warning],["🎯 Case Acceptance","$22,800",C.success],["📅 Smart Scheduling","$12,400",C.orange],["🎤 Voice Pipeline","$4,800",C.rose],["💲 Fee Optimization","$3,600",C.lime],["🛡️ Compliance","$2,400",C.sky]].map(([mod,impact,color],i) => (
          <Row key={i} bb>
            <span style={{fontSize:11}}>{mod}</span>
            <span style={{fontSize:12,fontWeight:900,color,fontFamily:"'JetBrains Mono'"}}>{impact}</span>
          </Row>
        ))}
        <Row style={{paddingTop:8,borderTop:`2px solid ${C.border}`,marginTop:6}}>
          <span style={{fontSize:14,fontWeight:900}}>Total Monthly AI Value</span>
          <span style={{fontSize:18,fontWeight:900,color:C.emerald,fontFamily:"'JetBrains Mono'"}}>$141,600</span>
        </Row>
        <div style={{textAlign:"center",fontSize:11,color:C.muted,marginTop:4}}>= <strong style={{color:C.emerald,fontSize:14}}>$1.7M/year</strong> from AI — at <strong style={{color:C.accent}}>$497/mo</strong></div>
      </Card>
      <div style={{display:"flex",flexDirection:"column",gap:10}}>
        <Card>
          <CardTitle>📊 Practice vs Benchmarks</CardTitle>
          {[["Production/Operatory","$24,800","$18,200","94th",C.success],["Collection Rate","99.5%","96.2%","98th",C.success],["Overhead %","57.3%","62.8%","88th",C.success],["New Patients/Mo","38","28","86th",C.success],["Case Acceptance","74%","58%","92nd",C.success],["Days in A/R","18.4","32","95th",C.success],["Hygiene Reappt","88%","82%","78th",C.warning],["Patient Retention","91%","85%","84th",C.success]].map(([metric,yours,bench,pctile,color],i) => (
            <div key={i} style={{display:"grid",gridTemplateColumns:"1.5fr 65px 65px 55px",padding:"4px 0",borderBottom:`1px solid ${C.border}`,alignItems:"center",fontSize:10}}>
              <span>{metric}</span>
              <span style={{fontWeight:800,fontFamily:"'JetBrains Mono'"}}>{yours}</span>
              <span style={{color:C.muted,fontFamily:"'JetBrains Mono'"}}>{bench}</span>
              <Badge color={color}>{pctile}</Badge>
            </div>
          ))}
        </Card>
        <div style={{background:`linear-gradient(135deg, ${C.accent}08, ${C.purple}08)`,border:`1px solid ${C.accent}15`,borderRadius:12,padding:"14px 16px"}}>
          <div style={{fontSize:11,fontWeight:800,color:C.accent,marginBottom:6}}>🧠 AI Strategic Recommendations</div>
          {["Hygiene reappt at 88% — implement AI phone recall for non-responders","Cross-coding at 34/mo — potential 60+ with TMJ, sleep, trauma detection","Rocklin 68.4% overhead — share hygienist with Auburn until breakeven","SEO ROI at 12.1x — increase AI blog content to 2x/week"].map((r,i) => (
            <div key={i} style={{fontSize:9,color:"#7A8298",padding:"3px 0 3px 10px",borderLeft:`2px solid ${C.accent}25`,marginBottom:4,lineHeight:1.4}}>💡 {r}</div>
          ))}
        </div>
      </div>
    </Grid>
  </Section>
)}

      </div>
      <style>{`*{box-sizing:border-box;margin:0;padding:0}button{transition:0.12s}button:hover{filter:brightness(1.1)}@keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}::-webkit-scrollbar{width:4px}::-webkit-scrollbar-track{background:${C.bg}}::-webkit-scrollbar-thumb{background:#2A2E3E;border-radius:3px}`}</style>
    </div>
  );
}
