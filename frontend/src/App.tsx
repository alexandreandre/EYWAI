// src/App.tsx

import { lazy, Suspense, type ReactNode } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { CompanyProvider, useCompany } from './contexts/CompanyContext';
import { ViewProvider, useView } from './contexts/ViewContext';
import { BootProvider } from './contexts/BootContext';
import { BootGate } from '@/components/BootGate';
import { isPlatformAdmin } from '@/lib/platformAdmin';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import { SignedPdfPreviewProvider } from '@/contexts/SignedPdfPreviewContext';
import { AppSidebar } from '@/components/ui/app-sidebar';
import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CompanySwitcher, CompanySwitcherCompact } from '@/components/CompanySwitcher';
import { ErrorBoundaryClass } from '@/components/ErrorBoundary';
import { EmployeeSidebar } from '@/components/ui/employee-sidebar';
import { RouteSkeleton } from '@/components/skeletons/RouteSkeleton';
import { ProtectedAppSkeleton } from '@/components/skeletons/ProtectedAppSkeleton';
import { TableSkeleton } from '@/components/skeletons/TableSkeleton';
import { PlanningPageSkeleton } from '@/components/skeletons/PlanningPageSkeleton';
import { BackgroundDataIndicator } from '@/components/BackgroundDataIndicator';
import * as Pages from '@/app/lazyPages';
import { employeeCollaboratorRoutes } from '@/app/employeeRoutes';
import { isEmployeeOnlyPath } from '@/lib/routeAccess';
import { isPayrollFocusActive, isPayrollFocusAllowed } from '@/lib/payrollFocus';
import { BADGEUSE_RH_TERMINAL_PATH } from '@/lib/badgeuseRoutes';
import { TestEnvBanner } from '@/components/TestEnvBanner';

const BadgeuseTerminalGate = lazy(
  () => import('@/components/badgeuse/rh/BadgeuseTerminalGate').then((m) => ({
    default: m.BadgeuseTerminalGate,
  }))
);

