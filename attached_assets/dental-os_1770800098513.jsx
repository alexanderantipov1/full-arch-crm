import { useState, useEffect, useRef, useCallback } from "react";

// ═══════════════════════════════════════════════
// AI C-SUITE AGENTS
// ═══════════════════════════════════════════════

const AI_AGENTS = {
  ceo: { name: "Chief Executive AI", short: "CEO", icon: "👔", color: "#D4A853", gradient: "linear-gradient(135deg, #D4A853, #B8860B)", desc: "Vision, strategy & growth trajectory", personality: "I see the big picture. Let me align your practice vision with market reality and build your empire roadmap." },
  coo: { name: "Chief Operations AI", short: "COO", icon: "⚙️", color: "#4ECDC4", gradient: "linear-gradient(135deg, #4ECDC4, #2BA89E)", desc: "Systems, workflows & daily execution", personality: "Systems run empires. I'll build your SOPs, optimize chair time, and make your practice run like clockwork." },
  cmo: { name: "Chief Marketing AI", short: "CMO", icon: "📣", color: "#FF6B6B", gradient: "linear-gradient(135deg, #FF6B6B, #D44444)", desc: "Patient acquisition & brand growth", personality: "Patients don't find you — you attract them. I'll build your Grand Slam Offer, funnels, and referral engine." },
  cfo: { name: "Chief Financial AI", short: "CFO", icon: "💰", color: "#95E77E", gradient: "linear-gradient(135deg, #95E77E, #6BBF59)", desc: "Revenue, cash flow & financial modeling", personality: "Every dollar has a job. I'll model your P&L, optimize collections, and show you exactly when you'll hit targets." },
  chro: { name: "Chief People AI", short: "CHRO", icon: "👥", color: "#A78BFA", gradient: "linear-gradient(135deg, #A78BFA, #7C5DCC)", desc: "Hiring, training & team culture", personality: "Your team IS your practice. I'll help you hire A-players, build culture, and create compensation that retains." },
  clo: { name: "Chief Legal AI", short: "CLO", icon: "⚖️", color: "#F59E0B", gradient: "linear-gradient(135deg, #F59E0B, #D97706)", desc: "Compliance, contracts & risk", personality: "Protect what you build. I'll guide entity setup, HIPAA compliance, contracts, and insurance credentialing." },
};

// ═══════════════════════════════════════════════
// PATH DATA — DE NOVO / EXISTING / ACQUISITION
// ═══════════════════════════════════════════════

