import { useState, useEffect, useRef } from "react";

// ═══════════════════════════════════════════════
// THEME
// ═══════════════════════════════════════════════
const T = {
  bg: "#050709", card: "rgba(255,255,255,0.016)", border: "rgba(255,255,255,0.052)",
  text: "#E2E8F0", muted: "#5B6A7D", accent: "#00D4AA", gold: "#C9A84C",
  red: "#EF4444", blue: "#3B82F6", purple: "#8B5CF6", orange: "#F59E0B",
  pink: "#EC4899", cyan: "#06B6D4", green: "#22C55E", lime: "#84CC16",
};

// ═══════════════════════════════════════════════
// EXISTING PRACTICE — OPTIMIZATION PATH
// ═══════════════════════════════════════════════

const EXISTING_PHASES = [
  { id: "audit", phase: 1, name: "Practice Audit & Diagnostic", icon: "🔍", duration: "Week 1-2", color: T.gold, desc: "Before optimizing, know EXACTLY where you stand. This 40-point diagnostic reveals your biggest revenue leaks and growth bottlenecks.",
    tasks: [
      { t: "Run 12-month production report by provider and procedure", ai: "Pull from your PMS. Compare each provider's production to benchmarks: GP $800K-$1.2M/yr, specialist $1-2M+/yr. Identify underperformers and top procedures.", cat: "finance", upgrade: false },
      { t: "Calculate collections rate (last 12 months)", ai: "Formula: Collections ÷ Net Production × 100. Target: 98%+. If below 95%, you have a collections crisis. Check A/R aging — nothing should be over 90 days.", cat: "finance", upgrade: false },
      { t: "Analyze case acceptance rate by procedure type", ai: "Pull treatment plans presented vs. accepted. National average: 50%. Target: 70%+. Break down by: implants, crowns, ortho, perio, cosmetic. Low acceptance = presentation problem, not patient problem.", cat: "operations", upgrade: false },
      { t: "Audit new patient flow (source → conversion → retention)", ai: "Track: where patients come from, how many call, how many book, how many show, how many accept treatment, how many return. Plug every leak in this funnel.", cat: "marketing", upgrade: false },
      { t: "Calculate overhead ratio by category", ai: "Pull P&L. Categories: Staff (target <28%), Facility (<8%), Supplies (<6%), Lab (<8%), Marketing (<5%), Admin (<4%). Total overhead target: <59%. Above 62% = crisis.", cat: "finance", upgrade: false },
      { t: "Assess chair utilization rate", ai: "Formula: Booked hours ÷ Available hours × 100. Target: 85-92%. Below 80% = scheduling problem. Above 95% = need more capacity. Check by day of week — Tue/Thu often underbooked.", cat: "operations", upgrade: false },
      { t: "Audit fee schedules vs UCR rates", ai: "Compare your fees to 80th percentile UCR for your zip code. Most practices are 15-30% below market. Raise fees to at least 80th percentile UCR — insurance pays what they pay regardless.", cat: "finance", upgrade: false },
      { t: "Review insurance mix (PPO vs FFS vs Medicaid vs uninsured)", ai: "Ideal mix: 40-50% PPO, 30-40% FFS, 10-15% membership plan, <5% Medicaid. Heavy PPO dependency (>70%) = vulnerability. Strategy: grow FFS + membership plan patients.", cat: "finance", upgrade: false },
      { t: "Mystery shop your own front desk (phone + online booking)", ai: "Have 3 people call pretending to be new patients. Score on: friendliness, information gathering, urgency creation, booking attempt, follow-up. Also test online booking flow — is it easy or broken?", cat: "operations", upgrade: false },
      { t: "Audit online reputation (Google rating, review count, Yelp)", ai: "Target: 4.8+ stars, 200+ Google reviews. Check: are you responding to all reviews? Are negative reviews addressed? Is your Google Business Profile fully optimized with photos, posts, services?", cat: "marketing", upgrade: false },
      { t: "Run patient attrition analysis (who left and why)", ai: "Pull patients who haven't visited in 12+ months. Categorize: moved away, dissatisfied, no recall system, insurance change, never asked to return. You're likely sitting on $200K+ in reactivation revenue.", cat: "operations", upgrade: false },
      { t: "Assess technology stack (PMS, imaging, scanner, communication)", ai: "Score each system 1-10. Outdated PMS? No digital scanner? No CBCT? No patient communication platform? Each gap costs you $50-200K/year in lost production.", cat: "tech", upgrade: true },
    ]
  },
  { id: "quickwins", phase: 2, name: "Quick Wins (First 30 Days)", icon: "⚡", duration: "Week 2-6", color: T.orange, desc: "Low-effort, high-impact changes that can add $10-50K/month in revenue within 30 days.",
    tasks: [
      { t: "Raise fees to 80th percentile UCR (immediate revenue lift)", ai: "This is free money. Most practices are undercharging. Insurance pays their contracted rate regardless — your fee schedule affects FFS patients and out-of-network benefits. Average impact: $80-200K/year.", cat: "finance", upgrade: false },
      { t: "Implement same-day treatment protocol", ai: "When diagnosis happens, treatment should too. Train team: 'We have time today to take care of this. Would you like us to go ahead?' Eliminates the biggest conversion killer: 'Let me think about it.'", cat: "operations", upgrade: false },
      { t: "Launch patient reactivation campaign (6+ months overdue)", ai: "Pull the list from your PMS. Typical practice has 500-2,000 overdue patients. 3-touch sequence: personalized SMS → email with offer → phone call. Expected recovery: $80-150K in treatment.", cat: "marketing", upgrade: false },
      { t: "Fix phone conversion (target: 80%+ of new patient calls book)", ai: "Record all calls for 2 weeks. Listen and score. Common problems: no urgency, not asking for the appointment, transferring too much, long hold times. Train on: empathy → value → urgency → book.", cat: "operations", upgrade: false },
      { t: "Implement block scheduling for production optimization", ai: "Block by procedure type: hygiene blocks, crown prep blocks, implant blocks, emergency slots (2/day max). Eliminates random scheduling that kills production. Target: $5K+ per chair per day.", cat: "operations", upgrade: false },
      { t: "Start collecting payment at time of service (reduce A/R)", ai: "New policy: patient pays their estimated portion TODAY. Use: 'Your insurance will cover approximately $X, leaving a balance of $Y. How would you like to handle that today?' Impact: A/R drops 40-60%.", cat: "finance", upgrade: false },
      { t: "Set up automated review requests (post every appointment)", ai: "Every patient who completes an appointment gets an automated SMS 2 hours later: 'How was your visit? Leave us a review [link]'. Target: 10+ new Google reviews/month. Use: Birdeye, Podium, or Weave.", cat: "marketing", upgrade: true },
      { t: "Create and promote an in-house membership plan", ai: "For uninsured patients: $25-35/month includes 2 cleanings, exams, X-rays, 15-20% off treatment. Platforms: Kleer, BoomCloud, Plan Forward. Average member spends 2-3x more than insured patients.", cat: "finance", upgrade: false },
    ]
  },
  { id: "upgrades", phase: 3, name: "System Upgrades & AI Integration", icon: "🔧", duration: "Month 1-3", color: T.cyan, desc: "Upgrade your technology stack, add AI-powered tools, and modernize operations. Each upgrade shows current → recommended with ROI projection.",
    tasks: [
      { t: "UPGRADE: Phone system → AI-powered smart phones (Weave/Slingshot)", ai: "CURRENT: Basic phone lines, no analytics, missed after-hours calls.\nUPGRADE TO: Weave or Mango Voice with AI.\nNEW CAPABILITIES: Call recording for training, 2-way texting, AI after-hours answering, call tracking by marketing source, automated appointment reminders, VoIP with dental PMS integration.\nROI: Captures 15-25 missed calls/week = $30-80K/year in recovered revenue.\nCOST: $300-500/month.", cat: "tech", upgrade: true },
      { t: "UPGRADE: Website → conversion-optimized with online booking", ai: "CURRENT: Basic informational site, no booking, slow, not mobile-first.\nUPGRADE TO: Conversion-focused site with NexHealth or LocalMed booking.\nNEW CAPABILITIES: Online scheduling (24/7 booking), click-to-call, live chat, before/after gallery, HIPAA forms, fast loading, SEO-optimized.\nROI: Online booking adds 15-30 new patients/month.\nCOST: $3-8K rebuild + $200-400/month booking platform.", cat: "tech", upgrade: true },
      { t: "UPGRADE: Patient communication → automated multi-channel platform", ai: "CURRENT: Manual reminder calls, no text capability, no email sequences.\nUPGRADE TO: Weave, RevenueWell, or Modento.\nNEW CAPABILITIES: Automated SMS/email reminders, 2-way texting, recall campaigns, review requests, referral asks, post-op follow-ups, birthday messages — all automated 24/7.\nROI: Reduces no-shows 30-50%, reactivates 15-25% of overdue patients.\nCOST: $300-600/month.", cat: "tech", upgrade: true },
      { t: "UPGRADE: Digital imaging → CBCT + intraoral scanner", ai: "CURRENT: 2D X-rays only, PVS impressions.\nUPGRADE TO: CBCT (Carestream/Planmeca) + iTero/3Shape scanner.\nNEW CAPABILITIES: 3D treatment planning, guided implant surgery, same-day scan-to-plan workflow, Invisalign digital submission, patient WOW factor with 3D visualizations.\nROI: Increases implant case acceptance 40-60%. Enables guided surgery premium.\nCOST: CBCT $80-150K, Scanner $25-45K. Finance over 5 years.", cat: "tech", upgrade: true },
      { t: "UPGRADE: Practice analytics → real-time AI dashboard", ai: "CURRENT: Monthly reports from PMS, reactive not proactive.\nUPGRADE TO: Dental Intel, Jarvis Analytics, or Practice by Numbers.\nNEW CAPABILITIES: Real-time production tracking, provider scorecards, scheduling optimization, unscheduled treatment alerts, morning huddle data, benchmarking vs. peers.\nROI: Practices using analytics platforms produce 15-25% more.\nCOST: $300-500/month.", cat: "tech", upgrade: true },
      { t: "UPGRADE: Insurance verification → AI-automated verification", ai: "CURRENT: Staff manually calls insurance for each patient (15-20 min each).\nUPGRADE TO: Vyne Dental, Dentistry.AI, or Zuub.\nNEW CAPABILITIES: Automated batch verification, real-time eligibility checks, benefits breakdown auto-populated, treatment cost estimates generated automatically.\nROI: Saves 20-30 staff hours/week = $25-40K/year in labor costs.\nCOST: $200-400/month.", cat: "tech", upgrade: true },
      { t: "UPGRADE: Treatment presentation → AI-assisted visual case acceptance", ai: "CURRENT: Verbal explanations, printed treatment plans.\nUPGRADE TO: Overjet AI, Pearl AI, or Yapi + intraoral scanner visuals.\nNEW CAPABILITIES: AI-detected conditions shown on X-rays, side-by-side before/after simulations, video treatment explanations, digital treatment plans with financing options embedded.\nROI: Increases case acceptance 15-30%.\nCOST: $200-500/month.", cat: "tech", upgrade: true },
      { t: "ADD: AI scheduling optimization", ai: "NEW TOOL: Dental Intelligence scheduling optimizer or TeleDent.\nCAPABILITIES: Predicts no-shows and overboks accordingly, fills cancellation slots from waitlist automatically, optimizes provider schedules for maximum production, identifies and fills open time proactively.\nROI: Increases chair utilization 10-20% = $100-300K/year.\nCOST: Included in analytics platforms or $200-400/month standalone.", cat: "tech", upgrade: true },
    ]
  },
  { id: "marketing", phase: 4, name: "Marketing & Growth Engine", icon: "📣", duration: "Month 2-4", color: T.red, desc: "Build a patient acquisition machine that delivers predictable, scalable new patient flow.",
    tasks: [
      { t: "Build Grand Slam Offer (Hormozi framework)", ai: "Create an irresistible entry offer: 'Free CBCT + Consultation + 3D Smile Preview + $500 Off Implants'. The goal: remove ALL risk and friction from the first visit. This is your lead magnet that feeds the value ladder.", cat: "marketing", upgrade: false },
      { t: "Launch/optimize Google Ads for high-value procedures", ai: "Budget: $3-5K/month. Target: 'dental implants [city]', 'best dentist [city]', 'Invisalign near me'. Create dedicated landing pages per service (NOT your homepage). Track: cost per lead, cost per patient, ROI by keyword. Target CAC: $150-350.", cat: "marketing", upgrade: false },
      { t: "Launch Meta/Instagram retargeting + cold campaigns", ai: "Budget: $1.5-3K/month. Strategy: retarget website visitors (warm) + cold audience with before/after content. Best formats: video testimonials, before/after sliders, Grand Slam Offer ads. Build lookalike audiences from your patient list.", cat: "marketing", upgrade: false },
      { t: "Build content engine (2 videos + 3 posts per week)", ai: "Content mix: educational (60%), behind-the-scenes (20%), testimonials (10%), promotional (10%). Video ideas: procedure explanations, patient transformations, day-in-the-life, myth-busting, Q&A. Post to: Instagram, Facebook, TikTok, YouTube Shorts.", cat: "marketing", upgrade: false },
      { t: "Create patient referral program ($250-500 per referral)", ai: "Structure: $250-500 credit per referred new patient who starts treatment. Automate the ask: send text 48 hours post-treatment when satisfaction is highest. Track referral source. Target: 20-30% of new patients from referrals.", cat: "marketing", upgrade: false },
      { t: "Build value ladder: cleaning → whitening → Invisalign → implants", ai: "Every patient should ascend. Cleaning patient → offer whitening. Whitening patient → offer Invisalign. Ortho patient → offer implants/cosmetic. Each step increases LTV. Average LTV should be $8K+ per patient.", cat: "marketing", upgrade: false },
      { t: "Optimize Google Business Profile (weekly posts, 50+ reviews)", ai: "Post weekly updates, respond to ALL reviews within 24 hours, add new photos monthly, update services list, use Q&A feature, enable messaging + booking. Target: 4.8+ stars with 200+ reviews.", cat: "marketing", upgrade: false },
      { t: "Launch local community partnerships (10+ referral sources)", ai: "Partner with: gyms, spas, salons, real estate agents, wedding planners, corporate HR offices, schools. Offer: free screening days, employee dental benefits, mutual referral programs. Each partner = 2-5 new patients/month.", cat: "marketing", upgrade: false },
    ]
  },
  { id: "management", phase: 5, name: "Management & AI Agent Delegation", icon: "🤖", duration: "Month 3-6", color: T.purple, desc: "Build your management layer — hire key people OR deploy AI agents to handle what you're currently doing yourself.",
    tasks: [
      { t: "HIRE OR AI: Office Manager / Practice Administrator", ai: "HUMAN OPTION: Hire an A-player office manager ($55-75K) who runs daily operations, manages team, handles HR, runs morning huddles, tracks KPIs. This is your most important hire.\n\nAI AGENT OPTION: Deploy AI scheduling optimizer + automated KPI dashboard + digital workflow automations. Handles 60% of what an office manager does. Still need a human team lead.\n\nRECOMMENDATION: Hire the human. Augment with AI tools. The combination is unbeatable.", cat: "hr", upgrade: false },
      { t: "HIRE OR AI: Treatment Coordinator", ai: "HUMAN OPTION: Hire a dedicated TC ($40-55K + bonus). They present treatment plans, handle financial discussions, close cases. A great TC adds $300-500K/year in accepted treatment.\n\nAI AGENT OPTION: AI-generated treatment presentations with visual aids, automated financing pre-qualification, digital treatment plan delivery with e-signature. Handles presentation support but NOT the personal close.\n\nRECOMMENDATION: This must be a human. Case acceptance is emotional. AI supports, human closes.", cat: "hr", upgrade: false },
      { t: "HIRE OR AI: Marketing Coordinator", ai: "HUMAN OPTION: Hire a marketing person ($40-55K) who manages social media, ad campaigns, content creation, community outreach, reputation management.\n\nAI AGENT OPTION: Use AI tools for content generation (ChatGPT/Claude), automated posting (Hootsuite/Buffer), AI ad optimization (Google/Meta AI), automated review management (Birdeye). Handles 80% of marketing tasks.\n\nRECOMMENDATION: Start with AI tools + part-time VA ($15-20/hr). Hire full-time when revenue exceeds $1.5M.", cat: "hr", upgrade: true },
      { t: "DEPLOY: AI receptionist for after-hours and overflow calls", ai: "TOOL: Slingshot AI, Synthflow, or Bland.ai\nCAPABILITIES: Answers calls 24/7, books appointments directly into your PMS, handles FAQs (insurance, hours, directions), triages emergencies, sends follow-up texts, captures leads that would be missed.\nROI: Captures 15-25 calls/week that currently go to voicemail = $30-80K/year.\nCOST: $200-500/month.", cat: "tech", upgrade: true },
      { t: "DEPLOY: AI-powered patient follow-up sequences", ai: "TOOL: Weave, RevenueWell, or custom automation via Zapier.\nSEQUENCES TO BUILD:\n• Post-consultation nurture (7 touches over 30 days for unconverted consults)\n• Post-treatment follow-up (check-in at 24hr, 1 week, 1 month)\n• Recall campaign (automated at 3, 6, 9, 12 months)\n• Reactivation campaign (12+ months, 6-touch sequence)\n• Referral ask (48hr after treatment completion)\n• Review request (2hr after appointment)\nROI: Recovers 20-35% of unconverted treatment plans = $100-300K/year.", cat: "tech", upgrade: true },
      { t: "Create weekly KPI review meeting (non-negotiable Monday ritual)", ai: "AGENDA (30 min max):\n1. Last week's numbers: production, collections, new patients, case acceptance (5 min)\n2. Wins — celebrate what went right (3 min)\n3. Misses — what fell short and why (5 min)\n4. This week's goals and focus areas (5 min)\n5. Individual accountability — each person states their #1 priority (10 min)\n6. Close with energy\n\nRULES: Start on time, end on time, data-driven not opinion-driven, everyone participates.", cat: "operations", upgrade: false },
      { t: "Build morning huddle protocol (daily 10-minute standup)", ai: "HUDDLE TEMPLATE:\n1. Review today's schedule — who's coming, what procedures (2 min)\n2. Identify high-value opportunities — undiagnosed treatment, pending plans (2 min)\n3. Confirm unconfirmed appointments — assign follow-up calls (2 min)\n4. Lab cases due — verify everything is ready (1 min)\n5. Patient notes — birthdays, special needs, anxiety flags (2 min)\n6. Yesterday's production number + today's goal (1 min)\n\nDO THIS EVERY. SINGLE. DAY.", cat: "operations", upgrade: false },
      { t: "Implement provider scorecards (monthly performance reviews)", ai: "TRACK PER PROVIDER:\n• Daily production average (target varies by specialty)\n• Collections rate (target: 98%+)\n• Case acceptance rate (target: 70%+)\n• Procedures per patient visit\n• Hygiene exam conversion rate\n• Patient satisfaction scores\n• Schedule utilization\n\nReview monthly 1-on-1 with each provider. Tie bonuses to performance metrics.", cat: "operations", upgrade: false },
    ]
  },
  { id: "scale", phase: 6, name: "Scale & Multiply", icon: "🚀", duration: "Month 6-18", color: T.accent, desc: "You've optimized. Now multiply. Add specialties, hire associates, prep for second location or acquisition.",
    tasks: [
      { t: "Add specialty services to increase revenue per patient", ai: "If you're GP only, add: implants (highest ROI), Invisalign (volume play), sleep apnea (emerging), Botox/filler (cosmetic upsell). Each specialty adds $200-500K/year. Either hire specialists or bring in itinerant providers 1-2 days/week.", cat: "strategy", upgrade: false },
      { t: "Hire associate dentist to scale production capacity", ai: "When to hire: you're producing $1M+ personally and chairs are 85%+ utilized. Compensation models: daily rate ($700-1200/day), % of production (25-30% collections), or hybrid. Cultural fit is non-negotiable — they represent your brand.", cat: "hr", upgrade: false },
      { t: "Build operations manual (the 'franchise playbook')", ai: "Document EVERYTHING: front desk procedures, clinical workflows, treatment coordinator scripts, billing processes, marketing SOPs, hiring/firing procedures, emergency protocols. This manual is what makes your practice scalable and sellable.", cat: "operations", upgrade: false },
      { t: "Evaluate expansion: second location vs. maximize current", ai: "Before opening #2, ask: Is location #1 at 90%+ capacity? Do I have a manager who can run #1 without me? Is my operations manual complete? If yes to all three → start scouting location #2 or acquisition targets.", cat: "strategy", upgrade: false },
      { t: "Remove yourself from daily clinical production (owner mindset shift)", ai: "The goal: work ON the business, not IN it. Reduce your clinical days from 5 → 4 → 3 → 2. Use freed time for: strategic planning, marketing oversight, team development, acquisition scouting, community relationships. Your hourly rate as CEO > your hourly rate as clinician.", cat: "strategy", upgrade: false },
      { t: "Set up financial dashboards for multi-location management", ai: "Track per-location: production, collections, overhead, profit margin, new patients, case acceptance, provider productivity. Compare locations side-by-side. Use: Dental Intel, Jarvis, or custom dashboard.", cat: "finance", upgrade: false },
    ]
  },
];

