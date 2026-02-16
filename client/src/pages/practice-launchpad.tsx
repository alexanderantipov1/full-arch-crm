import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { Accordion, AccordionItem, AccordionTrigger, AccordionContent } from "@/components/ui/accordion";
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";
import {
  Briefcase, Settings, Megaphone, DollarSign, Users, Scale,
  Building, Wrench, Target, Handshake, ChevronDown, ChevronRight,
  Info, Rocket,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

const AI_AGENTS: Record<string, { name: string; short: string; desc: string; personality: string; icon: LucideIcon; colorClass: string; badgeClass: string }> = {
  ceo: { name: "Chief Executive AI", short: "CEO", desc: "Vision, strategy & growth trajectory", personality: "I see the big picture. Let me align your practice vision with market reality and build your empire roadmap.", icon: Briefcase, colorClass: "text-amber-600 dark:text-amber-400", badgeClass: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300" },
  coo: { name: "Chief Operations AI", short: "COO", desc: "Systems, workflows & daily execution", personality: "Systems run empires. I'll build your SOPs, optimize chair time, and make your practice run like clockwork.", icon: Settings, colorClass: "text-teal-600 dark:text-teal-400", badgeClass: "bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300" },
  cmo: { name: "Chief Marketing AI", short: "CMO", desc: "Patient acquisition & brand growth", personality: "Patients don't find you \u2014 you attract them. I'll build your Grand Slam Offer, funnels, and referral engine.", icon: Megaphone, colorClass: "text-red-600 dark:text-red-400", badgeClass: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300" },
  cfo: { name: "Chief Financial AI", short: "CFO", desc: "Revenue, cash flow & financial modeling", personality: "Every dollar has a job. I'll model your P&L, optimize collections, and show you exactly when you'll hit targets.", icon: DollarSign, colorClass: "text-green-600 dark:text-green-400", badgeClass: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300" },
  chro: { name: "Chief People AI", short: "CHRO", desc: "Hiring, training & team culture", personality: "Your team IS your practice. I'll help you hire A-players, build culture, and create compensation that retains.", icon: Users, colorClass: "text-purple-600 dark:text-purple-400", badgeClass: "bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300" },
  clo: { name: "Chief Legal AI", short: "CLO", desc: "Compliance, contracts & risk", personality: "Protect what you build. I'll guide entity setup, HIPAA compliance, contracts, and insurance credentialing.", icon: Scale, colorClass: "text-yellow-600 dark:text-yellow-400", badgeClass: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300" },
};

interface TaskData {
  id: string;
  task: string;
  agent: string;
  details: string;
  subtasks: string[];
}

interface PhaseData {
  phase: number;
  name: string;
  duration: string;
  agent: string;
  tasks: TaskData[];
}

interface PathData {
  id: string;
  name: string;
  icon: LucideIcon;
  desc: string;
  phases: PhaseData[];
}

const PATHS: Record<string, PathData> = {
  denovo: {
    id: "denovo", name: "Open New Practice", icon: Building, desc: "Build from scratch. Site selection, buildout, licensing, hiring, marketing launch.",
    phases: [
      { phase: 1, name: "Foundation", duration: "Month 1-2", agent: "ceo", tasks: [
        { id: "d1", task: "Define your practice vision & specialty mix", agent: "ceo", details: "Choose: general + implants? Multi-specialty? Your vision determines everything downstream.", subtasks: ["Write 1-page vision statement", "Define target patient avatar", "Choose specialty mix (implants, ortho, perio, surgery)", "Set 1-year, 3-year, 5-year revenue targets"] },
        { id: "d2", task: "Create financial model & secure funding", agent: "cfo", details: "Build your P&L projection, determine startup costs, and secure SBA loan or private financing.", subtasks: ["Complete startup cost worksheet ($350K-$1.2M typical)", "Build 3-year P&L projection model", "Apply for SBA 7(a) loan or bank financing", "Set up business bank accounts & credit lines"] },
        { id: "d3", task: "Choose entity structure & register business", agent: "clo", details: "LLC, S-Corp, or PC? Each has different tax and liability implications for dental practices.", subtasks: ["Consult with dental CPA on entity type", "Register LLC/PC with state", "Obtain EIN from IRS", "Register for state tax ID"] },
        { id: "d4", task: "Site selection & lease negotiation", agent: "coo", details: "Location = destiny. Analyze demographics, competition density, traffic patterns, and visibility.", subtasks: ["Run demographic analysis for 3-5 target areas", "Evaluate 5+ potential locations", "Negotiate LOI with landlord (aim for TI allowance)", "Engage dental-specific real estate attorney for lease review"] },
        { id: "d5", task: "Apply for dental licenses & DEA registration", agent: "clo", details: "State dental license, DEA registration, NPI number, facility permits \u2014 start early.", subtasks: ["Verify state dental license active & current", "Apply for DEA registration", "Obtain NPI number for practice", "Apply for facility/business license", "Register with state dental board"] },
      ]},
      { phase: 2, name: "Buildout", duration: "Month 2-4", agent: "coo", tasks: [
        { id: "d6", task: "Design office layout & hire contractor", agent: "coo", details: "4-6 operatories minimum. Plan for growth \u2014 plumb for 8 even if you build 5.", subtasks: ["Hire dental-specific architect/designer", "Plan operatory count (start 4-6, plumb for 8+)", "Select contractor with dental buildout experience", "Design patient flow: reception to consult to ops to checkout"] },
        { id: "d7", task: "Order equipment & technology stack", agent: "coo", details: "CBCT, digital scanners, practice management software, patient communication platform.", subtasks: ["Order CBCT machine (Carestream/Planmeca)", "Order digital scanner (iTero/3Shape)", "Select & set up PMS (Dentrix/Eaglesoft/Open Dental)", "Order chairs, units, compressor, vacuum, sterilization", "Set up digital imaging system"] },
        { id: "d8", task: "Insurance credentialing (start NOW \u2014 takes 90+ days)", agent: "cfo", details: "Start credentialing immediately. Delta, Cigna, MetLife, Aetna \u2014 each takes 60-120 days.", subtasks: ["Compile credentialing packet (license, NPI, DEA, malpractice)", "Submit applications to top 8-10 insurance panels", "Track application status weekly", "Set up fee schedules for each plan"] },
        { id: "d9", task: "Build brand identity & website", agent: "cmo", details: "Logo, brand colors, website with online booking, Google Business Profile.", subtasks: ["Design logo & brand guidelines", "Build website with online booking integration", "Set up Google Business Profile", "Create social media profiles (Instagram, Facebook, TikTok)", "Professional photography of space"] },
        { id: "d10", task: "Begin hiring core team", agent: "chro", details: "Office manager first (they help hire everyone else). Then front desk, hygienist, assistant.", subtasks: ["Write job descriptions for all roles", "Post on dental-specific job boards", "Hire office manager FIRST (month 2-3)", "Hire front desk coordinator", "Hire 1-2 dental assistants"] },
      ]},
      { phase: 3, name: "Pre-Launch", duration: "Month 4-5", agent: "cmo", tasks: [
        { id: "d11", task: "Launch pre-opening marketing campaign", agent: "cmo", details: "Build buzz 6-8 weeks before opening. Grand Slam Offer, local partnerships, social media blitz.", subtasks: ["Create Grand Slam Offer (Free CBCT + Consult + 3D Preview)", "Launch Google Ads campaign (target: implant keywords)", "Launch Meta/Instagram ads (before/after + offer)", "Partner with 10+ local businesses for cross-referrals", "Direct mail to 5,000 households in 3-mile radius"] },
        { id: "d12", task: "Set up all SOPs & workflows", agent: "coo", details: "Document every process: patient intake, scheduling, treatment presentation, billing, follow-up.", subtasks: ["Create new patient intake workflow (digital forms)", "Build scheduling templates & block scheduling protocol", "Write treatment presentation scripts", "Set up billing & collections workflow", "Create morning huddle template"] },
        { id: "d13", task: "Train entire team (2-week intensive)", agent: "chro", details: "Software training, customer service scripts, treatment coordination, emergency protocols.", subtasks: ["PMS software training (3 days)", "Phone scripts & new patient call training", "Treatment coordination & case acceptance training", "Emergency protocols & OSHA compliance", "Role-play patient scenarios"] },
        { id: "d14", task: "Set up patient communication automations", agent: "cmo", details: "Welcome sequences, appointment reminders, post-op follow-ups, recall campaigns \u2014 all automated.", subtasks: ["Set up appointment reminder sequence (SMS + email)", "Create new patient welcome automation", "Build post-treatment follow-up sequences", "Configure recall/reactivation campaigns", "Set up review request automation"] },
        { id: "d15", task: "HIPAA compliance & malpractice insurance", agent: "clo", details: "HIPAA policies, BAAs with all vendors, malpractice coverage, workers comp, general liability.", subtasks: ["Complete HIPAA compliance program", "Sign BAAs with all technology vendors", "Obtain malpractice insurance", "Obtain general liability insurance", "Set up workers compensation coverage"] },
      ]},
      { phase: 4, name: "Grand Opening", duration: "Month 5-6", agent: "ceo", tasks: [
        { id: "d16", task: "Grand opening event & first patients", agent: "ceo", details: "You've built it. Now execute. Grand opening event, first patients, first treatments, first revenue.", subtasks: ["Host grand opening event (refreshments, tours, free screenings)", "See first 20-30 patients in week 1", "Daily team huddles \u2014 identify and fix issues fast", "Track all KPIs from day 1"] },
        { id: "d17", task: "Activate paid advertising at full budget", agent: "cmo", details: "Scale Google + Meta ads to full budget. Target: 40-60 new patients/month within 90 days.", subtasks: ["Scale Google Ads to $3-5K/month", "Scale Meta ads to $2-3K/month", "Launch YouTube pre-roll ads", "Activate referral bonus program"] },
        { id: "d18", task: "Implement KPI tracking & weekly reviews", agent: "cfo", details: "What gets measured gets managed. Track production, collections, new patients, case acceptance weekly.", subtasks: ["Set up daily production tracking dashboard", "Weekly financial review meeting (every Monday)", "Monthly P&L review with dental CPA", "Track case acceptance rate by provider", "Monitor marketing ROI by channel"] },
      ]},
    ],
  },
  existing: {
    id: "existing", name: "Optimize Existing Practice", icon: Wrench, desc: "You have a practice. Now 10x it. Fix bottlenecks, add specialties, scale revenue.",
    phases: [
      { phase: 1, name: "Practice Audit & Diagnostic", duration: "Week 1-2", agent: "ceo", tasks: [
        { id: "e1", task: "Run 12-month production report by provider and procedure", agent: "cfo", details: "Pull from your PMS. Compare each provider’s production to benchmarks: GP $800K-$1.2M/yr, specialist $1-2M+/yr. Identify underperformers and top procedures.", subtasks: ["Export production data from PMS for last 12 months", "Break down production by provider and procedure code", "Compare each provider against industry benchmarks", "Identify top 10 revenue-generating procedures", "Flag underperforming providers for coaching plan"] },
        { id: "e2", task: "Calculate collections rate (last 12 months)", agent: "cfo", details: "Formula: Collections / Net Production x 100. Target: 98%+. If below 95%, you have a collections crisis. Check A/R aging - nothing over 90 days.", subtasks: ["Pull total collections and net production figures", "Calculate monthly collections rate trend", "Run A/R aging report by 30/60/90/120 day buckets", "Identify top 10 outstanding balances over 90 days"] },
        { id: "e3", task: "Analyze case acceptance rate by procedure type", agent: "coo", details: "Pull treatment plans presented vs. accepted. National average: 50%. Target: 70%+. Break down by implants, crowns, ortho, perio, cosmetic. Low acceptance = presentation problem, not patient problem.", subtasks: ["Pull treatment plans presented vs accepted from PMS", "Break down acceptance rate by procedure category", "Identify lowest-acceptance procedures for improvement", "Compare acceptance rates by provider", "Review treatment presentation workflow for gaps"] },
        { id: "e4", task: "Audit new patient flow (source to conversion to retention)", agent: "cmo", details: "Track where patients come from, how many call, how many book, how many show, how many accept treatment, how many return. Plug every leak in this funnel.", subtasks: ["Map complete new patient journey from source to retention", "Calculate conversion rate at each funnel stage", "Identify biggest drop-off points in the funnel", "Track new patient sources for last 6 months", "Calculate cost per acquired patient by channel"] },
        { id: "e5", task: "Calculate overhead ratio by category", agent: "cfo", details: "Pull P&L. Categories: Staff target <28%, Facility <8%, Supplies <6%, Lab <8%, Marketing <5%, Admin <4%. Total overhead target: <59%. Above 62% = crisis.", subtasks: ["Pull detailed P&L for last 12 months", "Categorize all expenses into standard overhead buckets", "Compare each category against industry benchmarks", "Identify top 3 categories over target for immediate cuts"] },
        { id: "e6", task: "Assess chair utilization rate", agent: "coo", details: "Formula: Booked hours / Available hours x 100. Target: 85-92%. Below 80% = scheduling problem. Above 95% = need more capacity.", subtasks: ["Calculate available chair hours per week per operatory", "Pull booked hours from scheduling system", "Calculate utilization rate by day of week and time slot", "Identify peak and dead zones in the schedule"] },
        { id: "e7", task: "Audit fee schedules vs UCR rates", agent: "cfo", details: "Compare your fees to 80th percentile UCR for your zip code. Most practices are 15-30% below market. Raise fees to at least 80th percentile.", subtasks: ["Pull current fee schedule from PMS", "Obtain 80th percentile UCR data for your zip code", "Calculate percentage difference for top 50 procedures", "Create fee increase plan prioritized by revenue impact"] },
        { id: "e8", task: "Review insurance mix (PPO vs FFS vs Medicaid)", agent: "cfo", details: "Ideal mix: 40-50% PPO, 30-40% FFS, 10-15% membership plan, <5% Medicaid. Heavy PPO dependency >70% = vulnerability.", subtasks: ["Pull patient count and revenue by insurance type", "Calculate percentage of revenue from each payer category", "Identify most and least profitable insurance plans", "Create plan to reduce PPO dependency if over 70%"] },
        { id: "e9", task: "Mystery shop your own front desk", agent: "coo", details: "Have 3 people call pretending to be new patients. Score on friendliness, info gathering, urgency creation, booking attempt, follow-up.", subtasks: ["Recruit 3 mystery shoppers with different scenarios", "Create scoring rubric for phone performance", "Have shoppers call at different times and days", "Compile scores and identify training gaps", "Share results with front desk team for coaching"] },
        { id: "e10", task: "Audit online reputation (Google rating, review count)", agent: "cmo", details: "Target: 4.8+ stars, 200+ Google reviews. Check that you respond to all reviews and Google Business Profile is optimized.", subtasks: ["Check current Google star rating and total review count", "Audit response rate to all Google reviews", "Review Google Business Profile completeness", "Compare review count and rating to top 5 local competitors"] },
        { id: "e11", task: "Run patient attrition analysis", agent: "coo", details: "Pull patients who haven’t visited in 12+ months. Categorize: moved, dissatisfied, no recall system. You’re sitting on $200K+ in reactivation revenue.", subtasks: ["Pull list of patients inactive 12+ months from PMS", "Categorize reasons for attrition where possible", "Estimate dollar value of reactivation opportunity", "Segment inactive patients by last treatment for targeting"] },
        { id: "e12", task: "Assess technology stack (PMS, imaging, scanner)", agent: "coo", details: "Score each system 1-10. Outdated PMS? No scanner? No CBCT? Each gap costs you $50-200K/year in lost production.", subtasks: ["List all current technology systems and their age", "Score each system 1-10 on capability and reliability", "Identify critical technology gaps (CBCT, scanner, AI tools)", "Estimate revenue impact of each technology gap", "Prioritize technology upgrades by ROI"] },
      ]},
      { phase: 2, name: "Quick Wins (First 30 Days)", duration: "Week 2-6", agent: "coo", tasks: [
        { id: "e13", task: "Raise fees to 80th percentile UCR", agent: "cfo", details: "Free money. Insurance pays contracted rate regardless. Average impact: $80-200K/year.", subtasks: ["Update fee schedule in PMS to 80th percentile UCR", "Notify team of new fee schedule effective date", "Monitor impact on production over first 30 days"] },
        { id: "e14", task: "Implement same-day treatment protocol", agent: "coo", details: "When diagnosis happens, treatment should too. Eliminates the biggest conversion killer: 'Let me think about it.'", subtasks: ["Create same-day treatment workflow for common procedures", "Train providers on same-day diagnosis-to-treatment handoff", "Set up operatory for immediate treatment availability", "Track same-day acceptance rate weekly"] },
        { id: "e15", task: "Launch patient reactivation campaign (6+ months overdue)", agent: "cmo", details: "3-touch sequence: personalized SMS, email with offer, phone call. Expected recovery: $80-150K in treatment.", subtasks: ["Pull list of patients overdue 6+ months", "Create 3-touch reactivation sequence (SMS, email, call)", "Craft compelling reactivation offer with urgency", "Assign team member to manage campaign and track results", "Set target: 15-25% reactivation rate"] },
        { id: "e16", task: "Fix phone conversion (target: 80%+ new patient calls book)", agent: "coo", details: "Record all calls for 2 weeks. Common problems: no urgency, not asking for appointment. Train on empathy, value, urgency, book.", subtasks: ["Enable call recording for all incoming lines", "Review 20+ recorded calls and score each one", "Identify top 3 phone handling mistakes", "Create phone script with empathy-value-urgency-book framework", "Role-play new scripts with front desk team"] },
        { id: "e17", task: "Implement block scheduling for production optimization", agent: "coo", details: "Block by procedure type. Eliminates random scheduling that kills production. Target: $5K+ per chair per day.", subtasks: ["Design block schedule template by procedure type", "Assign specific blocks for high-value procedures", "Train scheduling team on block scheduling rules", "Monitor daily production per chair after implementation"] },
        { id: "e18", task: "Start collecting payment at time of service", agent: "cfo", details: "New policy: patient pays estimated portion today. Impact: A/R drops 40-60%.", subtasks: ["Create time-of-service payment policy and scripts", "Train front desk on collecting estimated patient portion", "Set up payment processing for multiple payment methods", "Track A/R reduction weekly after implementation"] },
        { id: "e19", task: "Set up automated review requests", agent: "cmo", details: "Every patient gets automated SMS 2 hours after appointment. Target: 10+ new Google reviews/month.", subtasks: ["Choose and set up automated review request platform", "Configure SMS to send 2 hours post-appointment", "Create review request message with direct Google link", "Monitor new review count weekly"] },
        { id: "e20", task: "Create and promote in-house membership plan", agent: "cfo", details: "For uninsured: $25-35/month includes cleanings, exams, X-rays, 15-20% off treatment. Average member spends 2-3x more.", subtasks: ["Design membership plan tiers and pricing", "Create marketing materials for in-office and online promotion", "Train team on presenting membership plan to uninsured patients", "Set up billing system for recurring membership payments", "Track enrollment and member spending vs non-members"] },
      ]},
      { phase: 3, name: "System Upgrades & AI Integration", duration: "Month 1-3", agent: "coo", tasks: [
        { id: "e21", task: "UPGRADE: Phone system to AI-powered (Weave/Slingshot)", agent: "coo", details: "Add call recording, 2-way texting, AI after-hours answering. ROI: Captures 15-25 missed calls/week = $30-80K/year. Cost: $300-500/month.", subtasks: ["Evaluate AI phone system vendors (Weave, Slingshot, etc.)", "Select vendor and schedule installation", "Configure AI after-hours answering and call routing", "Train team on 2-way texting and call recording features", "Track missed call reduction and new bookings from AI"] },
        { id: "e22", task: "UPGRADE: Website to conversion-optimized with online booking", agent: "cmo", details: "Online scheduling 24/7, click-to-call, live chat, fast loading, SEO. ROI: Online booking adds 15-30 new patients/month. Cost: $3-8K rebuild + $200-400/month.", subtasks: ["Audit current website for speed, SEO, and conversion issues", "Redesign with online booking, click-to-call, and live chat", "Optimize for mobile and page load speed under 3 seconds", "Launch and track online booking conversion rate"] },
        { id: "e23", task: "UPGRADE: Patient communication to automated multi-channel", agent: "cmo", details: "Automated SMS/email reminders, 2-way texting, recall campaigns, review requests. ROI: Reduces no-shows 30-50%. Cost: $300-600/month.", subtasks: ["Select multi-channel communication platform", "Set up automated appointment reminders (SMS + email)", "Configure recall and reactivation campaign sequences", "Track no-show rate reduction after implementation"] },
        { id: "e24", task: "UPGRADE: Digital imaging to CBCT + intraoral scanner", agent: "coo", details: "3D treatment planning, guided implant surgery. ROI: Increases implant case acceptance 40-60%. Cost: CBCT $80-150K, Scanner $25-45K.", subtasks: ["Evaluate CBCT and scanner models (Carestream, Planmeca, iTero, 3Shape)", "Calculate ROI based on current implant case volume", "Purchase and schedule installation", "Train clinical team on 3D imaging and scanning workflows"] },
        { id: "e25", task: "UPGRADE: Practice analytics to real-time AI dashboard", agent: "cfo", details: "Real-time production tracking, provider scorecards, scheduling optimization. ROI: 15-25% more production. Cost: $300-500/month.", subtasks: ["Evaluate AI analytics platforms for dental practices", "Connect PMS data feed to analytics dashboard", "Configure provider scorecards and KPI alerts", "Train leadership team on dashboard interpretation"] },
        { id: "e26", task: "UPGRADE: Insurance verification to AI-automated", agent: "cfo", details: "Automated batch verification, real-time eligibility checks. ROI: Saves 20-30 staff hours/week = $25-40K/year. Cost: $200-400/month.", subtasks: ["Select AI insurance verification platform", "Integrate with PMS for batch verification", "Configure real-time eligibility checks at check-in", "Reassign freed staff hours to revenue-generating tasks"] },
        { id: "e27", task: "UPGRADE: Treatment presentation to AI-assisted visual", agent: "coo", details: "AI-detected conditions on X-rays, before/after simulations. ROI: Increases case acceptance 15-30%. Cost: $200-500/month.", subtasks: ["Evaluate AI diagnostic and presentation tools", "Integrate AI detection with existing imaging workflow", "Train providers on using AI visuals during case presentation", "Track case acceptance rate improvement after deployment"] },
        { id: "e28", task: "ADD: AI scheduling optimization", agent: "coo", details: "Predicts no-shows, fills cancellations from waitlist automatically. ROI: Increases chair utilization 10-20% = $100-300K/year.", subtasks: ["Select AI scheduling optimization platform", "Connect to PMS and configure no-show prediction model", "Set up automated waitlist filling for cancellations", "Monitor chair utilization improvement monthly"] },
      ]},
      { phase: 4, name: "Marketing & Growth Engine", duration: "Month 2-4", agent: "cmo", tasks: [
        { id: "e29", task: "Build Grand Slam Offer (Hormozi framework)", agent: "cmo", details: "Create irresistible entry offer: Free CBCT + Consultation + 3D Smile Preview + $500 Off. Remove all risk from first visit.", subtasks: ["Define your Grand Slam Offer components and value stack", "Create landing page dedicated to the offer", "Design ad creatives highlighting the offer", "Train team on converting Grand Slam Offer patients"] },
        { id: "e30", task: "Launch/optimize Google Ads for high-value procedures", agent: "cmo", details: "Budget $3-5K/month. Dedicated landing pages per service. Track cost per lead, cost per patient. Target CAC: $150-350.", subtasks: ["Set up Google Ads campaigns by procedure (implants, Invisalign, etc.)", "Create dedicated landing pages for each high-value service", "Configure conversion tracking for calls and form submissions", "Optimize weekly based on cost per lead and cost per patient"] },
        { id: "e31", task: "Launch Meta/Instagram retargeting + cold campaigns", agent: "cmo", details: "Budget $1.5-3K/month. Retarget website visitors + cold audience with before/after content.", subtasks: ["Install Meta pixel and build retargeting audiences", "Create cold audience targeting by demographics and interests", "Design ad creatives with before/after transformations", "Launch and optimize campaigns weekly by CAC"] },
        { id: "e32", task: "Build content engine (2 videos + 3 posts per week)", agent: "cmo", details: "Content mix: educational 60%, behind-the-scenes 20%, testimonials 10%, promotional 10%. Post to Instagram, Facebook, TikTok, YouTube Shorts.", subtasks: ["Create content calendar with weekly themes", "Batch-produce 2 videos and 3 posts per week", "Post consistently to Instagram, Facebook, TikTok, YouTube Shorts", "Track engagement and adjust content mix monthly"] },
        { id: "e33", task: "Create patient referral program ($250-500 per referral)", agent: "cmo", details: "Automate the ask: send text 48 hours post-treatment. Target: 20-30% of new patients from referrals.", subtasks: ["Design referral reward structure ($250-500 per referral)", "Set up automated referral request SMS 48 hours post-treatment", "Create referral tracking system in PMS", "Train team to verbally ask for referrals at checkout"] },
        { id: "e34", task: "Build value ladder: cleaning to whitening to Invisalign to implants", agent: "cmo", details: "Every patient should ascend. Each step increases LTV. Average LTV target: $8K+ per patient.", subtasks: ["Map out patient value ladder from entry to premium services", "Create upsell scripts for each transition point", "Train hygienists and assistants on identifying upgrade opportunities", "Track average patient LTV monthly"] },
        { id: "e35", task: "Optimize Google Business Profile", agent: "cmo", details: "Post weekly updates, respond to ALL reviews within 24 hours, add new photos monthly. Target: 4.8+ stars, 200+ reviews.", subtasks: ["Complete all Google Business Profile fields and categories", "Schedule weekly GBP posts with photos and offers", "Set up alerts and respond to all reviews within 24 hours", "Add new professional photos to profile monthly"] },
        { id: "e36", task: "Launch local community partnerships (10+ referral sources)", agent: "cmo", details: "Partner with gyms, spas, salons, real estate agents, wedding planners, corporate HR. Each partner = 2-5 new patients/month.", subtasks: ["Identify 15+ local businesses for cross-referral partnerships", "Create partnership proposal with mutual benefits", "Sign agreements with 10+ partners", "Track referrals from each partner monthly"] },
      ]},
      { phase: 5, name: "Management & AI Agent Delegation", duration: "Month 3-6", agent: "coo", tasks: [
        { id: "e37", task: "HIRE OR AI: Office Manager / Practice Administrator", agent: "chro", details: "Human option: $55-75K, runs daily operations. AI option: scheduling optimizer + KPI dashboard covers 60%. Recommendation: hire human, augment with AI.", subtasks: ["Define office manager role, KPIs, and compensation", "Post job listing on dental-specific job boards", "Interview and hire experienced practice administrator", "Set up AI tools to augment office manager workflows"] },
        { id: "e38", task: "HIRE OR AI: Treatment Coordinator", agent: "chro", details: "Human: $40-55K + bonus, a great TC adds $300-500K/year. AI: treatment presentations + financing pre-qualification. Recommendation: must be human.", subtasks: ["Define TC role with case acceptance targets and bonus structure", "Recruit experienced treatment coordinator", "Train TC on presentation scripts and financing options", "Track TC impact on case acceptance rate monthly"] },
        { id: "e39", task: "HIRE OR AI: Marketing Coordinator", agent: "cmo", details: "Human: $40-55K. AI: content generation, automated posting, ad optimization covers 80%. Recommendation: start with AI tools + part-time VA.", subtasks: ["Evaluate AI marketing tools for content and ad management", "Set up AI content generation and automated posting", "Hire part-time VA for tasks AI cannot handle", "Monitor marketing output quality and adjust workflow"] },
        { id: "e40", task: "DEPLOY: AI receptionist for after-hours and overflow calls", agent: "coo", details: "Answers 24/7, books appointments, handles FAQs, triages emergencies. ROI: 15-25 calls/week captured = $30-80K/year. Cost: $200-500/month.", subtasks: ["Select AI receptionist platform and configure for your practice", "Program FAQs, booking rules, and emergency triage protocols", "Test AI receptionist with sample calls before going live", "Track calls captured and appointments booked by AI weekly"] },
        { id: "e41", task: "DEPLOY: AI-powered patient follow-up sequences", agent: "coo", details: "Build sequences: post-consult nurture, post-treatment follow-up, recall campaign, reactivation, referral ask, review request. ROI: Recovers 20-35% of unconverted treatment.", subtasks: ["Map out all patient follow-up sequence types", "Build automated sequences for each touchpoint", "Configure triggers and timing for each sequence", "Track conversion rate from follow-up sequences monthly"] },
        { id: "e42", task: "Create weekly KPI review meeting (non-negotiable Monday ritual)", agent: "ceo", details: "30 min max: last week’s numbers, wins, misses, this week’s goals, individual accountability. Rules: start on time, data-driven.", subtasks: ["Define weekly KPI meeting agenda and format", "Create KPI report template for Monday reviews", "Assign accountability for each key metric", "Hold first meeting and iterate on format"] },
        { id: "e43", task: "Build morning huddle protocol (daily 10-minute standup)", agent: "coo", details: "Review schedule, identify high-value opportunities, confirm appointments, lab cases, patient notes, production goals. Do this every single day.", subtasks: ["Create morning huddle checklist and format", "Assign roles for huddle facilitation", "Print or display daily schedule with production targets", "Track daily production goal achievement after huddle launch"] },
        { id: "e44", task: "Implement provider scorecards (monthly performance reviews)", agent: "ceo", details: "Track per provider: daily production, collections rate, case acceptance, procedures per visit, schedule utilization. Tie bonuses to metrics.", subtasks: ["Design provider scorecard template with key metrics", "Pull baseline data for each provider", "Set performance targets and bonus thresholds", "Conduct first monthly scorecard review with each provider"] },
      ]},
      { phase: 6, name: "Scale & Multiply", duration: "Month 6-18", agent: "ceo", tasks: [
        { id: "e45", task: "Add specialty services to increase revenue per patient", agent: "ceo", details: "Add implants (highest ROI), Invisalign (volume), sleep apnea (emerging), Botox/filler (cosmetic). Each adds $200-500K/year.", subtasks: ["Evaluate market demand for each specialty service", "Recruit or contract with specialists as needed", "Invest in required specialty equipment", "Launch specialty-specific marketing campaigns", "Track revenue contribution from each new specialty"] },
        { id: "e46", task: "Hire associate dentist to scale production capacity", agent: "chro", details: "When to hire: producing $1M+ personally and chairs 85%+ utilized. Compensation: daily rate $700-1200, or 25-30% of collections.", subtasks: ["Confirm readiness criteria: $1M+ production, 85%+ utilization", "Define associate compensation model (daily rate vs percentage)", "Post position and recruit through dental networks", "Onboard associate with mentorship and production goals"] },
        { id: "e47", task: "Build operations manual (the franchise playbook)", agent: "coo", details: "Document EVERYTHING: front desk, clinical workflows, TC scripts, billing, marketing SOPs, hiring/firing, emergency protocols. Makes practice scalable and sellable.", subtasks: ["Document all front desk and patient flow procedures", "Document clinical workflows by procedure type", "Create TC scripts and billing/collections SOPs", "Build hiring, onboarding, and termination checklists", "Compile into searchable digital operations manual"] },
        { id: "e48", task: "Evaluate expansion: second location vs. maximize current", agent: "ceo", details: "Before opening location 2: Is location 1 at 90%+ capacity? Do you have a manager who can run it? Is your ops manual complete?", subtasks: ["Assess current location capacity utilization", "Evaluate management readiness for multi-location", "Run financial model for second location vs current expansion", "Make go/no-go decision with data"] },
        { id: "e49", task: "Remove yourself from daily clinical production", agent: "ceo", details: "Reduce clinical days from 5 to 4 to 3 to 2. Your hourly rate as CEO > your hourly rate as clinician. Work ON the business.", subtasks: ["Calculate your hourly rate as clinician vs as CEO", "Create transition plan to reduce clinical days gradually", "Delegate clinical production to associate providers", "Reinvest freed time into growth and strategy"] },
        { id: "e50", task: "Set up financial dashboards for multi-location management", agent: "cfo", details: "Track per-location: production, collections, overhead, profit margin, new patients, case acceptance. Compare side-by-side.", subtasks: ["Select dashboard platform for multi-location tracking", "Configure per-location KPIs and benchmarks", "Set up automated data feeds from each location PMS", "Create side-by-side comparison reports for leadership review"] },
      ]},
    ],
  },
  acquisition: {
    id: "acquisition", name: "Acquire a Practice", icon: Handshake, desc: "Buy an existing practice, inject your systems and AI, and 3-5x EBITDA within 18 months.",
    phases: [
      { phase: 1, name: "Acquisition Strategy & Targeting", duration: "Month 1-2", agent: "ceo", tasks: [
        { id: "a1", task: "Define your acquisition criteria (buy box)", agent: "ceo", details: "Ideal target: Revenue $600K-$2M, EBITDA 15-25%, within 30 miles, 4-6 operatories, 1,500+ active patients. Deal breakers: declining revenue 3+ years, short lease.", subtasks: ["Define target revenue range and EBITDA threshold", "Set geographic radius and operatory count requirements", "List deal breakers (declining revenue, lease issues, staff problems)", "Document ideal patient base size and insurance mix"] },
        { id: "a2", task: "Assemble your deal team", agent: "clo", details: "You need: dental M&A attorney ($5-15K), dental CPA ($3-8K), practice appraiser ($3-5K), SBA-preferred lender, credentialing specialist, 3-5 broker relationships.", subtasks: ["Engage dental-specific M&A attorney", "Hire dental CPA experienced in acquisitions", "Contract with practice appraiser", "Identify SBA-preferred lender and credentialing specialist", "Build relationships with 3-5 dental practice brokers"] },
        { id: "a3", task: "Register with 5+ dental practice brokers", agent: "ceo", details: "Top brokers: AFTCO, Henry Schein Practice Transitions, DDSmatch. Also search BizBuySell, state dental associations.", subtasks: ["Register with AFTCO, Henry Schein, and DDSmatch", "Set up alerts on BizBuySell and state dental association listings", "Communicate your buy box criteria to each broker", "Schedule regular check-ins with brokers for new listings"] },
        { id: "a4", task: "Get pre-approved for SBA acquisition financing", agent: "cfo", details: "SBA 7(a): borrow up to $5M, 10-year term, 10-15% down. Requirements: financial statement, 3yr tax returns, business plan, 680+ credit.", subtasks: ["Compile personal financial statement and 3-year tax returns", "Draft acquisition business plan with projections", "Apply with 2-3 SBA-preferred lenders", "Obtain pre-approval letter with borrowing limit"] },
        { id: "a5", task: "Build acquisition financial model", agent: "cfo", details: "Valuation methods: % of Revenue (60-85%), EBITDA Multiple (3-5x), Asset-based. Target: buy at 0.6-0.8x revenue or 3-4x EBITDA.", subtasks: ["Build spreadsheet model with revenue multiple and EBITDA multiple methods", "Model debt service coverage ratio for SBA loan scenarios", "Create sensitivity analysis for best/worst case scenarios", "Set maximum purchase price based on cash flow analysis"] },
        { id: "a6", task: "Create target scorecard (evaluate each practice 1-100)", agent: "ceo", details: "Score: revenue stability 15pts, location 15pts, patient base 10pts, equipment 10pts, lease 10pts, reputation 10pts, staff 10pts, growth potential 10pts. Only pursue 70+.", subtasks: ["Build scoring template with weighted categories", "Define scoring criteria for each category", "Test scorecard on 2-3 sample listings", "Set minimum score threshold of 70 for serious pursuit"] },
      ]},
      { phase: 2, name: "Due Diligence Deep Dive", duration: "Month 2-4", agent: "cfo", tasks: [
        { id: "a7", task: "Request and analyze 3 years of tax returns", agent: "cfo", details: "Verify reported income matches production reports. Look for cash income, declining trends, unusual expenses.", subtasks: ["Request 3 years of personal and business tax returns", "Compare reported income to PMS production reports", "Identify any declining revenue trends year-over-year", "Flag unusual or one-time expenses for discussion"] },
        { id: "a8", task: "Analyze production by procedure code (CDT analysis)", agent: "cfo", details: "Look for revenue concentration risk >50% from one procedure. Hygiene should be 25-33% of total. Check fee schedules vs UCR.", subtasks: ["Pull production report by CDT procedure code", "Calculate revenue percentage from each procedure category", "Verify hygiene production is 25-33% of total", "Compare fee schedule to 80th percentile UCR for the area"] },
        { id: "a9", task: "Review A/R aging and collections history", agent: "cfo", details: "Target: <5% over 60 days. Heavy old A/R means poor collections - both a risk and an opportunity you can fix.", subtasks: ["Request A/R aging report by 30/60/90/120 day buckets", "Calculate percentage of A/R over 60 days", "Review 12-month collections rate trend", "Estimate recoverable A/R as post-acquisition opportunity"] },
        { id: "a10", task: "Audit patient base (active count, demographics, insurance mix)", agent: "coo", details: "Verify active patients visited in 18 months. Check age distribution, insurance mix, geographic distribution, new patient trends.", subtasks: ["Verify active patient count (visited within 18 months)", "Analyze patient age distribution and demographics", "Review insurance mix (PPO vs FFS vs Medicaid percentages)", "Check new patient trend over last 12 months", "Map patient geographic distribution by zip code"] },
        { id: "a11", task: "Inspect all equipment (age, condition, remaining life)", agent: "coo", details: "Create inventory with age, condition 1-10, replacement cost. Red flags: 15+ year chairs, failing compressor, no digital imaging.", subtasks: ["Create equipment inventory with age and condition score", "Estimate replacement cost for each major item", "Flag equipment over 15 years old or in poor condition", "Calculate total immediate capital expenditure needed"] },
        { id: "a12", task: "Review commercial lease in detail (with attorney)", agent: "clo", details: "Need 5+ years or renewal. Check: transferability, escalation 3% max, exclusive use clause, signage rights, parking.", subtasks: ["Review remaining lease term and renewal options", "Verify lease transferability or assignability", "Check annual escalation rate (target 3% max)", "Review exclusive use clause, signage rights, and parking"] },
        { id: "a13", task: "Assess staff (quality, tenure, compensation, flight risk)", agent: "chro", details: "Meet the team. How long has each been there? Paid at market rate? Will key people stay? Staff retention is #1 post-acquisition risk.", subtasks: ["Meet each staff member individually during site visit", "Review tenure, roles, and current compensation for each", "Compare compensation to market rates", "Assess flight risk and identify key retention targets", "Plan retention bonuses or agreements for critical staff"] },
        { id: "a14", task: "Verify all licenses, DEA, NPI, malpractice are current", agent: "clo", details: "Check dental license, DEA registration, NPI, malpractice insurance, business license. Run comprehensive background check.", subtasks: ["Verify seller’s dental license status with state board", "Confirm DEA registration is current", "Check NPI and malpractice insurance coverage", "Verify business license and any required permits"] },
      ]},
      { phase: 3, name: "Negotiate & Close the Deal", duration: "Month 3-5", agent: "clo", tasks: [
        { id: "a15", task: "Submit Letter of Intent (LOI) with key terms", agent: "ceo", details: "Include: purchase price, asset purchase structure, due diligence period 45-60 days, transition 60-90 days, non-compete 5yr/10mi, exclusivity.", subtasks: ["Draft LOI with purchase price and deal structure", "Include due diligence period of 45-60 days", "Specify transition period of 60-90 days", "Define non-compete terms (5 years, 10-mile radius)", "Request exclusivity during due diligence"] },
        { id: "a16", task: "Negotiate purchase price and deal structure", agent: "cfo", details: "Leverage: declining revenue, equipment needs, PPO dependence, seller urgency. Allocate maximum to goodwill for tax benefits. Include working capital.", subtasks: ["Identify leverage points from due diligence findings", "Negotiate price reduction for equipment needs and revenue trends", "Structure asset allocation to maximize goodwill for tax benefits", "Include working capital and transition support in deal terms"] },
        { id: "a17", task: "Finalize SBA loan package and submit to lender", agent: "cfo", details: "Package: signed LOI, practice financials 3yr, personal financials, business plan, lease, equipment list, appraisal. Timeline: 30-45 days to approval.", subtasks: ["Compile complete loan package with all required documents", "Submit to SBA-preferred lender with signed LOI", "Respond promptly to lender information requests", "Track approval timeline and coordinate with closing date"] },
        { id: "a18", task: "Execute definitive Asset Purchase Agreement", agent: "clo", details: "Key sections: price allocation, assets included/excluded, reps & warranties, indemnification, closing conditions, non-compete, patient records transfer.", subtasks: ["Review and negotiate all APA sections with attorney", "Define price allocation across asset categories", "Negotiate representations, warranties, and indemnification", "Specify closing conditions and patient records transfer process"] },
        { id: "a19", task: "Begin insurance credentialing transfer (start 90+ days before close)", agent: "cfo", details: "Apply for YOUR credentials with every insurance company. Processing takes 60-120 days. Hire credentialing specialist if needed.", subtasks: ["List all insurance panels the practice participates in", "Submit credentialing applications 90+ days before close", "Hire credentialing specialist to manage the process", "Track application status and follow up bi-weekly"] },
        { id: "a20", task: "Transfer or establish all licenses and permits", agent: "clo", details: "Facility license, DEA registration, NPI update, business license, radiation safety, OSHA compliance, HIPAA policies update.", subtasks: ["Apply for new facility license and business permits", "Register for DEA and update NPI information", "Ensure radiation safety and OSHA compliance", "Update HIPAA policies and Business Associate Agreements"] },
        { id: "a21", task: "Close the deal (signing day)", agent: "clo", details: "Walk-through, sign APA, wire funds, receive keys/codes/access, transfer utilities, receive patient records and vendor contracts.", subtasks: ["Conduct final walk-through of the practice", "Sign Asset Purchase Agreement and wire funds", "Receive keys, access codes, and alarm information", "Transfer utilities, vendor contracts, and patient records"] },
      ]},
      { phase: 4, name: "Post-Acquisition Transition", duration: "Month 5-8", agent: "coo", tasks: [
        { id: "a22", task: "Day 1: Send patient communication letter", agent: "ceo", details: "Warm, reassuring tone. Staff is staying. Improvements coming. Send physical letter + email + SMS. Post on Google Business Profile.", subtasks: ["Draft warm patient communication letter", "Send via physical mail, email, and SMS", "Post announcement on Google Business Profile", "Prepare front desk to handle patient inquiries"] },
        { id: "a23", task: "Day 1: All-staff meeting - vision, no layoffs, excitement", agent: "chro", details: "60 min: introduce yourself, reassure jobs safe, share vision, listen to their ideas, outline immediate changes, Q&A.", subtasks: ["Prepare presentation covering vision and immediate plans", "Reassure team that jobs are safe and improvements are coming", "Listen to team ideas and concerns in open Q&A", "Outline first 30-day changes and expectations"] },
        { id: "a24", task: "Week 1: Meet every team member 1-on-1 (30 min each)", agent: "chro", details: "Ask: what they love, what frustrates them, what they’d change, career goals, what they need from you. Take notes, follow through.", subtasks: ["Schedule 30-minute 1-on-1 with every team member", "Ask about their strengths, frustrations, and career goals", "Take detailed notes and identify common themes", "Follow through on actionable feedback within 2 weeks"] },
        { id: "a25", task: "Week 1-2: Maintain seller’s presence for patient introductions", agent: "ceo", details: "Seller 3-5 days/week for first 2 weeks, then 2-3 days for weeks 3-4, phone available weeks 5-8. Full transition by 60-90 days.", subtasks: ["Coordinate seller’s schedule for first 2 weeks (3-5 days/week)", "Reduce seller presence to 2-3 days for weeks 3-4", "Ensure seller is phone-available through week 8", "Complete full transition by day 60-90"] },
        { id: "a26", task: "Week 2-4: Install your technology stack", agent: "coo", details: "Week 2: AI phone + communication. Week 3: Analytics dashboard. Week 4: Digital imaging upgrade. Month 2: Automated workflows. Phase it - don’t change everything at once.", subtasks: ["Week 2: Install AI phone system and patient communication platform", "Week 3: Set up analytics dashboard and KPI tracking", "Week 4: Upgrade digital imaging if needed", "Month 2: Deploy automated workflows and follow-up sequences"] },
        { id: "a27", task: "Week 3-4: Train team on your protocols", agent: "chro", details: "TC: new case presentation scripts. Front desk: phone scripts. Clinical: documentation standards. All: morning huddle, KPI awareness. Use role-playing.", subtasks: ["Train TC on new case presentation and financial scripts", "Train front desk on phone scripts and booking protocol", "Train clinical team on documentation standards", "Launch morning huddle and train all staff on KPI awareness"] },
        { id: "a28", task: "Month 2-3: Embed new KPIs and accountability systems", agent: "ceo", details: "Implement: daily production tracking, morning huddle, weekly KPI meeting, monthly scorecards, monthly P&L review. Staff resistance is normal.", subtasks: ["Launch daily production tracking for all providers", "Start weekly KPI review meeting (Monday ritual)", "Implement monthly provider scorecards", "Conduct first monthly P&L review with leadership"] },
      ]},
      { phase: 5, name: "Inject Growth - Hit 3-5x EBITDA", duration: "Month 6-18", agent: "cmo", tasks: [
        { id: "a29", task: "Launch full marketing engine on acquired practice", agent: "cmo", details: "Google Ads $3-5K/month, Meta retargeting $1.5-3K/month, Grand Slam Offer, referral program, content engine. Goal: 40-60 new patients/month.", subtasks: ["Launch Google Ads campaigns for high-value procedures ($3-5K/month)", "Set up Meta retargeting and cold campaigns ($1.5-3K/month)", "Deploy Grand Slam Offer with dedicated landing page", "Activate patient referral program and content engine", "Track new patient count weekly (target: 40-60/month)"] },
        { id: "a30", task: "Add specialty services (implants, ortho, perio, cosmetic)", agent: "ceo", details: "Each specialty adds $200-500K/year. Add implants first ($4K-30K per case), then Invisalign, sleep apnea, Botox/filler.", subtasks: ["Prioritize specialties by market demand and revenue potential", "Recruit or contract with specialists for implants first", "Add Invisalign, sleep apnea, and cosmetic services", "Launch specialty-specific marketing campaigns", "Track revenue per specialty quarterly"] },
        { id: "a31", task: "Optimize overhead to <55% (from typical acquired 65-70%)", agent: "cfo", details: "Renegotiate supplies (save 10-15%), optimize lab costs (15-20%), right-size staffing, cut marketing waste. Every 1% = $10-20K more profit on $1M practice.", subtasks: ["Renegotiate supply contracts for 10-15% savings", "Optimize lab costs through competitive bidding (15-20% savings)", "Right-size staffing based on production per employee benchmarks", "Eliminate low-ROI marketing spend"] },
        { id: "a32", task: "Grow collections to 98%+ (from typical acquired 92-95%)", agent: "cfo", details: "Payment at service policy, automated reminders, multiple payment options, clean up old A/R, submit claims within 24 hours, follow up at 15 days.", subtasks: ["Implement payment-at-time-of-service policy", "Set up automated payment reminders and multiple payment options", "Clean up old A/R and write off uncollectable balances", "Submit insurance claims within 24 hours of service", "Follow up on unpaid claims at 15 days"] },
        { id: "a33", task: "Increase case acceptance to 70%+ (from typical acquired 45-55%)", agent: "coo", details: "Visual diagnosis, same-room presentation, TC handles financial discussion, always offer financing, follow up on unaccepted treatment. Impact: $400K more accepted on $2M presented.", subtasks: ["Implement visual diagnosis with AI-assisted imaging", "Train on same-room treatment presentation protocol", "Have TC handle all financial discussions and financing options", "Build automated follow-up sequence for unaccepted treatment", "Track case acceptance rate weekly by provider"] },
        { id: "a34", task: "Prepare for next acquisition (roll-up strategy)", agent: "ceo", details: "Document integration playbook, refinance loan with proven performance, use cash flow for next down payment. The Hormozi play: buy underperforming, inject systems, repeat.", subtasks: ["Document complete acquisition integration playbook", "Refinance existing loan with improved practice performance", "Allocate cash flow toward next acquisition down payment", "Apply buy box criteria and scorecard to new targets", "Begin sourcing next acquisition through broker network"] },
      ]},
    ],
  },
};

const AGENT_KEYS = ["ceo", "coo", "cmo", "cfo", "chro", "clo"] as const;

function getAllTaskIds(path: PathData): string[] {
  return path.phases.flatMap(p => p.tasks.map(t => t.id));
}

function AgentBadge({ agentKey }: { agentKey: string }) {
  const agent = AI_AGENTS[agentKey];
  if (!agent) return null;
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold ${agent.badgeClass}`} data-testid={`badge-agent-${agentKey}`}>
      {agent.short}
    </span>
  );
}

export default function PracticeLaunchPad() {
  const [completedTasks, setCompletedTasks] = useState<Record<string, boolean>>({});
  const [expandedSubtasks, setExpandedSubtasks] = useState<Record<string, boolean>>({});

  const toggleTask = (taskId: string) => {
    setCompletedTasks(prev => ({ ...prev, [taskId]: !prev[taskId] }));
  };

  const toggleSubtasks = (taskId: string) => {
    setExpandedSubtasks(prev => ({ ...prev, [taskId]: !prev[taskId] }));
  };

  const getPhaseProgress = (phase: PhaseData): number => {
    const total = phase.tasks.length;
    if (total === 0) return 0;
    const done = phase.tasks.filter(t => completedTasks[t.id]).length;
    return Math.round((done / total) * 100);
  };

  return (
    <div className="space-y-8" data-testid="practice-launchpad">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-foreground" data-testid="text-page-title">
          Practice Launch Pad
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          Your AI-powered roadmap to build, optimize, or acquire a dental practice
        </p>
      </div>

      <div>
        <h2 className="text-lg font-bold text-foreground mb-4" data-testid="text-agents-heading">AI C-Suite Agents</h2>
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3">
          {AGENT_KEYS.map(key => {
            const agent = AI_AGENTS[key];
            const Icon = agent.icon;
            return (
              <Card key={key} data-testid={`card-agent-${key}`}>
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <div className={`flex-shrink-0 mt-0.5 ${agent.colorClass}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-bold text-sm text-foreground">{agent.name}</span>
                        <AgentBadge agentKey={key} />
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">{agent.desc}</p>
                      <p className="text-xs text-muted-foreground/70 mt-2 italic leading-relaxed">
                        "{agent.personality}"
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      <div>
        <h2 className="text-lg font-bold text-foreground mb-4" data-testid="text-paths-heading">Practice Path Selector</h2>
        <Tabs defaultValue="denovo" data-testid="path-tabs">
          <TabsList data-testid="path-tabs-list">
            <TabsTrigger value="denovo" data-testid="tab-denovo">
              <Building className="h-3.5 w-3.5 mr-1.5" />
              De Novo
            </TabsTrigger>
            <TabsTrigger value="existing" data-testid="tab-existing">
              <Wrench className="h-3.5 w-3.5 mr-1.5" />
              Existing
            </TabsTrigger>
            <TabsTrigger value="acquisition" data-testid="tab-acquisition">
              <Handshake className="h-3.5 w-3.5 mr-1.5" />
              Acquisition
            </TabsTrigger>
          </TabsList>

          {Object.entries(PATHS).map(([pathKey, path]) => {
            const PathIcon = path.icon;
            return (
              <TabsContent key={pathKey} value={pathKey} className="mt-4" data-testid={`tabcontent-${pathKey}`}>
                <Card className="mb-4">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-3 flex-wrap">
                      <PathIcon className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                      <div>
                        <h3 className="font-bold text-foreground">{path.name}</h3>
                        <p className="text-xs text-muted-foreground">{path.desc}</p>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Accordion type="multiple" className="space-y-2" data-testid={`accordion-${pathKey}`}>
                  {path.phases.map(phase => {
                    const progress = getPhaseProgress(phase);
                    const phaseAgent = AI_AGENTS[phase.agent];
                    return (
                      <AccordionItem key={phase.phase} value={`phase-${pathKey}-${phase.phase}`} className="border rounded-md px-4" data-testid={`phase-${pathKey}-${phase.phase}`}>
                        <AccordionTrigger className="hover:no-underline" data-testid={`phase-trigger-${pathKey}-${phase.phase}`}>
                          <div className="flex items-center gap-3 flex-1 flex-wrap text-left">
                            <Badge variant="secondary" className="no-default-hover-elevate no-default-active-elevate" data-testid={`badge-phase-${pathKey}-${phase.phase}`}>
                              Phase {phase.phase}
                            </Badge>
                            <span className="font-bold text-foreground">{phase.name}</span>
                            <span className="text-xs text-muted-foreground">{phase.duration}</span>
                            <AgentBadge agentKey={phase.agent} />
                            <div className="ml-auto flex items-center gap-2 mr-2">
                              <span className="text-xs text-muted-foreground">{progress}%</span>
                              <Progress value={progress} className="w-20 h-2" data-testid={`progress-${pathKey}-${phase.phase}`} />
                            </div>
                          </div>
                        </AccordionTrigger>
                        <AccordionContent>
                          <div className="space-y-2 pt-2">
                            {phase.tasks.map(task => {
                              const isCompleted = !!completedTasks[task.id];
                              const isExpanded = !!expandedSubtasks[task.id];
                              const taskAgent = AI_AGENTS[task.agent];
                              return (
                                <div key={task.id} className="rounded-md border p-3" data-testid={`task-${task.id}`}>
                                  <div className="flex items-start gap-3">
                                    <Checkbox
                                      checked={isCompleted}
                                      onCheckedChange={() => toggleTask(task.id)}
                                      className="mt-0.5"
                                      data-testid={`checkbox-${task.id}`}
                                    />
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <span className={`text-sm font-medium ${isCompleted ? "line-through text-muted-foreground" : "text-foreground"}`}>
                                          {task.task}
                                        </span>
                                        <AgentBadge agentKey={task.agent} />
                                        <Tooltip>
                                          <TooltipTrigger asChild>
                                            <button className="inline-flex" data-testid={`info-${task.id}`}>
                                              <Info className="h-3.5 w-3.5 text-muted-foreground" />
                                            </button>
                                          </TooltipTrigger>
                                          <TooltipContent side="top" className="max-w-xs text-xs">
                                            <p className="font-semibold mb-1">{taskAgent?.short} Guidance</p>
                                            <p>{task.details}</p>
                                          </TooltipContent>
                                        </Tooltip>
                                      </div>

                                      <Collapsible open={isExpanded} onOpenChange={() => toggleSubtasks(task.id)}>
                                        <CollapsibleTrigger asChild>
                                          <button className="flex items-center gap-1 mt-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors" data-testid={`subtasks-toggle-${task.id}`}>
                                            {isExpanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                                            {task.subtasks.length} subtasks
                                          </button>
                                        </CollapsibleTrigger>
                                        <CollapsibleContent>
                                          <ul className="mt-2 space-y-1 pl-1">
                                            {task.subtasks.map((sub, si) => (
                                              <li key={si} className="flex items-start gap-2 text-xs text-muted-foreground" data-testid={`subtask-${task.id}-${si}`}>
                                                <span className="mt-1.5 h-1 w-1 rounded-full bg-muted-foreground/40 flex-shrink-0" />
                                                {sub}
                                              </li>
                                            ))}
                                          </ul>
                                        </CollapsibleContent>
                                      </Collapsible>
                                    </div>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </AccordionContent>
                      </AccordionItem>
                    );
                  })}
                </Accordion>
              </TabsContent>
            );
          })}
        </Tabs>
      </div>
    </div>
  );
}