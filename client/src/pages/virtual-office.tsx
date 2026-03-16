import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import {
  Building2, Users, Clock, DollarSign, Heart, GraduationCap, Megaphone,
  Video, CheckCircle, AlertCircle, Circle, Briefcase, Calendar, FileText,
  Phone, Stethoscope, FlaskConical, Coffee, MonitorSmartphone, Wifi,
  Shield, Star, TrendingUp, Bell, Send, PlusCircle, ChevronRight,
  UserPlus, Award, BarChart2, Mail, MessageSquare, Printer, Camera,
  ClipboardList, Lock, Layers, Activity, Home, MapPin, Zap, Globe,
} from "lucide-react";

// ─── Shared types ─────────────────────────────────────────────────────────────
type RoomStatus = "available" | "occupied" | "cleaning" | "offline";
type StaffStatus = "in-office" | "remote" | "out" | "with-patient";
type AppStatus = "new" | "screening" | "interview" | "offer" | "hired" | "rejected";

// ─── Floor Plan Data ──────────────────────────────────────────────────────────
interface Room {
  id: string; name: string; type: string;
  status: RoomStatus; occupant?: string; nextAppt?: string;
  icon: any;
}

const ROOMS: Room[] = [
  { id: "op1",  name: "Operatory 1",        type: "clinical",      status: "occupied",   occupant: "Dr. Blake + Patient",      nextAppt: "10:30 AM", icon: Stethoscope },
  { id: "op2",  name: "Operatory 2",        type: "clinical",      status: "occupied",   occupant: "Dr. Moreau + Patient",     nextAppt: "11:00 AM", icon: Stethoscope },
  { id: "op3",  name: "Operatory 3",        type: "clinical",      status: "cleaning",   nextAppt: "10:45 AM",                 icon: Stethoscope },
  { id: "op4",  name: "Operatory 4",        type: "clinical",      status: "available",  icon: Stethoscope },
  { id: "op5",  name: "Operatory 5",        type: "clinical",      status: "occupied",   occupant: "Dr. Kim + Patient",        nextAppt: "11:30 AM", icon: Stethoscope },
  { id: "op6",  name: "Operatory 6",        type: "clinical",      status: "available",  icon: Stethoscope },
  { id: "cons1","name": "Consultation A",   type: "consultation",  status: "occupied",   occupant: "Monica + New Patient",     icon: Users },
  { id: "cons2","name": "Consultation B",   type: "consultation",  status: "available",  icon: Users },
  { id: "xray", name: "X-Ray Suite",        type: "imaging",       status: "occupied",   occupant: "Sarah (Hygienist)",        icon: Activity },
  { id: "pano", name: "Panoramic / CBCT",   type: "imaging",       status: "available",  icon: Activity },
  { id: "ster", name: "Sterilization",      type: "support",       status: "occupied",   occupant: "Destiny (Lead DA)",        icon: FlaskConical },
  { id: "lab",  name: "In-House Lab",       type: "support",       status: "available",  icon: FlaskConical },
  { id: "front","name": "Front Desk",       type: "admin",         status: "occupied",   occupant: "Brenda + Kevin",           icon: Phone },
  { id: "mgr",  name: "Manager Office",     type: "admin",         status: "occupied",   occupant: "Rachel (Practice Mgr)",    icon: Briefcase },
  { id: "bill", name: "Billing Suite",      type: "admin",         status: "occupied",   occupant: "Carla + Keisha",           icon: DollarSign },
  { id: "tele", name: "Telehealth Room",    type: "telehealth",    status: "available",  icon: Video },
  { id: "conf", name: "Conference Room",    type: "meeting",       status: "available",  nextAppt: "12:00 PM Huddle",          icon: Users },
  { id: "break","name": "Break Room",       type: "support",       status: "occupied",   occupant: "2 staff",                  icon: Coffee },
  { id: "it",   name: "IT / Server Room",   type: "support",       status: "available",  icon: MonitorSmartphone },
  { id: "stor", name: "Supply Storage",     type: "support",       status: "available",  icon: Layers },
];

const ROOM_STATUS: Record<RoomStatus, { label: string; dot: string; border: string }> = {
  available: { label: "Available", dot: "bg-emerald-500",  border: "border-emerald-400/40 bg-emerald-500/5" },
  occupied:  { label: "In Use",    dot: "bg-blue-500",     border: "border-blue-400/40 bg-blue-500/5" },
  cleaning:  { label: "Cleaning",  dot: "bg-amber-500",    border: "border-amber-400/40 bg-amber-500/5" },
  offline:   { label: "Offline",   dot: "bg-gray-400",     border: "border-gray-300 bg-gray-100/50" },
};

// ─── HR Staff Data ────────────────────────────────────────────────────────────
interface Employee {
  id: string; name: string; title: string; dept: string;
  status: StaffStatus; email: string; phone: string;
  startDate: string; salary: string; pto: number; ptoUsed: number;
  benefits: string[]; certifications: string[];
}

