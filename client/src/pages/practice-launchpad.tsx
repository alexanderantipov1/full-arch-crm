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
      { phase: 1, name: "Audit & Diagnose", duration: "Week 1-2", agent: "ceo", tasks: [
        { id: "e1", task: "Complete practice health audit (30-point diagnostic)", agent: "ceo", details: "Before fixing anything, know exactly where you stand. This audit reveals your biggest bottlenecks.", subtasks: ["Run production report (last 12 months by provider)", "Analyze collections rate (target: 98%+)", "Calculate case acceptance rate by procedure type", "Audit new patient flow (source, conversion, no-shows)", "Review overhead ratio (target: <60%)"] },
        { id: "e2", task: "Financial deep dive \u2014 find the leaks", agent: "cfo", details: "Most practices leak $200K-$500K/year in undiagnosed treatment, bad collections, and fee schedule gaps.", subtasks: ["Run aging report \u2014 chase outstanding A/R", "Audit fee schedules vs. UCR rates", "Identify undiagnosed treatment in patient base", "Review insurance write-offs by plan", "Analyze overhead line-by-line"] },
        { id: "e3", task: "Team performance assessment", agent: "chro", details: "Your team either scales you or stalls you. Assess everyone against role expectations.", subtasks: ["Review each team member against KPIs", "Identify A-players, B-players, and mismatches", "Assess treatment coordinator effectiveness", "Evaluate front desk conversion rate", "Survey team satisfaction & engagement"] },
        { id: "e4", task: "Marketing & patient acquisition audit", agent: "cmo", details: "Where are patients coming from? What's the cost? What's the conversion rate at each step?", subtasks: ["Track patient source for last 6 months", "Calculate CAC by channel", "Audit Google Business Profile (reviews, photos, posts)", "Review website conversion rate", "Analyze phone call handling (mystery shop yourself)"] },
      ]},
      { phase: 2, name: "Quick Wins", duration: "Week 2-6", agent: "coo", tasks: [
        { id: "e5", task: "Fix case acceptance with AI presentation scripts", agent: "coo", details: "Most practices accept 40-50% of cases. Get to 70%+ with better scripting and visual aids.", subtasks: ["Train on same-day treatment presentation protocol", "Implement 3D scan visualization for all implant consults", "Create financing scripts (CareCredit, Proceed, Sunbit)", "Role-play objection handling with team weekly", "Implement treatment coordinator handoff process"] },
        { id: "e6", task: "Launch reactivation campaign \u2014 mine your database", agent: "cmo", details: "Reactivate patients who haven't been in 6+ months. Typical result: $80K-$150K recovered.", subtasks: ["Pull list of all patients not seen in 6+ months", "Segment by last treatment type", "Launch 3-touch reactivation campaign (SMS, email, call)", "Offer limited-time incentive for returning", "Track reactivation rate (target: 15-25%)"] },
        { id: "e7", task: "Optimize scheduling \u2014 eliminate dead time", agent: "coo", details: "Block scheduling + same-day treatment = more production per day. Target: $5K+ per chair per day.", subtasks: ["Implement block scheduling by procedure type", "Create same-day treatment protocol", "Set up waitlist/short-notice list", "Reduce no-shows with confirmation automation"] },
        { id: "e8", task: "Fix collections \u2014 get to 98%+", agent: "cfo", details: "You do the work, you should get paid. Most practices collect 91-94%. Get to 98%.", subtasks: ["Implement payment-at-time-of-service policy", "Set up automated payment reminders", "Renegotiate insurance fee schedules annually", "Offer in-house membership plan for uninsured", "Clean up A/R \u2014 nothing over 90 days"] },
      ]},
      { phase: 3, name: "Scale Systems", duration: "Month 2-4", agent: "coo", tasks: [
        { id: "e9", task: "Add specialty services (implants, ortho, perio)", agent: "ceo", details: "The fastest way to grow revenue: add high-value specialties. Implant cases = $4K-$30K each.", subtasks: ["Evaluate specialty demand in your market", "Recruit or contract with specialists", "Invest in specialty equipment (CBCT, scanner)", "Train team on specialty patient flow", "Launch specialty-specific marketing campaigns"] },
        { id: "e10", task: "Build automated patient communication engine", agent: "cmo", details: "Every touchpoint automated: reminders, follow-ups, recalls, reviews, referrals \u2014 24/7.", subtasks: ["Automate appointment reminders (2-day, same-day)", "Build post-treatment follow-up sequences by procedure", "Automate recall campaigns (3, 6, 9, 12 month)", "Set up review request automation"] },
        { id: "e11", task: "Create the operations manual", agent: "coo", details: "If it's not documented, it doesn't exist. Your ops manual is what makes your practice scalable.", subtasks: ["Document all front desk procedures", "Document clinical workflows by procedure type", "Create treatment coordinator playbook", "Build billing & collections procedures", "Create hiring & onboarding checklists"] },
        { id: "e12", task: "Scale marketing \u2014 build the patient acquisition machine", agent: "cmo", details: "Move from random marketing to a systematic acquisition engine. Target: predictable cost per new patient.", subtasks: ["Launch/optimize Google Ads for high-value procedures", "Build Meta ad funnels with retargeting", "Create content engine (2 videos + 3 posts/week)", "Launch patient referral program"] },
      ]},
      { phase: 4, name: "Multiply", duration: "Month 4-12", agent: "ceo", tasks: [
        { id: "e13", task: "Prepare for second location or associate hire", agent: "ceo", details: "Once systems are running, duplicate. Either open location #2 or add an associate.", subtasks: ["Determine expansion path: associate vs. 2nd location", "Build associate compensation model", "Create location #2 financial model", "Identify target area for expansion", "Begin recruitment for associate/partner"] },
        { id: "e14", task: "Build management layer \u2014 remove yourself from daily ops", agent: "chro", details: "You should work ON the business, not IN it. Hire/promote an office manager who runs the day-to-day.", subtasks: ["Promote or hire office manager / integrator", "Create management KPI dashboard", "Implement weekly leadership meetings", "Document owner's role & decision-making framework", "Build training program for future managers"] },
      ]},
    ],
  },
  acquisition: {
    id: "acquisition", name: "Acquire a Practice", icon: Handshake, desc: "Buy an existing practice, inject your systems and AI, and 3-5x EBITDA within 18 months.",
    phases: [
      { phase: 1, name: "Target & Evaluate", duration: "Month 1-3", agent: "ceo", tasks: [
        { id: "a1", task: "Define acquisition criteria & search strategy", agent: "ceo", details: "What's your ideal practice profile? Revenue, location, specialties, seller motivation \u2014 define your buy box.", subtasks: ["Set revenue range ($500K-$2M typical)", "Define geographic target area", "Choose specialty focus (general, implant-heavy, ortho)", "Identify deal breakers (lease issues, staff problems)", "Set max purchase price / multiple target"] },
        { id: "a2", task: "Source and screen acquisition targets", agent: "ceo", details: "Cast a wide net, screen ruthlessly. Evaluate 20+ practices, seriously pursue 3-5, close 1-2.", subtasks: ["Contact dental brokers for active listings", "Network with retiring dentists in target area", "Screen for: revenue stability, patient count, location quality", "Request preliminary financials on top 5 targets", "Schedule site visits for top 3"] },
        { id: "a3", task: "Financial due diligence deep-dive", agent: "cfo", details: "Verify everything. Last 3 years of tax returns, production reports, collections, overhead, patient mix.", subtasks: ["Request 3 years of tax returns", "Analyze production by procedure code", "Review collections rate and A/R aging", "Calculate adjusted EBITDA / owner benefit", "Get independent practice valuation"] },
        { id: "a4", task: "Legal due diligence & structure deal", agent: "clo", details: "Asset purchase vs. stock purchase. Review lease, contracts, employee agreements, insurance panels.", subtasks: ["Engage dental-specific M&A attorney", "Determine deal structure (asset vs. entity purchase)", "Review commercial lease terms & transferability", "Audit all vendor contracts", "Verify all licenses, permits, DEA current"] },
      ]},
      { phase: 2, name: "Close the Deal", duration: "Month 3-4", agent: "cfo", tasks: [
        { id: "a5", task: "Submit LOI & negotiate terms", agent: "ceo", details: "Letter of Intent: price, terms, transition period, seller's involvement, non-compete, earnout structure.", subtasks: ["Draft LOI with purchase price & terms", "Negotiate transition period (60-90 days ideal)", "Define seller involvement post-close", "Negotiate non-compete (5 years, 10-mile radius typical)", "Set contingencies (financing, due diligence)"] },
        { id: "a6", task: "Secure acquisition financing", agent: "cfo", details: "SBA 7(a) is king for dental acquisitions. 10-year term, competitive rates, up to $5M.", subtasks: ["Apply with 2-3 SBA-preferred lenders", "Prepare loan package (business plan, projections, personal financials)", "Get pre-approval before submitting LOI", "Negotiate terms (rate, term, down payment)"] },
        { id: "a7", task: "Execute definitive purchase agreement", agent: "clo", details: "The binding contract. Every detail matters \u2014 reps & warranties, indemnification, closing conditions.", subtasks: ["Draft/review Asset Purchase Agreement", "Negotiate representations & warranties", "Define indemnification terms", "Set closing conditions & timeline", "Coordinate lender requirements for closing"] },
      ]},
      { phase: 3, name: "Transition", duration: "Month 4-6", agent: "coo", tasks: [
        { id: "a8", task: "Day 1 takeover \u2014 communicate with patients & staff", agent: "ceo", details: "First impressions matter. How you communicate the transition determines patient and staff retention.", subtasks: ["Send patient communication letter (warm, reassuring)", "Hold all-staff meeting \u2014 vision, excitement", "Meet every team member 1-on-1 in first week", "Maintain seller's presence for 30-60 days", "Be visible and present \u2014 patients need to trust you"] },
        { id: "a9", task: "Install your systems & technology stack", agent: "coo", details: "Inject your systems: PMS upgrade, digital workflows, AI scheduling, patient communication platform.", subtasks: ["Evaluate and upgrade PMS if needed", "Install CBCT / digital scanner if not present", "Set up patient communication automation", "Implement digital intake forms", "Install production tracking dashboard"] },
        { id: "a10", task: "Train team on your systems & culture", agent: "chro", details: "The acquired team needs to learn your way. Be patient but firm. Culture transformation takes 90 days.", subtasks: ["Week 1-2: Software & workflow training", "Week 3-4: Treatment presentation & case acceptance", "Month 2: Phone skills & patient experience training", "Ongoing: Weekly team meetings with metrics review"] },
        { id: "a11", task: "Transfer insurance credentials & update contracts", agent: "cfo", details: "Critical: transfer insurance panel participation. Apply for new credentials 90+ days before close.", subtasks: ["Start credentialing applications pre-close (60-90 days)", "Coordinate with each insurance company on ownership transfer", "Update NPI, tax ID with all payers", "Renegotiate fee schedules where possible", "Update all vendor contracts to new entity"] },
      ]},
      { phase: 4, name: "Inject Growth", duration: "Month 6-18", agent: "cmo", tasks: [
        { id: "a12", task: "Launch aggressive marketing \u2014 fill the chairs", agent: "cmo", details: "Acquired practices are usually under-marketed. Inject your acquisition engine and watch revenue climb.", subtasks: ["Launch Google Ads for implants & high-value procedures", "Activate patient reactivation campaign (6+ months overdue)", "Build referral program for existing patient base", "Rebrand gradually (new website, updated signage)", "Launch social media content engine"] },
        { id: "a13", task: "Add specialty services to increase revenue per patient", agent: "ceo", details: "Most acquired GP practices are missing implants, ortho, and perio. Adding these can 2-3x revenue.", subtasks: ["Assess which specialties to add based on demand", "Recruit or contract with specialists", "Invest in specialty equipment if needed", "Train existing team on specialty patient flow", "Launch specialty marketing campaigns"] },
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