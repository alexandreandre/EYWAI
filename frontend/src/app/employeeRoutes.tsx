import { Navigate, Route } from 'react-router-dom';
import * as Pages from '@/app/lazyPages';

/**
 * Routes espace collaborateur (partagées entre rôle collaborateur et vue collaborateur RH).
 * Une seule source pour éviter la duplication dans App.tsx.
 */
export const employeeCollaboratorRoutes = (
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
);