function EmployeeLayout() {
  const { accessibleCompanies, activeCompany } = useCompany();
  const showCompanySwitcher =
    accessibleCompanies && accessibleCompanies.length > 1;
  const headerLogo = activeCompany?.logo_url ? (
    <img
      src={activeCompany.logo_url}
      alt={`Logo ${activeCompany.company_name}`}
      className="h-8 w-auto max-w-[140px] object-contain"
      style={{ transform: `scale(${activeCompany.logo_scale || 1})` }}
    />
  ) : (
    <img src="/Colorplast.png" alt="Logo par défaut" className="h-8 w-auto" />
  );

  return (
    <SidebarProvider>
      <div className="grid min-h-screen w-full md:grid-cols-[auto_1fr]">
        <EmployeeSidebar />
        <div className="flex min-w-0 flex-col flex-1">
          <TestEnvBanner />
          <header className="sticky top-0 z-10 flex h-14 items-center gap-4 border-b bg-background px-4 md:hidden">
            <SidebarTrigger>
              <Button variant="ghost" size="icon" className="md:hidden">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Toggle Menu</span>
              </Button>
            </SidebarTrigger>
            <div className="flex-1 min-w-0">{headerLogo}</div>
            {showCompanySwitcher && <CompanySwitcher />}
          </header>
          {showCompanySwitcher && (
            <div className="hidden md:flex items-center gap-4 border-b bg-background px-6 py-3">
              <div className="flex-1" />
              <CompanySwitcher />
            </div>
          )}
          <main className="min-w-0 flex-1 overflow-auto overflow-x-auto p-6 lg:p-8">
            <BackgroundDataIndicator />
            <Outlet />
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}

function ProtectedRoutesWithView() {
  const { user } = useAuth();
  return (
    <ViewProvider userRole={user?.role}>
      <ProtectedRoutes />
    </ViewProvider>
  );
}

function ProtectedRoutes() {
  const location = useLocation();
  const { user, isLoading } = useAuth();
  const { accessibleCompanies, isLoading: isCompanyLoading } = useCompany();
  const { viewMode, isCollaborateurRh } = useView();

  const isCollaborateurRhView = isCollaborateurRh && viewMode === 'collaborateur';

  if (isLoading || isCompanyLoading) {
    return <ProtectedAppSkeleton />;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (
    user.role !== 'collaborateur' &&
    !isCollaborateurRhView &&
    isEmployeeOnlyPath(location.pathname)
  ) {
    return <Navigate to="/" replace />;
  }

  // Mode paie : les écrans hors périmètre ne sont pas seulement retirés du
  // menu, ils sont inatteignables à l'URL.
  if (
    user.role !== 'collaborateur' &&
    !isCollaborateurRhView &&
    isPayrollFocusActive(user) &&
    !isPayrollFocusAllowed(location.pathname)
  ) {
    return <Navigate to="/" replace />;
  }

  if (user.role === 'collaborateur') {
    return (
      <Routes>
        <Route element={<EmployeeLayout />}>{employeeCollaboratorRoutes}</Route>
      </Routes>
    );
  }

  const showCompanySwitcher = accessibleCompanies && accessibleCompanies.length > 1;

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-muted/40">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TestEnvBanner />
          {showCompanySwitcher && (
            <header className="sticky top-0 z-10 flex h-14 items-center gap-4 border-b bg-background px-4 md:hidden">
              <SidebarTrigger>
                <Button variant="ghost" size="icon" className="md:hidden">
                  <Menu className="h-5 w-5" />
                  <span className="sr-only">Toggle Menu</span>
                </Button>
              </SidebarTrigger>
              <div className="flex-1">
                <img src="/Colorplast.png" alt="Logo Colorplast" className="h-8 w-auto" />
              </div>
              <CompanySwitcherCompact />
            </header>
          )}
          <main className="min-w-0 flex-1 overflow-x-auto overflow-y-auto bg-background p-6 lg:p-8">
            <BackgroundDataIndicator />
            <Routes>
              {isCollaborateurRhView ? (
                <>{employeeCollaboratorRoutes}</>
              ) : (
                <>
                  <Route path="/" element={<Pages.RhDashboard />} />
                  <Route
                    path="/analytics"
                    element={
                      <Suspense fallback={<RouteSkeleton />}>
                        <Pages.AnalyticsPage />
                      </Suspense>
                    }
                  />
                  <Route path="/analytics-paie" element={<Pages.AnalyticsPaiePage />} />
                  <Route path="/analytics-gestion" element={<Pages.AnalyticsGestionPage />} />
                  <Route
                    path="/employees"
                    element={
                      <Suspense fallback={<TableSkeleton rows={10} columns={4} />}>
                        <Pages.Employees />
                      </Suspense>
                    }
                  />
                  <Route path="/teams" element={<Pages.Teams />} />
                  <Route path="/employees/:employeeId" element={<Pages.EmployeeDetail />} />
                  <Route path="/saisies" element={<Pages.Saisies />} />
                  <Route path="/salary-seizures" element={<Pages.SalarySeizures />} />
                  <Route path="/salary-advances" element={<Pages.SalaryAdvances />} />
                  <Route path="/employee-loans" element={<Pages.EmployeeLoans />} />
                  <Route path="/rates" element={<Pages.Rates />} />
                  <Route
                    path="/payroll/generate"
                    element={
                      <Suspense fallback={<TableSkeleton rows={8} columns={5} />}>
                        <Pages.PayrollGenerate />
                      </Suspense>
                    }
                  />
                  <Route
                    path="/payroll"
                    element={
                      <Suspense fallback={<TableSkeleton rows={8} columns={5} />}>
                        <Pages.Payroll />
                      </Suspense>
                    }
                  />
                  <Route path="/payroll/:employeeId" element={<Pages.PayrollDetail />} />
                  <Route path="/payslips/:payslipId/edit" element={<Pages.PayslipEdit />} />
                  <Route path="/leaves" element={<Pages.RhAbsencesPage />} />
                  <Route path="/suivi-ijss" element={<Pages.SuiviIJSS />} />
                  <Route path="/suivi-temps-travail" element={<Pages.SuiviTempsTravail />} />
                  <Route path="/suivi-contingent-hs" element={<Pages.SuiviContingentHs />} />
                  <Route path="/suivi-modulation" element={<Pages.SuiviModulation />} />
                  <Route path="/suivi-cet" element={<Pages.SuiviCet />} />
                  <Route path="/employee/leaves/new" element={<Navigate to="/leaves" replace />} />
                  <Route
                    path="/planning"
                    element={
                      <Suspense fallback={<PlanningPageSkeleton />}>
                        <Pages.Planning />
                      </Suspense>
                    }
                  />
                  <Route path="/expenses" element={<Pages.RhExpensesPage />} />
                  <Route path="/schedules" element={<Pages.RhSchedulesPage />} />
                  <Route path="/employee-exits" element={<Pages.EmployeeExits />} />
                  <Route path="/employee-exits/:exitId/documents/:documentId/edit" element={<Pages.ExitDocumentEdit />} />
                  <Route path="/residence-permits" element={<Pages.ResidencePermits />} />
                  <Route path="/taux-pas" element={<Pages.TauxPas />} />
                  <Route path="/trial-periods" element={<Pages.TrialPeriods />} />
                  <Route
                    path="/medical-follow-up"
                    element={
                      <ErrorBoundaryClass>
                        <Pages.MedicalFollowUp />
                      </ErrorBoundaryClass>
                    }
                  />
                  <Route path="/annual-reviews" element={<Pages.AnnualReviews />} />
                  <Route path="/annual-reviews/:reviewId" element={<Pages.AnnualReviewDetail />} />
                  <Route path="/leave-requests" element={<Pages.LeaveRequests />} />
                  <Route path="/cet-requests" element={<Pages.CetRequests />} />
                  <Route path="/approvals" element={<Pages.ManagerApprovals />} />
                  <Route path="/formation" element={<Pages.FormationPage />} />
                  <Route path="/documents" element={<Pages.RhDocumentsPage />} />
                  <Route path="/augmentations-et-promotions" element={<Pages.AugmentationsEtPromotions />} />
                  <Route path="/augmentations-collectives" element={<Navigate to="/augmentations-et-promotions" replace />} />
                  <Route path="/habilitations" element={<Pages.RhFormationLegacyRedirect />} />
                  <Route path="/objectives" element={<Pages.RhFormationLegacyRedirect />} />
                  <Route path="/catalogue-formations" element={<Pages.RhFormationLegacyRedirect />} />
                  <Route path="/promotions" element={<Navigate to="/augmentations-et-promotions" replace />} />
                  <Route path="/promotions/:promotionId" element={<Pages.PromotionDetail />} />
                  <Route path="/cse/meetings/:meetingId" element={<Pages.MeetingDetailPage />} />
                  <Route path="/cse" element={<Pages.CSE />} />
                  <Route path="/recruitment" element={<Pages.Recruitment />} />
                  <Route path="/onboarding" element={<Pages.OnboardingHubPage />} />
                  <Route path="/onboarding/:employeeId" element={<Pages.OnboardingPage />} />
                  <Route path="/badgeuse-rh" element={<Pages.BadgeuseRhPage />} />
                  <Route path="/simulation" element={<Pages.Simulation />} />
                  <Route path="/exports" element={<Pages.Exports />} />
                  <Route path="/company" element={<Pages.CompanyPage />} />
                  <Route path="/groups/:groupId" element={<Pages.GroupDashboard />} />
                  <Route path="/users" element={<Pages.UserManagement />} />
                  <Route path="/users/create" element={<Pages.UserCreation />} />
                  <Route path="/users/:userId" element={<Pages.UserProfile />} />
                  <Route path="/users/:userId/edit" element={<Pages.UserEdit />} />
                  <Route path="/support" element={<Pages.SupportPage />} />
                  <Route path="/support/confirmation" element={<Pages.SupportConfirmationPage />} />
                  <Route path="/support/tickets" element={<Pages.TicketsHistoryPage />} />
                  <Route path="*" element={<Pages.NotFound />} />
                </>
              )}
            </Routes>
          </main>
        </div>
      </div>
    </SidebarProvider>
  );
}

function PlatformAdminRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();
  if (isLoading) {
    return <ProtectedAppSkeleton />;
  }
  if (!user || !isPlatformAdmin(user)) {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  return (
    <TooltipProvider>
      <SignedPdfPreviewProvider>
        <Toaster />
        <BootProvider>
        <AuthProvider>
          <BrowserRouter
            future={{
              v7_startTransition: true,
              v7_relativeSplatPath: true,
            }}
          >
            <CompanyProvider>
              <BootGate>
                <Suspense fallback={<RouteSkeleton />}>
                  <Routes>
                    <Route path="/login" element={<Pages.LoginPage />} />
                    <Route
                      path={BADGEUSE_RH_TERMINAL_PATH}
                      element={
                        <Suspense fallback={null}>
                          <BadgeuseTerminalGate />
                        </Suspense>
                      }
                    />
                    <Route
                      path="/badgeuse-rh/scan"
                      element={<Navigate to={BADGEUSE_RH_TERMINAL_PATH} replace />}
                    />
                    <Route path="/forgot-password" element={<Pages.ForgotPasswordPage />} />
                    <Route path="/reset-password" element={<Pages.ResetPasswordPage />} />
                    <Route path="/activation" element={<Pages.ActivationPage />} />
                    <Route
                      path="/super-admin"
                      element={
                        <PlatformAdminRoute>
                          <Pages.SuperAdminLayout />
                        </PlatformAdminRoute>
                      }
                    >
                      <Route index element={<Pages.SuperAdminDashboard />} />
                      <Route path="companies" element={<Pages.SuperAdminCompanies />} />
                      <Route path="companies/:companyId" element={<Pages.SuperAdminCompanyDetails />} />
                      <Route path="groups" element={<Pages.CompanyGroups />} />
                      <Route path="groups/:groupId" element={<Pages.CompanyGroupDetail />} />
                      <Route path="users" element={<Pages.SuperAdminUsers />} />
                      <Route path="activity" element={<Pages.AdminActivityLog />} />
                      <Route path="access" element={<Pages.AdminAccessRH />} />
                      <Route path="admins" element={<Pages.AdminSuperAdminsPage />} />
                      <Route path="collective-agreements" element={<Pages.CollectiveAgreementsCatalog />} />
                      <Route path="rates" element={<Pages.AdminRates />} />
                      <Route path="payroll-settings" element={<Pages.PayrollSettings />} />
                      <Route path="reduction-fillon" element={<Pages.SuperAdminReductionFillon />} />
                      <Route path="scraping" element={<Pages.SuperAdminScraping />} />
                      <Route path="dsn-transmissions" element={<Pages.SuperAdminDsnTransmissions />} />
                      <Route path="dsn-import" element={<Pages.SuperAdminDsnImport />} />
                      <Route path="company-setup" element={<Pages.SuperAdminDsnImport />} />
                      <Route path="accounting-integrations" element={<Pages.SuperAdminAccountingIntegrations />} />
                      <Route path="email-settings" element={<Pages.SuperAdminEmailSettings />} />
                      <Route path="monitoring" element={<Pages.SuperAdminMonitoring />} />
                      <Route path="tests" element={<Pages.SuperAdminTests />} />
                      <Route path="support" element={<Pages.AdminSupportCenter />} />
                      <Route path="support/confirmation" element={<Pages.SupportConfirmationPage />} />
                      <Route path="support/tickets" element={<Pages.AdminSupportCenter />} />
                      <Route path="*" element={<Pages.NotFound />} />
                    </Route>
                    <Route path="/*" element={<ProtectedRoutesWithView />} />
                  </Routes>
                </Suspense>
              </BootGate>
            </CompanyProvider>
          </BrowserRouter>
        </AuthProvider>
      </BootProvider>
      </SignedPdfPreviewProvider>
    </TooltipProvider>
  );
}