// ═══════════════════════════════════════════════
// ACQUISITION PATH — BUY & SCALE
// ═══════════════════════════════════════════════

const ACQUISITION_PHASES = [
  { id: "acq_strategy", phase: 1, name: "Acquisition Strategy & Targeting", icon: "🎯", duration: "Month 1-2", color: T.gold, desc: "Define your buy box, build your deal team, and start sourcing targets. The Hormozi acquisition.com playbook adapted for dental.",
    tasks: [
      { t: "Define your acquisition criteria ('buy box')", ai: "IDEAL TARGET PROFILE:\n• Revenue: $600K-$2M (sweet spot for value-add)\n• EBITDA margin: 15-25% (room to improve to 35-45%)\n• Location: within 30-mile radius of your base (operational efficiency)\n• Operatories: 4-6 (room to add capacity)\n• Patient base: 1,500+ active patients\n• Seller motivation: retiring, burned out, relocating, health issues\n• Lease: 5+ years remaining or renewable\n• NO red flags: lawsuits, board complaints, terrible online reputation\n\nDEAL BREAKERS: declining revenue 3+ years, <3 years on lease with no renewal, seller has non-compete issues, major equipment replacement needed.", cat: "strategy", upgrade: false },
      { t: "Assemble your deal team", ai: "YOU NEED:\n1. Dental-specific M&A attorney ($5-15K for full deal)\n2. Dental CPA / financial advisor ($3-8K for due diligence)\n3. Practice appraiser / valuator ($3-5K)\n4. SBA-preferred lender (Bank of America, Live Oak, Provide)\n5. Insurance credentialing specialist\n6. Dental broker relationships (3-5 brokers)\n\nDon't use a general business attorney or accountant. Dental M&A has unique nuances they'll miss.", cat: "legal", upgrade: false },
      { t: "Register with 5+ dental practice brokers", ai: "TOP DENTAL BROKERS:\n• AFTCO (nationwide)\n• Henry Schein Practice Transitions\n• Practice Transitions Group\n• DDSmatch\n• Local/regional brokers in your state\n\nAlso search: BizBuySell, LoopNet (dental category), state dental association classifieds, dental school alumni networks.\n\nTell each broker: your buy box, timeline, financing status, experience level.", cat: "strategy", upgrade: false },
      { t: "Get pre-approved for SBA acquisition financing", ai: "SBA 7(a) LOAN — THE GOLD STANDARD:\n• Borrow up to $5M\n• 10-year term typical for dental acquisitions\n• 10-15% down payment required\n• Rates: Prime + 1-2.75%\n• Include: purchase price + working capital + equipment\n\nPRE-APPROVAL REQUIREMENTS:\n• Personal financial statement\n• 3 years personal tax returns\n• Resume/CV\n• Business plan (1-2 pages is fine)\n• Credit score 680+ preferred\n\nGET THIS DONE BEFORE you find a practice. Sellers take you seriously with pre-approval.", cat: "finance", upgrade: false },
      { t: "Build acquisition financial model (valuation framework)", ai: "DENTAL PRACTICE VALUATION METHODS:\n1. % of Revenue: typically 60-85% of annual collections\n2. EBITDA Multiple: 3-5x adjusted EBITDA (most common)\n3. Asset-based: equipment + patient records + goodwill\n\nYOUR TARGET: Buy at 0.6-0.8x revenue or 3-4x EBITDA, then grow to 5-7x EBITDA through your operational improvements.\n\nRED FLAG: any practice priced above 1x revenue or 5x EBITDA without exceptional justification.", cat: "finance", upgrade: false },
      { t: "Create target scorecard (evaluate each practice 1-100)", ai: "SCORING CRITERIA (100 points total):\n• Revenue stability/growth (15 pts)\n• Location quality & demographics (15 pts)\n• Patient base size & loyalty (10 pts)\n• Equipment condition (10 pts)\n• Lease terms (10 pts)\n• Online reputation (10 pts)\n• Staff quality & retention (10 pts)\n• Growth potential (specialty gaps) (10 pts)\n• Seller motivation & transition willingness (5 pts)\n• Price relative to value (5 pts)\n\nOnly pursue practices scoring 70+.", cat: "strategy", upgrade: false },
    ]
  },
  { id: "acq_diligence", phase: 2, name: "Due Diligence Deep Dive", icon: "🔬", duration: "Month 2-4", color: T.blue, desc: "Verify everything. Trust but verify. This is where bad deals die — and that's a GOOD thing.",
    tasks: [
      { t: "Request and analyze 3 years of tax returns", ai: "VERIFY: reported income matches production reports. Look for: cash income not reported (ethical red flag), declining revenue trends, unusual expense spikes, owner perks disguised as business expenses. Your CPA should reconcile tax returns to PMS production reports.", cat: "finance", upgrade: false },
      { t: "Analyze production by procedure code (CDT analysis)", ai: "Pull production by CDT code for 3 years. Looking for:\n• Revenue concentration risk (>50% from one procedure type)\n• Mix of high vs. low-value procedures\n• Hygiene production % (healthy = 25-33% of total)\n• Procedure trends — are implant/ortho cases growing or declining?\n• Fee schedule comparison to UCR — are they undercharging?", cat: "finance", upgrade: false },
      { t: "Review A/R aging and collections history", ai: "REQUEST: A/R aging report (current, 30, 60, 90, 120+ days). Target: <5% over 60 days. Heavy old A/R means: poor collections practices, insurance billing issues, or patient financial problems. This is both a risk AND an opportunity — you can fix collections.", cat: "finance", upgrade: false },
      { t: "Audit patient base (active count, demographics, insurance mix)", ai: "VERIFY:\n• Active patients (visited in 18 months) — should match seller's claims\n• Age distribution — heavy 65+ = natural attrition concern\n• Insurance mix — heavy Medicaid = low reimbursement risk\n• Patient geographic distribution — patients within 5-mile radius?\n• New patient trends — growing, flat, or declining?", cat: "operations", upgrade: false },
      { t: "Inspect all equipment (age, condition, remaining useful life)", ai: "CREATE EQUIPMENT INVENTORY:\n• List every major piece of equipment\n• Age and condition (1-10 scale)\n• Remaining useful life\n• Replacement cost\n• Any items needing immediate replacement\n\nRED FLAGS: 15+ year old chairs, failing compressor/vacuum, no digital imaging, outdated sterilizers. Factor replacement costs into your offer price.", cat: "operations", upgrade: false },
      { t: "Review commercial lease in detail (with attorney)", ai: "CRITICAL LEASE TERMS:\n• Remaining term (need 5+ years or renewal option)\n• Monthly rent and annual escalation (3% max is standard)\n• Transferability / assignment clause (can you take over the lease?)\n• Personal guarantee requirements\n• Build-out restrictions\n• Exclusive use clause (no other dentist in building/plaza)\n• Signage rights\n• Parking requirements\n\nLEASE ISSUES KILL DEALS. Review with your attorney before submitting LOI.", cat: "legal", upgrade: false },
      { t: "Check online reputation and patient reviews", ai: "REVIEW:\n• Google rating and review count\n• Yelp rating\n• Healthgrades profile\n• Facebook reviews\n• BBB complaints\n• State dental board complaints/disciplinary actions\n\nRED FLAG: below 4.0 stars, multiple malpractice complaints, unaddressed negative reviews. Reputation can be rebuilt but factor the effort into your timeline.", cat: "marketing", upgrade: false },
      { t: "Assess staff (quality, tenure, compensation, flight risk)", ai: "MEET THE TEAM (before closing if possible):\n• How long has each person been there?\n• What are they paid vs. market rate?\n• Are key people likely to stay post-acquisition?\n• Is the office manager indispensable (risk if they leave)?\n• Any HR issues, complaints, or pending claims?\n\nSTAFF RETENTION is the #1 post-acquisition risk. Plan accordingly.", cat: "hr", upgrade: false },
      { t: "Verify all licenses, DEA, NPI, malpractice are current", ai: "VERIFY:\n• Seller's dental license — active, no restrictions\n• DEA registration — current, no issues\n• NPI — correct and active\n• Malpractice insurance — current, check for pending claims\n• Business license — current\n• Any pending or past state dental board complaints\n\nUse your attorney to run a comprehensive background check.", cat: "legal", upgrade: false },
      { t: "Check for any pending litigation or legal issues", ai: "YOUR ATTORNEY SHOULD:\n• Search court records for pending lawsuits\n• Check state dental board for complaints\n• Verify no OSHA violations\n• Check for tax liens or judgments\n• Review all vendor contracts for assignability\n• Verify no non-compete conflicts\n\nAny undisclosed legal issues = renegotiate or walk away.", cat: "legal", upgrade: false },
    ]
  },
  { id: "acq_deal", phase: 3, name: "Negotiate & Close the Deal", icon: "🤝", duration: "Month 3-5", color: T.orange, desc: "Submit your offer, negotiate terms, secure financing, and close. Every detail matters.",
    tasks: [
      { t: "Submit Letter of Intent (LOI) with key terms", ai: "LOI SHOULD INCLUDE:\n• Purchase price (based on your valuation analysis)\n• Deal structure (asset purchase vs. entity purchase — asset is almost always better)\n• Down payment amount and financing terms\n• Due diligence period (45-60 days)\n• Transition period (seller stays 60-90 days post-close)\n• Non-compete clause (5 years, 10-15 mile radius)\n• Seller's role during transition\n• Key contingencies (financing, due diligence, lease transfer)\n• Exclusivity period (you don't want them shopping your offer)\n\nLOI is non-binding but sets the framework. Don't overthink it — get it signed and move to diligence.", cat: "legal", upgrade: false },
      { t: "Negotiate purchase price and deal structure", ai: "NEGOTIATION LEVERAGE:\n• Declining revenue trends → lower price\n• Equipment needing replacement → subtract from price\n• Heavy PPO dependence → revenue risk → lower price\n• Seller urgency (retirement, health) → better terms\n• Lease concerns → negotiate price or walk\n\nSTRUCTURE TIPS:\n• Asset purchase (not stock/entity) for tax benefits\n• Allocate maximum to goodwill and non-compete (amortizable)\n• Include working capital in the deal\n• Negotiate seller financing for 10-20% (shows seller confidence)", cat: "finance", upgrade: false },
      { t: "Finalize SBA loan package and submit to lender", ai: "LOAN PACKAGE CONTENTS:\n• Signed LOI or Purchase Agreement\n• Practice financial statements (3 years)\n• Practice tax returns (3 years)\n• Your personal financial statement\n• Your personal tax returns (3 years)\n• Resume/CV\n• Business plan with financial projections\n• Lease agreement\n• Equipment list with values\n• Practice appraisal report\n\nTIMELINE: SBA approval typically takes 30-45 days from submission.", cat: "finance", upgrade: false },
      { t: "Execute definitive Asset Purchase Agreement (APA)", ai: "APA KEY SECTIONS:\n• Purchase price and allocation\n• Assets included/excluded\n• Representations and warranties (seller guarantees)\n• Indemnification (who pays if problems emerge)\n• Closing conditions\n• Non-compete and non-solicitation covenants\n• Employee transition terms\n• Patient records transfer\n• Insurance panel transfer procedures\n• Closing date and procedures\n\nYOUR ATTORNEY drafts or reviews. Never sign without legal review.", cat: "legal", upgrade: false },
      { t: "Begin insurance credentialing transfer (start 90+ days before close)", ai: "CRITICAL PATH — DO NOT DELAY:\n• Apply for YOUR credentials with every insurance company the practice accepts\n• Some allow 'assignment' of existing contract, others require new application\n• Each company has different processing times (60-120 days)\n• Submit credentialing applications THE DAY you sign the LOI\n• Hire a credentialing specialist if needed ($2-5K)\n\nGAP RISK: If credentialing isn't complete by closing, you can't bill insurance = no revenue.", cat: "finance", upgrade: false },
      { t: "Transfer or establish all licenses and permits", ai: "TRANSFER/NEW APPLICATIONS:\n• Facility license (new application in your name)\n• DEA registration (new registration at new address)\n• NPI (update Type 2 organizational NPI)\n• Business license (new application)\n• Radiation safety registration (transfer or new)\n• OSHA compliance (update written programs)\n• HIPAA (update policies, sign new BAAs)\n\nStart these 60-90 days before closing date.", cat: "legal", upgrade: false },
      { t: "Close the deal (signing day)", ai: "CLOSING DAY CHECKLIST:\n• Final walk-through of practice (condition as expected)\n• Sign APA and all closing documents\n• Wire purchase funds to escrow/title company\n• Receive keys, alarm codes, passwords, admin access\n• Transfer utilities to your name\n• Receive all patient records (digital and physical)\n• Receive all vendor contracts\n• Verify insurance on all assets\n• Celebrate — you just bought a dental practice 🎉", cat: "legal", upgrade: false },
    ]
  },
  { id: "acq_transition", phase: 4, name: "Post-Acquisition Transition", icon: "🔄", duration: "Month 5-8", color: T.purple, desc: "The first 90 days post-acquisition determine success or failure. Communication, systems, and culture — in that order.",
    tasks: [
      { t: "Day 1: Send patient communication letter", ai: "LETTER MUST CONVEY:\n• Warm, reassuring tone — change is scary for patients\n• You're committed to same quality of care\n• Staff is staying (if true — and it should be)\n• Improvements coming (extended hours, new technology, new services)\n• Your background and qualifications\n• Contact info for questions\n\nSEND: physical letter + email + SMS. Post on Google Business Profile and social media.", cat: "operations", upgrade: false },
      { t: "Day 1: All-staff meeting — vision, no layoffs, excitement", ai: "MEETING STRUCTURE (60 min):\n1. Introduce yourself — personal story, why dentistry, why this practice (10 min)\n2. Reassure: everyone's job is safe. No immediate changes. (5 min)\n3. Share your vision: where this practice is going (10 min)\n4. Listen: what do THEY think needs improving? (15 min)\n5. Immediate changes: what stays the same, what's coming (10 min)\n6. Q&A — answer everything honestly (10 min)\n\nCRITICAL: Be present, be human, be optimistic. First impressions with staff determine retention.", cat: "hr", upgrade: false },
      { t: "Week 1: Meet every team member 1-on-1 (30 min each)", ai: "ASK EACH PERSON:\n• What do you love about working here?\n• What frustrates you the most?\n• What would you change if you could?\n• What are your career goals?\n• What do you need from me to be successful?\n• Any concerns about the transition?\n\nTAKE NOTES. Follow through on what you learn. These conversations build trust faster than anything else.", cat: "hr", upgrade: false },
      { t: "Week 1-2: Maintain seller's presence for patient introductions", ai: "The selling doctor should:\n• Introduce you to patients personally\n• Be in the office 3-5 days/week for first 2 weeks\n• Reduce to 2-3 days/week for weeks 3-4\n• Available by phone for weeks 5-8\n• Full transition by 60-90 days\n\nThis 'warm handoff' is worth MORE than anything else in the deal. Negotiate this in the purchase agreement.", cat: "operations", upgrade: false },
      { t: "Week 2-4: Install your technology stack", ai: "PHASED TECHNOLOGY UPGRADE:\nWeek 2: Set up AI phone system + patient communication platform\nWeek 3: Install practice analytics dashboard + upgrade PMS if needed\nWeek 4: Digital imaging upgrade (CBCT, scanner if not present)\nMonth 2: Launch automated workflows (reminders, recalls, follow-ups)\n\nDON'T change everything at once. Phase it. Train the team on each system before adding the next.", cat: "tech", upgrade: true },
      { t: "Week 3-4: Train team on your treatment presentation protocol", ai: "TRAINING FOCUS:\n• Treatment coordinator: new case presentation scripts\n• Front desk: new phone scripts and booking protocol\n• Clinical: new documentation standards\n• All: morning huddle protocol\n• All: KPI awareness — what numbers matter and why\n\nUSE: role-playing, recorded calls, live observation, weekly feedback sessions. Change takes 90 days to stick.", cat: "operations", upgrade: false },
      { t: "Month 2-3: Launch reactivation campaign on acquired patient base", ai: "YOU INHERITED A GOLDMINE of overdue patients. Immediately:\n1. Pull all patients not seen in 6+ months\n2. Send personalized 'Under New Management' outreach\n3. Include compelling offer (free exam + X-rays, or discount)\n4. 3-touch sequence: SMS → email → phone call\n5. Target: reactivate 15-25% = $100-300K in treatment\n\nThis is the FASTEST ROI post-acquisition.", cat: "marketing", upgrade: false },
      { t: "Month 2-3: Embed new KPIs and accountability systems", ai: "IMPLEMENT:\n• Daily production tracking (screen in break room)\n• Morning huddle (non-negotiable, daily)\n• Weekly KPI meeting (Monday, 30 min)\n• Monthly provider scorecards\n• Monthly P&L review\n\nSTAFF RESISTANCE IS NORMAL. Be patient but firm. 'We track these numbers because they tell us how well we're serving patients.'", cat: "operations", upgrade: false },
    ]
  },
  { id: "acq_growth", phase: 5, name: "Inject Growth — Hit 3-5x EBITDA", icon: "📈", duration: "Month 6-18", color: T.accent, desc: "The acquisition was just the beginning. Now inject your systems, add specialties, scale marketing, and 3-5x the EBITDA within 18 months.",
    tasks: [
      { t: "Launch full marketing engine on acquired practice", ai: "NOW you go aggressive:\n• Google Ads: $3-5K/month targeting implants, cosmetic, emergency\n• Meta retargeting: $1.5-3K/month\n• Grand Slam Offer campaign\n• Referral program launch ($250-500 per referral)\n• Content engine: 2 videos + 3 posts per week\n• Google Business optimization: target 100+ reviews in 6 months\n\nGOAL: 40-60 new patients/month within 6 months.", cat: "marketing", upgrade: false },
      { t: "Add specialty services (implants, ortho, perio, cosmetic)", ai: "This is the BIGGEST revenue lever:\n• Add implants: $4K-30K per case. Recruit specialist or train yourself.\n• Add Invisalign: $3-7K per case. Volume play with marketing.\n• Add sleep apnea: $2-5K per appliance. Emerging market.\n• Add Botox/filler: $500-2K per treatment. Quick add-on.\n\nEach specialty can add $200-500K/year in revenue. Start with ONE, master it, add the next.", cat: "strategy", upgrade: false },
      { t: "Optimize overhead to <55% (from typical acquired 65-70%)", ai: "BIGGEST OVERHEAD REDUCTIONS:\n• Renegotiate supply contracts (switch to Oryx or bulk buy) — save 10-15%\n• Optimize lab costs (negotiate volume discounts or switch labs) — save 15-20%\n• Streamline staffing (no overstaffing, right-size to production) — save 5-10%\n• Reduce marketing waste (kill underperforming channels) — save 20-30%\n• Implement energy efficiency (LED, smart HVAC) — save $200-500/month\n\nEvery 1% overhead reduction = $10-20K more profit on a $1M practice.", cat: "finance", upgrade: false },
      { t: "Grow collections to 98%+ (from typical acquired 92-95%)", ai: "COLLECTIONS IMPROVEMENT PLAYBOOK:\n• Payment at time of service policy (immediate impact)\n• Automated payment reminders\n• Offer multiple payment options (CC, financing, membership)\n• Clean up old A/R (aggressive 30-day collections push)\n• Submit insurance claims within 24 hours\n• Follow up on unpaid claims at 15 days (not 30)\n• Outsource old A/R to dental-specific collections agency\n\nIMPACT: Going from 93% to 98% on a $1.5M practice = $75K more cash.", cat: "finance", upgrade: false },
      { t: "Increase case acceptance to 70%+ (from typical acquired 45-55%)", ai: "CASE ACCEPTANCE SYSTEM:\n1. Visual diagnosis (intraoral camera, CBCT, scanner) — patients must SEE the problem\n2. Same-room treatment presentation — not a separate consult\n3. Treatment coordinator handles financial discussion — doctor stays clinical\n4. Always offer financing (CareCredit, Proceed, Sunbit)\n5. Create urgency without fear — 'Here's what happens if we wait'\n6. Follow up on unaccepted treatment (7-touch sequence over 30 days)\n\nIMPACT: Going from 50% to 70% on $2M in presented treatment = $400K more accepted.", cat: "operations", upgrade: false },
      { t: "Scale to 85%+ chair utilization", ai: "UTILIZATION TACTICS:\n• AI scheduling optimizer to fill gaps\n• Automated waitlist fills cancellations\n• Extended hours (early morning, one evening, alternating Saturdays)\n• Same-day treatment protocol\n• Reduce no-shows below 5% with confirmation automation\n• Add hygiene days as demand grows\n\nIMPACT: Each 5% increase in utilization on a 6-chair practice = $150-250K/year more production.", cat: "operations", upgrade: false },
      { t: "Prepare for next acquisition (roll-up strategy)", ai: "WHEN YOU'VE HIT YOUR EBITDA TARGETS:\n1. Document your integration playbook (you'll use it again)\n2. Refinance the acquisition loan (better terms with proven performance)\n3. Use cash flow to fund next acquisition down payment\n4. Start scouting target #2 while practice #1 runs on systems\n5. Build toward DSO-level scale (3-5 locations)\n\nTHE HORMOZI PLAY: buy underperforming, inject systems, scale EBITDA, repeat. Each acquisition gets easier because your playbook is proven.", cat: "strategy", upgrade: false },
    ]
  },
];

