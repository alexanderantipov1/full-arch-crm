import { useState, useEffect, useRef, useCallback } from "react";

// ═══════════════════════════════════════════════════════
// DENTALOS ULTIMATE — THE EVERYTHING APP
// ═══════════════════════════════════════════════════════

const C = { bg: "#060810", card: "rgba(255,255,255,0.018)", border: "rgba(255,255,255,0.055)", text: "#E4E9F0", muted: "#5E6D80", accent: "#00D4AA", gold: "#D4A853", red: "#EF4444", blue: "#3B82F6", purple: "#8B5CF6", orange: "#F59E0B", pink: "#EC4899", cyan: "#06B6D4" };

// ─── AI BOT RESPONSES ───
const BOT_RESPONSES = {
  "permits": "🏛️ Here's your permit checklist for opening a dental practice:\n\n1. **State Dental License** — verify active with your state board\n2. **Business License** — apply with your city/county clerk\n3. **DEA Registration** — apply at deadiversion.usdoj.gov (takes 4-6 weeks)\n4. **NPI Number** — register at nppes.cms.hhs.gov (free, takes 1-2 days)\n5. **State Tax ID** — register with your state's dept of revenue\n6. **EIN (Federal Tax ID)** — apply at irs.gov (instant online)\n7. **Radiation Safety Certificate** — required for X-ray equipment\n8. **Fire Dept Inspection** — schedule before opening\n9. **Building/Occupancy Permit** — from your local building dept\n10. **OSHA Compliance Certificate** — complete training + documentation\n\n⏱️ Start these 90+ days before your planned opening date. Insurance credentialing takes the longest — begin ASAP.",
  "google": "📍 Setting up your Google Business Profile:\n\n1. Go to business.google.com and sign in\n2. Click 'Add your business' → enter practice name\n3. Choose category: 'Dental Implant Provider' or 'Dental Clinic'\n4. Enter your address (must be physical location)\n5. Add phone number + website URL\n6. Verify via postcard (5-7 days) or phone\n7. **Optimization tips:**\n   • Upload 20+ photos (office, equipment, team, results)\n   • Write a 750-word business description with keywords\n   • Add all services with descriptions\n   • Set up messaging + appointment booking\n   • Post weekly updates (Google Posts)\n   • Respond to every review within 24 hours\n\n🎯 Target: 50+ five-star reviews in first 6 months. Set up automated review requests post-appointment.",
  "logo": "🎨 Brand & Logo Creation Playbook:\n\n1. **Define brand personality**: Professional + warm? Modern + clinical? Luxury + approachable?\n2. **Color palette**: Blues/teals = trust. Greens = health. Gold/navy = premium.\n3. **Logo options**:\n   • Use Looka.com or 99designs for AI-generated logos ($20-$300)\n   • Hire on Fiverr/Upwork for custom ($100-$500)\n   • Work with local agency for full brand kit ($2K-$10K)\n4. **Must-haves in your brand kit**:\n   • Primary logo + icon mark\n   • Color codes (HEX, RGB, CMYK)\n   • Typography (heading + body fonts)\n   • Brand voice guidelines\n   • Business card template\n   • Letterhead + envelope\n   • Social media templates\n5. **Apply everywhere**: Signage, website, forms, scrubs embroidery, social profiles\n\n💡 AI Prompt: 'Design a modern dental logo for [Practice Name] specializing in implants and cosmetic dentistry. Use clean lines, a tooth/smile icon, and a blue-green-gold color palette.'",
  "phone": "📞 Smart Phone System Setup:\n\n1. **Choose a dental VoIP provider**:\n   • Weave (dental-specific, best integration)\n   • Mango Voice\n   • RingCentral\n   • 8x8\n2. **Features you NEED**:\n   • Auto-attendant with specialty routing\n   • Call recording for training\n   • Text/SMS capability (patients prefer texting)\n   • Integration with your PMS\n   • After-hours routing + emergency line\n   • Call analytics (missed calls, wait times)\n3. **Phone scripts to create**:\n   • New patient inquiry script\n   • Insurance verification script\n   • Emergency call triage script\n   • Appointment confirmation script\n   • Collections/billing call script\n4. **Tracking**: Every call logged, source tracked, conversion measured\n\n🤖 Set up AI call answering for after-hours with tools like Slingshot or DentistAI.",
  "website": "🌐 Website Creation Checklist:\n\n1. **Platform**: WordPress + Jesuspended theme OR custom Next.js\n2. **Must-have pages**:\n   • Homepage (hero + offer + trust signals)\n   • About/Meet the Doctor\n   • Services (one page per specialty)\n   • Before & After Gallery\n   • Patient Testimonials\n   • Insurance & Financing\n   • Contact + Online Booking\n   • Blog (for SEO)\n3. **Critical features**:\n   • Online scheduling integration\n   • Click-to-call on mobile\n   • HIPAA-compliant contact forms\n   • Live chat widget\n   • Fast loading (<3 seconds)\n   • Mobile-first design\n   • SSL certificate\n4. **SEO from day 1**:\n   • Target: 'dental implants [your city]'\n   • Create location pages\n   • Schema markup for dental practice\n   • Blog 2x/month minimum\n\n💰 Budget: $3K-$8K for a professional dental website. DIY with Squarespace: $200-$500.",
  "hiring": "👥 Hiring Playbook — Build Your A-Team:\n\n**Hire in this order:**\n1. Office Manager (month 1 — they help hire everyone else)\n2. Front Desk / Treatment Coordinator (month 2)\n3. Dental Assistant × 2 (month 2-3)\n4. Hygienist × 1 (month 3 — scale up later)\n5. Billing Specialist (month 3-4 or outsource)\n\n**Where to find talent:**\n• DentalPost.net (dental-specific)\n• Indeed + ZipRecruiter\n• Local dental hygiene schools\n• Facebook dental professional groups\n• Referrals from other offices\n\n**Compensation benchmarks (varies by market):**\n• Office Manager: $55-75K\n• Treatment Coordinator: $40-55K\n• Dental Assistant: $38-52K\n• Hygienist: $75-95K\n• Front Desk: $35-48K\n\n**Interview questions to ask:**\n• 'Tell me about a difficult patient interaction'\n• 'What's your approach to treatment presentation?'\n• 'How do you handle a scheduling conflict?'\n\n🎯 Culture fit > experience. You can train skills, not attitude.",
  "kpi": "📊 KPI Dashboard — Track These Numbers:\n\n**Daily KPIs (Morning Huddle):**\n• Production scheduled vs. goal\n• Open chair time\n• New patients scheduled\n• Unconfirmed appointments\n\n**Weekly KPIs:**\n• Production: actual vs. goal\n• Collections: amount + percentage\n• New patients: count + source\n• Case acceptance rate\n• Cancellation/no-show rate\n\n**Monthly KPIs (Dental Entrepreneur Org standard):**\n• Total production\n• Total collections (target: 98%+)\n• Overhead ratio (target: <59%)\n• New patients per month (target: 25-40)\n• Case acceptance rate (target: >70%)\n• Average production per visit\n• Hygiene production as % of total (target: 25-33%)\n• Reappointment rate (target: >85%)\n• Accounts receivable >90 days\n• Patient lifetime value\n\n**The 4 Numbers That Matter Most:**\n1. Production per day per provider\n2. Collections percentage\n3. New patients per month\n4. Case acceptance rate",
  "ads": "📣 Advertising & Patient Acquisition:\n\n**Google Ads (start here — highest intent):**\n• Budget: $2-5K/month to start\n• Target keywords: 'dental implants near me', 'dentist [city]'\n• Create landing pages for each service\n• Track cost per lead + cost per new patient\n• Target CAC: $150-$350\n\n**Meta/Instagram Ads:**\n• Budget: $1-3K/month\n• Before/after content performs best\n• Video testimonials = highest conversion\n• Retarget website visitors\n• Lookalike audiences from patient list\n\n**The Grand Slam Offer (Hormozi framework):**\n• 'Free CBCT Scan + Consultation + 3D Smile Preview'\n• Remove all risk from first visit\n• Make it a no-brainer to walk in the door\n• Then wow them with the experience\n\n**Referral Program:**\n• $250-$500 per referred patient who starts treatment\n• Automated ask sequence post-treatment\n• Track referral source religiously\n\n🎯 Goal: Predictable patient acquisition at <$300 CAC.",
  "default": "👋 I'm DentBot — your AI practice advisor. I can help with:\n\n• 🏛️ Permits & licensing\n• 📍 Google Business setup\n• 🎨 Logo & branding\n• 📞 Phone system\n• 🌐 Website creation\n• 👥 Hiring & HR\n• 📊 KPIs & metrics\n• 📣 Advertising\n• ⚙️ Protocols & SOPs\n• 💰 Financial planning\n\nJust type what you need help with, or ask me anything about opening and running your dental practice!"
};