const EMPLOYEES: Employee[] = [
  { id:"ceo",  name:"Dr. Marcus Rivera",  title:"CEO / Owner",             dept:"Executive",        status:"in-office",   email:"marcus@fullarch.com",   phone:"(310) 555-0101", startDate:"2016-01-15", salary:"$320,000", pto:25, ptoUsed:8, benefits:["Medical","Dental","Vision","401k","Life"], certifications:["DDS","ABOI/ID","AAOMS"] },
  { id:"coo",  name:"Angela Torres",      title:"COO",                     dept:"Executive",        status:"remote",      email:"angela@fullarch.com",    phone:"(310) 555-0102", startDate:"2019-03-01", salary:"$195,000", pto:20, ptoUsed:6, benefits:["Medical","Dental","Vision","401k"], certifications:["MBA","MGMA"] },
  { id:"cfo",  name:"James Whitmore",     title:"CFO",                     dept:"Executive",        status:"in-office",   email:"james@fullarch.com",     phone:"(310) 555-0103", startDate:"2020-06-01", salary:"$185,000", pto:20, ptoUsed:5, benefits:["Medical","Dental","Vision","401k"], certifications:["CPA","MBA"] },
  { id:"cdo",  name:"Dr. Sofia Chen",     title:"Chief Dental Officer",    dept:"Executive",        status:"with-patient",email:"sofia@fullarch.com",     phone:"(310) 555-0104", startDate:"2018-08-15", salary:"$295,000", pto:20, ptoUsed:10,benefits:["Medical","Dental","Vision","401k","Life"], certifications:["DMD","FAGD","ABOMS"] },
  { id:"pm",   name:"Rachel Nguyen",      title:"Practice Manager",        dept:"Management",       status:"in-office",   email:"rachel@fullarch.com",    phone:"(310) 555-0105", startDate:"2021-02-01", salary:"$88,000",  pto:15, ptoUsed:3, benefits:["Medical","Dental","Vision","401k"], certifications:["FAADOM"] },
  { id:"hr",   name:"Lisa Park",          title:"HR & Payroll Manager",    dept:"Management",       status:"remote",      email:"lisa@fullarch.com",       phone:"(310) 555-0106", startDate:"2022-04-01", salary:"$72,000",  pto:15, ptoUsed:4, benefits:["Medical","Dental","Vision","401k"], certifications:["PHR","SHRM-CP"] },
  { id:"comp", name:"David Okafor",       title:"HIPAA Compliance Officer",dept:"Management",       status:"in-office",   email:"david@fullarch.com",     phone:"(310) 555-0107", startDate:"2020-09-01", salary:"$78,000",  pto:15, ptoUsed:2, benefits:["Medical","Dental","Vision","401k"], certifications:["CHC","CHPC","CHCO"] },
  { id:"bdir", name:"Carla Mendez",       title:"Billing Director",        dept:"Revenue Cycle",    status:"in-office",   email:"carla@fullarch.com",     phone:"(310) 555-0108", startDate:"2019-07-01", salary:"$95,000",  pto:18, ptoUsed:7, benefits:["Medical","Dental","Vision","401k"], certifications:["CPB","CPCO"] },
  { id:"ins",  name:"Miguel Santos",      title:"Insurance Coordinator",   dept:"Revenue Cycle",    status:"in-office",   email:"miguel@fullarch.com",    phone:"(310) 555-0109", startDate:"2022-01-10", salary:"$54,000",  pto:12, ptoUsed:3, benefits:["Medical","Dental","Vision"], certifications:["CDIA+"] },
  { id:"app",  name:"Tanya Brooks",       title:"Appeals Specialist",      dept:"Revenue Cycle",    status:"in-office",   email:"tanya@fullarch.com",     phone:"(310) 555-0110", startDate:"2021-05-01", salary:"$62,000",  pto:12, ptoUsed:2, benefits:["Medical","Dental","Vision","401k"], certifications:["CPCO","CPC"] },
  { id:"pp",   name:"Priya Patel",        title:"Marketing Director",      dept:"Marketing",        status:"remote",      email:"priya@fullarch.com",     phone:"(310) 555-0111", startDate:"2022-08-01", salary:"$82,000",  pto:15, ptoUsed:5, benefits:["Medical","Dental","Vision","401k"], certifications:["Google Ads","Meta Blueprint"] },
  { id:"surg", name:"Dr. Nathan Blake",   title:"Lead Oral Surgeon",       dept:"Clinical",         status:"with-patient",email:"nathan@fullarch.com",    phone:"(310) 555-0112", startDate:"2017-03-15", salary:"$285,000", pto:20, ptoUsed:12,benefits:["Medical","Dental","Vision","401k","Life","Disability"], certifications:["DDS","OMS Board","ABOMS"] },
  { id:"dent1",name:"Dr. Aisha Moreau",  title:"Associate Dentist",       dept:"Clinical",         status:"with-patient",email:"aisha@fullarch.com",     phone:"(310) 555-0113", startDate:"2021-01-01", salary:"$198,000", pto:15, ptoUsed:6, benefits:["Medical","Dental","Vision","401k"], certifications:["DMD","AGD Fellowship"] },
  { id:"dent2",name:"Dr. Ryan Kim",      title:"Associate Dentist",       dept:"Clinical",         status:"with-patient",email:"ryan@fullarch.com",      phone:"(310) 555-0114", startDate:"2023-06-01", salary:"$165,000", pto:12, ptoUsed:1, benefits:["Medical","Dental","Vision"], certifications:["DDS"] },
  { id:"hyg1", name:"Sarah Bloom",       title:"Dental Hygienist",        dept:"Clinical",         status:"with-patient",email:"sarah@fullarch.com",     phone:"(310) 555-0115", startDate:"2020-03-01", salary:"$88,000",  pto:12, ptoUsed:4, benefits:["Medical","Dental","Vision","401k"], certifications:["RDH","BSDH"] },
  { id:"hyg2", name:"Omar Farris",       title:"Dental Hygienist",        dept:"Clinical",         status:"in-office",   email:"omar@fullarch.com",      phone:"(310) 555-0116", startDate:"2022-09-01", salary:"$82,000",  pto:12, ptoUsed:3, benefits:["Medical","Dental","Vision"], certifications:["RDH"] },
  { id:"da1",  name:"Destiny Johnson",   title:"Lead Dental Assistant",   dept:"Clinical",         status:"in-office",   email:"destiny@fullarch.com",   phone:"(310) 555-0117", startDate:"2019-01-15", salary:"$58,000",  pto:12, ptoUsed:2, benefits:["Medical","Dental","Vision","401k"], certifications:["CDA","RDA","EDDA"] },
  { id:"da2",  name:"Carlos Vega",       title:"Dental Assistant",        dept:"Clinical",         status:"in-office",   email:"carlos@fullarch.com",    phone:"(310) 555-0118", startDate:"2022-03-01", salary:"$46,000",  pto:10, ptoUsed:1, benefits:["Medical","Dental"], certifications:["CDA"] },
  { id:"da3",  name:"Nina Reeves",       title:"Dental Assistant",        dept:"Clinical",         status:"out",         email:"nina@fullarch.com",       phone:"(310) 555-0119", startDate:"2023-08-01", salary:"$42,000",  pto:10, ptoUsed:3, benefits:["Medical"], certifications:["DANB in progress"] },
  { id:"txc1", name:"Monica Hill",       title:"Treatment Coordinator",   dept:"Patient Services", status:"in-office",   email:"monica@fullarch.com",    phone:"(310) 555-0120", startDate:"2018-04-01", salary:"$68,000",  pto:15, ptoUsed:5, benefits:["Medical","Dental","Vision","401k"], certifications:["ABO-Cert"] },
  { id:"txc2", name:"Andre Lewis",       title:"Treatment Coordinator",   dept:"Patient Services", status:"in-office",   email:"andre@fullarch.com",     phone:"(310) 555-0121", startDate:"2023-02-01", salary:"$54,000",  pto:10, ptoUsed:2, benefits:["Medical","Dental"], certifications:["CTC"] },
  { id:"rec1", name:"Brenda Torres",     title:"Lead Receptionist",       dept:"Patient Services", status:"in-office",   email:"brenda@fullarch.com",    phone:"(310) 555-0122", startDate:"2021-07-01", salary:"$48,000",  pto:10, ptoUsed:3, benefits:["Medical","Dental","Vision"], certifications:[""] },
  { id:"sch",  name:"Kevin Park",        title:"Scheduler",               dept:"Patient Services", status:"in-office",   email:"kevin@fullarch.com",     phone:"(310) 555-0123", startDate:"2022-11-01", salary:"$44,000",  pto:10, ptoUsed:1, benefits:["Medical","Dental"], certifications:[""] },
];

// ─── Recruitment Data ─────────────────────────────────────────────────────────
interface JobPosting { id: string; title: string; dept: string; type: string; posted: string; apps: number; status: "active"|"paused"|"filled"; }
interface Applicant { id: string; name: string; role: string; stage: AppStatus; score: number; appliedDate: string; }

