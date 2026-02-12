import { Link, useLocation } from "wouter";
import {
  Users,
  Calendar,
  FileText,
  ClipboardList,
  MessageSquare,
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

const mainNavItems = [
  { title: "Dashboard", url: "/", icon: LayoutDashboard },
  { title: "Command Center", url: "/command-center", icon: Zap },
  { title: "Lead Management", url: "/leads", icon: UserPlus },
  { title: "Patients", url: "/patients", icon: Users },
  { title: "Appointments", url: "/appointments", icon: Calendar },
  { title: "Reminders", url: "/reminders", icon: Phone },
  { title: "Treatment Plans", url: "/treatment-plans", icon: ClipboardList },
  { title: "Treatment Progress", url: "/treatment-progress", icon: ClipboardList },
  { title: "Treatment Packages", url: "/packages", icon: Package },
];

const patientJourneyItems = [
  { title: "Patient Intake", url: "/intake", icon: ClipboardCheck },
  { title: "Check-In", url: "/check-in", icon: ClipboardCheck },
  { title: "Financing", url: "/financing", icon: CreditCard },
  { title: "Medical Clearance", url: "/medical-clearance", icon: HeartPulse },
  { title: "Pre-Surgery", url: "/pre-surgery", icon: ClipboardCheck },
  { title: "Surgery Day", url: "/surgery", icon: Syringe },
  { title: "Lab & Design", url: "/lab", icon: Wrench },
  { title: "Post-Op & Delivery", url: "/post-op", icon: CheckCircle },
  { title: "Warranty", url: "/warranty", icon: Shield },
  { title: "Maintenance", url: "/maintenance", icon: RefreshCcw },
  { title: "Testimonials", url: "/testimonials", icon: Star },
];

const clinicalItems = [
  { title: "Clinical Notes", url: "/notes", icon: FileText },
  { title: "Patient Documents", url: "/documents", icon: FileText },
  { title: "AI Assistant", url: "/ai-assistant", icon: MessageSquare },
  { title: "AI Documentation", url: "/ai-documentation", icon: Sparkles },
  { title: "Exams & Evaluations", url: "/evaluations", icon: Stethoscope },
];

const growthItems = [
  { title: "Practice Launch Pad", url: "/practice-launchpad", icon: Rocket },
  { title: "DentBot Advisor", url: "/dentbot", icon: Bot },
  { title: "Practice CRM", url: "/practice-crm", icon: Contact },
  { title: "SaaS Admin", url: "/saas-admin", icon: Cog },
];

const adminItems = [
  { title: "Billing & Claims", url: "/billing", icon: DollarSign },
  { title: "Payment Tracking", url: "/payments", icon: CreditCard },
  { title: "Coding Engine", url: "/coding", icon: FileCode },
  { title: "ERA Processing", url: "/era-processing", icon: Receipt },
  { title: "Appeals Engine", url: "/appeals", icon: Gavel },
  { title: "Eligibility Check", url: "/eligibility", icon: Shield },
  { title: "Consent Forms", url: "/consent-forms", icon: FileText },
  { title: "Cost Calculator", url: "/calculator", icon: Calculator },
  { title: "Reports & Analytics", url: "/reports", icon: BarChart3 },
  { title: "Predictive Analytics", url: "/predictive", icon: TrendingUp },
  { title: "Training Center", url: "/training", icon: GraduationCap },
  { title: "Referring Providers", url: "/providers", icon: Building2 },
  { title: "HIPAA Audit Logs", url: "/audit-logs", icon: Shield },
  { title: "Settings", url: "/settings", icon: Settings },
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
        <SidebarGroup>
          <SidebarGroupLabel>Main</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {mainNavItems.map((item) => (
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

        <SidebarGroup>
          <SidebarGroupLabel>Patient Journey</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {patientJourneyItems.map((item) => (
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

        <SidebarGroup>
          <SidebarGroupLabel>Clinical</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {clinicalItems.map((item) => (
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

        <SidebarGroup>
          <SidebarGroupLabel>Practice Growth</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {growthItems.map((item) => (
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

        <SidebarGroup>
          <SidebarGroupLabel>Administration</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {adminItems.map((item) => (
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
