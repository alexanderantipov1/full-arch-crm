import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Collapsible,
  CollapsibleTrigger,
  CollapsibleContent,
} from "@/components/ui/collapsible";
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
} from "@/components/ui/tooltip";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Bot,
  Send,
  ChevronDown,
  ChevronRight,
  Scale,
  Landmark,
  Building,
  FileText,
  Palette,
  Users,
  Phone,
  ClipboardList,
  Megaphone,
  BarChart3,
  MessageSquare,
  Info,
} from "lucide-react";

const BOT_RESPONSES: Record<string, string> = {
  permits:
    "Here's your complete permit checklist for opening a dental practice:\n\n**1. State Dental License** -- Verify active with your state board. If relocating states, apply for reciprocity 90+ days in advance.\n\n**2. Business License** -- Apply with your city/county clerk. Cost ranges from $50-$500 depending on jurisdiction.\n\n**3. DEA Registration** -- Apply at deadiversion.usdoj.gov. Fee is approximately $888 for 3 years. Processing takes 4-6 weeks, so START IMMEDIATELY.\n\n**4. NPI Number** -- Register at nppes.cms.hhs.gov. Free registration. Type 1 is for you personally, Type 2 is for your practice entity. Takes 1-2 business days.\n\n**5. State Tax ID** -- Register with your state's Department of Revenue for sales tax on retail items.\n\n**6. EIN (Federal Tax ID)** -- Apply at irs.gov. Instant approval online and completely free.\n\n**7. Radiation Safety Certificate** -- Required for all X-ray equipment. Register with your state radiation control program.\n\n**8. Fire Department Inspection** -- Schedule before your planned opening date.\n\n**9. Building/Occupancy Permit** -- Obtain from your local building department. Your contractor should handle filing but you must verify.\n\n**10. OSHA Compliance Certificate** -- Complete training and documentation. Use OSHA Review or DDS Compliance for turnkey programs.\n\nStart these 90+ days before your planned opening date. Insurance credentialing takes the longest so begin that process as soon as possible.",

  google:
    "Setting up your **Google Business Profile** is critical for local patient acquisition:\n\n**Step-by-Step Setup:**\n1. Go to business.google.com and sign in with your Google account\n2. Click 'Add your business' and enter your practice name\n3. Choose category: 'Dental Implant Provider' or 'Dental Clinic'\n4. Enter your physical address (must be a real location)\n5. Add your phone number and website URL\n6. Verify via postcard (5-7 days) or phone verification\n\n**Optimization Tips:**\n- Upload 20+ high-quality photos (office exterior, interior, equipment, team, before/after results)\n- Write a 750-word business description with relevant keywords\n- Add all services with detailed descriptions\n- Set up messaging and appointment booking features\n- Post weekly updates using Google Posts\n- Respond to every single review within 24 hours\n\n**Review Strategy:**\nTarget 50+ five-star reviews in your first 6 months. Set up automated review requests that send via SMS after every appointment. Use tools like Birdeye, Podium, or Weave for automation. Your Google Business Profile will be the single biggest driver of local search visibility.",

  logo:
    "**Brand and Logo Creation Playbook:**\n\n**Step 1: Define Brand Personality**\nDecide your positioning: Professional + warm? Modern + clinical? Luxury + approachable? Your brand personality drives every visual and verbal decision.\n\n**Step 2: Choose Your Color Palette**\n- Blues and teals convey trust and professionalism\n- Greens signal health and wellness\n- Gold and navy communicate premium quality\n- Avoid overly bright or trendy colors that may feel dated quickly\n\n**Step 3: Logo Design Options**\n- AI-generated logos via Looka.com ($20-$300)\n- Freelance designers on Fiverr or Upwork ($100-$500)\n- Local agency for a full brand kit ($2,000-$10,000)\n\n**Step 4: Complete Brand Kit Must-Haves**\n- Primary logo plus icon mark\n- Color codes in HEX, RGB, and CMYK\n- Typography selections for headings and body text\n- Brand voice guidelines document\n- Business card and letterhead templates\n- Social media profile templates\n- Signage specifications\n\n**Step 5: Apply Everywhere**\nConsistency is everything. Apply your brand to signage, website, patient forms, scrub embroidery, social profiles, office decor, and all printed materials.",

  phone:
    "**Smart Phone System Setup for Your Practice:**\n\n**Choosing a Dental VoIP Provider:**\n- Weave: Dental-specific with best PMS integration\n- Mango Voice: Great for multi-location practices\n- RingCentral: Enterprise-grade reliability\n- 8x8: Budget-friendly option with solid features\n\n**Essential Features You Need:**\n- Auto-attendant with specialty routing (new patient, existing, emergency, billing)\n- Call recording for training and quality assurance\n- 2-way text/SMS capability (patients prefer texting 3:1 over calling)\n- Integration with your Practice Management Software\n- After-hours routing plus emergency line\n- Call analytics tracking missed calls and wait times\n\n**Phone Scripts to Create:**\n1. New patient inquiry script (target 80%+ conversion rate)\n2. Insurance verification script\n3. Emergency call triage script\n4. Appointment confirmation script\n5. Collections and billing call script\n\n**Advanced Setup:**\nSet up AI after-hours call handling with tools like Slingshot AI or DentistAI. These handle appointment requests, emergency triage, FAQ responses, and route urgent calls to you. Configure appointment reminder automation with a sequence: 1 week before via email, 2 days before via text, same-day morning via text.",

  website:
    "**Website Creation Checklist:**\n\n**Platform Selection:**\nWordPress with a dental theme for ease of use, or custom Next.js build for maximum performance and flexibility.\n\n**Must-Have Pages:**\n1. Homepage with hero section, offer, and trust signals\n2. About / Meet the Doctor page\n3. Services pages (one dedicated page per specialty)\n4. Before and After Gallery\n5. Patient Testimonials\n6. Insurance and Financing information\n7. Contact page with Online Booking\n8. Blog for ongoing SEO content\n\n**Critical Technical Features:**\n- Online scheduling integration with your PMS\n- Click-to-call functionality on mobile devices\n- HIPAA-compliant contact and intake forms\n- Live chat widget for real-time engagement\n- Fast page loading under 3 seconds\n- Mobile-first responsive design\n- SSL certificate for security\n\n**SEO Strategy from Day One:**\n- Target primary keyword: 'dental implants [your city]'\n- Create individual location pages if serving multiple areas\n- Implement schema markup for dental practice structured data\n- Publish blog content at least 2 times per month\n- Build local citations on dental directories\n\n**Budget:** $3,000-$8,000 for a professional dental website. DIY option with Squarespace runs $200-$500.",

  hiring:
    "**Hiring Playbook -- Build Your A-Team:**\n\n**Recommended Hiring Order:**\n1. Office Manager (Month 1) -- They help hire everyone else and set up operations\n2. Front Desk / Treatment Coordinator (Month 2)\n3. Dental Assistants x2 (Month 2-3)\n4. Hygienist x1 (Month 3) -- Scale up as patient volume grows\n5. Billing Specialist (Month 3-4) -- Or outsource initially\n\n**Where to Find Dental Talent:**\n- DentalPost.net (dental-specific job board)\n- Indeed and ZipRecruiter for broad reach\n- Local dental hygiene schools for new graduates\n- Facebook dental professional groups\n- Referral bonuses from other offices\n\n**Compensation Benchmarks (varies by market):**\n- Office Manager: $55,000-$75,000\n- Treatment Coordinator: $40,000-$55,000\n- Dental Assistant: $38,000-$52,000\n- Hygienist: $75,000-$95,000\n- Front Desk: $35,000-$48,000\n\n**Key Interview Questions:**\n- 'Tell me about a difficult patient interaction and how you handled it'\n- 'What is your approach to treatment presentation?'\n- 'How do you handle a scheduling conflict or double-booking?'\n\n**Important Principle:** Culture fit matters more than experience. You can train skills, but you cannot train attitude and work ethic. Always prioritize personality and values alignment.",

  kpi:
    "**KPI Dashboard -- Track These Numbers Religiously:**\n\n**Daily KPIs (Review in Morning Huddle):**\n- Production scheduled vs. daily goal\n- Open chair time and utilization rate\n- New patients scheduled for the day\n- Unconfirmed appointments requiring follow-up\n\n**Weekly KPIs:**\n- Production: actual vs. goal with variance analysis\n- Collections: total amount and collection percentage\n- New patients: count and source attribution\n- Case acceptance rate by provider\n- Cancellation and no-show rate\n\n**Monthly KPIs (Dental Entrepreneur Org Standards):**\n- Total production revenue\n- Total collections (target: 98%+)\n- Overhead ratio (target: under 59%)\n- New patients per month (target: 25-40)\n- Case acceptance rate (target: above 70%)\n- Average production per visit\n- Hygiene production as percentage of total (target: 25-33%)\n- Reappointment rate (target: above 85%)\n- Accounts receivable over 90 days\n- Patient lifetime value\n\n**The 4 Numbers That Matter Most:**\n1. Production per day per provider\n2. Collections percentage\n3. New patients per month\n4. Case acceptance rate\n\nDisplay these on a screen in your break room and review them every single morning huddle.",

  ads:
    "**Advertising and Patient Acquisition Guide:**\n\n**Google Ads (Start Here -- Highest Intent):**\n- Budget: $2,000-$5,000 per month to start\n- Target keywords: 'dental implants near me', 'dentist [city]', 'emergency dentist [city]'\n- Create dedicated landing pages for each service\n- Track cost per lead and cost per new patient\n- Target customer acquisition cost: $150-$350\n\n**Meta and Instagram Ads:**\n- Budget: $1,000-$3,000 per month\n- Before/after content performs best for engagement\n- Video testimonials deliver the highest conversion rates\n- Retarget website visitors who did not book\n- Build lookalike audiences from your existing patient list\n\n**The Grand Slam Offer (Hormozi Framework):**\n- Offer: 'Free CBCT Scan + Consultation + 3D Smile Preview'\n- Remove all risk from the first visit experience\n- Make it an absolute no-brainer to walk through your door\n- Then deliver an exceptional patient experience that sells itself\n\n**Referral Program:**\n- Reward $250-$500 per referred patient who starts treatment\n- Automate the referral ask via text 48 hours after treatment completion\n- Track referral source attribution religiously\n\nGoal: Build a predictable patient acquisition machine at under $300 cost per acquisition.",

  default:
    "I'm **DentBot** -- your AI practice advisor. I can help you with any aspect of opening and running a successful dental practice.\n\n**Topics I can assist with:**\n\n1. **Permits and Licensing** -- State dental license, DEA, NPI, business permits\n2. **Google Business Profile** -- Setup, optimization, review strategy\n3. **Logo and Branding** -- Brand identity, color palette, design resources\n4. **Phone Systems** -- VoIP setup, scripts, call tracking\n5. **Website Creation** -- Platform selection, SEO, must-have features\n6. **Hiring and HR** -- Team building, compensation, interview process\n7. **KPIs and Metrics** -- Daily, weekly, and monthly tracking\n8. **Advertising** -- Google Ads, Meta Ads, referral programs\n\nJust type what you need help with, or ask me anything about opening and running your dental practice. I'm here to guide you through every step of the process.",
};

