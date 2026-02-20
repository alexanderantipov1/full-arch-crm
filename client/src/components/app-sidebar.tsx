import { Link, useLocation } from "wouter";
import {
  Users,
  Calendar,
  FileText,
  ClipboardList,
  MessageSquare,
  Mail,
  Settings,
  LayoutDashboard,
  Stethoscope,
  DollarSign,
  Building2,
  LogOut,
  FileCode,
  Calculator,
  BarChart3,
  Sparkles,
  Gavel,
  Receipt,
  Shield,
  TrendingUp,
  GraduationCap,
  UserPlus,
  Phone,
  CreditCard,
  ClipboardCheck,
  Syringe,
  HeartPulse,
  Package,
  Star,
  Wrench,
  CheckCircle,
  RefreshCcw,
  Zap,
  Rocket,
  Bot,
  Contact,
  Cog,
  Layers,
  PenTool,
  Award,
  Microscope,
  Pill,
  Brain,
  Smile,
  FlaskConical,
  Mic,
  Target,
  Video,
  MapPin,
  Activity,
  Wallet,
  Megaphone,
  ThumbsUp,
  ShieldCheck,
  PieChart,
  CircleDot,
  Handshake,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useAuth } from "@/hooks/use-auth";

const homeItems = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  { title: "Command Center", url: "/command-center", icon: Zap },
  { title: "Messages", url: "/messages", icon: Mail },
];

const patientsItems = [
  { title: "Patients", url: "/patients", icon: Users },
  { title: "Appointments", url: "/appointments", icon: Calendar },
  { title: "Reminders", url: "/reminders", icon: Phone },
  { title: "Lead Management", url: "/leads", icon: UserPlus },
  { title: "Patient Intake", url: "/intake", icon: ClipboardCheck },
  { title: "Check-In", url: "/check-in", icon: ClipboardCheck },
];

const clinicalItems = [
  { title: "Treatment Plans", url: "/treatment-plans", icon: ClipboardList },
  { title: "Treatment Progress", url: "/treatment-progress", icon: ClipboardList },
  { title: "Clinical Notes", url: "/notes", icon: FileText },
  { title: "Exams & Evaluations", url: "/evaluations", icon: Stethoscope },
  { title: "Dental Charting", url: "/dental-charting", icon: CircleDot },
  { title: "Perio Charting", url: "/perio", icon: BarChart3 },
  { title: "AI Diagnostics", url: "/ai-diagnostics", icon: Microscope },
  { title: "Patient Documents", url: "/documents", icon: FileText },
  { title: "E-Prescribing", url: "/e-prescribing", icon: Pill },
  { title: "Consent Forms", url: "/consent-forms", icon: FileText },
  { title: "Decision Support", url: "/decision-support", icon: Brain },
];

const surgeryItems = [
  { title: "Case Acceptance", url: "/case-acceptance", icon: Target },
  { title: "Treatment Packages", url: "/packages", icon: Package },
  { title: "Financing", url: "/financing", icon: CreditCard },
  { title: "Medical Clearance", url: "/medical-clearance", icon: HeartPulse },
  { title: "Pre-Surgery", url: "/pre-surgery", icon: ClipboardCheck },
  { title: "Surgery Day", url: "/surgery", icon: Syringe },
  { title: "Lab & Design", url: "/lab", icon: Wrench },
  { title: "Post-Op & Delivery", url: "/post-op", icon: CheckCircle },
  { title: "Implant Tracker", url: "/implant-tracker", icon: Wrench },
  { title: "Ortho Tracker", url: "/ortho", icon: Smile },
  { title: "Teledentistry", url: "/telehealth", icon: Video },
];

const billingItems = [
  { title: "Billing & Claims", url: "/billing", icon: DollarSign },
  { title: "Coding Engine", url: "/coding", icon: FileCode },
  { title: "Payment Tracking", url: "/payments", icon: CreditCard },
  { title: "ERA Processing", url: "/era-processing", icon: Receipt },
  { title: "Appeals Engine", url: "/appeals", icon: Gavel },
  { title: "Eligibility Check", url: "/eligibility", icon: Shield },
  { title: "Cost Calculator", url: "/calculator", icon: Calculator },
  { title: "Revenue Cycle", url: "/rcm", icon: Activity },
  { title: "Financial Center", url: "/financial", icon: Wallet },
  { title: "Fee Optimizer", url: "/fee-optimizer", icon: DollarSign },
];