const getResponse = (msg) => {
  const m = msg.toLowerCase();
  if (m.includes("permit") || m.includes("license") || m.includes("dea") || m.includes("npi")) return BOT_RESPONSES.permits;
  if (m.includes("google") || m.includes("gmb") || m.includes("maps")) return BOT_RESPONSES.google;
  if (m.includes("logo") || m.includes("brand") || m.includes("design")) return BOT_RESPONSES.logo;
  if (m.includes("phone") || m.includes("call") || m.includes("voip")) return BOT_RESPONSES.phone;
  if (m.includes("website") || m.includes("site") || m.includes("web")) return BOT_RESPONSES.website;
  if (m.includes("hir") || m.includes("staff") || m.includes("team") || m.includes("recruit")) return BOT_RESPONSES.hiring;
  if (m.includes("kpi") || m.includes("metric") || m.includes("track") || m.includes("number")) return BOT_RESPONSES.kpi;
  if (m.includes("ad") || m.includes("market") || m.includes("patient acquisition") || m.includes("google ad")) return BOT_RESPONSES.ads;
  return BOT_RESPONSES.default;
};

// ─── LAUNCH PHASES DATA ───
const LAUNCH_PHASES = [
  { id: "legal", phase: 1, name: "Legal & Entity Formation", icon: "⚖️", duration: "Week 1-2", color: C.gold, tasks: [
    { t: "Choose entity structure (LLC, S-Corp, or Professional Corp)", ai: "Consult dental CPA. Most solo practitioners start with single-member LLC taxed as S-Corp for tax efficiency.", done: false },
    { t: "Register business entity with state Secretary of State", ai: "File online at your state's SOS website. Cost: $50-$500 depending on state. Processing: 3-10 business days.", done: false },
    { t: "Obtain EIN (Federal Tax ID) from IRS", ai: "Apply at irs.gov/ein — instant approval online. Free. You need this for banking, hiring, and insurance.", done: false },
    { t: "Register for state tax ID / sales tax permit", ai: "Register with your state's Department of Revenue. Required for collecting sales tax on retail items.", done: false },
    { t: "Open business bank account + credit line", ai: "Bring EIN, formation docs, and operating agreement. Recommend: dental-friendly banks like Bank of America, Live Oak Bank.", done: false },
    { t: "Purchase malpractice insurance", ai: "Contact: MedPro, Dentists Advantage, or AADA. Budget: $1,500-$4,000/year. Get quotes from 3+ carriers.", done: false },
    { t: "Purchase general liability + property insurance", ai: "Bundle with malpractice carrier. Include: general liability, property, business interruption, workers comp.", done: false },
    { t: "Engage dental-specific CPA and attorney", ai: "Find through your state dental association. CPA sets up bookkeeping, payroll, tax planning from day 1.", done: false },
  ]},
  { id: "licensing", phase: 2, name: "Licenses & Permits", icon: "🏛️", duration: "Week 2-6", color: C.blue, tasks: [
    { t: "Verify state dental license is active and current", ai: "Check your state dental board website. If relocating states, apply for new license 90+ days early.", done: false },
    { t: "Apply for DEA Registration (Schedule II-V)", ai: "Apply at deadiversion.usdoj.gov. Fee: ~$888 for 3 years. Processing: 4-6 weeks. START IMMEDIATELY.", done: false },
    { t: "Register for NPI Number (Type 1 individual + Type 2 organization)", ai: "Apply at nppes.cms.hhs.gov. Free. Type 1 = you personally. Type 2 = your practice entity. Takes 1-2 days.", done: false },
    { t: "Apply for city/county business license", ai: "Visit your local city clerk or apply online. Cost: $50-$500. Some cities require zoning approval for dental.", done: false },
    { t: "Obtain building/occupancy permit for dental use", ai: "Required if doing buildout. Your contractor should handle but YOU verify it's filed.", done: false },
    { t: "Apply for radiation safety certificate", ai: "Required for X-ray equipment. Register with your state radiation control program. Inspection required.", done: false },
    { t: "Complete OSHA compliance program", ai: "Training for all staff, written exposure control plan, SDS sheets, PPE protocols. Use OSHA Review or DDS Compliance.", done: false },
    { t: "Set up HIPAA compliance program", ai: "Written policies, staff training, BAAs with all vendors, breach notification plan. Use Compliancy Group or PCIHIPAA.", done: false },
    { t: "Apply for state controlled substance license (if required)", ai: "Some states require separate state-level controlled substance registration in addition to DEA.", done: false },
  ]},
  { id: "location", phase: 3, name: "Location & Buildout", icon: "🏗️", duration: "Week 2-12", color: C.cyan, tasks: [
    { t: "Run demographic analysis for target areas (3-5 locations)", ai: "Use ADA Health Policy Institute data, Dental Intelligence, or Buxton Analytics. Look for: population density, median income, competition ratio, growth trends.", done: false },
    { t: "Evaluate 5+ potential locations (score each)", ai: "Score on: visibility, traffic count, parking, signage rights, proximity to competitors, lease terms, TI allowance.", done: false },
    { t: "Negotiate lease with tenant improvement (TI) allowance", ai: "Target: $50-$100/SF TI allowance. Negotiate: 10-year lease with 5-year renewal option, 3-6 months free rent during buildout, signage rights, exclusive dental use clause.", done: false },
    { t: "Hire dental-specific architect", ai: "Must have dental office experience. They'll design operatory layout, plumbing specs, equipment placement, patient flow.", done: false },
    { t: "Design office layout (5-8 operatories, plan for expansion)", ai: "Minimum 5 ops. Plumb for 8+. Include: sterilization center, lab, private consult room, break room, server room.", done: false },
    { t: "Hire general contractor with dental buildout experience", ai: "Get 3 bids. Verify dental references. Include: plumbing, electrical (dedicated circuits), HVAC, vacuum/compressor, data.", done: false },
    { t: "Order dental equipment (lead times: 6-12 weeks)", ai: "Major items: chairs/units, CBCT, digital scanner, panoramic, sterilizers, compressor, vacuum. Budget: $150K-$400K.", done: false },
    { t: "Order IT infrastructure (network, servers, computers)", ai: "Dental-specific IT: HIPAA-compliant network, encrypted workstations, backup system, VoIP phones, digital display screens.", done: false },
    { t: "Select and implement Practice Management Software", ai: "Top options: Dentrix, Eaglesoft, Open Dental (open source), Curve (cloud). Decision factors: cloud vs. server, integrations, cost.", done: false },
    { t: "Pass final inspection and obtain Certificate of Occupancy", ai: "Schedule with building dept 2 weeks before planned opening. Have contractor present. Fix any issues immediately.", done: false },
  ]},
  { id: "insurance", phase: 4, name: "Insurance Credentialing", icon: "📋", duration: "Week 1-16 (START EARLY)", color: C.red, tasks: [
    { t: "Compile master credentialing packet", ai: "Gather: dental license, DEA, NPI, malpractice COI, diploma, residency cert, specialty cert, CV, W-9, voided check.", done: false },
    { t: "Apply to Delta Dental (largest network — apply first)", ai: "Each state has its own Delta. Apply through their provider portal. Processing: 60-120 days.", done: false },
    { t: "Apply to MetLife Dental", ai: "Apply at metlife.com/dental-providers. Processing: 60-90 days.", done: false },
    { t: "Apply to Cigna Dental", ai: "Apply through Cigna's provider portal. Processing: 60-90 days.", done: false },
    { t: "Apply to Aetna Dental", ai: "Apply at aetna.com/providers. Processing: 60-90 days.", done: false },
    { t: "Apply to United Healthcare Dental", ai: "Apply through UHC provider portal. Processing: 45-90 days.", done: false },
    { t: "Apply to Guardian Dental", ai: "Apply at guardiananytime.com. Processing: 60-90 days.", done: false },
    { t: "Apply to BlueCross BlueShield Dental (your state)", ai: "Each state has its own BCBS. Apply through your state's provider portal.", done: false },
    { t: "Set up fee schedules for each insurance plan", ai: "Review UCR rates for your zip code. Set fees at 80th percentile UCR. Never set below insurance maximum allowable.", done: false },
    { t: "Set up in-house dental membership plan for uninsured", ai: "Create a membership plan: $25-$35/month includes 2 cleanings, exams, X-rays, 15-20% off treatment. Use Kleer or BoomCloud.", done: false },
  ]},
  { id: "brand", phase: 5, name: "Brand & Digital Presence", icon: "🎨", duration: "Week 4-10", color: C.purple, tasks: [
    { t: "Define practice name, tagline, and brand personality", ai: "Name should be: memorable, easy to spell, available as .com domain. Check state dental board for name restrictions.", done: false },
    { t: "Design logo and complete brand kit", ai: "Include: primary logo, icon mark, color palette (HEX/RGB/CMYK), typography, brand voice guide. Use Looka, 99designs, or local designer.", done: false },
    { t: "Register domain name and set up business email", ai: "Register .com at Namecheap or Google Domains. Set up Google Workspace for professional email (name@yourpractice.com).", done: false },
    { t: "Build website with online booking integration", ai: "WordPress + dental theme or custom build. Must have: online scheduling, mobile-first, HIPAA forms, live chat, SSL, fast loading.", done: false },
    { t: "Set up and optimize Google Business Profile", ai: "Category: Dental Implant Provider. Add 20+ photos. Write 750-word description. Set hours, services, insurance accepted.", done: false },
    { t: "Create social media profiles (Instagram, Facebook, TikTok, YouTube)", ai: "Use consistent branding across all platforms. Bio should include: specialty, location, booking link. Start posting 30 days before opening.", done: false },
    { t: "Set up online review management system", ai: "Use Birdeye, Podium, or Weave. Automate review requests via SMS after every appointment. Respond to all reviews within 24 hours.", done: false },
    { t: "Order physical brand materials", ai: "Business cards, letterhead, appointment cards, referral cards, welcome packets, signage, window decals, scrub embroidery.", done: false },
    { t: "Create patient-facing videos (intro, office tour, meet the doctor)", ai: "Hire videographer ($500-$2K) or use iPhone + good lighting. These go on website, YouTube, social, and Google Business Profile.", done: false },
  ]},
  { id: "team", phase: 6, name: "Hiring & Team Building", icon: "👥", duration: "Week 6-14", color: C.pink, tasks: [
    { t: "Write job descriptions for all positions", ai: "Include: role responsibilities, qualifications, compensation range, benefits, culture description. Be specific about specialty experience.", done: false },
    { t: "Hire Office Manager / Practice Administrator (FIRST HIRE)", ai: "This person is your #2. They run daily operations, manage team, handle HR. Look for: dental experience, leadership, systems-minded.", done: false },
    { t: "Hire Front Desk / Patient Coordinator", ai: "Must have: warm phone voice, dental software experience, insurance verification skills. TEST their phone skills in the interview.", done: false },
    { t: "Hire Treatment Coordinator", ai: "This is your REVENUE position. They present treatment plans and close cases. Look for: sales ability, empathy, dental knowledge.", done: false },
    { t: "Hire Dental Assistants (2 minimum)", ai: "Expanded function preferred. Check state requirements for certification. Include: chairside, radiology, impressions, sterilization.", done: false },
    { t: "Hire Dental Hygienist (1 to start, scale up)", ai: "RDH license required. Look for: perio focus, patient education skills, production-oriented. Start with 3 days/week.", done: false },
    { t: "Set up payroll system (Gusto, ADP, or QuickBooks Payroll)", ai: "Gusto is easiest for small practices. Auto-calculates taxes, handles direct deposit, benefits enrollment.", done: false },
    { t: "Create employee handbook and policies", ai: "Include: at-will statement, PTO policy, dress code, social media policy, HIPAA obligations, termination procedures.", done: false },
    { t: "Set up employee benefits (health, dental, 401k, CE allowance)", ai: "Offer dental plan (your own office), health insurance stipend, PTO, CE reimbursement ($1-2K/year), scrub allowance.", done: false },
    { t: "Schedule 2-week pre-opening team training intensive", ai: "Cover: PMS software, phone scripts, patient flow, treatment presentation, emergency protocols, customer service standards.", done: false },
  ]},
  { id: "phones", phase: 7, name: "Phone & Communication System", icon: "📞", duration: "Week 8-12", color: C.orange, tasks: [
    { t: "Select dental VoIP phone provider", ai: "Recommended: Weave (dental-specific, best PMS integration), Mango Voice, RingCentral. Look for: call recording, SMS, analytics.", done: false },
    { t: "Set up auto-attendant and call routing", ai: "Route by: new patient, existing patient, emergency, billing, specialty. After-hours message with emergency callback.", done: false },
    { t: "Write and record phone scripts for all call types", ai: "Scripts needed: new patient inquiry, insurance questions, appointment confirmation, cancellation save, billing, emergency triage.", done: false },
    { t: "Set up 2-way texting for patient communication", ai: "Patients prefer texting 3:1 over calling. Use for: confirmations, reminders, quick questions, review requests.", done: false },
    { t: "Configure call tracking for marketing attribution", ai: "Assign unique tracking numbers to each marketing channel (Google Ads, website, mailers). Use CallRail or built-in provider tracking.", done: false },
    { t: "Set up AI after-hours call handling", ai: "Tools: Slingshot AI, DentistAI, or Weave AI. Handles: appointment requests, emergency triage, FAQ, routes urgent calls to you.", done: false },
    { t: "Train front desk on phone conversion scripts", ai: "New patient calls should convert at 80%+. Record calls, review weekly, role-play daily. The phone is your #1 revenue tool.", done: false },
    { t: "Set up appointment reminder automation (text + email)", ai: "Sequence: 1 week before (email), 2 days before (text), same-day morning (text). Include: confirm/reschedule buttons.", done: false },
  ]},
  { id: "protocols", phase: 8, name: "Clinical & Business Protocols", icon: "📑", duration: "Week 10-14", color: C.cyan, tasks: [
    { t: "Create new patient intake workflow (100% digital)", ai: "Digital forms via Yosi Health, Dentrix Kiosk, or NexHealth. Include: medical history, dental history, insurance, consent, financial agreement.", done: false },
    { t: "Build scheduling templates with block scheduling", ai: "Block by procedure type: hygiene blocks, crown prep blocks, implant surgery blocks, emergency slots. Optimize production per hour.", done: false },
    { t: "Write treatment presentation protocol", ai: "Step by step: diagnose → educate (show images) → present options → discuss financing → close. Use intraoral photos/scans for visual impact.", done: false },
    { t: "Create morning huddle template", ai: "Daily 10-min meeting: review schedule, identify high-value cases, unconfirmed appointments, lab cases due, patient notes/concerns.", done: false },
    { t: "Develop sterilization and infection control SOP", ai: "Follow CDC guidelines. Document: instrument processing, surface disinfection, PPE protocols, waterline treatment, waste management.", done: false },
    { t: "Create financial policy and payment protocols", ai: "Include: payment at time of service, insurance estimation process, treatment financing options (CareCredit, Proceed, Sunbit), collections protocol.", done: false },
    { t: "Build emergency protocol manual", ai: "Protocols for: syncope, allergic reaction, cardiac event, seizure, aspiration, hemorrhage. Post in every operatory. Train quarterly.", done: false },
    { t: "Create patient follow-up and recall system", ai: "Automate: post-op check (24hr), 1-week follow-up, 6-month recall, annual recall, reactivation (12+ months). Use PMS + communication platform.", done: false },
    { t: "Develop case acceptance tracking system", ai: "Track by: provider, procedure type, dollar amount. Review weekly. Target: 70%+ overall, 85%+ for hygiene-generated treatment.", done: false },
  ]},
  { id: "marketing", phase: 9, name: "Marketing & Advertising Launch", icon: "📣", duration: "Week 10-16", color: C.red, tasks: [
    { t: "Create Grand Slam Offer (Hormozi framework)", ai: "Make it irresistible: 'Free CBCT + Consultation + 3D Smile Preview + $500 Off Treatment'. Remove ALL risk from first visit.", done: false },
    { t: "Set up Google Ads campaign ($2-5K/month)", ai: "Target high-intent keywords: 'dental implants [city]', 'dentist near me'. Create dedicated landing pages. Track cost per lead + cost per patient.", done: false },
    { t: "Launch Meta/Instagram advertising ($1-3K/month)", ai: "Best performing: before/after content, video testimonials, Grand Slam Offer ads. Retarget website visitors. Build lookalike audiences.", done: false },
    { t: "Build patient referral program", ai: "$250-$500 per referred patient who starts treatment. Automate the ask via text 48 hours after treatment completion.", done: false },
    { t: "Launch direct mail campaign to local households", ai: "5,000-10,000 pieces to households within 3-5 miles. Include Grand Slam Offer. Use dental-specific mailer (PostcardMania, MVP Mailhouse).", done: false },
    { t: "Create content calendar (social media + blog)", ai: "2-3 social posts/week, 2 blog posts/month. Content mix: educational (60%), behind-the-scenes (20%), testimonials (10%), promotional (10%).", done: false },
    { t: "Partner with 10+ local businesses for cross-referrals", ai: "Target: gyms, spas, salons, real estate agents, wedding planners, corporate HR departments. Offer: employee dental days, mutual referrals.", done: false },
    { t: "Set up marketing ROI tracking dashboard", ai: "Track: spend by channel, leads generated, cost per lead, patients acquired, cost per acquisition, ROI. Review weekly.", done: false },
    { t: "Plan grand opening event", ai: "Free screenings, office tours, refreshments, raffle prizes, local media invite, social media live stream. Target: 100+ attendees.", done: false },
  ]},
  { id: "kpis", phase: 10, name: "KPIs & Financial Systems", icon: "📊", duration: "Week 12-16", color: C.gold, tasks: [
    { t: "Set up daily production tracking dashboard", ai: "Track: daily production per provider, procedures completed, production vs. goal. Display on screen in break room. Review in morning huddle.", done: false },
    { t: "Implement collections tracking (target: 98%+)", ai: "Track: gross production, adjustments, net production, collections, collections rate. Review A/R aging weekly. Nothing over 90 days.", done: false },
    { t: "Build new patient tracking system", ai: "Track: total new patients/month, source attribution, conversion rate from call to booked to arrived. Target: 30-50/month.", done: false },
    { t: "Set up case acceptance reporting", ai: "Track: treatment presented vs. accepted, by provider, by procedure type, by dollar amount. Report weekly. Target: 70%+.", done: false },
    { t: "Create overhead monitoring system", ai: "Track monthly: staff costs, facility costs, supplies, lab, marketing, admin. Target: total overhead <59% of collections.", done: false },
    { t: "Implement patient satisfaction tracking (NPS)", ai: "Send NPS survey 24 hours after appointment. Track score monthly. Target: NPS 70+. Follow up on any score below 7.", done: false },
    { t: "Set up monthly P&L review with dental CPA", ai: "Compare actual vs. budget. Track: revenue growth, overhead trends, profit margin. Adjust strategy based on financial performance.", done: false },
    { t: "Create weekly team scorecard meeting", ai: "Every Monday: review last week's KPIs, celebrate wins, identify problems, assign action items. 30 minutes max. Non-negotiable.", done: false },
  ]},
];