const JOB_POSTINGS: JobPosting[] = [
  { id:"j1", title:"Oral Surgeon (FT)",         dept:"Clinical",         type:"Full-time",  posted:"Mar 1",  apps:14, status:"active" },
  { id:"j2", title:"Dental Hygienist (PT)",      dept:"Clinical",         type:"Part-time",  posted:"Mar 5",  apps:9,  status:"active" },
  { id:"j3", title:"Insurance Coordinator",      dept:"Revenue Cycle",    type:"Full-time",  posted:"Mar 8",  apps:22, status:"active" },
  { id:"j4", title:"Patient Care Coordinator",   dept:"Patient Services", type:"Full-time",  posted:"Mar 10", apps:17, status:"active" },
  { id:"j5", title:"Marketing Specialist",       dept:"Marketing",        type:"Full-time",  posted:"Feb 20", apps:31, status:"paused" },
  { id:"j6", title:"Dental Assistant (Lead)",    dept:"Clinical",         type:"Full-time",  posted:"Feb 15", apps:8,  status:"filled" },
];

const APPLICANTS: Applicant[] = [
  { id:"a1", name:"Jennifer Walsh",   role:"Oral Surgeon",             stage:"interview",  score:92, appliedDate:"Mar 3"  },
  { id:"a2", name:"Dr. Luis Gomez",   role:"Oral Surgeon",             stage:"offer",      score:96, appliedDate:"Mar 2"  },
  { id:"a3", name:"Sam Archer",       role:"Dental Hygienist",         stage:"screening",  score:81, appliedDate:"Mar 8"  },
  { id:"a4", name:"Tina Cho",         role:"Insurance Coordinator",    stage:"new",        score:74, appliedDate:"Mar 14" },
  { id:"a5", name:"Marcus Webb",      role:"Insurance Coordinator",    stage:"interview",  score:88, appliedDate:"Mar 9"  },
  { id:"a6", name:"Aaliyah Grant",    role:"Patient Care Coordinator", stage:"hired",      score:90, appliedDate:"Mar 5"  },
  { id:"a7", name:"Felix Obi",        role:"Marketing Specialist",     stage:"rejected",   score:62, appliedDate:"Feb 22" },
];

const APP_STAGE: Record<AppStatus, { label: string; color: string }> = {
  new:       { label: "New",       color: "bg-gray-100 text-gray-600 border-gray-300" },
  screening: { label: "Screening", color: "bg-blue-100 text-blue-700 border-blue-300" },
  interview: { label: "Interview", color: "bg-purple-100 text-purple-700 border-purple-300" },
  offer:     { label: "Offer Sent",color: "bg-amber-100 text-amber-700 border-amber-300" },
  hired:     { label: "Hired",     color: "bg-emerald-100 text-emerald-700 border-emerald-300" },
  rejected:  { label: "Rejected",  color: "bg-red-100 text-red-700 border-red-300" },
};

// ─── Attendance / Timesheet ───────────────────────────────────────────────────
const TIMESHEETS = [
  { name:"Dr. Nathan Blake",  mon:"8:00-5:00",  tue:"8:00-5:00",  wed:"Off",        thu:"8:00-4:00",  fri:"8:00-2:00",  hrs:38 },
  { name:"Dr. Aisha Moreau",  mon:"9:00-6:00",  tue:"9:00-6:00",  wed:"9:00-6:00",  thu:"9:00-6:00",  fri:"9:00-1:00",  hrs:40 },
  { name:"Sarah Bloom",       mon:"7:30-4:30",  tue:"7:30-4:30",  wed:"Off",        thu:"7:30-4:30",  fri:"7:30-4:30",  hrs:36 },
  { name:"Monica Hill",       mon:"8:30-5:30",  tue:"8:30-5:30",  wed:"8:30-5:30",  thu:"8:30-5:30",  fri:"8:30-3:30",  hrs:40 },
  { name:"Brenda Torres",     mon:"8:00-5:00",  tue:"8:00-5:00",  wed:"8:00-5:00",  thu:"8:00-5:00",  fri:"8:00-5:00",  hrs:45 },
  { name:"Destiny Johnson",   mon:"7:45-4:45",  tue:"7:45-4:45",  wed:"7:45-4:45",  thu:"7:45-4:45",  fri:"7:45-1:00",  hrs:38.5 },
  { name:"Carlos Vega",       mon:"8:00-5:00",  tue:"8:00-5:00",  wed:"Off",        thu:"8:00-5:00",  fri:"8:00-5:00",  hrs:36 },
  { name:"Nina Reeves",       mon:"Off (PTO)",  tue:"8:00-5:00",  wed:"8:00-5:00",  thu:"8:00-5:00",  fri:"8:00-4:00",  hrs:32 },
];

const PTO_REQUESTS = [
  { name:"Dr. Ryan Kim",    dates:"Mar 21–23",  type:"Vacation",    days:3, status:"approved" },
  { name:"Omar Farris",     dates:"Apr 4",       type:"Personal",    days:1, status:"pending" },
  { name:"Andre Lewis",     dates:"Apr 7–11",    type:"Vacation",    days:5, status:"pending" },
  { name:"Nina Reeves",     dates:"Mar 17",      type:"Sick Day",    days:1, status:"approved" },
  { name:"Kevin Park",      dates:"May 26–30",   type:"Vacation",    days:5, status:"pending" },
];

// ─── Payroll ──────────────────────────────────────────────────────────────────
const PAYROLL_PERIODS = [
  { period:"Mar 1–15, 2026",  processed:"Mar 16",  total:"$184,320",  status:"processing" },
  { period:"Feb 16–28, 2026", processed:"Mar 2",   total:"$182,910",  status:"paid" },
  { period:"Feb 1–15, 2026",  processed:"Feb 16",  total:"$181,440",  status:"paid" },
  { period:"Jan 16–31, 2026", processed:"Feb 2",   total:"$179,880",  status:"paid" },
];

// ─── Benefits ─────────────────────────────────────────────────────────────────
const BENEFITS_PLANS = [
  { name:"Medical – Blue Shield PPO",  enrolled:21, eligible:23, cost:"$38,400/yr",  carrier:"Blue Shield",   renewal:"Jan 2027" },
  { name:"Dental – Delta Dental",      enrolled:21, eligible:23, cost:"$8,640/yr",   carrier:"Delta Dental",  renewal:"Jan 2027" },
  { name:"Vision – VSP",               enrolled:18, eligible:23, cost:"$2,160/yr",   carrier:"VSP",           renewal:"Jan 2027" },
  { name:"401(k) – Fidelity",          enrolled:16, eligible:23, cost:"Match 4%",    carrier:"Fidelity",      renewal:"Ongoing" },
  { name:"Life Insurance",             enrolled:10, eligible:23, cost:"$3,600/yr",   carrier:"Principal",     renewal:"Jan 2027" },
  { name:"Long-Term Disability",       enrolled:8,  eligible:23, cost:"$5,400/yr",   carrier:"Principal",     renewal:"Jan 2027" },
  { name:"FSA / HSA",                  enrolled:12, eligible:23, cost:"Employee-funded", carrier:"Paychex",   renewal:"Jan 2027" },
  { name:"EAP (Employee Assist.)",     enrolled:23, eligible:23, cost:"Employer-paid",   carrier:"Cigna EAP", renewal:"Jan 2027" },
];