const aiToolsItems = [
  { title: "AI Assistant", url: "/ai-assistant", icon: MessageSquare },
  { title: "AI Documentation", url: "/ai-documentation", icon: Sparkles },
  { title: "AI Phone Agent", url: "/ai-phone", icon: Phone },
  { title: "Voice-to-Code", url: "/voice-to-code", icon: Mic },
  { title: "DentBot Advisor", url: "/dentbot", icon: Bot },
];

const growthItems = [
  { title: "Marketing Suite", url: "/marketing", icon: Megaphone },
  { title: "Union Flow", url: "/union-flow", icon: Handshake },
  { title: "Content Engine", url: "/content-engine", icon: PenTool },
  { title: "Reputation Manager", url: "/reputation", icon: Award },
  { title: "Patient NPS", url: "/nps", icon: ThumbsUp },
  { title: "Testimonials", url: "/testimonials", icon: Star },
  { title: "Practice Launch Pad", url: "/practice-launchpad", icon: Rocket },
  { title: "Practice CRM", url: "/practice-crm", icon: Contact },
];

const analyticsItems = [
  { title: "Reports & Analytics", url: "/reports", icon: BarChart3 },
  { title: "Predictive Analytics", url: "/predictive", icon: TrendingUp },
  { title: "Business Intel", url: "/business-intelligence", icon: PieChart },
  { title: "Provider Intel", url: "/provider-intel", icon: TrendingUp },
  { title: "Payer Intel", url: "/payer-intel", icon: Building2 },
  { title: "Compliance Audit", url: "/compliance", icon: ShieldCheck },
];

const adminItems = [
  { title: "Advanced Modules", url: "/advanced-modules", icon: Layers },
  { title: "SaaS Admin", url: "/saas-admin", icon: Cog },
  { title: "Multi-Location", url: "/multi-location", icon: MapPin },
  { title: "Inventory", url: "/inventory", icon: Package },
  { title: "HR & Payroll", url: "/hr", icon: Users },
  { title: "Sterilization", url: "/sterilization", icon: FlaskConical },
  { title: "Warranty", url: "/warranty", icon: Shield },
  { title: "Maintenance", url: "/maintenance", icon: RefreshCcw },
  { title: "Training Center", url: "/training", icon: GraduationCap },
  { title: "Referring Providers", url: "/providers", icon: Building2 },
  { title: "HIPAA Audit Logs", url: "/audit-logs", icon: Shield },
  { title: "Settings", url: "/settings", icon: Settings },
];

const navGroups = [
  { label: "Home", items: homeItems },
  { label: "Patients & Scheduling", items: patientsItems },
  { label: "Clinical Care", items: clinicalItems },
  { label: "Surgery Center", items: surgeryItems },
  { label: "Billing & Revenue", items: billingItems },
  { label: "AI Tools", items: aiToolsItems },
  { label: "Marketing & Growth", items: growthItems },
  { label: "Analytics & Intel", items: analyticsItems },
  { label: "Administration", items: adminItems },
];

export function AppSidebar() {
  const [location] = useLocation();
  const { user, logout } = useAuth();

  const isActive = (url: string) => {
    if (url === "/") return location === "/";
    return location.startsWith(url);
  };

  return (
    <Sidebar>
      <SidebarHeader className="border-b border-sidebar-border px-4 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <Stethoscope className="h-5 w-5" />
          </div>
          <div className="flex flex-col">
            <span className="font-semibold text-sidebar-foreground">Full Arch CRM</span>
            <span className="text-xs text-muted-foreground">Practice Management</span>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        {navGroups.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {group.items.map((item) => (
                  <SidebarMenuItem key={item.title}>
                    <SidebarMenuButton
                      asChild
                      isActive={isActive(item.url)}
                      data-testid={`nav-${item.title.toLowerCase().replace(/\s+/g, "-")}`}
                    >
                      <Link href={item.url}>
                        <item.icon className="h-4 w-4" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border p-4">
        {user && (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Avatar className="h-8 w-8">
                <AvatarImage src={user.profileImageUrl || undefined} />
                <AvatarFallback className="bg-primary/10 text-primary text-sm">
                  {user.firstName?.[0] || user.email?.[0]?.toUpperCase() || "U"}
                </AvatarFallback>
              </Avatar>
              <div className="flex flex-col">
                <span className="text-sm font-medium text-sidebar-foreground">
                  {user.firstName} {user.lastName}
                </span>
                <span className="text-xs text-muted-foreground">{user.email}</span>
              </div>
            </div>
            <SidebarMenuButton
              size="sm"
              onClick={() => logout()}
              className="h-8 w-8 p-0"
              data-testid="button-logout"
            >
              <LogOut className="h-4 w-4" />
            </SidebarMenuButton>
          </div>
        )}
      </SidebarFooter>
    </Sidebar>
  );
}
