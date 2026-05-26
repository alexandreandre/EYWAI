// src/App.tsx

import { Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { CompanyProvider, useCompany } from './contexts/CompanyContext';
import { ViewProvider, useView } from './contexts/ViewContext';
import { BootProvider } from './contexts/BootContext';
import { BootGate } from '@/components/BootGate';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import { AppSidebar } from '@/components/ui/app-sidebar';
import { SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar';
import { Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { CompanySwitcher } from '@/components/CompanySwitcher';
import { ErrorBoundaryClass } from '@/components/ErrorBoundary';
import { EmployeeSidebar } from '@/components/ui/employee-sidebar';
import { RouteSkeleton } from '@/components/skeletons/RouteSkeleton';
import * as Pages from '@/app/lazyPages';

function EmployeeLayout() {
  const { accessibleCompanies } = useCompany();
  const showCompanySwitcher =
    accessibleCompanies && accessibleCompanies.length > 1;

  return (
    <SidebarProvider>
      <div className="grid min-h-screen w-full md:grid-cols-[auto_1fr]">
        <EmployeeSidebar />
        <div className="flex min-w-0 flex-col flex-1">
          <header className="sticky top-0 z-10 flex h-14 items-center gap-4 border-b bg-background px-4 md:hidden">
            <SidebarTrigger>
              <Button variant="ghost" size="icon" className="md:hidden">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Toggle Menu</span>
              </Button>
            </SidebarTrigger>
            <div className="flex-1 min-w-0">
              <img src="/Colorplast.png" alt="Logo Colorplast" className="h-8 w-auto" />
            </div>
            {showCompanySwitcher && <CompanySwitcher />}
          </header>
          {showCompanySwitcher && (
            <div className="hidden md:flex items-center gap-4 border-b bg-background px-6 py-3">
              <div className="flex-1" />
              <CompanySwitcher />
            </div>
          )}
          <main className="min-w-0 flex-1 overflow-auto overflow-x-auto p-6 lg:p-8">
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

  if (isLoading) {
    return null;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  const isSuperAdmin = user.is_super_admin === true || user.role === 'super_admin';
  if (!isSuperAdmin && isCompanyLoading) {
    return null;
  }

  if (user.role === 'collaborateur') {
    return (
      <Routes>
        <Route element={<EmployeeLayout />}>
          <Route path="/" element={<Pages.EmployeeDashboard />} />
          <Route path="/profile" element={<Pages.ProfilePage />} />
          <Route path="/payslips" element={<Pages.PayslipsPage />} />
          <Route path="/employee/payslips/:payslipId" element={<Pages.EmployeePayslipDetail />} />
          <Route path="/badgeuse" element={<Pages.EmployeeBadgeusePage />} />
          <Route path="/annual-reviews" element={<Pages.EmployeeAnnualReviews />} />
          <Route path="/annual-reviews/:reviewId" element={<Pages.EmployeeAnnualReviewDetail />} />
          <Route path="/employee/formation" element={<Pages.EmployeeFormationPage />} />
          <Route path="/habilitations" element={<Pages.EmployeeFormationLegacyRedirect />} />
          <Route path="/objectives" element={<Pages.EmployeeFormationLegacyRedirect />} />
          <Route path="/catalogue-formations" element={<Pages.EmployeeFormationLegacyRedirect />} />
          <Route path="/absences" element={<Pages.EmployeeAbsencesPage />} />
          <Route path="/employee/leaves/new" element={<Navigate to="/absences" replace />} />
          <Route path="/employee/planning" element={<Pages.EmployeePlanning />} />
          <Route path="/calendar" element={<Pages.EmployeeCalendarPage />} />
          <Route path="/expenses" element={<Pages.ExpensesPage />} />
          <Route path="/salary-advances" element={<Pages.SalaryAdvancesPage />} />
          <Route path="/employee/documents" element={<Pages.EmployeeCollaboratorDocumentsPage />} />
          <Route path="/documents" element={<Navigate to="/employee/documents" replace />} />
          <Route path="/medical-follow-up" element={<Pages.EmployeeMedicalFollowUp />} />
          <Route path="/cse/meetings/:meetingId" element={<Pages.MeetingDetailPage />} />
          <Route path="/cse" element={<Pages.EmployeeCSE />} />
          <Route path="/employee/onboarding" element={<Pages.EmployeeOnboardingRedirect />} />
          <Route path="/onboarding/:employeeId" element={<Pages.OnboardingPage />} />
          <Route path="/support" element={<Pages.SupportPage />} />
          <Route path="/support/confirmation" element={<Pages.SupportConfirmationPage />} />
          <Route path="/support/tickets" element={<Pages.TicketsHistoryPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    );
  }

  const showCompanySwitcher = accessibleCompanies && accessibleCompanies.length > 1;
  const isCollaborateurRhView = isCollaborateurRh && viewMode === 'collaborateur';

  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-muted/40">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
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
              <CompanySwitcher />
            </header>
          )}
          {showCompanySwitcher && (
            <div className="hidden md:flex items-center gap-4 border-b bg-background px-6 py-3">
              <div className="flex-1" />
              <CompanySwitcher />
            </div>
          )}
          <main className="min-w-0 flex-1 overflow-x-auto overflow-y-auto bg-background p-6 lg:p-8">
            <Routes>
              {isCollaborateurRhView ? (
                <>
                  <Route path="/" element={<Pages.EmployeeDashboard />} />
                  <Route path="/profile" element={<Pages.ProfilePage />} />
                  <Route path="/payslips" element={<Pages.PayslipsPage />} />
                  <Route path="/employee/payslips/:payslipId" element={<Pages.EmployeePayslipDetail />} />
                  <Route path="/badgeuse" element={<Pages.EmployeeBadgeusePage />} />
                  <Route path="/annual-reviews" element={<Pages.EmployeeAnnualReviews />} />
                  <Route path="/annual-reviews/:reviewId" element={<Pages.EmployeeAnnualReviewDetail />} />
                  <Route path="/employee/formation" element={<Pages.EmployeeFormationPage />} />
                  <Route path="/habilitations" element={<Pages.EmployeeFormationLegacyRedirect />} />
                  <Route path="/objectives" element={<Pages.EmployeeFormationLegacyRedirect />} />
                  <Route path="/catalogue-formations" element={<Pages.EmployeeFormationLegacyRedirect />} />
                  <Route path="/absences" element={<Pages.EmployeeAbsencesPage />} />
                  <Route path="/employee/leaves/new" element={<Navigate to="/absences" replace />} />
                  <Route path="/employee/planning" element={<Pages.EmployeePlanning />} />
                  <Route path="/calendar" element={<Pages.EmployeeCalendarPage />} />
                  <Route path="/expenses" element={<Pages.ExpensesPage />} />
                  <Route path="/salary-advances" element={<Pages.SalaryAdvancesPage />} />
                  <Route path="/employee/documents" element={<Pages.EmployeeCollaboratorDocumentsPage />} />
                  <Route path="/documents" element={<Navigate to="/employee/documents" replace />} />
                  <Route path="/medical-follow-up" element={<Pages.EmployeeMedicalFollowUp />} />
                  <Route path="/cse/meetings/:meetingId" element={<Pages.MeetingDetailPage />} />
                  <Route path="/cse" element={<Pages.EmployeeCSE />} />
                  <Route path="/employee/onboarding" element={<Pages.EmployeeOnboardingRedirect />} />
                  <Route path="/onboarding/:employeeId" element={<Pages.OnboardingPage />} />
                  <Route path="/support" element={<Pages.SupportPage />} />
                  <Route path="/support/confirmation" element={<Pages.SupportConfirmationPage />} />
                  <Route path="/support/tickets" element={<Pages.TicketsHistoryPage />} />
                  <Route path="*" element={<Navigate to="/" replace />} />
                </>
              ) : (
                <>
                  <Route path="/" element={<Pages.RhDashboard />} />
                  <Route path="/analytics" element={<Pages.AnalyticsPage />} />
                  <Route path="/analytics-paie" element={<Pages.AnalyticsPaiePage />} />
                  <Route path="/analytics-gestion" element={<Pages.AnalyticsGestionPage />} />
                  <Route path="/employees" element={<Pages.Employees />} />
                  <Route path="/teams" element={<Pages.Teams />} />
                  <Route path="/employees/:employeeId" element={<Pages.EmployeeDetail />} />
                  <Route path="/saisies" element={<Pages.Saisies />} />
                  <Route path="/salary-seizures" element={<Pages.SalarySeizures />} />
                  <Route path="/salary-advances" element={<Pages.SalaryAdvances />} />
                  <Route path="/rates" element={<Pages.Rates />} />
                  <Route path="/payroll" element={<Pages.Payroll />} />
                  <Route path="/payroll/:employeeId" element={<Pages.PayrollDetail />} />
                  <Route path="/payslips/:payslipId/edit" element={<Pages.PayslipEdit />} />
                  <Route path="/leaves" element={<Pages.RhAbsencesPage />} />
                  <Route path="/employee/leaves/new" element={<Navigate to="/leaves" replace />} />
                  <Route path="/planning" element={<Pages.Planning />} />
                  <Route path="/expenses" element={<Pages.RhExpensesPage />} />
                  <Route path="/schedules" element={<Pages.RhSchedulesPage />} />
                  <Route path="/employee-exits" element={<Pages.EmployeeExits />} />
                  <Route path="/employee-exits/:exitId/documents/:documentId/edit" element={<Pages.ExitDocumentEdit />} />
                  <Route path="/residence-permits" element={<Pages.ResidencePermits />} />
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
                  <Route path="/badgeuse-rh/scan" element={<Navigate to="/badgeuse-rh" replace />} />
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

export default function App() {
  return (
    <TooltipProvider>
      <Toaster />
      <BootProvider>
        <AuthProvider>
          <CompanyProvider>
            <BrowserRouter>
              <BootGate>
                <Suspense fallback={<RouteSkeleton />}>
                  <Routes>
                    <Route path="/login" element={<Pages.LoginPage />} />
                    <Route path="/forgot-password" element={<Pages.ForgotPasswordPage />} />
                    <Route path="/reset-password" element={<Pages.ResetPasswordPage />} />
                    <Route path="/super-admin" element={<Pages.SuperAdminLayout />}>
                      <Route index element={<Pages.SuperAdminDashboard />} />
                      <Route path="companies" element={<Pages.SuperAdminCompanies />} />
                      <Route path="companies/:companyId" element={<Pages.SuperAdminCompanyDetails />} />
                      <Route path="groups" element={<Pages.CompanyGroups />} />
                      <Route path="groups/:groupId" element={<Pages.CompanyGroupDetail />} />
                      <Route path="users" element={<Pages.SuperAdminUsers />} />
                      <Route path="collective-agreements" element={<Pages.CollectiveAgreementsCatalog />} />
                      <Route path="reduction-fillon" element={<Pages.SuperAdminReductionFillon />} />
                      <Route path="scraping" element={<Pages.SuperAdminScraping />} />
                      <Route path="monitoring" element={<Pages.SuperAdminMonitoring />} />
                      <Route path="tests" element={<Pages.SuperAdminTests />} />
                      <Route path="support" element={<Pages.SupportPage />} />
                      <Route path="support/confirmation" element={<Pages.SupportConfirmationPage />} />
                      <Route path="support/tickets" element={<Pages.TicketsHistoryPage />} />
                      <Route path="*" element={<Pages.NotFound />} />
                    </Route>
                    <Route path="/*" element={<ProtectedRoutesWithView />} />
                  </Routes>
                </Suspense>
              </BootGate>
            </BrowserRouter>
          </CompanyProvider>
        </AuthProvider>
      </BootProvider>
    </TooltipProvider>
  );
}