// ─── Training & CE ────────────────────────────────────────────────────────────
const CE_COURSES = [
  { title:"HIPAA Annual Refresh",            category:"Compliance",  due:"Mar 31",   completed:21, total:23, required:true },
  { title:"OSHA Bloodborne Pathogens",       category:"Safety",      due:"Apr 15",   completed:20, total:23, required:true },
  { title:"Full Arch Implant Protocol v3",   category:"Clinical",    due:"Apr 30",   completed:8,  total:12, required:true },
  { title:"Medical Billing & Coding 2026",   category:"Billing",     due:"May 1",    completed:5,  total:6,  required:true },
  { title:"CPR / BLS Recertification",       category:"Safety",      due:"Jun 1",    completed:15, total:23, required:true },
  { title:"Digital Impressions (iTero)",     category:"Clinical",    due:"Jun 30",   completed:4,  total:7,  required:false },
  { title:"Conscious Sedation Update",       category:"Clinical",    due:"Jul 1",    completed:3,  total:5,  required:false },
  { title:"AI Tools for Dental Practices",   category:"Technology",  due:"Aug 15",   completed:9,  total:23, required:false },
  { title:"Infection Control 2026",          category:"Compliance",  due:"Sep 30",   completed:22, total:23, required:true },
  { title:"Radiography Safety & Updates",    category:"Clinical",    due:"Oct 1",    completed:7,  total:9,  required:false },
];

// ─── Announcements / Huddle ───────────────────────────────────────────────────
const ANNOUNCEMENTS = [
  { id:"a1", type:"info",    title:"New Patient Portal Launch",           body:"Patient portal is live as of today. Please guide new patients to register at check-in.",      author:"Angela Torres", time:"9:02 AM", pinned:true },
  { id:"a2", type:"success", title:"March Revenue Milestone Hit!",        body:"We crossed $800K in monthly revenue for the first time. Incredible team effort!",            author:"Dr. Marcus Rivera", time:"8:45 AM", pinned:true },
  { id:"a3", type:"warning", title:"Supply Order – Low Bone Graft Stock", body:"We have 3 units left of Bio-Oss. Miguel please expedite reorder. Need by Friday.",          author:"Destiny Johnson", time:"8:30 AM", pinned:false },
  { id:"a4", type:"info",    title:"New HIPAA Training Due Mar 31",       body:"All staff must complete the annual HIPAA refresh before end of month. Link in training hub.", author:"David Okafor",    time:"Yesterday", pinned:false },
  { id:"a5", type:"info",    title:"Q2 Review Dates Set",                 body:"Performance reviews will be held April 14–18. Managers please submit peer evaluations by April 7.", author:"Lisa Park", time:"Yesterday", pinned:false },
];

const HUDDLE_ITEMS = [
  { category:"Schedule",   item:"3 full-arch consults scheduled (10 AM, 1 PM, 3 PM)", done:false },
  { category:"Clinical",   item:"Op 3 deep clean completed – available at 10:45", done:true },
  { category:"Billing",    item:"12 claims submitted this morning – 2 pending auth", done:true },
  { category:"Follow-ups", item:"Call Mr. Johnson re: implant post-op pain complaint", done:false },
  { category:"Admin",      item:"Order missing patient consent forms (digital)", done:false },
  { category:"Marketing",  item:"Reply to 4 Google reviews from last week", done:true },
];

// ─── Telehealth Rooms ─────────────────────────────────────────────────────────
const TELE_ROOMS = [
  { id:"t1", name:"Virtual Consult A", status:"available",  provider:"—",               next:"2:30 PM – New Patient", tech:"Zoom (HIPAA)" },
  { id:"t2", name:"Virtual Consult B", status:"in-session", provider:"Dr. Blake",        patient:"James R.",           duration:"12 min", tech:"Zoom (HIPAA)" },
  { id:"t3", name:"Post-Op Follow-Up", status:"scheduled",  provider:"Dr. Moreau",       next:"11:45 AM",              tech:"Doxy.me" },
  { id:"t4", name:"Insurance Pre-Auth", status:"available", provider:"—",               next:"No upcoming sessions",  tech:"Secure Meet" },
];

// ─── Staff Status helpers ─────────────────────────────────────────────────────
const STAFF_STATUS_CFG: Record<StaffStatus, { label: string; dot: string; text: string }> = {
  "in-office":    { label:"In Office",    dot:"bg-emerald-500", text:"text-emerald-600" },
  "remote":       { label:"Remote",       dot:"bg-blue-400",    text:"text-blue-600"    },
  "out":          { label:"Out Today",    dot:"bg-gray-400",    text:"text-muted-foreground" },
  "with-patient": { label:"With Patient", dot:"bg-purple-500",  text:"text-purple-600"  },
};

// ─── Sub-components ───────────────────────────────────────────────────────────
function RoomCard({ room }: { room: Room }) {
  const cfg = ROOM_STATUS[room.status];
  const Icon = room.icon;
  return (
    <div className={`rounded-lg border p-3 ${cfg.border} transition-all`} data-testid={`room-${room.id}`}>
      <div className="flex items-start gap-2">
        <Icon className="h-4 w-4 mt-0.5 text-muted-foreground shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="font-medium text-xs">{room.name}</span>
            <span className={`w-2 h-2 rounded-full shrink-0 ${cfg.dot}`} />
          </div>
          {room.occupant && <div className="text-[10px] text-muted-foreground truncate">{room.occupant}</div>}
          {room.nextAppt && <div className="text-[10px] text-primary">Next: {room.nextAppt}</div>}
          <div className="text-[9px] text-muted-foreground mt-0.5 uppercase tracking-wider">{cfg.label}</div>
        </div>
      </div>
    </div>
  );
}