// ═══════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════

const Badge = ({ children, color = T.accent }) => <span style={{ background: `${color}12`, color, padding: "2px 9px", borderRadius: 20, fontSize: 10, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", border: `1px solid ${color}20`, whiteSpace: "nowrap" }}>{children}</span>;
const Pbar = ({ v, color = T.accent, h = 5 }) => <div style={{ height: h, background: "rgba(255,255,255,0.04)", borderRadius: h, overflow: "hidden", flex: 1 }}><div style={{ height: "100%", width: `${Math.min(v, 100)}%`, background: color, borderRadius: h, transition: "width 0.8s" }} /></div>;
const CAT_ICONS = { finance: "💰", operations: "⚙️", marketing: "📣", tech: "🔧", hr: "👥", legal: "⚖️", strategy: "🎯" };

// ═══════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════

export default function DentalOSPaths() {
  const [path, setPath] = useState(null); // null = select, "existing" | "acquisition"
  const [taskStates, setTaskStates] = useState({});
  const [openPhase, setOpenPhase] = useState(null);
  const [openTask, setOpenTask] = useState(null);
  const [catFilter, setCatFilter] = useState("all");

  const toggleTask = (phaseId, taskIdx) => {
    setTaskStates(p => ({ ...p, [`${phaseId}-${taskIdx}`]: !p[`${phaseId}-${taskIdx}`] }));
  };

  const phases = path === "existing" ? EXISTING_PHASES : path === "acquisition" ? ACQUISITION_PHASES : [];

  const getPhaseProgress = (phase) => {
    const done = phase.tasks.filter((_, i) => taskStates[`${phase.id}-${i}`]).length;
    return phase.tasks.length ? (done / phase.tasks.length) * 100 : 0;
  };

  const getOverallProgress = () => {
    const total = phases.reduce((s, p) => s + p.tasks.length, 0);
    const done = phases.reduce((s, p) => s + p.tasks.filter((_, i) => taskStates[`${p.id}-${i}`]).length, 0);
    return total ? (done / total) * 100 : 0;
  };

  useEffect(() => { if (phases.length && !openPhase) setOpenPhase(phases[0].id); }, [path]);

  const currentPhase = phases.find(p => p.id === openPhase);
  const filteredTasks = currentPhase?.tasks.filter(t => catFilter === "all" || t.cat === catFilter) || [];

  // ── PATH SELECT SCREEN ──
  if (!path) return (
    <div style={{ minHeight: "100vh", background: T.bg, color: T.text, fontFamily: "'Outfit', system-ui", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 32 }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Crimson+Pro:ital,wght@0,400;0,700;1,400&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet" />
      <div style={{ textAlign: "center", marginBottom: 40 }}>
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "rgba(201,168,76,0.06)", border: "1px solid rgba(201,168,76,0.12)", borderRadius: 20, padding: "5px 16px", marginBottom: 16 }}>
          <div style={{ width: 6, height: 6, borderRadius: "50%", background: T.gold, boxShadow: `0 0 10px ${T.gold}`, animation: "pulse 2s infinite" }} />
          <span style={{ fontSize: 10, color: T.gold, fontWeight: 700, letterSpacing: 2, textTransform: "uppercase" }}>DentalOS — Choose Your Path</span>
        </div>
        <h1 style={{ fontSize: "clamp(28px, 5vw, 48px)", fontWeight: 900, lineHeight: 1.05, background: `linear-gradient(135deg, #F0F4F8 30%, ${T.gold})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>Where Are You Today?</h1>
        <p style={{ fontSize: 15, color: T.muted, marginTop: 8, maxWidth: 500, margin: "8px auto 0", fontFamily: "'Crimson Pro', serif", fontStyle: "italic" }}>Each path is a complete implementation roadmap with AI guidance at every step.</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 24, maxWidth: 900, width: "100%" }}>
        {[
          { id: "existing", icon: "🏥", name: "Optimize Existing Practice", tagline: "Scale what you have", color: T.cyan, desc: "You already have a practice running — phones, website, team. Now upgrade with AI, add powerful protocols, scale marketing, and build management systems that let you step back.", phases: EXISTING_PHASES.length, tasks: EXISTING_PHASES.reduce((s, p) => s + p.tasks.length, 0), highlights: ["40-point diagnostic audit", "AI upgrade modules with ROI", "Hire vs. AI Agent decisions", "Hormozi growth engine", "Management delegation system", "Scale to multi-location"] },
          { id: "acquisition", icon: "🤝", name: "Acquire & Scale a Practice", tagline: "Buy, transform, multiply", color: T.orange, desc: "Buy an underperforming practice, inject your systems and AI, and 3-5x EBITDA within 18 months. The acquisition.com playbook for dental.", phases: ACQUISITION_PHASES.length, tasks: ACQUISITION_PHASES.reduce((s, p) => s + p.tasks.length, 0), highlights: ["Acquisition buy box framework", "10-point due diligence", "SBA financing playbook", "Post-acquisition transition", "90-day integration plan", "3-5x EBITDA growth engine"] },
        ].map(p => (
          <div key={p.id} onClick={() => setPath(p.id)} style={{ background: T.card, border: `1px solid ${T.border}`, borderRadius: 24, padding: 32, cursor: "pointer", transition: "all 0.3s", position: "relative", overflow: "hidden" }} onMouseOver={e => { e.currentTarget.style.borderColor = p.color + "40"; e.currentTarget.style.transform = "translateY(-4px)"; }} onMouseOut={e => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.transform = "none"; }}>
            <div style={{ position: "absolute", top: -40, right: -40, width: 160, height: 160, background: `radial-gradient(circle, ${p.color}06, transparent)`, borderRadius: "50%" }} />
            <div style={{ fontSize: 48, marginBottom: 14 }}>{p.icon}</div>
            <Badge color={p.color} >{p.tagline}</Badge>
            <h2 style={{ fontSize: 24, fontWeight: 900, marginTop: 10, marginBottom: 6, color: p.color }}>{p.name}</h2>
            <p style={{ fontSize: 14, color: T.muted, lineHeight: 1.6, marginBottom: 18 }}>{p.desc}</p>
            <div style={{ display: "flex", gap: 20, marginBottom: 18 }}>
              <div><div style={{ fontSize: 24, fontWeight: 900 }}>{p.phases}</div><div style={{ fontSize: 10, color: T.muted, letterSpacing: 1, textTransform: "uppercase" }}>Phases</div></div>
              <div><div style={{ fontSize: 24, fontWeight: 900 }}>{p.tasks}</div><div style={{ fontSize: 10, color: T.muted, letterSpacing: 1, textTransform: "uppercase" }}>Tasks</div></div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 20 }}>
              {p.highlights.map((h, i) => <div key={i} style={{ fontSize: 12, color: "#8899AA", display: "flex", alignItems: "center", gap: 6 }}><span style={{ color: p.color }}>✓</span> {h}</div>)}
            </div>
            <button style={{ width: "100%", background: `linear-gradient(135deg, ${p.color}, ${p.color}CC)`, color: T.bg, border: "none", borderRadius: 12, padding: "13px 24px", fontWeight: 800, fontSize: 15, cursor: "pointer" }}>Start This Path →</button>
          </div>
        ))}
      </div>
      <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}} *{box-sizing:border-box;margin:0;padding:0} button{transition:0.2s} button:hover{filter:brightness(1.1)}`}</style>
    </div>
  );

  // ── MAIN PATH VIEW ──
  const pathConfig = path === "existing" ? { name: "Optimize Existing Practice", icon: "🏥", color: T.cyan } : { name: "Acquire & Scale a Practice", icon: "🤝", color: T.orange };

  return (
    <div style={{ minHeight: "100vh", background: T.bg, color: T.text, fontFamily: "'Outfit', system-ui" }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Crimson+Pro:ital,wght@0,400;0,700;1,400&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet" />

      {/* Header */}
      <div style={{ background: "rgba(255,255,255,0.01)", borderBottom: `1px solid ${T.border}`, padding: "10px 20px", display: "flex", alignItems: "center", justifyContent: "space-between", position: "sticky", top: 0, zIndex: 50, backdropFilter: "blur(16px)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button onClick={() => { setPath(null); setOpenPhase(null); setOpenTask(null); setCatFilter("all"); }} style={{ background: "none", border: `1px solid ${T.border}`, borderRadius: 7, padding: "4px 10px", color: T.muted, cursor: "pointer", fontSize: 13 }}>←</button>
          <div style={{ width: 30, height: 30, borderRadius: 8, background: `linear-gradient(135deg, ${pathConfig.color}, ${pathConfig.color}AA)`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 15 }}>{pathConfig.icon}</div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 900, color: pathConfig.color }}>{pathConfig.name}</div>
            <div style={{ fontSize: 9, color: T.muted, letterSpacing: 2, textTransform: "uppercase" }}>DentalOS • {phases.length} phases • {phases.reduce((s, p) => s + p.tasks.length, 0)} tasks</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 11, color: T.muted }}>Progress:</span>
          <div style={{ width: 90 }}><Pbar v={getOverallProgress()} color={pathConfig.color} h={4} /></div>
          <span style={{ fontSize: 12, fontWeight: 800, color: pathConfig.color }}>{Math.round(getOverallProgress())}%</span>
        </div>
      </div>

      <div style={{ display: "flex", minHeight: "calc(100vh - 51px)" }}>
        {/* Sidebar: Phases */}
        <div style={{ width: 250, borderRight: `1px solid ${T.border}`, padding: "14px 12px", overflowY: "auto", flexShrink: 0, background: "rgba(255,255,255,0.004)" }}>
          <div style={{ fontSize: 9, color: T.muted, letterSpacing: 2, textTransform: "uppercase", fontWeight: 700, paddingLeft: 6, marginBottom: 10 }}>Implementation Phases</div>
          {phases.map(phase => {
            const prog = getPhaseProgress(phase);
            return (
              <div key={phase.id} onClick={() => { setOpenPhase(phase.id); setOpenTask(null); setCatFilter("all"); }} style={{ background: openPhase === phase.id ? `${phase.color}08` : "transparent", border: `1px solid ${openPhase === phase.id ? phase.color + "18" : "transparent"}`, borderRadius: 12, padding: "11px 12px", marginBottom: 6, cursor: "pointer", transition: "0.2s" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
                  <div style={{ width: 24, height: 24, borderRadius: 7, background: openPhase === phase.id ? phase.color : "rgba(255,255,255,0.05)", color: openPhase === phase.id ? T.bg : T.muted, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 900 }}>{phase.phase}</div>
                  <div style={{ fontSize: 12, fontWeight: 800, color: openPhase === phase.id ? phase.color : "#C8D2DC" }}>{phase.name}</div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                  <span style={{ fontSize: 14 }}>{phase.icon}</span>
                  <span style={{ fontSize: 10, color: T.muted }}>{phase.duration}</span>
                </div>
                <Pbar v={prog} color={prog === 100 ? T.green : phase.color} h={3} />
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
                  <span style={{ fontSize: 10, color: T.muted }}>{phase.tasks.length} tasks</span>
                  <span style={{ fontSize: 10, fontWeight: 700, color: phase.color }}>{Math.round(prog)}%</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Main Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
          {currentPhase && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              {/* Phase Header */}
              <div style={{ background: `${currentPhase.color}06`, border: `1px solid ${currentPhase.color}12`, borderRadius: 16, padding: "18px 22px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
                  <span style={{ fontSize: 28 }}>{currentPhase.icon}</span>
                  <div>
                    <div style={{ fontSize: 10, color: currentPhase.color, letterSpacing: 1.5, textTransform: "uppercase", fontWeight: 700 }}>Phase {currentPhase.phase} · {currentPhase.duration}</div>
                    <div style={{ fontSize: 22, fontWeight: 900 }}>{currentPhase.name}</div>
                  </div>
                </div>
                <div style={{ fontSize: 13, color: "#8899AA", lineHeight: 1.6, marginTop: 4 }}>{currentPhase.desc}</div>
              </div>

              {/* Category Filters */}
              <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                {["all", ...new Set(currentPhase.tasks.map(t => t.cat))].map(c => (
                  <button key={c} onClick={() => setCatFilter(c)} style={{ background: catFilter === c ? `${currentPhase.color}10` : "transparent", border: `1px solid ${catFilter === c ? currentPhase.color + "25" : T.border}`, color: catFilter === c ? currentPhase.color : T.muted, borderRadius: 7, padding: "4px 12px", fontSize: 11, fontWeight: 700, cursor: "pointer", textTransform: "capitalize", display: "flex", alignItems: "center", gap: 4 }}>
                    {c !== "all" && <span style={{ fontSize: 12 }}>{CAT_ICONS[c]}</span>}{c === "all" ? "All Categories" : c}
                  </button>
                ))}
              </div>

              {/* Task Cards */}
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {filteredTasks.map((task, ti) => {
                  const realIdx = currentPhase.tasks.indexOf(task);
                  const done = taskStates[`${currentPhase.id}-${realIdx}`];
                  const isOpen = openTask === `${currentPhase.id}-${realIdx}`;
                  return (
                    <div key={realIdx} style={{ background: T.card, border: `1px solid ${done ? T.accent + "18" : task.upgrade ? T.cyan + "12" : T.border}`, borderRadius: 14, overflow: "hidden", transition: "0.2s" }}>
                      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "14px 16px", cursor: "pointer" }} onClick={() => setOpenTask(isOpen ? null : `${currentPhase.id}-${realIdx}`)}>
                        <div onClick={(e) => { e.stopPropagation(); toggleTask(currentPhase.id, realIdx); }} style={{ width: 22, height: 22, borderRadius: 6, border: `2px solid ${done ? T.accent : "rgba(255,255,255,0.1)"}`, background: done ? T.accent : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1, cursor: "pointer", transition: "0.2s" }}>
                          {done && <span style={{ color: T.bg, fontSize: 13, fontWeight: 900 }}>✓</span>}
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 2 }}>
                            <span style={{ fontSize: 14, fontWeight: 700, color: done ? T.muted : T.text, textDecoration: done ? "line-through" : "none" }}>{task.t}</span>
                          </div>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            <Badge color={T.muted}>{CAT_ICONS[task.cat]} {task.cat}</Badge>
                            {task.upgrade && <Badge color={T.cyan}>⚡ UPGRADE</Badge>}
                          </div>
                        </div>
                        <div style={{ fontSize: 16, color: T.muted, transform: `rotate(${isOpen ? 180 : 0}deg)`, transition: "0.3s", flexShrink: 0 }}>▾</div>
                      </div>
                      {isOpen && (
                        <div style={{ padding: "0 16px 16px", borderTop: `1px solid ${T.border}` }}>
                          <div style={{ margin: "12px 0", padding: "14px 16px", background: `${currentPhase.color}06`, borderRadius: 12, borderLeft: `3px solid ${currentPhase.color}35` }}>
                            <div style={{ fontSize: 10, color: currentPhase.color, letterSpacing: 1, textTransform: "uppercase", fontWeight: 700, marginBottom: 6 }}>🤖 AI Implementation Guide</div>
                            <div style={{ fontSize: 13, color: "#8899AA", lineHeight: 1.7, whiteSpace: "pre-line" }}>{task.ai}</div>
                          </div>
                          {task.upgrade && (
                            <div style={{ marginTop: 8, padding: "10px 14px", background: `${T.cyan}06`, borderRadius: 10, border: `1px solid ${T.cyan}15`, display: "flex", alignItems: "center", gap: 8 }}>
                              <span style={{ fontSize: 16 }}>⚡</span>
                              <span style={{ fontSize: 12, color: T.cyan, fontWeight: 700 }}>This is a technology upgrade — includes CURRENT → UPGRADE comparison with ROI projection</span>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Phase Navigation */}
              <div style={{ display: "flex", justifyContent: "space-between", paddingTop: 16, borderTop: `1px solid ${T.border}`, marginTop: 8 }}>
                {(() => {
                  const idx = phases.findIndex(p => p.id === openPhase);
                  return <>
                    <button onClick={() => idx > 0 && setOpenPhase(phases[idx - 1].id)} disabled={idx === 0} style={{ background: "rgba(255,255,255,0.02)", border: `1px solid ${T.border}`, borderRadius: 10, padding: "9px 18px", fontSize: 13, fontWeight: 700, cursor: idx > 0 ? "pointer" : "default", color: idx > 0 ? T.text : "#3A4550", opacity: idx > 0 ? 1 : 0.4 }}>← Previous Phase</button>
                    <button onClick={() => idx < phases.length - 1 && setOpenPhase(phases[idx + 1].id)} disabled={idx >= phases.length - 1} style={{ background: idx < phases.length - 1 ? `linear-gradient(135deg, ${pathConfig.color}, ${pathConfig.color}CC)` : "rgba(255,255,255,0.02)", color: idx < phases.length - 1 ? T.bg : "#3A4550", border: "none", borderRadius: 10, padding: "9px 22px", fontSize: 13, fontWeight: 800, cursor: idx < phases.length - 1 ? "pointer" : "default" }}>Next Phase →</button>
                  </>;
                })()}
              </div>
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}
        *{box-sizing:border-box;margin:0;padding:0}
        ::-webkit-scrollbar{width:5px;height:5px}
        ::-webkit-scrollbar-track{background:transparent}
        ::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.05);border-radius:3px}
        button{transition:0.15s} button:hover:not(:disabled){filter:brightness(1.12)}
      `}</style>
    </div>
  );
}