function getResponse(msg: string): string {
  const m = msg.toLowerCase();
  if (m.includes("permit") || m.includes("license") || m.includes("dea") || m.includes("npi")) return BOT_RESPONSES.permits;
  if (m.includes("google") || m.includes("gmb") || m.includes("maps")) return BOT_RESPONSES.google;
  if (m.includes("logo") || m.includes("brand") || m.includes("design")) return BOT_RESPONSES.logo;
  if (m.includes("phone") || m.includes("call") || m.includes("voip")) return BOT_RESPONSES.phone;
  if (m.includes("website") || m.includes("site") || m.includes("web")) return BOT_RESPONSES.website;
  if (m.includes("hir") || m.includes("staff") || m.includes("team") || m.includes("recruit")) return BOT_RESPONSES.hiring;
  if (m.includes("kpi") || m.includes("metric") || m.includes("track") || m.includes("number")) return BOT_RESPONSES.kpi;
  if (m.includes("ad") || m.includes("market") || m.includes("patient acquisition")) return BOT_RESPONSES.ads;
  return BOT_RESPONSES.default;
}

interface LaunchTask {
  t: string;
  ai: string;
}

interface LaunchPhase {
  id: string;
  phase: number;
  name: string;
  icon: typeof Scale;
  duration: string;
  tasks: LaunchTask[];
}