function EmployeeRow({ emp }: { emp: Employee }) {
  const [open, setOpen] = useState(false);
  const sc = STAFF_STATUS_CFG[emp.status];
  const ptoRemaining = emp.pto - emp.ptoUsed;
  return (
    <div className="border rounded-lg overflow-hidden" data-testid={`employee-${emp.id}`}>
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-3 p-3 hover:bg-muted/40 text-left">
        <div className="w-9 h-9 rounded-full bg-primary/10 text-primary flex items-center justify-center font-semibold text-xs shrink-0">
          {emp.name.split(" ").map(n => n[0]).join("").slice(0,2)}
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm">{emp.name}</div>
          <div className="text-xs text-muted-foreground">{emp.title} · {emp.dept}</div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex items-center gap-1">
            <span className={`w-2 h-2 rounded-full ${sc.dot}`} />
            <span className={`text-[10px] ${sc.text}`}>{sc.label}</span>
          </div>
          <ChevronRight className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${open ? "rotate-90" : ""}`} />
        </div>
      </button>
      {open && (
        <div className="border-t bg-muted/20 p-4 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          <div><div className="text-muted-foreground mb-0.5">Email</div><div>{emp.email}</div></div>
          <div><div className="text-muted-foreground mb-0.5">Phone</div><div>{emp.phone}</div></div>
          <div><div className="text-muted-foreground mb-0.5">Start Date</div><div>{emp.startDate}</div></div>
          <div><div className="text-muted-foreground mb-0.5">Salary</div><div className="font-semibold">{emp.salary}</div></div>
          <div>
            <div className="text-muted-foreground mb-1">PTO ({ptoRemaining} days left)</div>
            <Progress value={(emp.ptoUsed / emp.pto) * 100} className="h-1.5" />
            <div className="text-[10px] text-muted-foreground mt-0.5">{emp.ptoUsed} used of {emp.pto}</div>
          </div>
          <div>
            <div className="text-muted-foreground mb-1">Benefits</div>
            <div className="flex flex-wrap gap-1">
              {emp.benefits.map(b => <Badge key={b} className="text-[9px] px-1">{b}</Badge>)}
            </div>
          </div>
          <div className="col-span-2">
            <div className="text-muted-foreground mb-1">Certifications</div>
            <div className="flex flex-wrap gap-1">
              {emp.certifications.filter(Boolean).map(c => <Badge key={c} variant="outline" className="text-[9px] px-1">{c}</Badge>)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function VirtualOfficePage() {
  const [search, setSearch] = useState("");
  const [deptFilter, setDeptFilter] = useState("All");
  const [huddle, setHuddle] = useState(HUDDLE_ITEMS);

  const inOffice  = EMPLOYEES.filter(e => e.status === "in-office" || e.status === "with-patient").length;
  const remote    = EMPLOYEES.filter(e => e.status === "remote").length;
  const out       = EMPLOYEES.filter(e => e.status === "out").length;
  const occupied  = ROOMS.filter(r => r.status === "occupied").length;
  const available = ROOMS.filter(r => r.status === "available").length;
  const depts     = ["All", ...Array.from(new Set(EMPLOYEES.map(e => e.dept)))];
  const filteredEmp = EMPLOYEES.filter(e =>
    (deptFilter === "All" || e.dept === deptFilter) &&
    (!search || e.name.toLowerCase().includes(search.toLowerCase()) || e.title.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Virtual Dental Office</h1>
          <p className="text-sm text-muted-foreground">Full practice infrastructure — floor, HR, operations, and more</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1.5 text-xs text-emerald-600"><span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /> Live</span>
        </div>
      </div>

      {/* Quick status bar */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        {[
          { label:"In Office / Active", value:inOffice,  icon:Users,     color:"text-emerald-600" },
          { label:"Remote Today",       value:remote,    icon:Globe,     color:"text-blue-600"    },
          { label:"Out Today",          value:out,       icon:Home,      color:"text-muted-foreground" },
          { label:"Rooms Occupied",     value:occupied,  icon:MapPin,    color:"text-purple-600"  },
          { label:"Rooms Available",    value:available, icon:CheckCircle,color:"text-emerald-600" },
        ].map(k => (
          <Card key={k.label}>
            <CardContent className="pt-3 pb-3">
              <k.icon className={`h-4 w-4 ${k.color} mb-1`} />
              <div className={`text-2xl font-bold font-mono ${k.color}`} data-testid={`stat-${k.label.toLowerCase().replace(/\s/g,"-")}`}>{k.value}</div>
              <div className="text-[10px] text-muted-foreground">{k.label}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="floor">
        <TabsList className="flex-wrap h-auto gap-1">
          {[
            ["floor",      "Office Floor",        Building2],
            ["hr",         "HR Directory",        Users],
            ["recruit",    "Recruitment",         UserPlus],
            ["attendance", "Time & Attendance",   Clock],
            ["payroll",    "Payroll",             DollarSign],
            ["benefits",   "Benefits",            Heart],
            ["training",   "Training & CE",       GraduationCap],
            ["ops",        "Daily Operations",    Megaphone],
            ["telehealth", "Telehealth Rooms",    Video],
            ["it",         "IT & Infrastructure", MonitorSmartphone],
          ].map(([val, label, Icon]: any) => (
            <TabsTrigger key={val} value={val} className="text-xs" data-testid={`tab-${val}`}>
              <Icon className="h-3.5 w-3.5 mr-1" />{label}
            </TabsTrigger>
          ))}
        </TabsList>

        {/* ── OFFICE FLOOR ── */}
        <TabsContent value="floor" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {/* Floor map */}
            <div className="space-y-3">
              <h3 className="font-semibold text-sm flex items-center gap-2"><Stethoscope className="h-4 w-4 text-primary" /> Clinical Operatories</h3>
              <div className="grid grid-cols-2 gap-2">
                {ROOMS.filter(r => r.type === "clinical").map(r => <RoomCard key={r.id} room={r} />)}
              </div>
            </div>
            <div className="space-y-4">
              <div>
                <h3 className="font-semibold text-sm flex items-center gap-2 mb-2"><Activity className="h-4 w-4 text-primary" /> Imaging</h3>
                <div className="grid grid-cols-2 gap-2">
                  {ROOMS.filter(r => r.type === "imaging").map(r => <RoomCard key={r.id} room={r} />)}
                </div>
              </div>
              <div>
                <h3 className="font-semibold text-sm flex items-center gap-2 mb-2"><Video className="h-4 w-4 text-primary" /> Consultation & Telehealth</h3>
                <div className="grid grid-cols-2 gap-2">
                  {ROOMS.filter(r => r.type === "consultation" || r.type === "telehealth").map(r => <RoomCard key={r.id} room={r} />)}
                </div>
              </div>
              <div>
                <h3 className="font-semibold text-sm flex items-center gap-2 mb-2"><Briefcase className="h-4 w-4 text-primary" /> Admin & Support</h3>
                <div className="grid grid-cols-2 gap-2">
                  {ROOMS.filter(r => r.type === "admin" || r.type === "meeting" || r.type === "support").map(r => <RoomCard key={r.id} room={r} />)}
                </div>
              </div>
            </div>
          </div>
          {/* Legend */}
          <div className="flex gap-4 flex-wrap text-xs text-muted-foreground pt-2 border-t">
            {Object.entries(ROOM_STATUS).map(([k, v]) => (
              <span key={k} className="flex items-center gap-1.5"><span className={`w-2.5 h-2.5 rounded-full ${v.dot}`} />{v.label}</span>
            ))}
          </div>
          {/* Staff Whereabouts */}
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm flex items-center gap-2"><Users className="h-4 w-4 text-primary" /> Staff Whereabouts — Today</CardTitle></CardHeader>
            <CardContent className="pt-0">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {EMPLOYEES.map(e => {
                  const sc = STAFF_STATUS_CFG[e.status];
                  return (
                    <div key={e.id} className="flex items-center gap-2 p-2 rounded-lg bg-muted/30">
                      <span className={`w-2 h-2 rounded-full shrink-0 ${sc.dot}`} />
                      <div className="min-w-0">
                        <div className="text-xs font-medium truncate">{e.name}</div>
                        <div className={`text-[10px] ${sc.text}`}>{sc.label}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── HR DIRECTORY ── */}
        <TabsContent value="hr" className="mt-4 space-y-4">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="relative flex-1 max-w-sm">
              <Users className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <Input className="pl-8 h-8 text-xs" placeholder="Search employees…" value={search} onChange={e => setSearch(e.target.value)} data-testid="input-hr-search" />
            </div>
            <div className="flex gap-1.5 flex-wrap">
              {depts.map(d => (
                <button key={d} onClick={() => setDeptFilter(d)}
                  className={`px-2.5 py-1 rounded-full text-[10px] font-medium border transition-colors ${deptFilter === d ? "bg-primary text-primary-foreground border-primary" : "border-border text-muted-foreground hover:border-primary/50"}`}>
                  {d}
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            {filteredEmp.map(e => <EmployeeRow key={e.id} emp={e} />)}
          </div>
        </TabsContent>

        {/* ── RECRUITMENT ── */}
        <TabsContent value="recruit" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Job postings */}
            <div className="space-y-3">
              <h3 className="font-semibold text-sm flex items-center gap-2"><Briefcase className="h-4 w-4 text-primary" /> Open Positions</h3>
              {JOB_POSTINGS.map(j => (
                <div key={j.id} className="flex items-center gap-3 p-3 border rounded-lg hover:bg-muted/30 transition-colors" data-testid={`job-${j.id}`}>
                  <div className="flex-1">
                    <div className="font-medium text-sm">{j.title}</div>
                    <div className="text-xs text-muted-foreground">{j.dept} · {j.type} · Posted {j.posted}</div>
                  </div>
                  <div className="text-xs text-muted-foreground">{j.apps} apps</div>
                  <Badge className={`text-[10px] border px-1.5
                    ${j.status === "active" ? "bg-emerald-100 text-emerald-700 border-emerald-300"
                    : j.status === "paused" ? "bg-amber-100 text-amber-700 border-amber-300"
                    : "bg-gray-100 text-gray-600 border-gray-300"}`}>
                    {j.status}
                  </Badge>
                </div>
              ))}
              <Button size="sm" className="w-full gap-1.5 h-8 text-xs" data-testid="btn-post-job">
                <PlusCircle className="h-3.5 w-3.5" /> Post New Position
              </Button>
            </div>

            {/* Applicant pipeline */}
            <div className="space-y-3">
              <h3 className="font-semibold text-sm flex items-center gap-2"><Award className="h-4 w-4 text-primary" /> Applicant Pipeline</h3>
              {(["new","screening","interview","offer","hired","rejected"] as AppStatus[]).map(stage => {
                const apps = APPLICANTS.filter(a => a.stage === stage);
                if (!apps.length) return null;
                const cfg = APP_STAGE[stage];
                return (
                  <div key={stage}>
                    <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1.5">{cfg.label} ({apps.length})</div>
                    {apps.map(a => (
                      <div key={a.id} className="flex items-center gap-3 p-2.5 border rounded-lg mb-1.5" data-testid={`applicant-${a.id}`}>
                        <div className="w-7 h-7 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-semibold shrink-0">
                          {a.name.split(" ").map(n=>n[0]).join("")}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="font-medium text-xs">{a.name}</div>
                          <div className="text-[10px] text-muted-foreground">{a.role} · Applied {a.appliedDate}</div>
                        </div>
                        <div className="text-xs font-semibold text-primary">{a.score}%</div>
                        <Badge className={`text-[9px] border px-1 ${cfg.color}`}>{cfg.label}</Badge>
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          </div>
        </TabsContent>

        {/* ── TIME & ATTENDANCE ── */}
        <TabsContent value="attendance" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Weekly timesheet */}
            <div className="lg:col-span-2 space-y-3">
              <h3 className="font-semibold text-sm flex items-center gap-2"><Clock className="h-4 w-4 text-primary" /> Weekly Timesheet — Mar 16–20, 2026</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b">
                      {["Employee","Mon","Tue","Wed","Thu","Fri","Hrs/Wk"].map(h => (
                        <th key={h} className="py-2 px-2 text-left font-semibold text-muted-foreground whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {TIMESHEETS.map((t, i) => (
                      <tr key={i} className="border-b hover:bg-muted/30">
                        <td className="py-2 px-2 font-medium whitespace-nowrap">{t.name}</td>
                        {[t.mon, t.tue, t.wed, t.thu, t.fri].map((day, di) => (
                          <td key={di} className={`py-2 px-2 whitespace-nowrap text-[10px]
                            ${day === "Off" || day.includes("PTO") ? "text-muted-foreground italic" : ""}`}>{day}</td>
                        ))}
                        <td className="py-2 px-2 font-semibold text-primary">{t.hrs}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* PTO Requests */}
            <div className="space-y-3">
              <h3 className="font-semibold text-sm flex items-center gap-2"><Calendar className="h-4 w-4 text-primary" /> PTO Requests</h3>
              {PTO_REQUESTS.map((r, i) => (
                <div key={i} className="p-3 border rounded-lg space-y-1" data-testid={`pto-${i}`}>
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-xs">{r.name}</span>
                    <Badge className={`text-[9px] border px-1.5
                      ${r.status === "approved" ? "bg-emerald-100 text-emerald-700 border-emerald-300"
                      : "bg-amber-100 text-amber-700 border-amber-300"}`}>
                      {r.status}
                    </Badge>
                  </div>
                  <div className="text-[10px] text-muted-foreground">{r.dates} · {r.type} · {r.days} day{r.days > 1 ? "s" : ""}</div>
                  {r.status === "pending" && (
                    <div className="flex gap-1.5 pt-1">
                      <Button size="sm" className="h-5 text-[10px] px-2 bg-emerald-600 hover:bg-emerald-700">Approve</Button>
                      <Button size="sm" variant="outline" className="h-5 text-[10px] px-2">Deny</Button>
                    </div>
                  )}
                </div>
              ))}
              <Button size="sm" variant="outline" className="w-full gap-1.5 h-8 text-xs" data-testid="btn-request-pto">
                <PlusCircle className="h-3.5 w-3.5" /> Submit PTO Request
              </Button>
            </div>
          </div>
        </TabsContent>

        {/* ── PAYROLL ── */}
        <TabsContent value="payroll" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { label:"Current Period Total", value:"$184,320", icon:DollarSign, color:"text-primary" },
              { label:"YTD Payroll",          value:"$1.47M",   icon:TrendingUp,  color:"text-emerald-600" },
              { label:"Next Payroll Date",    value:"Apr 2",    icon:Calendar,    color:"text-blue-600" },
            ].map(k => (
              <Card key={k.label}>
                <CardContent className="pt-4 pb-4">
                  <k.icon className={`h-4 w-4 ${k.color} mb-1`} />
                  <div className={`text-2xl font-bold font-mono ${k.color}`}>{k.value}</div>
                  <div className="text-[10px] text-muted-foreground">{k.label}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Pay Periods</CardTitle></CardHeader>
            <CardContent className="pt-0 space-y-2">
              {PAYROLL_PERIODS.map((p, i) => (
                <div key={i} className="flex items-center gap-4 p-3 border rounded-lg" data-testid={`payroll-${i}`}>
                  <div className="flex-1">
                    <div className="font-medium text-sm">{p.period}</div>
                    <div className="text-xs text-muted-foreground">Processed: {p.processed}</div>
                  </div>
                  <div className="font-semibold text-sm font-mono">{p.total}</div>
                  <Badge className={`text-[10px] border px-1.5
                    ${p.status === "paid" ? "bg-emerald-100 text-emerald-700 border-emerald-300"
                    : "bg-amber-100 text-amber-700 border-amber-300"}`}>
                    {p.status}
                  </Badge>
                  <Button size="sm" variant="outline" className="h-7 text-xs gap-1"><Printer className="h-3 w-3" />Payslips</Button>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm">Staff Compensation Overview</CardTitle></CardHeader>
            <CardContent className="pt-0">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b">
                      {["Name","Title","Department","Salary","Type","Status"].map(h => (
                        <th key={h} className="py-2 px-3 text-left font-semibold text-muted-foreground">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {EMPLOYEES.map(e => (
                      <tr key={e.id} className="border-b hover:bg-muted/30">
                        <td className="py-2 px-3 font-medium">{e.name}</td>
                        <td className="py-2 px-3 text-muted-foreground">{e.title}</td>
                        <td className="py-2 px-3">{e.dept}</td>
                        <td className="py-2 px-3 font-semibold font-mono">{e.salary}</td>
                        <td className="py-2 px-3">{e.title.includes("Dr.") ? "Production" : "Salary"}</td>
                        <td className="py-2 px-3"><Badge className="text-[9px] bg-emerald-100 text-emerald-700 border-emerald-300 border px-1">Active</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── BENEFITS ── */}
        <TabsContent value="benefits" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { label:"Annual Benefits Cost", value:"$58,200",  icon:Heart,   color:"text-red-500" },
              { label:"Avg Enrollment Rate",  value:"80%",      icon:Users,   color:"text-emerald-600" },
              { label:"Plans Offered",         value:8,          icon:Layers,  color:"text-primary" },
            ].map(k => (
              <Card key={k.label}>
                <CardContent className="pt-4 pb-4">
                  <k.icon className={`h-4 w-4 ${k.color} mb-1`} />
                  <div className={`text-2xl font-bold font-mono ${k.color}`}>{k.value}</div>
                  <div className="text-[10px] text-muted-foreground">{k.label}</div>
                </CardContent>
              </Card>
            ))}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {BENEFITS_PLANS.map((b, i) => (
              <div key={i} className="p-4 border rounded-xl space-y-2" data-testid={`benefit-${i}`}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-semibold text-sm">{b.name}</div>
                    <div className="text-xs text-muted-foreground">{b.carrier} · Renews {b.renewal}</div>
                  </div>
                  <span className="text-xs font-mono font-semibold text-primary shrink-0">{b.cost}</span>
                </div>
                <div>
                  <div className="flex justify-between text-[10px] text-muted-foreground mb-1">
                    <span>{b.enrolled} enrolled of {b.eligible} eligible</span>
                    <span>{Math.round((b.enrolled / b.eligible) * 100)}%</span>
                  </div>
                  <Progress value={(b.enrolled / b.eligible) * 100} className="h-1.5" />
                </div>
              </div>
            ))}
          </div>
        </TabsContent>

        {/* ── TRAINING & CE ── */}
        <TabsContent value="training" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { label:"Courses Active",   value:CE_COURSES.length, icon:GraduationCap, color:"text-primary" },
              { label:"Required Due Soon",value:CE_COURSES.filter(c=>c.required).length, icon:AlertCircle, color:"text-amber-600" },
              { label:"Avg Completion",   value:`${Math.round(CE_COURSES.reduce((a,c) => a + (c.completed/c.total)*100, 0) / CE_COURSES.length)}%`, icon:CheckCircle, color:"text-emerald-600" },
            ].map(k => (
              <Card key={k.label}>
                <CardContent className="pt-4 pb-4">
                  <k.icon className={`h-4 w-4 ${k.color} mb-1`} />
                  <div className={`text-2xl font-bold font-mono ${k.color}`}>{k.value}</div>
                  <div className="text-[10px] text-muted-foreground">{k.label}</div>
                </CardContent>
              </Card>
            ))}
          </div>
          <div className="space-y-2">
            {CE_COURSES.map((c, i) => {
              const pct = Math.round((c.completed / c.total) * 100);
              return (
                <div key={i} className="p-4 border rounded-xl" data-testid={`course-${i}`}>
                  <div className="flex items-center gap-3 mb-2">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-sm">{c.title}</span>
                        {c.required && <Badge className="text-[9px] bg-red-100 text-red-700 border-red-300 border px-1">Required</Badge>}
                      </div>
                      <div className="text-xs text-muted-foreground">{c.category} · Due: {c.due}</div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm font-bold font-mono text-primary">{pct}%</div>
                      <div className="text-[10px] text-muted-foreground">{c.completed}/{c.total} done</div>
                    </div>
                  </div>
                  <Progress value={pct} className={`h-1.5 ${pct === 100 ? "[&>div]:bg-emerald-500" : pct > 70 ? "[&>div]:bg-blue-500" : "[&>div]:bg-amber-500"}`} />
                </div>
              );
            })}
          </div>
        </TabsContent>

        {/* ── DAILY OPERATIONS ── */}
        <TabsContent value="ops" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Announcements */}
            <div className="space-y-3">
              <h3 className="font-semibold text-sm flex items-center gap-2"><Bell className="h-4 w-4 text-primary" /> Announcements</h3>
              {ANNOUNCEMENTS.map(a => (
                <div key={a.id} className={`p-3 border rounded-xl space-y-1 ${a.pinned ? "border-primary/40 bg-primary/[0.02]" : ""}`} data-testid={`announce-${a.id}`}>
                  <div className="flex items-center gap-1.5">
                    {a.pinned && <Badge className="text-[9px] bg-primary/10 text-primary border-primary/30 border px-1">Pinned</Badge>}
                    <Badge className={`text-[9px] border px-1
                      ${a.type === "success" ? "bg-emerald-100 text-emerald-700 border-emerald-300"
                      : a.type === "warning" ? "bg-amber-100 text-amber-700 border-amber-300"
                      : "bg-blue-100 text-blue-700 border-blue-300"}`}>{a.type}</Badge>
                  </div>
                  <div className="font-semibold text-sm">{a.title}</div>
                  <div className="text-xs text-muted-foreground">{a.body}</div>
                  <div className="text-[10px] text-muted-foreground">— {a.author} · {a.time}</div>
                </div>
              ))}
              <Button size="sm" className="w-full gap-1.5 h-8 text-xs" variant="outline" data-testid="btn-new-announce">
                <PlusCircle className="h-3.5 w-3.5" /> Post Announcement
              </Button>
            </div>

            {/* Daily Huddle */}
            <div className="space-y-3">
              <h3 className="font-semibold text-sm flex items-center gap-2"><ClipboardList className="h-4 w-4 text-primary" /> Daily Huddle — Mar 16, 2026</h3>
              <div className="p-3 border rounded-xl bg-muted/20 space-y-2">
                {huddle.map((item, i) => (
                  <div key={i} className="flex items-start gap-2" data-testid={`huddle-${i}`}>
                    <button onClick={() => setHuddle(h => h.map((x, j) => j === i ? { ...x, done: !x.done } : x))}
                      className="mt-0.5 shrink-0">
                      {item.done
                        ? <CheckCircle className="h-4 w-4 text-emerald-500" />
                        : <Circle className="h-4 w-4 text-muted-foreground" />}
                    </button>
                    <div>
                      <span className={`text-[10px] font-semibold text-primary uppercase tracking-wider`}>{item.category} · </span>
                      <span className={`text-xs ${item.done ? "line-through text-muted-foreground" : ""}`}>{item.item}</span>
                    </div>
                  </div>
                ))}
              </div>
              <Button size="sm" variant="outline" className="w-full gap-1.5 h-8 text-xs" data-testid="btn-add-huddle">
                <PlusCircle className="h-3.5 w-3.5" /> Add Huddle Item
              </Button>

              {/* Quick message */}
              <h3 className="font-semibold text-sm flex items-center gap-2 pt-2"><MessageSquare className="h-4 w-4 text-primary" /> Quick Broadcast</h3>
              <div className="flex gap-2">
                <Input className="h-8 text-xs flex-1" placeholder="Message all staff…" data-testid="input-broadcast" />
                <Button size="sm" className="h-8 gap-1 text-xs" data-testid="btn-send-broadcast">
                  <Send className="h-3 w-3" /> Send
                </Button>
              </div>
            </div>
          </div>
        </TabsContent>

        {/* ── TELEHEALTH ROOMS ── */}
        <TabsContent value="telehealth" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              { label:"Rooms Available", value: TELE_ROOMS.filter(r=>r.status==="available").length, icon:CheckCircle, color:"text-emerald-600" },
              { label:"In Session Now",  value: TELE_ROOMS.filter(r=>r.status==="in-session").length, icon:Video, color:"text-purple-600" },
              { label:"Scheduled Today", value: TELE_ROOMS.filter(r=>r.status==="scheduled").length,  icon:Calendar, color:"text-blue-600" },
              { label:"Platform",        value:"HIPAA ✓",   icon:Shield, color:"text-primary" },
            ].map(k => (
              <Card key={k.label}>
                <CardContent className="pt-4 pb-4">
                  <k.icon className={`h-4 w-4 ${k.color} mb-1`} />
                  <div className={`text-2xl font-bold font-mono ${k.color}`}>{k.value}</div>
                  <div className="text-[10px] text-muted-foreground">{k.label}</div>
                </CardContent>
              </Card>
            ))}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {TELE_ROOMS.map(room => (
              <div key={room.id} className={`p-4 border rounded-xl space-y-3
                ${room.status === "in-session" ? "border-purple-400/50 bg-purple-500/5"
                : room.status === "available" ? "border-emerald-400/40 bg-emerald-500/5"
                : "border-blue-400/40 bg-blue-500/5"}`} data-testid={`tele-${room.id}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Video className="h-4 w-4 text-muted-foreground" />
                    <span className="font-semibold text-sm">{room.name}</span>
                  </div>
                  <Badge className={`text-[10px] border px-1.5
                    ${room.status === "in-session" ? "bg-purple-100 text-purple-700 border-purple-300"
                    : room.status === "available" ? "bg-emerald-100 text-emerald-700 border-emerald-300"
                    : "bg-blue-100 text-blue-700 border-blue-300"}`}>
                    {room.status === "in-session" ? "In Session" : room.status === "available" ? "Available" : "Scheduled"}
                  </Badge>
                </div>
                <div className="text-xs space-y-0.5">
                  {room.status === "in-session" && (
                    <>
                      <div className="text-muted-foreground">Provider: <span className="text-foreground font-medium">{room.provider}</span></div>
                      <div className="text-muted-foreground">Patient: <span className="text-foreground font-medium">{(room as any).patient}</span></div>
                      <div className="text-muted-foreground">Duration: <span className="text-purple-600 font-semibold">{(room as any).duration}</span></div>
                    </>
                  )}
                  {room.status !== "in-session" && (
                    <div className="text-muted-foreground">Next: <span className="text-foreground">{room.next}</span></div>
                  )}
                  <div className="text-muted-foreground text-[10px]">Platform: {room.tech}</div>
                </div>
                <div className="flex gap-2">
                  {room.status === "available" && (
                    <Button size="sm" className="h-7 text-xs gap-1 flex-1" data-testid={`btn-start-${room.id}`}>
                      <Video className="h-3 w-3" /> Start Session
                    </Button>
                  )}
                  {room.status === "in-session" && (
                    <Button size="sm" variant="outline" className="h-7 text-xs gap-1 flex-1 text-purple-600 border-purple-300" data-testid={`btn-join-${room.id}`}>
                      <Video className="h-3 w-3" /> Join Session
                    </Button>
                  )}
                  {room.status === "scheduled" && (
                    <Button size="sm" variant="outline" className="h-7 text-xs gap-1 flex-1" data-testid={`btn-view-${room.id}`}>
                      <Calendar className="h-3 w-3" /> View Schedule
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </TabsContent>

        {/* ── IT & INFRASTRUCTURE ── */}
        <TabsContent value="it" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              { title:"Network & Internet",    icon:Wifi,           status:"Online",      details:["Fiber 1Gbps – Primary","LTE Backup – Standby","Guest VLAN isolated","VPN: 3 active tunnels"], ok:true },
              { title:"Workstations",          icon:MonitorSmartphone, status:"18/19 Online", details:["18 active workstations","1 offline (Op 4)","Last patch: Mar 14","Antivirus: Current"], ok:true },
              { title:"EHR / CRM Platform",   icon:Activity,       status:"Operational", details:["Uptime: 99.98%","Last backup: 2:00 AM","DB size: 42 GB","API latency: 84ms"], ok:true },
              { title:"HIPAA Security",        icon:Lock,           status:"Secure",      details:["MFA enabled: 23/23","Last pentest: Feb 2026","SOC 2 Type II active","BAAs on file: 12"], ok:true },
              { title:"Practice Management SW",icon:Layers,         status:"v5.4.1",      details:["Schedulon PM","Last update: Mar 10","Integrations: 8 active","Support: Premium"], ok:true },
              { title:"Digital Imaging",       icon:Camera,         status:"Online",      details:["Dentsply CBCT active","iTero Element 5D","Dexis sensor x6","DICOM server: Local"], ok:true },
              { title:"Phone System",          icon:Phone,          status:"VoIP Active", details:["RingCentral (HIPAA)","8 extensions active","AI Receptionist: Live","Fax: Digital only"], ok:true },
              { title:"Print / Scan / Fax",   icon:Printer,        status:"4 Online",    details:["HP LaserJet x4","All networked","HIPAA print policy","Scan-to-EHR active"], ok:true },
              { title:"Cloud Storage & Backup",icon:Globe,          status:"Synced",      details:["Google Workspace (HIPAA)","Daily incremental backup","7-year HIPAA retention","AES-256 encryption"], ok:true },
            ].map(item => (
              <div key={item.title} className="p-4 border rounded-xl space-y-2" data-testid={`it-${item.title.toLowerCase().replace(/\s/g,"-")}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <item.icon className="h-4 w-4 text-primary" />
                    <span className="font-semibold text-sm">{item.title}</span>
                  </div>
                  <Badge className={`text-[9px] border px-1.5 ${item.ok ? "bg-emerald-100 text-emerald-700 border-emerald-300" : "bg-red-100 text-red-700 border-red-300"}`}>
                    {item.status}
                  </Badge>
                </div>
                <ul className="space-y-0.5">
                  {item.details.map((d, i) => (
                    <li key={i} className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
                      <CheckCircle className="h-2.5 w-2.5 text-emerald-500 shrink-0" />{d}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