// ─── CRM PATIENTS ───
const CRM_PATIENTS = [
  { id: 1, name: "Margaret Sullivan", avatar: "MS", stage: "In Treatment", specialty: "Implants", provider: "Dr. Chen", ltv: 24500, score: 95, phone: "(555) 234-8901", email: "msullivan@email.com", nextAppt: "Feb 18", insurance: "Delta Dental PPO", treatment: "Full Arch Implants (Upper)", color: C.accent },
  { id: 2, name: "Robert Kim", avatar: "RK", stage: "Treatment Plan", specialty: "Implants", provider: "Dr. Chen", ltv: 8200, score: 72, phone: "(555) 345-6789", email: "rkim@email.com", nextAppt: "Pending", insurance: "MetLife", treatment: "Single Implant #14 + Crown", color: C.orange },
  { id: 3, name: "Diana Patel", avatar: "DP", stage: "Consultation", specialty: "Ortho", provider: "Dr. Park", ltv: 3200, score: 65, phone: "(555) 456-7890", email: "dpatel@email.com", nextAppt: "Pending", insurance: "Cigna", treatment: "Invisalign Comprehensive", color: C.blue },
  { id: 4, name: "James Okafor", avatar: "JO", stage: "In Treatment", specialty: "Ortho", provider: "Dr. Park", ltv: 6800, score: 88, phone: "(555) 567-8901", email: "jokafor@email.com", nextAppt: "Mar 5", insurance: "Aetna", treatment: "Invisalign + Whitening", color: C.accent },
  { id: 5, name: "Sarah Chen", avatar: "SC", stage: "New Lead", specialty: "Implants", provider: "Unassigned", ltv: 0, score: 45, phone: "(555) 678-9012", email: "schen@email.com", nextAppt: "Pending", insurance: "UHC", treatment: "Implant Inquiry", color: C.purple },
  { id: 6, name: "Michael Torres", avatar: "MT", stage: "Completed", specialty: "Surgery", provider: "Dr. Okafor", ltv: 18700, score: 98, phone: "(555) 789-0123", email: "mtorres@email.com", nextAppt: "Jul 15", insurance: "Guardian", treatment: "Wisdom Teeth + Bone Graft", color: C.cyan },
];

