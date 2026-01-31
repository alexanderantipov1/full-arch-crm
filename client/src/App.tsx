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

function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
  const sidebarStyle = {
    "--sidebar-width": "280px",
    "--sidebar-width-icon": "4rem",
  } as React.CSSProperties;

  return (
    <SidebarProvider style={sidebarStyle}>
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

  if (isLoading) {
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

  return (
    <AuthenticatedLayout>
      <Switch>
        <Route path="/" component={Dashboard} />
        <Route path="/leads" component={LeadsPage} />
        <Route path="/packages" component={TreatmentPackagesPage} />
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
          <Router />
          <Toaster />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

export default App;