const PHASE_ICONS = [Scale, Landmark, Building, FileText, Palette, Users, Phone, ClipboardList, Megaphone, BarChart3];

const LAUNCH_PHASES: LaunchPhase[] = [
  {
    id: "legal", phase: 1, name: "Legal & Entity Formation", icon: Scale, duration: "Week 1-2",
    tasks: [
      { t: "Choose entity structure (LLC, S-Corp, or Professional Corp)", ai: "Consult dental CPA. Most solo practitioners start with single-member LLC taxed as S-Corp for tax efficiency." },
      { t: "Register business entity with state Secretary of State", ai: "File online at your state's SOS website. Cost: $50-$500 depending on state. Processing: 3-10 business days." },
      { t: "Obtain EIN (Federal Tax ID) from IRS", ai: "Apply at irs.gov/ein -- instant approval online. Free. You need this for banking, hiring, and insurance." },
      { t: "Register for state tax ID / sales tax permit", ai: "Register with your state's Department of Revenue. Required for collecting sales tax on retail items." },
      { t: "Open business bank account + credit line", ai: "Bring EIN, formation docs, and operating agreement. Recommend: dental-friendly banks like Bank of America, Live Oak Bank." },
      { t: "Purchase malpractice insurance", ai: "Contact: MedPro, Dentists Advantage, or AADA. Budget: $1,500-$4,000/year. Get quotes from 3+ carriers." },
      { t: "Purchase general liability + property insurance", ai: "Bundle with malpractice carrier. Include: general liability, property, business interruption, workers comp." },
      { t: "Engage dental-specific CPA and attorney", ai: "Find through your state dental association. CPA sets up bookkeeping, payroll, tax planning from day 1." },
    ],
  },
  {
    id: "licensing", phase: 2, name: "Licenses & Permits", icon: Landmark, duration: "Week 2-6",
    tasks: [
      { t: "Verify state dental license is active and current", ai: "Check your state dental board website. If relocating states, apply for new license 90+ days early." },
      { t: "Apply for DEA Registration (Schedule II-V)", ai: "Apply at deadiversion.usdoj.gov. Fee: ~$888 for 3 years. Processing: 4-6 weeks. START IMMEDIATELY." },
      { t: "Register for NPI Number (Type 1 + Type 2)", ai: "Apply at nppes.cms.hhs.gov. Free. Type 1 = you personally. Type 2 = your practice entity. Takes 1-2 days." },
      { t: "Apply for city/county business license", ai: "Visit your local city clerk or apply online. Cost: $50-$500. Some cities require zoning approval for dental." },
      { t: "Obtain building/occupancy permit for dental use", ai: "Required if doing buildout. Your contractor should handle but YOU verify it's filed." },
      { t: "Apply for radiation safety certificate", ai: "Required for X-ray equipment. Register with your state radiation control program. Inspection required." },
      { t: "Complete OSHA compliance program", ai: "Training for all staff, written exposure control plan, SDS sheets, PPE protocols. Use OSHA Review or DDS Compliance." },
      { t: "Set up HIPAA compliance program", ai: "Written policies, staff training, BAAs with all vendors, breach notification plan. Use Compliancy Group or PCIHIPAA." },
      { t: "Apply for state controlled substance license (if required)", ai: "Some states require separate state-level controlled substance registration in addition to DEA." },
    ],
  },
  {
    id: "location", phase: 3, name: "Location & Buildout", icon: Building, duration: "Week 2-12",
    tasks: [
      { t: "Run demographic analysis for target areas (3-5 locations)", ai: "Use ADA Health Policy Institute data, Dental Intelligence, or Buxton Analytics. Look for: population density, median income, competition ratio, growth trends." },
      { t: "Evaluate 5+ potential locations (score each)", ai: "Score on: visibility, traffic count, parking, signage rights, proximity to competitors, lease terms, TI allowance." },
      { t: "Negotiate lease with tenant improvement (TI) allowance", ai: "Target: $50-$100/SF TI allowance. Negotiate: 10-year lease with 5-year renewal option, 3-6 months free rent during buildout." },
      { t: "Hire dental-specific architect", ai: "Must have dental office experience. They design operatory layout, plumbing specs, equipment placement, patient flow." },
      { t: "Design office layout (5-8 operatories, plan for expansion)", ai: "Minimum 5 ops. Plumb for 8+. Include: sterilization center, lab, private consult room, break room, server room." },
      { t: "Hire general contractor with dental buildout experience", ai: "Get 3 bids. Verify dental references. Include: plumbing, electrical, HVAC, vacuum/compressor, data infrastructure." },
      { t: "Order dental equipment (lead times: 6-12 weeks)", ai: "Major items: chairs/units, CBCT, digital scanner, panoramic, sterilizers, compressor, vacuum. Budget: $150K-$400K." },
      { t: "Order IT infrastructure (network, servers, computers)", ai: "Dental-specific IT: HIPAA-compliant network, encrypted workstations, backup system, VoIP phones, digital displays." },
      { t: "Select and implement Practice Management Software", ai: "Top options: Dentrix, Eaglesoft, Open Dental (open source), Curve (cloud). Decision factors: cloud vs. server, integrations, cost." },
      { t: "Pass final inspection and obtain Certificate of Occupancy", ai: "Schedule with building dept 2 weeks before planned opening. Have contractor present. Fix any issues immediately." },
    ],
  },
  {
    id: "insurance", phase: 4, name: "Insurance Credentialing", icon: FileText, duration: "Week 1-16",
    tasks: [
      { t: "Compile master credentialing packet", ai: "Gather: dental license, DEA, NPI, malpractice COI, diploma, residency cert, specialty cert, CV, W-9, voided check." },
      { t: "Apply to Delta Dental (largest network -- apply first)", ai: "Each state has its own Delta. Apply through their provider portal. Processing: 60-120 days." },
      { t: "Apply to MetLife Dental", ai: "Apply at metlife.com/dental-providers. Processing: 60-90 days." },
      { t: "Apply to Cigna Dental", ai: "Apply through Cigna's provider portal. Processing: 60-90 days." },
      { t: "Apply to Aetna Dental", ai: "Apply at aetna.com/providers. Processing: 60-90 days." },
      { t: "Apply to United Healthcare Dental", ai: "Apply through UHC provider portal. Processing: 45-90 days." },
      { t: "Apply to Guardian Dental", ai: "Apply at guardiananytime.com. Processing: 60-90 days." },
      { t: "Apply to BlueCross BlueShield Dental (your state)", ai: "Each state has its own BCBS. Apply through your state's provider portal." },
      { t: "Set up fee schedules for each insurance plan", ai: "Review UCR rates for your zip code. Set fees at 80th percentile UCR. Never set below insurance maximum allowable." },
      { t: "Set up in-house dental membership plan for uninsured", ai: "Create a membership plan: $25-$35/month includes 2 cleanings, exams, X-rays, 15-20% off treatment. Use Kleer or BoomCloud." },
    ],
  },
  {
    id: "brand", phase: 5, name: "Brand & Digital Presence", icon: Palette, duration: "Week 4-10",
    tasks: [
      { t: "Define practice name, tagline, and brand personality", ai: "Name should be: memorable, easy to spell, available as .com domain. Check state dental board for name restrictions." },
      { t: "Design logo and complete brand kit", ai: "Include: primary logo, icon mark, color palette (HEX/RGB/CMYK), typography, brand voice guide. Budget: $100-$10,000." },
      { t: "Register domain name and set up business email", ai: "Register .com at Namecheap or Google Domains. Set up Google Workspace for professional email." },
      { t: "Build website with online booking integration", ai: "WordPress + dental theme or custom build. Must have: online scheduling, mobile-first, HIPAA forms, live chat, SSL." },
      { t: "Set up and optimize Google Business Profile", ai: "Category: Dental Implant Provider. Add 20+ photos. Write 750-word description. Set hours, services, insurance accepted." },
      { t: "Create social media profiles (Instagram, Facebook, TikTok)", ai: "Use consistent branding across all platforms. Bio should include: specialty, location, booking link." },
      { t: "Set up online review management system", ai: "Use Birdeye, Podium, or Weave. Automate review requests via SMS after every appointment." },
      { t: "Order physical brand materials", ai: "Business cards, letterhead, appointment cards, referral cards, welcome packets, signage, window decals." },
      { t: "Create patient-facing videos (intro, office tour)", ai: "Hire videographer ($500-$2K) or use iPhone + good lighting. Post on website, YouTube, social, and Google." },
    ],
  },
  {
    id: "team", phase: 6, name: "Hiring & Team Building", icon: Users, duration: "Week 6-14",
    tasks: [
      { t: "Write job descriptions for all positions", ai: "Include: role responsibilities, qualifications, compensation range, benefits, culture description." },
      { t: "Hire Office Manager / Practice Administrator (FIRST HIRE)", ai: "This person is your #2. They run daily operations, manage team, handle HR. Look for: dental experience, leadership." },
      { t: "Hire Front Desk / Patient Coordinator", ai: "Must have: warm phone voice, dental software experience, insurance verification skills. TEST phone skills in interview." },
      { t: "Hire Treatment Coordinator", ai: "This is your REVENUE position. They present treatment plans and close cases. Look for: sales ability, empathy." },
      { t: "Hire Dental Assistants (2 minimum)", ai: "Expanded function preferred. Check state requirements for certification. Include: chairside, radiology, sterilization." },
      { t: "Hire Dental Hygienist (1 to start, scale up)", ai: "RDH license required. Look for: perio focus, patient education skills, production-oriented. Start with 3 days/week." },
      { t: "Set up payroll system (Gusto, ADP, or QuickBooks Payroll)", ai: "Gusto is easiest for small practices. Auto-calculates taxes, handles direct deposit, benefits enrollment." },
      { t: "Create employee handbook and policies", ai: "Include: at-will statement, PTO policy, dress code, social media policy, HIPAA obligations, termination procedures." },
      { t: "Set up employee benefits (health, dental, 401k, CE allowance)", ai: "Offer dental plan, health insurance stipend, PTO, CE reimbursement ($1-2K/year), scrub allowance." },
      { t: "Schedule 2-week pre-opening team training intensive", ai: "Cover: PMS software, phone scripts, patient flow, treatment presentation, emergency protocols, customer service." },
    ],
  },
  {
    id: "phones", phase: 7, name: "Phone & Communication", icon: Phone, duration: "Week 8-12",
    tasks: [
      { t: "Select dental VoIP phone provider", ai: "Recommended: Weave (dental-specific, best PMS integration), Mango Voice, RingCentral. Look for: call recording, SMS, analytics." },
      { t: "Set up auto-attendant and call routing", ai: "Route by: new patient, existing patient, emergency, billing, specialty. After-hours message with emergency callback." },
      { t: "Write and record phone scripts for all call types", ai: "Scripts needed: new patient inquiry, insurance questions, appointment confirmation, cancellation save, emergency triage." },
      { t: "Set up 2-way texting for patient communication", ai: "Patients prefer texting 3:1 over calling. Use for: confirmations, reminders, quick questions, review requests." },
      { t: "Configure call tracking for marketing attribution", ai: "Assign unique tracking numbers to each marketing channel. Use CallRail or built-in provider tracking." },
      { t: "Set up AI after-hours call handling", ai: "Tools: Slingshot AI, DentistAI, or Weave AI. Handles: appointment requests, emergency triage, FAQ, routes urgent calls." },
      { t: "Train front desk on phone conversion scripts", ai: "New patient calls should convert at 80%+. Record calls, review weekly, role-play daily." },
      { t: "Set up appointment reminder automation (text + email)", ai: "Sequence: 1 week before (email), 2 days before (text), same-day morning (text). Include confirm/reschedule buttons." },
    ],
  },
  {
    id: "protocols", phase: 8, name: "Clinical & Business Protocols", icon: ClipboardList, duration: "Week 10-14",
    tasks: [
      { t: "Create new patient intake workflow (100% digital)", ai: "Digital forms via Yosi Health, Dentrix Kiosk, or NexHealth. Include: medical history, dental history, insurance, consent." },
      { t: "Build scheduling templates with block scheduling", ai: "Block by procedure type: hygiene blocks, crown prep blocks, implant surgery blocks, emergency slots." },
      { t: "Write treatment presentation protocol", ai: "Steps: diagnose, educate with images, present options, discuss financing, close. Use intraoral photos/scans." },
      { t: "Create morning huddle template", ai: "Daily 10-min meeting: review schedule, identify high-value cases, unconfirmed appointments, lab cases due." },
      { t: "Develop sterilization and infection control SOP", ai: "Follow CDC guidelines. Document: instrument processing, surface disinfection, PPE protocols, waterline treatment." },
      { t: "Create financial policy and payment protocols", ai: "Include: payment at time of service, insurance estimation, treatment financing options, collections protocol." },
      { t: "Build emergency protocol manual", ai: "Protocols for: syncope, allergic reaction, cardiac event, seizure, aspiration, hemorrhage. Post in every operatory." },
      { t: "Create patient follow-up and recall system", ai: "Automate: post-op check (24hr), 1-week follow-up, 6-month recall, annual recall, reactivation (12+ months)." },
      { t: "Develop case acceptance tracking system", ai: "Track by: provider, procedure type, dollar amount. Review weekly. Target: 70%+ overall." },
    ],
  },
  {
    id: "marketing", phase: 9, name: "Marketing Launch", icon: Megaphone, duration: "Week 10-16",
    tasks: [
      { t: "Create Grand Slam Offer (Hormozi framework)", ai: "Make it irresistible: 'Free CBCT + Consultation + 3D Smile Preview + $500 Off Treatment'. Remove ALL risk from first visit." },
      { t: "Set up Google Ads campaign ($2-5K/month)", ai: "Target high-intent keywords: 'dental implants [city]', 'dentist near me'. Create dedicated landing pages." },
      { t: "Launch Meta/Instagram advertising ($1-3K/month)", ai: "Best performing: before/after content, video testimonials, Grand Slam Offer ads. Retarget website visitors." },
      { t: "Build patient referral program", ai: "$250-$500 per referred patient who starts treatment. Automate the ask via text 48 hours after treatment." },
      { t: "Launch direct mail campaign to local households", ai: "5,000-10,000 pieces to households within 3-5 miles. Include Grand Slam Offer. Use PostcardMania or MVP Mailhouse." },
      { t: "Create content calendar (social media + blog)", ai: "2-3 social posts/week, 2 blog posts/month. Mix: educational (60%), behind-the-scenes (20%), testimonials (10%), promo (10%)." },
      { t: "Partner with 10+ local businesses for cross-referrals", ai: "Target: gyms, spas, salons, real estate agents, wedding planners, corporate HR departments." },
      { t: "Set up marketing ROI tracking dashboard", ai: "Track: spend by channel, leads generated, cost per lead, patients acquired, cost per acquisition, ROI." },
      { t: "Plan grand opening event", ai: "Free screenings, office tours, refreshments, raffle prizes, local media invite. Target: 100+ attendees." },
    ],
  },
  {
    id: "kpis", phase: 10, name: "KPIs & Financial Systems", icon: BarChart3, duration: "Week 12-16",
    tasks: [
      { t: "Set up daily production tracking dashboard", ai: "Track: daily production per provider, procedures completed, production vs. goal. Display on break room screen." },
      { t: "Implement collections tracking (target: 98%+)", ai: "Track: gross production, adjustments, net production, collections, collections rate. Review A/R aging weekly." },
      { t: "Build new patient tracking system", ai: "Track: total new patients/month, source attribution, conversion rate from call to booked to arrived. Target: 30-50/month." },
      { t: "Set up case acceptance reporting", ai: "Track: treatment presented vs. accepted, by provider, by procedure type, by dollar amount. Target: 70%+." },
      { t: "Create overhead monitoring system", ai: "Track monthly: staff costs, facility costs, supplies, lab, marketing, admin. Target: total overhead <59% of collections." },
      { t: "Implement patient satisfaction tracking (NPS)", ai: "Send NPS survey 24 hours after appointment. Track score monthly. Target: NPS 70+. Follow up on scores below 7." },
      { t: "Set up monthly P&L review with dental CPA", ai: "Compare actual vs. budget. Track: revenue growth, overhead trends, profit margin. Adjust strategy based on performance." },
      { t: "Create weekly team scorecard meeting", ai: "Every Monday: review last week's KPIs, celebrate wins, identify problems, assign action items. 30 minutes max." },
    ],
  },
];