const KPI_DATA = [
  { label: "Production/Day", value: "$52.4K", target: "$55K", pct: 95, color: C.accent },
  { label: "Collections %", value: "96.2%", target: "98%", pct: 98, color: C.blue },
  { label: "New Patients/Mo", value: "38", target: "45", pct: 84, color: C.purple },
  { label: "Case Acceptance", value: "72%", target: "80%", pct: 90, color: C.orange },
  { label: "Overhead Ratio", value: "57.3%", target: "<59%", pct: 97, color: C.gold },
  { label: "Reappt Rate", value: "87%", target: "90%", pct: 97, color: C.pink },
  { label: "Hygiene Prod %", value: "29%", target: "30%", pct: 97, color: C.cyan },
  { label: "Patient LTV", value: "$8,740", target: "$12K", pct: 73, color: C.red },
];

// ═══════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════

const Badge = ({ children, color = C.accent }) => <span style={{ background: `${color}14`, color, padding: "2px 9px", borderRadius: 20, fontSize: 10, fontWeight: 700, letterSpacing: 0.4, textTransform: "uppercase", border: `1px solid ${color}20`, whiteSpace: "nowrap" }}>{children}</span>;
const Pbar = ({ v, color = C.accent, h = 5 }) => <div style={{ height: h, background: "rgba(255,255,255,0.04)", borderRadius: h, overflow: "hidden", flex: 1 }}><div style={{ height: "100%", width: `${Math.min(v, 100)}%`, background: color, borderRadius: h, transition: "width 0.8s" }} /></div>;