const PATHS = {
  denovo: {
    id: "denovo", name: "Open New Practice", icon: "🏗️", tagline: "Build from scratch", color: "#D4A853",
    desc: "Start a brand new dental office from zero. Site selection, buildout, licensing, hiring, marketing launch — the complete playbook.",
    phases: [
      { phase: 1, name: "Foundation", duration: "Month 1-2", agent: "ceo",
        tasks: [
          { id: "d1", task: "Define your practice vision & specialty mix", agent: "ceo", dept: "strategy", status: "not_started", details: "Choose: general + implants? Multi-specialty? Ortho-focused? Your vision determines everything downstream.", subtasks: ["Write 1-page vision statement", "Define target patient avatar", "Choose specialty mix (implants, ortho, perio, surgery)", "Set 1-year, 3-year, 5-year revenue targets"] },
          { id: "d2", task: "Create financial model & secure funding", agent: "cfo", dept: "finance", status: "not_started", details: "Build your P&L projection, determine startup costs, and secure SBA loan or private financing.", subtasks: ["Complete startup cost worksheet ($350K-$1.2M typical)", "Build 3-year P&L projection model", "Apply for SBA 7(a) loan or bank financing", "Set up business bank accounts & credit lines"] },
          { id: "d3", task: "Choose entity structure & register business", agent: "clo", dept: "legal", status: "not_started", details: "LLC, S-Corp, or PC? Each has different tax and liability implications for dental practices.", subtasks: ["Consult with dental CPA on entity type", "Register LLC/PC with state", "Obtain EIN from IRS", "Register for state tax ID"] },
          { id: "d4", task: "Site selection & lease negotiation", agent: "coo", dept: "operations", status: "not_started", details: "Location = destiny. Analyze demographics, competition density, traffic patterns, and visibility.", subtasks: ["Run demographic analysis for 3-5 target areas", "Evaluate 5+ potential locations", "Negotiate LOI with landlord (aim for TI allowance)", "Engage dental-specific real estate attorney for lease review"] },
          { id: "d5", task: "Apply for dental licenses & DEA registration", agent: "clo", dept: "legal", status: "not_started", details: "State dental license, DEA registration, NPI number, facility permits — start early, these take weeks.", subtasks: ["Verify state dental license active & current", "Apply for DEA registration", "Obtain NPI number for practice", "Apply for facility/business license", "Register with state dental board"] },
        ]
      },
      { phase: 2, name: "Buildout", duration: "Month 2-4", agent: "coo",
        tasks: [
          { id: "d6", task: "Design office layout & hire contractor", agent: "coo", dept: "operations", status: "not_started", details: "4-6 operatories minimum. Plan for growth — plumb for 8 even if you build 5.", subtasks: ["Hire dental-specific architect/designer", "Plan operatory count (start 4-6, plumb for 8+)", "Select contractor with dental buildout experience", "Design patient flow: reception → consult → ops → checkout"] },
          { id: "d7", task: "Order equipment & technology stack", agent: "coo", dept: "operations", status: "not_started", details: "CBCT, digital scanners, practice management software, patient communication platform.", subtasks: ["Order CBCT machine (Carestream/Planmeca)", "Order digital scanner (iTero/3Shape)", "Select & set up PMS (Dentrix/Eaglesoft/Open Dental)", "Order chairs, units, compressor, vacuum, sterilization", "Set up digital imaging system (sensors, pano)"] },
          { id: "d8", task: "Insurance credentialing (start NOW — takes 90+ days)", agent: "cfo", dept: "finance", status: "not_started", details: "Start credentialing immediately. Delta, Cigna, MetLife, Aetna — each takes 60-120 days.", subtasks: ["Compile credentialing packet (license, NPI, DEA, malpractice)", "Submit applications to top 8-10 insurance panels", "Track application status weekly", "Set up fee schedules for each plan"] },
          { id: "d9", task: "Build brand identity & website", agent: "cmo", dept: "marketing", status: "not_started", details: "Logo, brand colors, website with online booking, Google Business Profile — your digital front door.", subtasks: ["Design logo & brand guidelines", "Build website with online booking integration", "Set up Google Business Profile", "Create social media profiles (Instagram, Facebook, TikTok)", "Professional photography of space (during buildout for 'coming soon' content)"] },
          { id: "d10", task: "Begin hiring core team", agent: "chro", dept: "hr", status: "not_started", details: "Office manager first (they help hire everyone else). Then front desk, hygienist, assistant.", subtasks: ["Write job descriptions for all roles", "Post on dental-specific job boards (DentalPost, Indeed)", "Hire office manager FIRST (month 2-3)", "Hire front desk coordinator", "Hire 1-2 dental assistants", "Hire 1 hygienist (scale up later)"] },
        ]
      },
      { phase: 3, name: "Pre-Launch", duration: "Month 4-5", agent: "cmo",
        tasks: [
          { id: "d11", task: "Launch pre-opening marketing campaign", agent: "cmo", dept: "marketing", status: "not_started", details: "Build buzz 6-8 weeks before opening. Grand Slam Offer, local partnerships, social media blitz.", subtasks: ["Create Grand Slam Offer (Free CBCT + Consult + 3D Preview)", "Launch Google Ads campaign (target: implant keywords)", "Launch Meta/Instagram ads (before/after + offer)", "Partner with 10+ local businesses for cross-referrals", "Direct mail to 5,000 households in 3-mile radius", "Host 'VIP Preview' event for local influencers & referring docs"] },
          { id: "d12", task: "Set up all SOPs & workflows", agent: "coo", dept: "operations", status: "not_started", details: "Document every process: patient intake, scheduling, treatment presentation, billing, follow-up.", subtasks: ["Create new patient intake workflow (digital forms)", "Build scheduling templates & block scheduling protocol", "Write treatment presentation scripts (AI-assisted)", "Set up billing & collections workflow", "Create morning huddle template", "Document sterilization & OSHA protocols"] },
          { id: "d13", task: "Train entire team (2-week intensive)", agent: "chro", dept: "hr", status: "not_started", details: "Software training, customer service scripts, treatment coordination, emergency protocols.", subtasks: ["PMS software training (3 days)", "Phone scripts & new patient call training", "Treatment coordination & case acceptance training", "Emergency protocols & OSHA compliance", "Role-play patient scenarios", "Team culture & values alignment workshop"] },
          { id: "d14", task: "Set up patient communication automations", agent: "cmo", dept: "marketing", status: "not_started", details: "Welcome sequences, appointment reminders, post-op follow-ups, recall campaigns — all automated.", subtasks: ["Set up appointment reminder sequence (SMS + email)", "Create new patient welcome automation (5-touch)", "Build post-treatment follow-up sequences", "Configure recall/reactivation campaigns", "Set up review request automation", "Build referral ask sequence"] },
          { id: "d15", task: "HIPAA compliance & malpractice insurance", agent: "clo", dept: "legal", status: "not_started", details: "HIPAA policies, BAAs with all vendors, malpractice coverage, workers comp, general liability.", subtasks: ["Complete HIPAA compliance program", "Sign BAAs with all technology vendors", "Obtain malpractice insurance", "Obtain general liability insurance", "Set up workers compensation coverage", "Create patient consent forms & financial agreements"] },
        ]
      },
      { phase: 4, name: "Grand Opening", duration: "Month 5-6", agent: "ceo",
        tasks: [
          { id: "d16", task: "LAUNCH — Grand opening event & first patients", agent: "ceo", dept: "strategy", status: "not_started", details: "You've built it. Now execute. Grand opening event, first patients, first treatments, first revenue.", subtasks: ["Host grand opening event (refreshments, tours, free screenings)", "See first 20-30 patients in week 1", "Daily team huddles — identify and fix issues fast", "Track all KPIs from day 1 (new patients, production, collections)"] },
          { id: "d17", task: "Activate paid advertising at full budget", agent: "cmo", dept: "marketing", status: "not_started", details: "Scale Google + Meta ads to full budget. Target: 40-60 new patients/month within 90 days.", subtasks: ["Scale Google Ads to $3-5K/month", "Scale Meta ads to $2-3K/month", "Launch YouTube pre-roll ads", "Activate referral bonus program ($250-500 per referral)", "Begin SEO content strategy (blog + video)"] },
          { id: "d18", task: "Implement KPI tracking & weekly reviews", agent: "cfo", dept: "finance", status: "not_started", details: "What gets measured gets managed. Track production, collections, new patients, case acceptance weekly.", subtasks: ["Set up daily production tracking dashboard", "Weekly financial review meeting (every Monday)", "Monthly P&L review with dental CPA", "Track case acceptance rate by provider", "Monitor marketing ROI by channel", "Benchmark against 6-month plan"] },
        ]
      },
    ],
  },
  existing: {
    id: "existing", name: "Optimize Existing Practice", icon: "🏥", tagline: "Scale what you have", color: "#4ECDC4",
    desc: "You have a practice. Now 10x it. Fix bottlenecks, add specialties, increase case acceptance, build systems, and scale revenue.",
    phases: [
      { phase: 1, name: "Audit & Diagnose", duration: "Week 1-2", agent: "ceo",
        tasks: [
          { id: "e1", task: "Complete practice health audit (30-point diagnostic)", agent: "ceo", dept: "strategy", status: "not_started", details: "Before fixing anything, know exactly where you stand. This audit reveals your biggest bottlenecks.", subtasks: ["Run production report (last 12 months by provider)", "Analyze collections rate (target: 98%+)", "Calculate case acceptance rate by procedure type", "Audit new patient flow (source, conversion, no-shows)", "Review overhead ratio (target: <60%)", "Assess chair utilization (target: >85%)"] },
          { id: "e2", task: "Financial deep dive — find the leaks", agent: "cfo", dept: "finance", status: "not_started", details: "Most practices leak $200K-$500K/year in undiagnosed treatment, bad collections, and fee schedule gaps.", subtasks: ["Run aging report — chase outstanding A/R", "Audit fee schedules vs. UCR rates", "Identify undiagnosed treatment in patient base", "Review insurance write-offs by plan", "Analyze overhead line-by-line", "Calculate true hourly production per chair"] },
          { id: "e3", task: "Team performance assessment", agent: "chro", dept: "hr", status: "not_started", details: "Your team either scales you or stalls you. Assess everyone against role expectations.", subtasks: ["Review each team member against KPIs", "Identify A-players, B-players, and mismatches", "Assess treatment coordinator effectiveness", "Evaluate front desk conversion rate (calls → booked)", "Survey team satisfaction & engagement", "Identify training gaps"] },
          { id: "e4", task: "Marketing & patient acquisition audit", agent: "cmo", dept: "marketing", status: "not_started", details: "Where are patients coming from? What's the cost? What's the conversion rate at each step?", subtasks: ["Track patient source for last 6 months", "Calculate CAC by channel", "Audit Google Business Profile (reviews, photos, posts)", "Review website conversion rate", "Analyze phone call handling (mystery shop yourself)", "Assess online reputation (reviews, rating)"] },
        ]
      },
      { phase: 2, name: "Quick Wins", duration: "Week 2-6", agent: "coo",
        tasks: [
          { id: "e5", task: "Fix case acceptance — implement AI presentation scripts", agent: "coo", dept: "operations", status: "not_started", details: "Most practices accept 40-50% of cases. Get to 70%+ with better scripting and visual aids.", subtasks: ["Train on same-day treatment presentation protocol", "Implement 3D scan visualization for all implant consults", "Create financing scripts (CareCredit, Proceed, Sunbit)", "Role-play objection handling with team weekly", "Implement treatment coordinator handoff process"] },
          { id: "e6", task: "Launch reactivation campaign — mine your database", agent: "cmo", dept: "marketing", status: "not_started", details: "You're sitting on gold. Reactivate patients who haven't been in 6+ months. Typical result: $80K-$150K recovered.", subtasks: ["Pull list of all patients not seen in 6+ months", "Segment by last treatment type", "Launch 3-touch reactivation campaign (SMS → email → call)", "Offer limited-time incentive for returning", "Track reactivation rate (target: 15-25%)"] },
          { id: "e7", task: "Optimize scheduling — eliminate dead time", agent: "coo", dept: "operations", status: "not_started", details: "Block scheduling + same-day treatment = more production per day. Target: $5K+ per chair per day.", subtasks: ["Implement block scheduling by procedure type", "Create same-day treatment protocol", "Set up waitlist/short-notice list", "Reduce no-shows with confirmation automation", "Fill empty slots with hygiene-generated treatment"] },
          { id: "e8", task: "Fix collections — get to 98%+", agent: "cfo", dept: "finance", status: "not_started", details: "You do the work, you should get paid. Most practices collect 91-94%. Get to 98%.", subtasks: ["Implement payment-at-time-of-service policy", "Set up automated payment reminders", "Renegotiate insurance fee schedules annually", "Offer in-house membership plan for uninsured", "Clean up A/R — nothing over 90 days"] },
        ]
      },
      { phase: 3, name: "Scale Systems", duration: "Month 2-4", agent: "coo",
        tasks: [
          { id: "e9", task: "Add specialty services (implants, ortho, perio)", agent: "ceo", dept: "strategy", status: "not_started", details: "The fastest way to grow revenue: add high-value specialties. Implant cases = $4K-$30K each.", subtasks: ["Evaluate specialty demand in your market", "Recruit or contract with specialists", "Invest in specialty equipment (CBCT, scanner)", "Train team on specialty patient flow", "Launch specialty-specific marketing campaigns"] },
          { id: "e10", task: "Build automated patient communication engine", agent: "cmo", dept: "marketing", status: "not_started", details: "Every touchpoint automated: reminders, follow-ups, recalls, reviews, referrals — 24/7.", subtasks: ["Automate appointment reminders (2-day, same-day)", "Build post-treatment follow-up sequences by procedure", "Automate recall campaigns (3, 6, 9, 12 month)", "Set up review request automation (post-appointment)", "Create referral program with automated ask", "Build nurture sequences for unconverted leads"] },
          { id: "e11", task: "Systematize everything — create the operations manual", agent: "coo", dept: "operations", status: "not_started", details: "If it's not documented, it doesn't exist. Your ops manual is what makes your practice scalable.", subtasks: ["Document all front desk procedures", "Document clinical workflows by procedure type", "Create treatment coordinator playbook", "Build billing & collections procedures", "Create hiring & onboarding checklists", "Document emergency & compliance protocols"] },
          { id: "e12", task: "Scale marketing — build the patient acquisition machine", agent: "cmo", dept: "marketing", status: "not_started", details: "Move from random marketing to a systematic acquisition engine. Target: predictable cost per new patient.", subtasks: ["Launch/optimize Google Ads for high-value procedures", "Build Meta ad funnels with retargeting", "Create content engine (2 videos + 3 posts/week)", "Launch patient referral program ($250-$500 bonus)", "Optimize Google Business Profile weekly", "Build community partnerships (gyms, spas, realtors)"] },
        ]
      },
      { phase: 4, name: "Multiply", duration: "Month 4-12", agent: "ceo",
        tasks: [
          { id: "e13", task: "Prepare for second location or associate hire", agent: "ceo", dept: "strategy", status: "not_started", details: "Once systems are running, duplicate. Either open location #2 or add an associate to max out location #1.", subtasks: ["Determine expansion path: associate vs. 2nd location", "Build associate compensation model", "Create location #2 financial model", "Identify target area for expansion", "Begin recruitment for associate/partner"] },
          { id: "e14", task: "Build management layer — remove yourself from daily ops", agent: "chro", dept: "hr", status: "not_started", details: "You should work ON the business, not IN it. Hire/promote an office manager who runs the day-to-day.", subtasks: ["Promote or hire office manager / integrator", "Create management KPI dashboard", "Implement weekly leadership meetings", "Document owner's role & decision-making framework", "Build training program for future managers"] },
        ]
      },
    ],
  },
  acquisition: {
    id: "acquisition", name: "Acquire a Practice", icon: "🤝", tagline: "Buy & transform", color: "#FF6B6B",
    desc: "Buy an existing practice, inject your systems and AI, and 3-5x EBITDA within 18 months. The Hormozi acquisition playbook for dentistry.",
    phases: [
      { phase: 1, name: "Target & Evaluate", duration: "Month 1-3", agent: "ceo",
        tasks: [
          { id: "a1", task: "Define acquisition criteria & search strategy", agent: "ceo", dept: "strategy", status: "not_started", details: "What's your ideal practice profile? Revenue, location, specialties, seller motivation — define your buy box.", subtasks: ["Set revenue range ($500K-$2M typical)", "Define geographic target area", "Choose specialty focus (general, implant-heavy, ortho)", "Identify deal breakers (lease issues, staff problems, reputation)", "Set max purchase price / multiple target (0.6-0.8x revenue)", "Register with dental practice brokers (3-5)"] },
          { id: "a2", task: "Source and screen acquisition targets", agent: "ceo", dept: "strategy", status: "not_started", details: "Cast a wide net, screen ruthlessly. Evaluate 20+ practices, seriously pursue 3-5, close 1-2.", subtasks: ["Contact dental brokers for active listings", "Network with retiring dentists in target area", "Post acquisition interest on dental forums/groups", "Screen for: revenue stability, patient count, location quality", "Request preliminary financials on top 5 targets", "Schedule site visits for top 3"] },
          { id: "a3", task: "Financial due diligence deep-dive", agent: "cfo", dept: "finance", status: "not_started", details: "Verify everything. Last 3 years of tax returns, production reports, collections, overhead, patient mix.", subtasks: ["Request 3 years of tax returns", "Analyze production by procedure code", "Review collections rate and A/R aging", "Calculate adjusted EBITDA / owner benefit", "Assess patient mix (insurance vs. FFS vs. uninsured)", "Identify hidden liabilities (old equipment, pending lawsuits)", "Get independent practice valuation"] },
          { id: "a4", task: "Legal due diligence & structure deal", agent: "clo", dept: "legal", status: "not_started", details: "Asset purchase vs. stock purchase. Review lease, contracts, employee agreements, insurance panels.", subtasks: ["Engage dental-specific M&A attorney", "Determine deal structure (asset vs. entity purchase)", "Review commercial lease terms & transferability", "Audit all vendor contracts", "Review employee agreements & benefits", "Verify all licenses, permits, DEA current", "Check for any pending litigation or complaints"] },
        ]
      },
      { phase: 2, name: "Close the Deal", duration: "Month 3-4", agent: "cfo",
        tasks: [
          { id: "a5", task: "Submit LOI & negotiate terms", agent: "ceo", dept: "strategy", status: "not_started", details: "Letter of Intent: price, terms, transition period, seller's involvement, non-compete, earnout structure.", subtasks: ["Draft LOI with purchase price & terms", "Negotiate transition period (60-90 days ideal)", "Define seller involvement post-close", "Negotiate non-compete (5 years, 10-mile radius typical)", "Agree on allocation of purchase price", "Set contingencies (financing, due diligence)"] },
          { id: "a6", task: "Secure acquisition financing", agent: "cfo", dept: "finance", status: "not_started", details: "SBA 7(a) is king for dental acquisitions. 10-year term, competitive rates, up to $5M.", subtasks: ["Apply with 2-3 SBA-preferred lenders", "Prepare loan package (business plan, projections, personal financials)", "Get pre-approval before submitting LOI", "Negotiate terms (rate, term, down payment)", "Coordinate with seller on timing", "Set up escrow account"] },
          { id: "a7", task: "Execute definitive purchase agreement", agent: "clo", dept: "legal", status: "not_started", details: "The binding contract. Every detail matters — reps & warranties, indemnification, closing conditions.", subtasks: ["Draft/review Asset Purchase Agreement", "Negotiate representations & warranties", "Define indemnification terms", "Set closing conditions & timeline", "Prepare closing checklist", "Coordinate lender requirements for closing"] },
        ]
      },
      { phase: 3, name: "Transition", duration: "Month 4-6", agent: "coo",
        tasks: [
          { id: "a8", task: "Day 1 takeover — communicate with patients & staff", agent: "ceo", dept: "strategy", status: "not_started", details: "First impressions matter. How you communicate the transition determines patient and staff retention.", subtasks: ["Send patient communication letter (warm, reassuring)", "Hold all-staff meeting — vision, no layoffs (if true), excitement", "Meet every team member 1-on-1 in first week", "Maintain seller's presence for 30-60 days", "Keep branding consistent initially (change later)", "Be visible and present — patients need to trust you"] },
          { id: "a9", task: "Install your systems & technology stack", agent: "coo", dept: "operations", status: "not_started", details: "Inject your systems: PMS upgrade, digital workflows, AI scheduling, patient communication platform.", subtasks: ["Evaluate and upgrade PMS if needed", "Install CBCT / digital scanner if not present", "Set up patient communication automation", "Implement digital intake forms", "Install production tracking dashboard", "Set up AI scheduling optimization"] },
          { id: "a10", task: "Train team on your systems & culture", agent: "chro", dept: "hr", status: "not_started", details: "The acquired team needs to learn your way. Be patient but firm. Culture transformation takes 90 days.", subtasks: ["Week 1-2: Software & workflow training", "Week 3-4: Treatment presentation & case acceptance", "Month 2: Phone skills & patient experience training", "Month 2-3: Embed new KPIs and accountability", "Ongoing: Weekly team meetings with metrics review", "Identify team members who thrive vs. resist change"] },
          { id: "a11", task: "Transfer insurance credentials & update contracts", agent: "cfo", dept: "finance", status: "not_started", details: "Critical: transfer insurance panel participation to you. Apply for new credentials 90+ days before close.", subtasks: ["Start credentialing applications pre-close (60-90 days)", "Coordinate with each insurance company on ownership transfer", "Update NPI, tax ID with all payers", "Renegotiate fee schedules where possible", "Update all vendor contracts to new entity", "Transfer merchant services & payment processing"] },
        ]
      },
      { phase: 4, name: "Inject Growth", duration: "Month 6-18", agent: "cmo",
        tasks: [
          { id: "a12", task: "Launch aggressive marketing — fill the chairs", agent: "cmo", dept: "marketing", status: "not_started", details: "Acquired practices are usually under-marketed. Inject your acquisition engine and watch revenue climb.", subtasks: ["Launch Google Ads for implants & high-value procedures", "Activate patient reactivation campaign (6+ months overdue)", "Build referral program for existing patient base", "Rebrand gradually (new website, updated signage)", "Launch social media content engine", "Host community event / open house"] },
          { id: "a13", task: "Add specialty services to increase revenue per patient", agent: "ceo", dept: "strategy", status: "not_started", details: "Most acquired GP practices are missing implants, ortho, and perio. Adding these can 2-3x revenue.", subtasks: ["Assess which specialties to add based on demand", "Recruit or contract with specialists", "Invest in equipment for new services", "Train existing team on specialty patient flow", "Create value ladder: cleaning → whitening → Invisalign → implants"] },
          { id: "a14", task: "Optimize operations & hit 3-5x EBITDA target", agent: "cfo", dept: "finance", status: "not_started", details: "The endgame: transform a $200K-$400K EBITDA practice into a $800K-$1.5M EBITDA machine in 18 months.", subtasks: ["Track monthly production growth vs. acquisition baseline", "Optimize overhead ratio to <55%", "Grow collections to 98%+", "Increase case acceptance to 70%+", "Scale to 85%+ chair utilization", "Prepare for potential refinance or next acquisition"] },
        ]
      },
    ],
  },
};