const TOTAL_TASKS = LAUNCH_PHASES.reduce((sum, p) => sum + p.tasks.length, 0);

interface ChatMessage {
  role: "user" | "bot";
  content: string;
}

function renderBotContent(text: string) {
  const lines = text.split("\n");
  return lines.map((line, i) => {
    if (line.trim() === "") return <br key={i} />;

    const parts: (string | JSX.Element)[] = [];
    const regex = /\*\*(.+?)\*\*/g;
    let lastIndex = 0;
    let match;
    let keyIdx = 0;
    while ((match = regex.exec(line)) !== null) {
      if (match.index > lastIndex) {
        parts.push(line.slice(lastIndex, match.index));
      }
      parts.push(
        <span key={`b-${i}-${keyIdx++}`} className="font-bold">
          {match[1]}
        </span>
      );
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < line.length) {
      parts.push(line.slice(lastIndex));
    }

    const trimmed = line.trim();
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      return (
        <div key={i} className="flex gap-1.5 ml-2">
          <span className="text-muted-foreground">-</span>
          <span>{parts}</span>
        </div>
      );
    }
    if (/^\d+\./.test(trimmed)) {
      return (
        <div key={i} className="ml-2">
          {parts}
        </div>
      );
    }

    return <div key={i}>{parts}</div>;
  });
}

