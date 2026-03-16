import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import { useAuth } from "@/hooks/use-auth";
import { SidebarProvider, SidebarTrigger, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "@/components/app-sidebar";
import { SessionTimeout } from "@/components/session-timeout";
import { Skeleton } from "@/components/ui/skeleton";

import NotFound from "@/pages/not-found";
import Landing from "@/pages/landing";
import Dashboard from "@/pages/dashboard";
import PatientsPage from "@/pages/patients";
import PatientForm from "@/pages/patient-form";
import PatientDetailPage from "@/pages/patient-detail";
import TreatmentPlansPage from "@/pages/treatment-plans";
import AppointmentsPage from "@/pages/appointments";
import BillingPage from "@/pages/billing";
import ProvidersPage from "@/pages/providers";
import CodingEnginePage from "@/pages/coding-engine";
import CalculatorPage from "@/pages/calculator";
import AnalyticsPage from "@/pages/analytics";
import AIAssistantPage from "@/pages/ai-assistant";
import AIDocumentationPage from "@/pages/ai-documentation";
import AppealsEnginePage from "@/pages/appeals-engine";
import ERAProcessingPage from "@/pages/era-processing";
import InsuranceVerificationPage from "@/pages/insurance-verification";
import PredictiveAnalyticsPage from "@/pages/predictive-analytics";
import TrainingPage from "@/pages/training";
import LeadsPage from "@/pages/leads";
import TreatmentPackagesPage from "@/pages/treatment-packages";
import AppointmentRemindersPage from "@/pages/appointment-reminders";
import PatientCheckInPage from "@/pages/patient-checkin";
import FinancingPage from "@/pages/financing";
import MedicalClearancePage from "@/pages/medical-clearance";
import PreSurgeryPage from "@/pages/pre-surgery";
import SurgeryDayPage from "@/pages/surgery-day";
import LabPage from "@/pages/lab";
import PostOpPage from "@/pages/post-op";
import TestimonialsPage from "@/pages/testimonials";
import WarrantyPage from "@/pages/warranty";
import MaintenancePage from "@/pages/maintenance";
import AuditLogsPage from "@/pages/audit-logs";
import ClinicalNotesPage from "@/pages/clinical-notes";
import EvaluationsPage from "@/pages/evaluations";
import SettingsPage from "@/pages/settings";
import PaymentsPage from "@/pages/payments";
import ConsentFormsPage from "@/pages/consent-forms";
import ReportsPage from "@/pages/reports";
import PatientDocumentsPage from "@/pages/patient-documents";
import TreatmentProgressPage from "@/pages/treatment-progress";
import IntakeFormPage from "@/pages/intake-form";
import CommandCenterPage from "@/pages/command-center";
import PracticeLaunchPadPage from "@/pages/practice-launchpad";
import DentBotPage from "@/pages/dentbot";
import PracticeCRMPage from "@/pages/practice-crm";
import SaasAdminPage from "@/pages/saas-admin";
import AdvancedModulesPage from "@/pages/advanced-modules";
import ContentEnginePage from "@/pages/content-engine";
import ReputationManagerPage from "@/pages/reputation-manager";
import AllOn4Page from "@/pages/seo-all-on-4";
import AllOn6Page from "@/pages/seo-all-on-6";
import DentalImplantBillingPage from "@/pages/seo-dental-billing";
import AboutPage from "@/pages/about";
import PerioChartingPage from "@/pages/perio-charting";
import AIDiagnosticsPage from "@/pages/ai-diagnostics";
import EPrescribingPage from "@/pages/e-prescribing";
import DecisionSupportPage from "@/pages/decision-support";
import OrthoTrackerPage from "@/pages/ortho-tracker";
import EndoTrackerPage from "@/pages/endo-tracker";
import RecallSystemPage from "@/pages/recall-system";
import MultiProviderSchedulingPage from "@/pages/multi-provider-scheduling";
import PatientPortalPage from "@/pages/patient-portal";
import PatientMessagingPage from "@/pages/patient-messaging";
import PediatricModulePage from "@/pages/pediatric-module";
import OralSurgeryModulePage from "@/pages/oral-surgery-module";
import ImplantTrackerPage from "@/pages/implant-tracker";
import InventoryPage from "@/pages/inventory";
import HRPayrollPage from "@/pages/hr-payroll";
import SterilizationPage from "@/pages/sterilization";
import AIPhonePage from "@/pages/ai-phone";
import VoiceToCodePage from "@/pages/voice-to-code";
import CaseAcceptancePage from "@/pages/case-acceptance";
import UnionFlowPage from "@/pages/union-flow";
import TelehealthPage from "@/pages/telehealth";
import FeeOptimizerPage from "@/pages/fee-optimizer";
import ProviderIntelPage from "@/pages/provider-intel";
import PayerIntelPage from "@/pages/payer-intel";
import MultiLocationPage from "@/pages/multi-location";
import RcmPage from "@/pages/rcm";
import FinancialPage from "@/pages/financial";
import MarketingSuitePage from "@/pages/marketing";
import NpsPage from "@/pages/nps";
import CompliancePage from "@/pages/compliance";
import BusinessIntelligencePage from "@/pages/business-intelligence";
import MessagesPage from "@/pages/messages";
import DentalChartingPage from "@/pages/dental-charting";
import OnboardingPage from "@/pages/onboarding";
import { useQuery } from "@tanstack/react-query";

function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const sidebarStyle = {
    "--sidebar-width": "280px",
    "--sidebar-width-icon": "4rem",
  } as React.CSSProperties;

  return (
    <SidebarProvider style={sidebarStyle}>
      <SessionTimeout />
      <div className="flex min-h-screen w-full">
        <AppSidebar />
        <SidebarInset className="flex flex-1 flex-col">
          <header className="sticky top-0 z-40 flex h-14 items-center justify-between gap-4 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <SidebarTrigger data-testid="button-sidebar-toggle" />
            <ThemeToggle />
          </header>
          <main className="flex-1 overflow-auto p-6">
            {children}
          </main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}

function Router() {
  const { user, isLoading } = useAuth();

  const { data: onboardingStatus, isLoading: onboardingLoading } = useQuery<{
    hasStarted: boolean;
    isComplete: boolean;
    currentStep: number;
  }>({
    queryKey: ["/api/onboarding/status"],
    enabled: !!user,
  });

  if (isLoading || (user && onboardingLoading)) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="space-y-4 text-center">
          <Skeleton className="h-12 w-12 rounded-full mx-auto" />
          <Skeleton className="h-4 w-32 mx-auto" />
        </div>
      </div>
    );
  }

  if (!user) {
    return <Landing />;
  }

  if (onboardingStatus && !onboardingStatus.isComplete) {
    return <OnboardingPage />;
  }

  return (
    <AuthenticatedLayout>
      <Switch>
        <Route path="/" component={Dashboard} />
        <Route path="/leads" component={LeadsPage} />
        <Route path="/packages" component={TreatmentPackagesPage} />
        <Route path="/reminders" component={AppointmentRemindersPage} />
        <Route path="/check-in" component={PatientCheckInPage} />
        <Route path="/financing" component={FinancingPage} />
        <Route path="/medical-clearance" component={MedicalClearancePage} />
        <Route path="/surgery" component={SurgeryDayPage} />
        <Route path="/pre-surgery" component={PreSurgeryPage} />
        <Route path="/lab" component={LabPage} />
        <Route path="/post-op" component={PostOpPage} />
        <Route path="/testimonials" component={TestimonialsPage} />
        <Route path="/warranty" component={WarrantyPage} />
        <Route path="/maintenance" component={MaintenancePage} />
        <Route path="/audit-logs" component={AuditLogsPage} />
        <Route path="/patients" component={PatientsPage} />
        <Route path="/patients/new" component={PatientForm} />
        <Route path="/patients/:id" component={PatientDetailPage} />
        <Route path="/treatment-plans" component={TreatmentPlansPage} />
        <Route path="/appointments" component={AppointmentsPage} />
        <Route path="/billing" component={BillingPage} />
        <Route path="/providers" component={ProvidersPage} />
        <Route path="/coding" component={CodingEnginePage} />
        <Route path="/calculator" component={CalculatorPage} />
        <Route path="/analytics" component={AnalyticsPage} />
        <Route path="/ai-assistant" component={AIAssistantPage} />
        <Route path="/ai-documentation" component={AIDocumentationPage} />
        <Route path="/appeals" component={AppealsEnginePage} />
        <Route path="/era-processing" component={ERAProcessingPage} />
        <Route path="/eligibility" component={InsuranceVerificationPage} />
        <Route path="/predictive" component={PredictiveAnalyticsPage} />
        <Route path="/training" component={TrainingPage} />
        <Route path="/notes" component={ClinicalNotesPage} />
        <Route path="/evaluations" component={EvaluationsPage} />
        <Route path="/settings" component={SettingsPage} />
        <Route path="/payments" component={PaymentsPage} />
        <Route path="/consent-forms" component={ConsentFormsPage} />
        <Route path="/reports" component={ReportsPage} />
        <Route path="/documents" component={PatientDocumentsPage} />
        <Route path="/treatment-progress" component={TreatmentProgressPage} />
        <Route path="/intake" component={IntakeFormPage} />
        <Route path="/command-center" component={CommandCenterPage} />
        <Route path="/practice-launchpad" component={PracticeLaunchPadPage} />
        <Route path="/dentbot" component={DentBotPage} />
        <Route path="/practice-crm" component={PracticeCRMPage} />
        <Route path="/saas-admin" component={SaasAdminPage} />
        <Route path="/advanced-modules" component={AdvancedModulesPage} />
        <Route path="/content-engine" component={ContentEnginePage} />
        <Route path="/reputation" component={ReputationManagerPage} />
        <Route path="/dental-charting/:id?" component={DentalChartingPage} />
        <Route path="/perio" component={PerioChartingPage} />
        <Route path="/ai-diagnostics" component={AIDiagnosticsPage} />
        <Route path="/e-prescribing" component={EPrescribingPage} />
        <Route path="/decision-support" component={DecisionSupportPage} />
        <Route path="/ortho" component={OrthoTrackerPage} />
        <Route path="/endo" component={EndoTrackerPage} />
        <Route path="/recall" component={RecallSystemPage} />
        <Route path="/multi-scheduling" component={MultiProviderSchedulingPage} />
        <Route path="/patient-portal" component={PatientPortalPage} />
        <Route path="/patient-messaging" component={PatientMessagingPage} />
        <Route path="/pediatric" component={PediatricModulePage} />
        <Route path="/oral-surgery" component={OralSurgeryModulePage} />
        <Route path="/implant-tracker" component={ImplantTrackerPage} />
        <Route path="/inventory" component={InventoryPage} />
        <Route path="/hr" component={HRPayrollPage} />
        <Route path="/sterilization" component={SterilizationPage} />
        <Route path="/ai-phone" component={AIPhonePage} />
        <Route path="/voice-to-code" component={VoiceToCodePage} />
        <Route path="/case-acceptance" component={CaseAcceptancePage} />
        <Route path="/telehealth" component={TelehealthPage} />
        <Route path="/fee-optimizer" component={FeeOptimizerPage} />
        <Route path="/provider-intel" component={ProviderIntelPage} />
        <Route path="/payer-intel" component={PayerIntelPage} />
        <Route path="/multi-location" component={MultiLocationPage} />
        <Route path="/rcm" component={RcmPage} />
        <Route path="/financial" component={FinancialPage} />
        <Route path="/marketing" component={MarketingSuitePage} />
        <Route path="/nps" component={NpsPage} />
        <Route path="/compliance" component={CompliancePage} />
        <Route path="/business-intelligence" component={BusinessIntelligencePage} />
        <Route path="/messages" component={MessagesPage} />
        <Route path="/union-flow" component={UnionFlowPage} />
        <Route component={NotFound} />
      </Switch>
    </AuthenticatedLayout>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="light" storageKey="implantcrm-theme">
        <TooltipProvider>
          <Switch>
            <Route path="/all-on-4-billing" component={AllOn4Page} />
            <Route path="/all-on-6-billing" component={AllOn6Page} />
            <Route path="/dental-implant-billing" component={DentalImplantBillingPage} />
            <Route path="/about" component={AboutPage} />
            <Route>
              <Router />
            </Route>
          </Switch>
          <Toaster />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