// ═══════════════════════════════════════════════════════
// MAIN APPLICATION
// ═══════════════════════════════════════════════════════

export default function DentalOSUltimate() {
  const [module, setModule] = useState("launch");
  const [taskStates, setTaskStates] = useState({});
  const [openPhase, setOpenPhase] = useState("legal");
  const [openTask, setOpenTask] = useState(null);
  const [chatMessages, setChatMessages] = useState([{ from: "bot", text: BOT_RESPONSES.default }]);
  const [chatInput, setChatInput] = useState("");
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [crmFilter, setCrmFilter] = useState("all");
  const chatEndRef = useRef(null);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chatMessages]);

  const toggleTask = (phaseId, taskIdx) => {
    const key = `${phaseId}-${taskIdx}`;
    setTaskStates(p => ({ ...p, [key]: !p[key] }));
  };

  const getPhaseProgress = (phase) => {
    const done = phase.tasks.filter((_, i) => taskStates[`${phase.id}-${i}`]).length;
    return phase.tasks.length ? (done / phase.tasks.length) * 100 : 0;
  };

  const getOverallProgress = () => {
    const total = LAUNCH_PHASES.reduce((s, p) => s + p.tasks.length, 0);
    const done = LAUNCH_PHASES.reduce((s, p) => s + p.tasks.filter((_, i) => taskStates[`${p.id}-${i}`]).length, 0);
    return total ? (done / total) * 100 : 0;
  };

  const sendChat = () => {
    if (!chatInput.trim()) return;
    const userMsg = chatInput.trim();
    setChatMessages(p => [...p, { from: "user", text: userMsg }]);
    setChatInput("");
    setTimeout(() => {
      setChatMessages(p => [...p, { from: "bot", text: getResponse(userMsg) }]);
    }, 600);
  };

  const modules = [
    { id: "launch", label: "Launch Pad", icon: "🚀", desc: "Step-by-step opening guide" },
    { id: "dentbot", label: "DentBot AI", icon: "🤖", desc: "Your AI practice advisor" },
    { id: "crm", label: "Patient CRM", icon: "👥", desc: "Contact management" },
    { id: "phones", label: "Phone System", icon: "📞", desc: "Smart communications" },
    { id: "brand", label: "Brand Studio", icon: "🎨", desc: "Logo, website, identity" },
    { id: "ads", label: "Ad Engine", icon: "📣", desc: "Patient acquisition" },
    { id: "hr", label: "HR Hub", icon: "🧑‍💼", desc: "Hiring & training" },
    { id: "protocols", label: "Protocols", icon: "📑", desc: "SOPs & workflows" },
    { id: "kpis", label: "KPI Dashboard", icon: "📊", desc: "Metrics & tracking" },
  ];

  return (
    <div style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "'Outfit', 'DM Sans', system-ui" }}>
      <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&family=Crimson+Pro:ital,wght@0,400;0,700;1,400&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet" />

      {/* ═══ HEADER ═══ */}
      <div style={{ background: "rgba(255,255,255,0.01)", borderBottom: `1px solid ${C.border}`, padding: "10px 20px", display: "flex", alignItems: "center", justifyContent: "space-between", position: "sticky", top: 0, zIndex: 50, backdropFilter: "blur(16px)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 32, height: 32, borderRadius: 9, background: `linear-gradient(135deg, ${C.gold}, ${C.accent})`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>🦷</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 900, background: `linear-gradient(90deg, #F0F4F8, ${C.gold})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>DentalOS</div>
            <div style={{ fontSize: 9, color: C.muted, letterSpacing: 2.5, textTransform: "uppercase", fontWeight: 600 }}>The Everything App for Dental Practices</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ fontSize: 11, color: C.muted }}>Overall:</div>
          <div style={{ width: 80 }}><Pbar v={getOverallProgress()} color={C.gold} h={4} /></div>
          <span style={{ fontSize: 12, fontWeight: 800, color: C.gold }}>{Math.round(getOverallProgress())}%</span>
          <div style={{ display: "flex", alignItems: "center", gap: 5, background: "rgba(0,212,170,0.06)", padding: "3px 10px", borderRadius: 14, border: "1px solid rgba(0,212,170,0.12)" }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.accent, boxShadow: `0 0 8px ${C.accent}`, animation: "pulse 2s infinite" }} />
            <span style={{ fontSize: 10, color: C.accent, fontWeight: 700 }}>AI ON</span>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", minHeight: "calc(100vh - 52px)" }}>
        {/* ═══ SIDEBAR ═══ */}
        <div style={{ width: 220, borderRight: `1px solid ${C.border}`, padding: "12px 10px", overflowY: "auto", flexShrink: 0, background: "rgba(255,255,255,0.005)" }}>
          <div style={{ fontSize: 9, color: C.muted, letterSpacing: 2, textTransform: "uppercase", fontWeight: 700, padding: "4px 8px", marginBottom: 8 }}>Modules</div>
          {modules.map(m => (
            <button key={m.id} onClick={() => setModule(m.id)} style={{ width: "100%", display: "flex", alignItems: "center", gap: 10, padding: "9px 10px", borderRadius: 10, border: "none", background: module === m.id ? `${C.gold}0D` : "transparent", cursor: "pointer", marginBottom: 3, transition: "0.15s", textAlign: "left" }}>
              <span style={{ fontSize: 18, width: 28, textAlign: "center" }}>{m.icon}</span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: module === m.id ? C.gold : C.text }}>{m.label}</div>
                <div style={{ fontSize: 10, color: C.muted }}>{m.desc}</div>
              </div>
            </button>
          ))}
        </div>

        {/* ═══ MAIN CONTENT ═══ */}
        <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>

          {/* ═══ LAUNCH PAD ═══ */}
          {module === "launch" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              <div>
                <div style={{ fontSize: 24, fontWeight: 900 }}>Launch Pad</div>
                <div style={{ fontSize: 13, color: C.muted, marginTop: 2 }}>Complete step-by-step guide — from permits to grand opening. {LAUNCH_PHASES.reduce((s, p) => s + p.tasks.length, 0)} tasks across {LAUNCH_PHASES.length} phases.</div>
              </div>

              {/* Phase Timeline */}
              <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 4 }}>
                {LAUNCH_PHASES.map(p => {
                  const prog = getPhaseProgress(p);
                  return (
                    <button key={p.id} onClick={() => setOpenPhase(p.id)} style={{ background: openPhase === p.id ? `${p.color}0D` : C.card, border: `1px solid ${openPhase === p.id ? p.color + "30" : C.border}`, borderRadius: 12, padding: "10px 14px", cursor: "pointer", minWidth: 130, flex: "0 0 auto", textAlign: "left", transition: "0.2s" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                        <span style={{ fontSize: 16 }}>{p.icon}</span>
                        <span style={{ fontSize: 11, fontWeight: 800, color: openPhase === p.id ? p.color : C.text }}>{p.name}</span>
                      </div>
                      <Pbar v={prog} color={prog === 100 ? C.cyan : p.color} h={3} />
                      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
                        <span style={{ fontSize: 9, color: C.muted }}>{p.duration}</span>
                        <span style={{ fontSize: 10, fontWeight: 700, color: p.color }}>{Math.round(prog)}%</span>
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* Active Phase Tasks */}
              {LAUNCH_PHASES.filter(p => p.id === openPhase).map(phase => (
                <div key={phase.id}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
                    <span style={{ fontSize: 24 }}>{phase.icon}</span>
                    <div>
                      <div style={{ fontSize: 10, color: phase.color, letterSpacing: 1.5, textTransform: "uppercase", fontWeight: 700 }}>Phase {phase.phase} · {phase.duration}</div>
                      <div style={{ fontSize: 18, fontWeight: 900 }}>{phase.name}</div>
                    </div>
                  </div>

                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {phase.tasks.map((task, ti) => {
                      const done = taskStates[`${phase.id}-${ti}`];
                      const isOpen = openTask === `${phase.id}-${ti}`;
                      return (
                        <div key={ti} style={{ background: C.card, border: `1px solid ${done ? C.accent + "20" : C.border}`, borderRadius: 14, overflow: "hidden" }}>
                          <div style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "14px 16px", cursor: "pointer" }} onClick={() => setOpenTask(isOpen ? null : `${phase.id}-${ti}`)}>
                            <div onClick={(e) => { e.stopPropagation(); toggleTask(phase.id, ti); }} style={{ width: 22, height: 22, borderRadius: 6, border: `2px solid ${done ? C.accent : "rgba(255,255,255,0.12)"}`, background: done ? C.accent : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1, cursor: "pointer", transition: "0.2s" }}>
                              {done && <span style={{ color: C.bg, fontSize: 13, fontWeight: 900 }}>✓</span>}
                            </div>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontSize: 14, fontWeight: 700, color: done ? C.muted : C.text, textDecoration: done ? "line-through" : "none" }}>{task.t}</div>
                            </div>
                            <div style={{ fontSize: 16, color: C.muted, transform: `rotate(${isOpen ? 180 : 0}deg)`, transition: "0.3s", flexShrink: 0 }}>▾</div>
                          </div>
                          {isOpen && (
                            <div style={{ padding: "0 16px 16px", borderTop: `1px solid ${C.border}` }}>
                              <div style={{ margin: "12px 0", padding: "12px 14px", background: `${phase.color}08`, borderRadius: 10, borderLeft: `3px solid ${phase.color}40` }}>
                                <div style={{ fontSize: 10, color: phase.color, letterSpacing: 1, textTransform: "uppercase", fontWeight: 700, marginBottom: 4 }}>🤖 AI Guidance</div>
                                <div style={{ fontSize: 13, color: "#8899AA", lineHeight: 1.6, whiteSpace: "pre-line" }}>{task.ai}</div>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* ═══ DENTBOT AI ═══ */}
          {module === "dentbot" && (
            <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 100px)" }}>
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 24, fontWeight: 900 }}>🤖 DentBot AI</div>
                <div style={{ fontSize: 13, color: C.muted, marginTop: 2 }}>Your AI practice advisor. Ask me anything about opening and running your dental practice.</div>
              </div>

              {/* Quick prompts */}
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
                {[
                  { label: "🏛️ Permits", q: "What permits do I need?" },
                  { label: "📍 Google Setup", q: "How do I set up Google Business?" },
                  { label: "🎨 Logo & Brand", q: "Help me create my brand and logo" },
                  { label: "📞 Phone System", q: "What phone system should I use?" },
                  { label: "🌐 Website", q: "How do I build my website?" },
                  { label: "👥 Hiring", q: "Help me hire my team" },
                  { label: "📊 KPIs", q: "What KPIs should I track?" },
                  { label: "📣 Advertising", q: "How should I advertise?" },
                ].map((p, i) => (
                  <button key={i} onClick={() => { setChatMessages(prev => [...prev, { from: "user", text: p.q }]); setTimeout(() => setChatMessages(prev => [...prev, { from: "bot", text: getResponse(p.q) }]), 500); }} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: "5px 12px", fontSize: 12, fontWeight: 600, color: C.text, cursor: "pointer", transition: "0.15s" }}>
                    {p.label}
                  </button>
                ))}
              </div>

              {/* Chat Area */}
              <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 10, paddingRight: 4, marginBottom: 14 }}>
                {chatMessages.map((msg, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: msg.from === "user" ? "flex-end" : "flex-start" }}>
                    <div style={{ maxWidth: "85%", background: msg.from === "user" ? `${C.gold}15` : C.card, border: `1px solid ${msg.from === "user" ? C.gold + "25" : C.border}`, borderRadius: msg.from === "user" ? "14px 14px 4px 14px" : "14px 14px 14px 4px", padding: "12px 16px" }}>
                      {msg.from === "bot" && <div style={{ fontSize: 10, color: C.accent, fontWeight: 700, letterSpacing: 0.5, marginBottom: 6 }}>🤖 DENTBOT</div>}
                      <div style={{ fontSize: 13, lineHeight: 1.65, color: msg.from === "user" ? C.text : "#9AAABB", whiteSpace: "pre-line" }}>{msg.text}</div>
                    </div>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>

              {/* Input */}
              <div style={{ display: "flex", gap: 8 }}>
                <input value={chatInput} onChange={e => setChatInput(e.target.value)} onKeyDown={e => e.key === "Enter" && sendChat()} placeholder="Ask DentBot anything about your practice..." style={{ flex: 1, background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: "12px 16px", fontSize: 14, color: C.text, outline: "none" }} />
                <button onClick={sendChat} style={{ background: `linear-gradient(135deg, ${C.gold}, ${C.accent})`, color: C.bg, border: "none", borderRadius: 12, padding: "12px 20px", fontWeight: 800, fontSize: 14, cursor: "pointer" }}>Send</button>
              </div>
            </div>
          )}

          {/* ═══ PATIENT CRM ═══ */}
          {module === "crm" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
                <div>
                  <div style={{ fontSize: 24, fontWeight: 900 }}>Patient CRM</div>
                  <div style={{ fontSize: 13, color: C.muted, marginTop: 2 }}>Salesforce-grade patient management with AI lead scoring</div>
                </div>
                <button style={{ background: `linear-gradient(135deg, ${C.accent}, ${C.blue})`, color: C.bg, border: "none", borderRadius: 10, padding: "9px 20px", fontWeight: 800, fontSize: 13, cursor: "pointer" }}>+ Add Patient</button>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 10 }}>
                {[{ l: "Total Patients", v: "3,105", c: C.accent }, { l: "New Leads (30d)", v: "234", c: C.blue }, { l: "Pipeline Value", v: "$4.78M", c: C.purple }, { l: "Avg LTV", v: "$8,740", c: C.gold }, { l: "Case Accept.", v: "72%", c: C.orange }].map((s, i) => (
                  <div key={i} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 12, padding: "14px 16px" }}>
                    <div style={{ fontSize: 10, color: C.muted, letterSpacing: 1.2, textTransform: "uppercase", fontWeight: 600, marginBottom: 4 }}>{s.l}</div>
                    <div style={{ fontSize: 22, fontWeight: 900, color: s.c }}>{s.v}</div>
                  </div>
                ))}
              </div>

              <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                {["all", "New Lead", "Consultation", "Treatment Plan", "In Treatment", "Completed"].map(f => (
                  <button key={f} onClick={() => setCrmFilter(f)} style={{ background: crmFilter === f ? `${C.gold}12` : "transparent", border: `1px solid ${crmFilter === f ? C.gold + "25" : C.border}`, color: crmFilter === f ? C.gold : C.muted, borderRadius: 7, padding: "4px 12px", fontSize: 11, fontWeight: 700, cursor: "pointer", textTransform: "capitalize" }}>{f === "all" ? "All Stages" : f}</button>
                ))}
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {CRM_PATIENTS.filter(p => crmFilter === "all" || p.stage === crmFilter).map(p => (
                  <div key={p.id} onClick={() => setSelectedPatient(selectedPatient?.id === p.id ? null : p)} style={{ background: C.card, border: `1px solid ${selectedPatient?.id === p.id ? p.color + "30" : C.border}`, borderRadius: 14, overflow: "hidden", cursor: "pointer", transition: "0.2s" }}>
                    <div style={{ padding: "14px 16px", display: "flex", alignItems: "center", gap: 14 }}>
                      <div style={{ width: 38, height: 38, borderRadius: 10, background: `${p.color}15`, color: p.color, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, fontWeight: 800, border: `1px solid ${p.color}25`, flexShrink: 0 }}>{p.avatar}</div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                          <span style={{ fontSize: 14, fontWeight: 800 }}>{p.name}</span>
                          <Badge color={p.color}>{p.stage}</Badge>
                          <Badge color={C.muted}>{p.specialty}</Badge>
                        </div>
                        <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{p.provider} · {p.treatment}</div>
                      </div>
                      <div style={{ textAlign: "right", flexShrink: 0 }}>
                        <div style={{ fontSize: 16, fontWeight: 800, color: p.ltv > 10000 ? C.accent : C.text, fontFamily: "'JetBrains Mono'" }}>${p.ltv.toLocaleString()}</div>
                        <div style={{ display: "flex", alignItems: "center", gap: 4, justifyContent: "flex-end", marginTop: 2 }}>
                          <div style={{ width: 30, height: 4, borderRadius: 2 }}><Pbar v={p.score} color={p.score > 80 ? C.accent : p.score > 60 ? C.orange : C.red} h={4} /></div>
                          <span style={{ fontSize: 10, fontWeight: 700, color: p.score > 80 ? C.accent : C.orange }}>{p.score}</span>
                        </div>
                      </div>
                    </div>
                    {selectedPatient?.id === p.id && (
                      <div style={{ padding: "0 16px 16px", borderTop: `1px solid ${C.border}` }}>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginTop: 12 }}>
                          {[{ l: "Phone", v: p.phone }, { l: "Email", v: p.email }, { l: "Insurance", v: p.insurance }, { l: "Next Appt", v: p.nextAppt }, { l: "Lead Score", v: `${p.score}/100` }, { l: "LTV", v: `$${p.ltv.toLocaleString()}` }].map((f, i) => (
                            <div key={i} style={{ background: "rgba(255,255,255,0.01)", borderRadius: 8, padding: "8px 10px", border: `1px solid ${C.border}` }}>
                              <div style={{ fontSize: 9, color: C.muted, letterSpacing: 1, textTransform: "uppercase", fontWeight: 600 }}>{f.l}</div>
                              <div style={{ fontSize: 12, fontWeight: 700, marginTop: 2 }}>{f.v}</div>
                            </div>
                          ))}
                        </div>
                        <div style={{ display: "flex", gap: 6, marginTop: 12, flexWrap: "wrap" }}>
                          {["📞 Call", "📧 Email", "💬 SMS", "📅 Schedule", "📄 Treatment Plan"].map((a, i) => (
                            <button key={i} style={{ background: C.card, border: `1px solid ${C.border}`, color: C.text, borderRadius: 8, padding: "6px 12px", fontSize: 11, fontWeight: 700, cursor: "pointer" }}>{a}</button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ═══ PHONE / BRAND / ADS / HR / PROTOCOLS — Quick Setup Modules ═══ */}
          {["phones", "brand", "ads", "hr", "protocols"].includes(module) && (() => {
            const modConfig = {
              phones: { title: "Smart Phone System", desc: "Set up your practice communication hub", icon: "📞", phaseIds: ["phones"] },
              brand: { title: "Brand & Digital Studio", desc: "Logo, website, Google Business, and online presence", icon: "🎨", phaseIds: ["brand"] },
              ads: { title: "Advertising & Patient Acquisition Engine", desc: "Google Ads, Meta, referrals, and Grand Slam Offers", icon: "📣", phaseIds: ["marketing"] },
              hr: { title: "HR & Team Building Hub", desc: "Hiring playbook, onboarding, training, compensation", icon: "🧑‍💼", phaseIds: ["team"] },
              protocols: { title: "Clinical & Business Protocols", desc: "SOPs, workflows, and operational systems", icon: "📑", phaseIds: ["protocols"] },
            };
            const cfg = modConfig[module];
            const phases = LAUNCH_PHASES.filter(p => cfg.phaseIds.includes(p.id));
            return (
              <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                <div>
                  <div style={{ fontSize: 24, fontWeight: 900 }}>{cfg.icon} {cfg.title}</div>
                  <div style={{ fontSize: 13, color: C.muted, marginTop: 2 }}>{cfg.desc}</div>
                </div>
                {phases.map(phase => {
                  const prog = getPhaseProgress(phase);
                  return (
                    <div key={phase.id}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                        <Pbar v={prog} color={phase.color} h={5} />
                        <span style={{ fontSize: 12, fontWeight: 800, color: phase.color, minWidth: 36 }}>{Math.round(prog)}%</span>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                        {phase.tasks.map((task, ti) => {
                          const done = taskStates[`${phase.id}-${ti}`];
                          const isOpen = openTask === `${phase.id}-${ti}`;
                          return (
                            <div key={ti} style={{ background: C.card, border: `1px solid ${done ? C.accent + "20" : C.border}`, borderRadius: 14, overflow: "hidden" }}>
                              <div style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "14px 16px", cursor: "pointer" }} onClick={() => setOpenTask(isOpen ? null : `${phase.id}-${ti}`)}>
                                <div onClick={(e) => { e.stopPropagation(); toggleTask(phase.id, ti); }} style={{ width: 22, height: 22, borderRadius: 6, border: `2px solid ${done ? C.accent : "rgba(255,255,255,0.12)"}`, background: done ? C.accent : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1, cursor: "pointer", transition: "0.2s" }}>
                                  {done && <span style={{ color: C.bg, fontSize: 13, fontWeight: 900 }}>✓</span>}
                                </div>
                                <div style={{ flex: 1 }}>
                                  <div style={{ fontSize: 14, fontWeight: 700, color: done ? C.muted : C.text, textDecoration: done ? "line-through" : "none" }}>{task.t}</div>
                                </div>
                                <div style={{ fontSize: 16, color: C.muted, transform: `rotate(${isOpen ? 180 : 0}deg)`, transition: "0.3s" }}>▾</div>
                              </div>
                              {isOpen && (
                                <div style={{ padding: "0 16px 16px", borderTop: `1px solid ${C.border}` }}>
                                  <div style={{ margin: "12px 0", padding: "12px 14px", background: `${phase.color}08`, borderRadius: 10, borderLeft: `3px solid ${phase.color}40` }}>
                                    <div style={{ fontSize: 10, color: phase.color, letterSpacing: 1, textTransform: "uppercase", fontWeight: 700, marginBottom: 4 }}>🤖 AI Guidance</div>
                                    <div style={{ fontSize: 13, color: "#8899AA", lineHeight: 1.6, whiteSpace: "pre-line" }}>{task.ai}</div>
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })()}

          {/* ═══ KPI DASHBOARD ═══ */}
          {module === "kpis" && (
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              <div>
                <div style={{ fontSize: 24, fontWeight: 900 }}>📊 KPI Dashboard</div>
                <div style={{ fontSize: 13, color: C.muted, marginTop: 2 }}>Dental Entrepreneur Organization standard metrics — the numbers that run your practice</div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}>
                {KPI_DATA.map((k, i) => (
                  <div key={i} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: "16px 18px", textAlign: "center" }}>
                    <div style={{ fontSize: 26, fontWeight: 900, color: k.color, marginBottom: 2 }}>{k.value}</div>
                    <div style={{ fontSize: 11, fontWeight: 700, marginBottom: 6 }}>{k.label}</div>
                    <Pbar v={k.pct} color={k.color} h={4} />
                    <div style={{ fontSize: 10, color: C.muted, marginTop: 4 }}>Target: {k.target}</div>
                  </div>
                ))}
              </div>

              {/* DEO-Style Scorecard */}
              <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 16, overflow: "hidden" }}>
                <div style={{ padding: "14px 18px", borderBottom: `1px solid ${C.border}`, fontSize: 12, fontWeight: 700, color: C.gold, letterSpacing: 1.2, textTransform: "uppercase" }}>Weekly Scorecard — DEO Framework</div>
                <div style={{ overflowX: "auto" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                    <thead>
                      <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                        {["Metric", "Mon", "Tue", "Wed", "Thu", "Fri", "Week Total", "Goal", "Status"].map((h, i) => (
                          <th key={i} style={{ padding: "10px 12px", textAlign: i > 0 ? "center" : "left", fontSize: 10, color: C.muted, letterSpacing: 1, textTransform: "uppercase", fontWeight: 700, whiteSpace: "nowrap" }}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { m: "Production", vals: ["$48K", "$52K", "$55K", "$49K", "$51K"], total: "$255K", goal: "$275K", hit: false },
                        { m: "Collections", vals: ["$46K", "$50K", "$53K", "$47K", "$49K"], total: "$245K", goal: "$250K", hit: false },
                        { m: "New Patients", vals: ["3", "2", "4", "2", "3"], total: "14", goal: "10", hit: true },
                        { m: "Cases Presented", vals: ["5", "4", "6", "5", "4"], total: "24", goal: "20", hit: true },
                        { m: "Cases Accepted", vals: ["3", "3", "5", "4", "2"], total: "17", goal: "15", hit: true },
                        { m: "Hygiene Prod.", vals: ["$14K", "$16K", "$15K", "$14K", "$15K"], total: "$74K", goal: "$80K", hit: false },
                      ].map((r, i) => (
                        <tr key={i} style={{ borderBottom: `1px solid ${C.border}` }}>
                          <td style={{ padding: "10px 12px", fontWeight: 700 }}>{r.m}</td>
                          {r.vals.map((v, j) => <td key={j} style={{ padding: "10px 12px", textAlign: "center", fontSize: 12, color: C.muted, fontFamily: "'JetBrains Mono'" }}>{v}</td>)}
                          <td style={{ padding: "10px 12px", textAlign: "center", fontWeight: 800, fontFamily: "'JetBrains Mono'" }}>{r.total}</td>
                          <td style={{ padding: "10px 12px", textAlign: "center", fontSize: 12, color: C.muted }}>{r.goal}</td>
                          <td style={{ padding: "10px 12px", textAlign: "center" }}>
                            <span style={{ background: r.hit ? `${C.accent}15` : `${C.red}15`, color: r.hit ? C.accent : C.red, padding: "2px 8px", borderRadius: 6, fontSize: 10, fontWeight: 800 }}>{r.hit ? "✓ HIT" : "✗ MISS"}</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* KPI Setup Checklist */}
              {(() => {
                const kpiPhase = LAUNCH_PHASES.find(p => p.id === "kpis");
                const prog = getPhaseProgress(kpiPhase);
                return (
                  <div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                      <div style={{ fontSize: 14, fontWeight: 800 }}>Setup Checklist</div>
                      <Pbar v={prog} color={C.gold} h={4} />
                      <span style={{ fontSize: 12, fontWeight: 800, color: C.gold }}>{Math.round(prog)}%</span>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {kpiPhase.tasks.map((task, ti) => {
                        const done = taskStates[`kpis-${ti}`];
                        return (
                          <div key={ti} onClick={() => toggleTask("kpis", ti)} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, cursor: "pointer" }}>
                            <div style={{ width: 20, height: 20, borderRadius: 5, border: `2px solid ${done ? C.accent : "rgba(255,255,255,0.1)"}`, background: done ? C.accent : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                              {done && <span style={{ color: C.bg, fontSize: 12, fontWeight: 900 }}>✓</span>}
                            </div>
                            <span style={{ fontSize: 13, fontWeight: 600, color: done ? C.muted : C.text, textDecoration: done ? "line-through" : "none" }}>{task.t}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}
            </div>
          )}
        </div>
      </div>

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        * { box-sizing:border-box; margin:0; padding:0; }
        ::-webkit-scrollbar { width:5px; height:5px; }
        ::-webkit-scrollbar-track { background:transparent; }
        ::-webkit-scrollbar-thumb { background:rgba(255,255,255,0.06); border-radius:3px; }
        button { transition:all 0.15s; }
        button:hover { filter:brightness(1.12); }
        input::placeholder { color: #4A5568; }
      `}</style>
    </div>
  );
}