export default function DentBotPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "bot", content: BOT_RESPONSES.default },
  ]);
  const [inputValue, setInputValue] = useState("");
  const [completedTasks, setCompletedTasks] = useState<Record<string, boolean>>({});
  const [openPhases, setOpenPhases] = useState<Record<string, boolean>>({});
  const chatEndRef = useRef<HTMLDivElement>(null);

  const completedCount = Object.values(completedTasks).filter(Boolean).length;
  const progressPct = TOTAL_TASKS > 0 ? Math.round((completedCount / TOTAL_TASKS) * 100) : 0;

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function handleSend() {
    const text = inputValue.trim();
    if (!text) return;
    const userMsg: ChatMessage = { role: "user", content: text };
    const botMsg: ChatMessage = { role: "bot", content: getResponse(text) };
    setMessages((prev) => [...prev, userMsg, botMsg]);
    setInputValue("");
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function toggleTask(phaseId: string, taskIdx: number) {
    const key = `${phaseId}-${taskIdx}`;
    setCompletedTasks((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function togglePhase(phaseId: string) {
    setOpenPhases((prev) => ({ ...prev, [phaseId]: !prev[phaseId] }));
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-8rem)]" data-testid="dentbot-page">
      <div className="flex flex-col w-[60%] min-w-0">
        <Card className="flex flex-col flex-1 min-h-0">
          <CardHeader className="flex flex-row items-center gap-2 flex-wrap pb-3">
            <Bot className="h-5 w-5 text-primary" />
            <CardTitle className="text-lg">DentBot AI Practice Advisor</CardTitle>
            <Badge variant="secondary" className="ml-auto">
              <MessageSquare className="h-3 w-3 mr-1" />
              {messages.length} messages
            </Badge>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col min-h-0 gap-3 pb-4">
            <ScrollArea className="flex-1 min-h-0" data-testid="chat-scroll-area">
              <div className="flex flex-col gap-3 pr-4">
                {messages.map((msg, i) => (
                  <div
                    key={i}
                    className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                    data-testid={`chat-message-${i}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                        msg.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-foreground"
                      }`}
                    >
                      {msg.role === "bot" ? (
                        <div className="space-y-0.5">{renderBotContent(msg.content)}</div>
                      ) : (
                        msg.content
                      )}
                    </div>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>
            </ScrollArea>

            <div className="flex gap-2">
              <Input
                data-testid="input-chat-message"
                placeholder="Ask about permits, hiring, KPIs, marketing..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyDown}
              />
              <Button
                data-testid="button-send-message"
                onClick={handleSend}
                disabled={!inputValue.trim()}
              >
                <Send className="h-4 w-4 mr-1.5" />
                Send
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-col w-[40%] min-w-0">
        <Card className="flex flex-col flex-1 min-h-0">
          <CardHeader className="flex flex-row items-center gap-2 flex-wrap pb-3">
            <ClipboardList className="h-5 w-5 text-primary" />
            <CardTitle className="text-lg">Practice Launch Checklist</CardTitle>
            <Badge variant="secondary" className="ml-auto">
              {completedCount}/{TOTAL_TASKS}
            </Badge>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col min-h-0 gap-3 pb-4">
            <div className="flex items-center gap-3">
              <Progress value={progressPct} className="flex-1" data-testid="progress-checklist" />
              <span className="text-sm font-bold text-muted-foreground whitespace-nowrap">
                {progressPct}%
              </span>
            </div>

            <ScrollArea className="flex-1 min-h-0" data-testid="checklist-scroll-area">
              <div className="flex flex-col gap-2 pr-4">
                {LAUNCH_PHASES.map((phase) => {
                  const PhaseIcon = phase.icon;
                  const isOpen = openPhases[phase.id] ?? false;
                  const phaseCompleted = phase.tasks.filter(
                    (_, ti) => completedTasks[`${phase.id}-${ti}`]
                  ).length;

                  return (
                    <Collapsible
                      key={phase.id}
                      open={isOpen}
                      onOpenChange={() => togglePhase(phase.id)}
                    >
                      <CollapsibleTrigger asChild>
                        <Button
                          variant="ghost"
                          className="w-full justify-start gap-2 text-left"
                          data-testid={`button-phase-${phase.id}`}
                        >
                          {isOpen ? (
                            <ChevronDown className="h-4 w-4 flex-shrink-0" />
                          ) : (
                            <ChevronRight className="h-4 w-4 flex-shrink-0" />
                          )}
                          <PhaseIcon className="h-4 w-4 flex-shrink-0" />
                          <span className="flex-1 truncate text-sm font-medium">
                            {phase.phase}. {phase.name}
                          </span>
                          <Badge variant="outline" className="ml-auto flex-shrink-0">
                            {phaseCompleted}/{phase.tasks.length}
                          </Badge>
                          <span className="text-xs text-muted-foreground flex-shrink-0">
                            {phase.duration}
                          </span>
                        </Button>
                      </CollapsibleTrigger>
                      <CollapsibleContent>
                        <div className="flex flex-col gap-1 pl-10 pr-2 pb-2">
                          {phase.tasks.map((task, ti) => {
                            const taskKey = `${phase.id}-${ti}`;
                            const checked = completedTasks[taskKey] ?? false;
                            return (
                              <div
                                key={ti}
                                className="flex items-start gap-2 py-1"
                                data-testid={`task-${phase.id}-${ti}`}
                              >
                                <Checkbox
                                  data-testid={`checkbox-${phase.id}-${ti}`}
                                  checked={checked}
                                  onCheckedChange={() => toggleTask(phase.id, ti)}
                                  className="mt-0.5"
                                />
                                <span
                                  className={`text-sm flex-1 ${
                                    checked
                                      ? "line-through text-muted-foreground"
                                      : "text-foreground"
                                  }`}
                                >
                                  {task.t}
                                </span>
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="flex-shrink-0"
                                      data-testid={`tooltip-${phase.id}-${ti}`}
                                    >
                                      <Info className="h-3.5 w-3.5 text-muted-foreground" />
                                    </Button>
                                  </TooltipTrigger>
                                  <TooltipContent side="left" className="max-w-xs">
                                    <p className="text-sm">{task.ai}</p>
                                  </TooltipContent>
                                </Tooltip>
                              </div>
                            );
                          })}
                        </div>
                      </CollapsibleContent>
                    </Collapsible>
                  );
                })}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