const DEPT_ICONS = { strategy: "🎯", finance: "💰", legal: "⚖️", operations: "⚙️", marketing: "📣", hr: "👥" };

// ═══════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════

const Badge = ({ children, color = "#D4A853", size = "sm" }) => (
  <span style={{ background: `${color}14`, color, padding: size === "sm" ? "2px 9px" : "4px 14px", borderRadius: 20, fontSize: size === "sm" ? 10 : 12, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", whiteSpace: "nowrap", border: `1px solid ${color}20` }}>{children}</span>
);

const ProgressBar = ({ value, max = 100, color = "#D4A853", height = 6, showLabel = false }) => (
  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
    <div style={{ flex: 1, height, background: "rgba(255,255,255,0.04)", borderRadius: height / 2, overflow: "hidden" }}>
      <div style={{ height: "100%", width: `${Math.min((value / max) * 100, 100)}%`, background: `linear-gradient(90deg, ${color}, ${color}AA)`, borderRadius: height / 2, transition: "width 0.8s ease" }} />
    </div>
    {showLabel && <span style={{ fontSize: 12, fontWeight: 800, color, minWidth: 40, textAlign: "right" }}>{Math.round((value / max) * 100)}%</span>}
  </div>
);

const AgentCard = ({ agentId, active, onClick, compact }) => {
  const a = AI_AGENTS[agentId];
  if (compact) return (
    <button onClick={onClick} style={{ display: "flex", alignItems: "center", gap: 8, background: active ? `${a.color}12` : "rgba(255,255,255,0.02)", border: `1px solid ${active ? a.color + "30" : "rgba(255,255,255,0.06)"}`, borderRadius: 10, padding: "8px 14px", cursor: "pointer", transition: "0.2s", whiteSpace: "nowrap" }}>
      <span style={{ fontSize: 16 }}>{a.icon}</span>
      <span style={{ fontSize: 12, fontWeight: 700, color: active ? a.color : "#8899AA" }}>{a.short}</span>
    </button>
  );
  return (
    <div onClick={onClick} style={{ background: active ? `${a.color}08` : "rgba(255,255,255,0.015)", border: `1px solid ${active ? a.color + "25" : "rgba(255,255,255,0.05)"}`, borderRadius: 14, padding: "16px 18px", cursor: "pointer", transition: "all 0.25s" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
        <div style={{ width: 36, height: 36, borderRadius: 10, background: a.gradient, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>{a.icon}</div>
        <div>
          <div style={{ fontSize: 13, fontWeight: 800, color: active ? a.color : "var(--text)" }}>{a.name}</div>
          <div style={{ fontSize: 10, color: "#6B7B8D", letterSpacing: 0.5 }}>{a.desc}</div>
        </div>
      </div>
      {active && <div style={{ fontSize: 12, color: "#8899AA", lineHeight: 1.5, fontStyle: "italic", padding: "8px 12px", background: `${a.color}06`, borderRadius: 8, borderLeft: `3px solid ${a.color}30` }}>"{a.personality}"</div>}
    </div>
  );
};

const NeuralBG = () => {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d");
    c.width = c.offsetWidth * 2; c.height = c.offsetHeight * 2;
    let t = 0, af;
    const pts = Array.from({ length: 35 }, () => ({ x: Math.random() * c.width, y: Math.random() * c.height, vx: (Math.random() - 0.5) * 0.7, vy: (Math.random() - 0.5) * 0.7 }));
    const draw = () => {
      t += 0.006; ctx.clearRect(0, 0, c.width, c.height);
      pts.forEach(n => { n.x += n.vx; n.y += n.vy; if (n.x < 0 || n.x > c.width) n.vx *= -1; if (n.y < 0 || n.y > c.height) n.vy *= -1; });
      pts.forEach((a, i) => pts.slice(i + 1).forEach(b => {
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        if (d < 180) { ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.strokeStyle = `rgba(212,168,83,${0.05 * (1 - d / 180)})`; ctx.lineWidth = 0.6; ctx.stroke(); }
      }));
      pts.forEach(n => { const p = Math.sin(t * 2 + n.x * 0.01) * 0.5 + 0.5; ctx.beginPath(); ctx.arc(n.x, n.y, 1.5 + p, 0, Math.PI * 2); ctx.fillStyle = `rgba(212,168,83,${0.12 + p * 0.18})`; ctx.fill(); });
      af = requestAnimationFrame(draw);
    };
    draw(); return () => cancelAnimationFrame(af);
  }, []);
  return <canvas ref={ref} style={{ width: "100%", height: "100%", position: "absolute", inset: 0, opacity: 0.6 }} />;
};

// ═══════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════

export default function DentalOS() {
  const [screen, setScreen] = useState("select"); // select | path | task
  const [selectedPath, setSelectedPath] = useState(null);
  const [selectedPhase, setSelectedPhase] = useState(0);
  const [selectedTask, setSelectedTask] = useState(null);
  const [agentFilter, setAgentFilter] = useState("all");
  const [deptFilter, setDeptFilter] = useState("all");
  const [taskStates, setTaskStates] = useState({});
  const [activeAgent, setActiveAgent] = useState("ceo");
  const [showAgentPanel, setShowAgentPanel] = useState(false);

  const toggleSubtask = (taskId, subIdx) => {
    setTaskStates(prev => {
      const key = `${taskId}-${subIdx}`;
      return { ...prev, [key]: !prev[key] };
    });
  };

  const getTaskProgress = (task) => {
    if (!task.subtasks) return 0;
    const done = task.subtasks.filter((_, i) => taskStates[`${task.id}-${i}`]).length;
    return (done / task.subtasks.length) * 100;
  };

  const getPhaseProgress = (phase) => {
    if (!phase.tasks.length) return 0;
    const total = phase.tasks.reduce((sum, t) => sum + (t.subtasks?.length || 0), 0);
    const done = phase.tasks.reduce((sum, t) => sum + (t.subtasks?.filter((_, i) => taskStates[`${t.id}-${i}`])?.length || 0), 0);
    return total ? (done / total) * 100 : 0;
  };

  const getOverallProgress = () => {
    if (!selectedPath) return 0;
    const path = PATHS[selectedPath];
    const total = path.phases.reduce((s, p) => s + p.tasks.reduce((s2, t) => s2 + (t.subtasks?.length || 0), 0), 0);
    const done = path.phases.reduce((s, p) => s + p.tasks.reduce((s2, t) => s2 + (t.subtasks?.filter((_, i) => taskStates[`${t.id}-${i}`])?.length || 0), 0), 0);
    return total ? (done / total) * 100 : 0;
  };

  const pathData = selectedPath ? PATHS[selectedPath] : null;
  const currentPhase = pathData?.phases[selectedPhase];

  const filteredTasks = currentPhase?.tasks.filter(t => {
    if (agentFilter !== "all" && t.agent !== agentFilter) return false;
    if (deptFilter !== "all" && t.dept !== deptFilter) return false;
    return true;
  }) || [];

  // ── PATH SELECTION SCREEN ──
  if (screen === "select") {
    return (
      <div style={{ minHeight: "100vh", background: "#08090D", color: "#E8EDF2", fontFamily: "'Outfit', 'DM Sans', system-ui, sans-serif", display: "flex", flexDirection: "column" }}>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Crimson+Pro:ital,wght@0,400;0,700;1,400&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet" />

        {/* Hero */}
        <div style={{ position: "relative", padding: "60px 32px 50px", textAlign: "center", overflow: "hidden" }}>
          <NeuralBG />
          <div style={{ position: "relative", zIndex: 1 }}>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 10, background: "rgba(212,168,83,0.06)", border: "1px solid rgba(212,168,83,0.12)", borderRadius: 24, padding: "6px 18px", marginBottom: 20 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#D4A853", boxShadow: "0 0 12px #D4A853", animation: "pulse 2s infinite" }} />
              <span style={{ fontSize: 11, color: "#D4A853", fontWeight: 700, letterSpacing: 1.5, textTransform: "uppercase" }}>AI-Powered Practice Operating System</span>
            </div>
            <h1 style={{ fontSize: "clamp(32px, 5vw, 56px)", fontWeight: 900, lineHeight: 1.05, marginBottom: 12, background: "linear-gradient(135deg, #F0F4F8 30%, #D4A853)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              DentalOS
            </h1>
            <p style={{ fontSize: "clamp(14px, 2vw, 18px)", color: "#6B7B8D", maxWidth: 620, margin: "0 auto 8px", lineHeight: 1.5, fontFamily: "'Crimson Pro', serif", fontStyle: "italic" }}>
              Your AI C-Suite — CEO, COO, CMO, CFO, CHRO & CLO — guiding every step from first patient to dental empire.
            </p>
            <p style={{ fontSize: 13, color: "#4A5568", maxWidth: 500, margin: "0 auto" }}>
              Choose your path below. Each comes with a complete implementation roadmap, automated task generation, and AI agent guidance.
            </p>
          </div>
        </div>

        {/* Path Cards */}
        <div style={{ padding: "0 32px 40px", maxWidth: 1100, margin: "0 auto", width: "100%" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: 20 }}>
            {Object.values(PATHS).map((p) => (
              <div key={p.id} onClick={() => { setSelectedPath(p.id); setScreen("path"); setSelectedPhase(0); }} style={{ background: "rgba(255,255,255,0.015)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 20, padding: 32, cursor: "pointer", transition: "all 0.3s", position: "relative", overflow: "hidden" }} onMouseOver={e => { e.currentTarget.style.borderColor = p.color + "40"; e.currentTarget.style.transform = "translateY(-4px)"; }} onMouseOut={e => { e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)"; e.currentTarget.style.transform = "translateY(0)"; }}>
                <div style={{ position: "absolute", top: -30, right: -30, width: 140, height: 140, background: `radial-gradient(circle, ${p.color}08, transparent)`, borderRadius: "50%" }} />
                <div style={{ fontSize: 48, marginBottom: 16 }}>{p.icon}</div>
                <Badge color={p.color} size="md">{p.tagline}</Badge>
                <h3 style={{ fontSize: 24, fontWeight: 900, marginTop: 12, marginBottom: 8, color: p.color }}>{p.name}</h3>
                <p style={{ fontSize: 14, color: "#6B7B8D", lineHeight: 1.6, marginBottom: 20 }}>{p.desc}</p>
                <div style={{ display: "flex", gap: 16, marginBottom: 20 }}>
                  <div><div style={{ fontSize: 22, fontWeight: 900, color: "#E8EDF2" }}>{p.phases.length}</div><div style={{ fontSize: 10, color: "#5A6B7B", letterSpacing: 1, textTransform: "uppercase" }}>Phases</div></div>
                  <div><div style={{ fontSize: 22, fontWeight: 900, color: "#E8EDF2" }}>{p.phases.reduce((s, ph) => s + ph.tasks.length, 0)}</div><div style={{ fontSize: 10, color: "#5A6B7B", letterSpacing: 1, textTransform: "uppercase" }}>Tasks</div></div>
                  <div><div style={{ fontSize: 22, fontWeight: 900, color: "#E8EDF2" }}>{p.phases.reduce((s, ph) => s + ph.tasks.reduce((s2, t) => s2 + (t.subtasks?.length || 0), 0), 0)}</div><div style={{ fontSize: 10, color: "#5A6B7B", letterSpacing: 1, textTransform: "uppercase" }}>Steps</div></div>
                </div>
                <button style={{ width: "100%", background: `linear-gradient(135deg, ${p.color}, ${p.color}CC)`, color: "#08090D", border: "none", borderRadius: 12, padding: "12px 24px", fontWeight: 800, fontSize: 15, cursor: "pointer" }}>
                  Start This Path →
                </button>
              </div>
            ))}
          </div>

          {/* AI Agents Preview */}
          <div style={{ marginTop: 40 }}>
            <div style={{ textAlign: "center", marginBottom: 24 }}>
              <div style={{ fontSize: 11, color: "#D4A853", letterSpacing: 2, textTransform: "uppercase", fontWeight: 700, marginBottom: 6 }}>Your AI C-Suite</div>
              <div style={{ fontSize: 24, fontWeight: 900 }}>6 AI Agents Working For You</div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
              {Object.entries(AI_AGENTS).map(([id, a]) => (
                <div key={id} style={{ background: "rgba(255,255,255,0.015)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 14, padding: "18px 16px", textAlign: "center" }}>
                  <div style={{ width: 44, height: 44, borderRadius: 12, background: a.gradient, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22, margin: "0 auto 10px" }}>{a.icon}</div>
                  <div style={{ fontSize: 13, fontWeight: 800, color: a.color, marginBottom: 2 }}>{a.short}</div>
                  <div style={{ fontSize: 11, color: "#6B7B8D", lineHeight: 1.4 }}>{a.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
        <style>{`@keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.4 } } * { box-sizing:border-box; margin:0; padding:0; } button:hover { filter:brightness(1.1); transform:scale(1.01); } button { transition:0.2s; }`}</style>
      </div>
    );
  }

  // ── MAIN PATH SCREEN ──
  return (
    <div style={{ minHeight: "100vh", background: "#08090D", color: "#E8EDF2", fontFamily: "'Outfit', 'DM Sans', system-ui, sans-serif" }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Crimson+Pro:ital,wght@0,400;0,700;1,400&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet" />

      {/* Header */}
      <div style={{ background: "rgba(255,255,255,0.015)", borderBottom: "1px solid rgba(255,255,255,0.06)", padding: "10px 22px", display: "flex", alignItems: "center", justifyContent: "space-between", position: "sticky", top: 0, zIndex: 50, backdropFilter: "blur(12px)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => setScreen("select")} style={{ background: "none", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, padding: "5px 10px", color: "#6B7B8D", cursor: "pointer", fontSize: 14 }}>←</button>
          <div style={{ width: 32, height: 32, borderRadius: 8, background: `linear-gradient(135deg, ${pathData.color}, ${pathData.color}AA)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>{pathData.icon}</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 900, color: pathData.color }}>{pathData.name}</div>
            <div style={{ fontSize: 10, color: "#5A6B7B", letterSpacing: 1.5, textTransform: "uppercase" }}>DentalOS • Phase {selectedPhase + 1} of {pathData.phases.length}</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 11, color: "#6B7B8D" }}>Overall:</span>
            <div style={{ width: 100 }}><ProgressBar value={getOverallProgress()} color={pathData.color} height={5} /></div>
            <span style={{ fontSize: 12, fontWeight: 800, color: pathData.color }}>{Math.round(getOverallProgress())}%</span>
          </div>
          <button onClick={() => setShowAgentPanel(!showAgentPanel)} style={{ display: "flex", alignItems: "center", gap: 6, background: showAgentPanel ? "rgba(212,168,83,0.1)" : "rgba(255,255,255,0.03)", border: `1px solid ${showAgentPanel ? "rgba(212,168,83,0.2)" : "rgba(255,255,255,0.06)"}`, borderRadius: 8, padding: "6px 12px", cursor: "pointer", fontSize: 12, fontWeight: 700, color: showAgentPanel ? "#D4A853" : "#6B7B8D" }}>
            🤖 AI Agents
          </button>
        </div>
      </div>

      <div style={{ display: "flex", minHeight: "calc(100vh - 53px)" }}>
        {/* ── Sidebar: Phases ── */}
        <div style={{ width: 260, borderRight: "1px solid rgba(255,255,255,0.05)", padding: "16px 14px", overflowY: "auto", flexShrink: 0, background: "rgba(255,255,255,0.008)" }}>
          <div style={{ fontSize: 10, color: "#5A6B7B", letterSpacing: 1.5, textTransform: "uppercase", fontWeight: 700, marginBottom: 12, paddingLeft: 4 }}>Implementation Phases</div>
          {pathData.phases.map((phase, i) => {
            const prog = getPhaseProgress(phase);
            const agent = AI_AGENTS[phase.agent];
            return (
              <div key={i} onClick={() => setSelectedPhase(i)} style={{ background: selectedPhase === i ? `${pathData.color}0A` : "transparent", border: `1px solid ${selectedPhase === i ? pathData.color + "20" : "transparent"}`, borderRadius: 12, padding: "12px 14px", marginBottom: 8, cursor: "pointer", transition: "0.2s" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ width: 24, height: 24, borderRadius: 7, background: selectedPhase === i ? pathData.color : "rgba(255,255,255,0.06)", color: selectedPhase === i ? "#08090D" : "#6B7B8D", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 900 }}>{phase.phase}</div>
                    <div style={{ fontSize: 13, fontWeight: 800, color: selectedPhase === i ? pathData.color : "#C8D2DC" }}>{phase.name}</div>
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                  <span style={{ fontSize: 14 }}>{agent.icon}</span>
                  <span style={{ fontSize: 10, color: "#6B7B8D" }}>Led by {agent.short}</span>
                  <span style={{ fontSize: 10, color: "#5A6B7B" }}>· {phase.duration}</span>
                </div>
                <ProgressBar value={prog} color={prog === 100 ? "#22D3EE" : pathData.color} height={4} />
                <div style={{ fontSize: 10, color: "#5A6B7B", marginTop: 4, textAlign: "right" }}>{phase.tasks.length} tasks · {Math.round(prog)}%</div>
              </div>
            );
          })}
        </div>

        {/* ── Main Content ── */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
          {/* Phase Header */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <div style={{ width: 36, height: 36, borderRadius: 10, background: AI_AGENTS[currentPhase.agent].gradient, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>{AI_AGENTS[currentPhase.agent].icon}</div>
              <div>
                <div style={{ fontSize: 10, color: pathData.color, letterSpacing: 1.5, textTransform: "uppercase", fontWeight: 700 }}>Phase {currentPhase.phase} · {currentPhase.duration}</div>
                <div style={{ fontSize: 22, fontWeight: 900 }}>{currentPhase.name}</div>
              </div>
            </div>
            <div style={{ fontSize: 13, color: "#8899AA", fontStyle: "italic", padding: "10px 14px", background: `${AI_AGENTS[currentPhase.agent].color}06`, borderRadius: 10, borderLeft: `3px solid ${AI_AGENTS[currentPhase.agent].color}30`, marginTop: 10 }}>
              🤖 <strong style={{ color: AI_AGENTS[currentPhase.agent].color }}>{AI_AGENTS[currentPhase.agent].short}:</strong> "{AI_AGENTS[currentPhase.agent].personality}"
            </div>
          </div>

          {/* Filters */}
          <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
            <div style={{ display: "flex", gap: 4, marginRight: 8 }}>
              {["all", ...Object.keys(DEPT_ICONS)].map(d => (
                <button key={d} onClick={() => setDeptFilter(d)} style={{ background: deptFilter === d ? `${pathData.color}12` : "transparent", border: `1px solid ${deptFilter === d ? pathData.color + "25" : "rgba(255,255,255,0.06)"}`, color: deptFilter === d ? pathData.color : "#6B7B8D", borderRadius: 7, padding: "4px 11px", fontSize: 11, fontWeight: 700, cursor: "pointer", textTransform: "capitalize" }}>
                  {d === "all" ? "All Depts" : `${DEPT_ICONS[d]} ${d}`}
                </button>
              ))}
            </div>
          </div>

          {/* Task Cards */}
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {filteredTasks.map((task) => {
              const agent = AI_AGENTS[task.agent];
              const progress = getTaskProgress(task);
              const isOpen = selectedTask === task.id;
              return (
                <div key={task.id} style={{ background: "rgba(255,255,255,0.015)", border: `1px solid ${isOpen ? agent.color + "25" : "rgba(255,255,255,0.05)"}`, borderRadius: 16, overflow: "hidden", transition: "0.2s" }}>
                  {/* Task Header */}
                  <div onClick={() => setSelectedTask(isOpen ? null : task.id)} style={{ padding: "16px 20px", cursor: "pointer", display: "flex", alignItems: "flex-start", gap: 14 }}>
                    <div style={{ width: 36, height: 36, borderRadius: 10, background: agent.gradient, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, flexShrink: 0, marginTop: 2 }}>{agent.icon}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, flexWrap: "wrap" }}>
                        <span style={{ fontSize: 15, fontWeight: 800 }}>{task.task}</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                        <Badge color={agent.color}>{agent.short}</Badge>
                        <Badge color="#6B7B8D">{DEPT_ICONS[task.dept]} {task.dept}</Badge>
                        {task.subtasks && <span style={{ fontSize: 11, color: "#5A6B7B" }}>{task.subtasks.filter((_, i) => taskStates[`${task.id}-${i}`]).length}/{task.subtasks.length} steps</span>}
                      </div>
                      <div style={{ marginTop: 8 }}><ProgressBar value={progress} color={progress === 100 ? "#22D3EE" : agent.color} height={4} /></div>
                    </div>
                    <div style={{ fontSize: 18, color: "#5A6B7B", transform: `rotate(${isOpen ? 180 : 0}deg)`, transition: "0.3s", flexShrink: 0, marginTop: 4 }}>▾</div>
                  </div>

                  {/* Expanded Content */}
                  {isOpen && (
                    <div style={{ padding: "0 20px 20px", borderTop: "1px solid rgba(255,255,255,0.04)" }}>
                      {/* AI Guidance */}
                      <div style={{ margin: "14px 0", padding: "12px 16px", background: `${agent.color}06`, borderRadius: 10, borderLeft: `3px solid ${agent.color}30` }}>
                        <div style={{ fontSize: 10, color: agent.color, letterSpacing: 1, textTransform: "uppercase", fontWeight: 700, marginBottom: 4 }}>🤖 {agent.short} Guidance</div>
                        <div style={{ fontSize: 13, color: "#8899AA", lineHeight: 1.6 }}>{task.details}</div>
                      </div>

                      {/* Subtask Checklist */}
                      {task.subtasks && (
                        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                          {task.subtasks.map((sub, si) => {
                            const done = taskStates[`${task.id}-${si}`];
                            return (
                              <div key={si} onClick={() => toggleSubtask(task.id, si)} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "8px 12px", borderRadius: 8, cursor: "pointer", background: done ? `${agent.color}06` : "transparent", transition: "0.15s" }}>
                                <div style={{ width: 20, height: 20, borderRadius: 6, border: `2px solid ${done ? agent.color : "rgba(255,255,255,0.12)"}`, background: done ? agent.color : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1, transition: "0.2s" }}>
                                  {done && <span style={{ color: "#08090D", fontSize: 12, fontWeight: 900 }}>✓</span>}
                                </div>
                                <span style={{ fontSize: 13, color: done ? "#6B7B8D" : "#C8D2DC", textDecoration: done ? "line-through" : "none", lineHeight: 1.5, transition: "0.2s" }}>{sub}</span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Phase Navigation */}
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24, paddingTop: 20, borderTop: "1px solid rgba(255,255,255,0.04)" }}>
            <button onClick={() => selectedPhase > 0 && setSelectedPhase(selectedPhase - 1)} disabled={selectedPhase === 0} style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, padding: "10px 20px", fontSize: 13, fontWeight: 700, cursor: selectedPhase > 0 ? "pointer" : "default", color: selectedPhase > 0 ? "#C8D2DC" : "#3A4550", opacity: selectedPhase > 0 ? 1 : 0.5 }}>
              ← Previous Phase
            </button>
            <button onClick={() => selectedPhase < pathData.phases.length - 1 && setSelectedPhase(selectedPhase + 1)} disabled={selectedPhase >= pathData.phases.length - 1} style={{ background: selectedPhase < pathData.phases.length - 1 ? `linear-gradient(135deg, ${pathData.color}, ${pathData.color}CC)` : "rgba(255,255,255,0.03)", color: selectedPhase < pathData.phases.length - 1 ? "#08090D" : "#3A4550", border: "none", borderRadius: 10, padding: "10px 24px", fontSize: 13, fontWeight: 800, cursor: selectedPhase < pathData.phases.length - 1 ? "pointer" : "default" }}>
              Next Phase →
            </button>
          </div>
        </div>

        {/* ── Agent Panel (Collapsible) ── */}
        {showAgentPanel && (
          <div style={{ width: 280, borderLeft: "1px solid rgba(255,255,255,0.05)", padding: "16px 14px", overflowY: "auto", flexShrink: 0, background: "rgba(255,255,255,0.008)" }}>
            <div style={{ fontSize: 10, color: "#D4A853", letterSpacing: 1.5, textTransform: "uppercase", fontWeight: 700, marginBottom: 12, paddingLeft: 4 }}>AI C-Suite Agents</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {Object.entries(AI_AGENTS).map(([id, a]) => (
                <AgentCard key={id} agentId={id} active={activeAgent === id} onClick={() => setActiveAgent(id)} />
              ))}
            </div>
            {activeAgent && (
              <div style={{ marginTop: 16, padding: "14px 16px", background: `${AI_AGENTS[activeAgent].color}06`, borderRadius: 12, border: `1px solid ${AI_AGENTS[activeAgent].color}15` }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: AI_AGENTS[activeAgent].color, marginBottom: 6 }}>Agent Focus Areas</div>
                <div style={{ fontSize: 12, color: "#6B7B8D", lineHeight: 1.6 }}>
                  {activeAgent === "ceo" && "• Practice vision & positioning\n• Growth strategy & milestones\n• Partnership & expansion decisions\n• Market analysis & competitive positioning"}
                  {activeAgent === "coo" && "• Daily operations & workflows\n• Scheduling optimization\n• Equipment & technology stack\n• SOPs & quality control"}
                  {activeAgent === "cmo" && "• Patient acquisition funnels\n• Brand identity & reputation\n• Digital marketing & SEO\n• Referral programs & community"}
                  {activeAgent === "cfo" && "• Revenue & cash flow modeling\n• Insurance & billing optimization\n• Overhead management\n• Financial benchmarking"}
                  {activeAgent === "chro" && "• Hiring & onboarding\n• Training & skill development\n• Compensation & benefits\n• Culture & retention"}
                  {activeAgent === "clo" && "• Entity structure & compliance\n• HIPAA & OSHA protocols\n• Contracts & lease review\n• Insurance credentialing"}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.4 } }
        * { box-sizing:border-box; margin:0; padding:0; }
        ::-webkit-scrollbar { width:5px; }
        ::-webkit-scrollbar-track { background:transparent; }
        ::-webkit-scrollbar-thumb { background:rgba(255,255,255,0.06); border-radius:3px; }
        button { transition:all 0.15s; }
        button:hover:not(:disabled) { filter:brightness(1.1); }
        pre { white-space: pre-line; }
      `}</style>
    </div>
  );
}
