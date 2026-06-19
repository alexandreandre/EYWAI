import { Suspense } from 'react';
import { Navigate, Route } from 'react-router-dom';
import * as Pages from '@/app/lazyPages';
import { EmployeeCalendarGridSkeleton } from '@/components/employee-calendar/EmployeeCalendarGridSkeleton';
import { EmployeeAbsencesPageSkeleton } from '@/components/skeletons/EmployeeAbsencesPageSkeleton';
import { EmployeeDashboardSkeleton } from '@/components/skeletons/EmployeeDashboardSkeleton';
import { TableSkeleton } from '@/components/skeletons/TableSkeleton';

/**
 * Routes espace collaborateur (partagées entre rôle collaborateur et vue collaborateur RH).
 * Une seule source pour éviter la duplication dans App.tsx.
 */
export const employeeCollaboratorRoutes = (
  <>
    <Route
      path="/"
      element={
        <Suspense fallback={<EmployeeDashboardSkeleton />}>
          <Pages.EmployeeDashboard />
        </Suspense>
      }
    />
    <Route path="/profile" element={<Pages.ProfilePage />} />
    <Route
      path="/payslips"
      element={
        <Suspense fallback={<TableSkeleton rows={8} columns={4} />}>
          <Pages.PayslipsPage />
        </Suspense>
      }
    />
    <Route path="/employee/payslips/:payslipId" element={<Pages.EmployeePayslipDetail />} />
    <Route path="/badgeuse" element={<Pages.EmployeeBadgeusePage />} />
    <Route path="/annual-reviews" element={<Pages.EmployeeAnnualReviews />} />
    <Route path="/annual-reviews/:reviewId" element={<Pages.EmployeeAnnualReviewDetail />} />
    <Route path="/employee/formation" element={<Pages.EmployeeFormationPage />} />
    <Route path="/habilitations" element={<Pages.EmployeeFormationLegacyRedirect />} />
    <Route path="/objectives" element={<Pages.EmployeeFormationLegacyRedirect />} />
    <Route path="/catalogue-formations" element={<Pages.EmployeeFormationLegacyRedirect />} />
    <Route
      path="/absences"
      element={
        <Suspense fallback={<EmployeeAbsencesPageSkeleton />}>
          <Pages.EmployeeAbsencesPage />
        </Suspense>
      }
    />
    <Route path="/mon-cet" element={<Pages.MonCet />} />
    <Route path="/employee/leaves/new" element={<Navigate to="/absences" replace />} />
    <Route path="/employee/planning" element={<Pages.EmployeePlanning />} />
    <Route
      path="/calendar"
      element={
        <Suspense fallback={<EmployeeCalendarGridSkeleton />}>
          <Pages.EmployeeCalendarPage />
        </Suspense>
      }
    />
    <Route path="/expenses" element={<Pages.ExpensesPage />} />
    <Route path="/salary-advances" element={<Pages.SalaryAdvancesPage />} />
    <Route path="/employee-loans" element={<Pages.EmployeeLoansPage />} />
    <Route path="/employee/documents" element={<Pages.EmployeeCollaboratorDocumentsPage />} />
    <Route path="/employee/participation" element={<Pages.EmployeeParticipationPage />} />
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
);
