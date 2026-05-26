import { lazy } from 'react';

export const LoginPage = lazy(() => import('@/pages/Login'));
export const ForgotPasswordPage = lazy(() => import('@/pages/ForgotPassword'));
export const ResetPasswordPage = lazy(() => import('@/pages/ResetPassword'));

export const RhDashboard = lazy(() => import('@/pages/Dashboard'));
export const Employees = lazy(() => import('@/pages/Employees'));
export const Teams = lazy(() => import('@/pages/Teams'));
export const EmployeeDetail = lazy(() => import('@/pages/EmployeeDetail'));
export const Rates = lazy(() => import('@/pages/Rates'));
export const Payroll = lazy(() => import('@/pages/Payroll'));
export const PayrollDetail = lazy(() => import('@/pages/PayrollDetail'));
export const PayslipEdit = lazy(() => import('@/pages/PayslipEdit'));
export const Saisies = lazy(() => import('@/pages/Saisies'));
export const SalarySeizures = lazy(() => import('@/pages/SalarySeizures'));
export const SalaryAdvances = lazy(() => import('@/pages/SalaryAdvances'));
export const RhAbsencesPage = lazy(() => import('@/pages/Absences'));
export const Planning = lazy(() => import('@/pages/Planning'));
export const RhExpensesPage = lazy(() => import('@/pages/Expenses'));
export const RhSchedulesPage = lazy(() => import('@/pages/Schedules'));
export const CompanyPage = lazy(() => import('@/pages/CompanyPage'));
export const EmployeeExits = lazy(() => import('@/pages/EmployeeExits'));
export const ExitDocumentEdit = lazy(() => import('@/pages/ExitDocumentEdit'));
export const Exports = lazy(() => import('@/pages/Exports'));
export const ResidencePermits = lazy(() => import('@/pages/ResidencePermits'));
export const MedicalFollowUp = lazy(() => import('@/pages/MedicalFollowUp'));
export const AnnualReviews = lazy(() => import('@/pages/AnnualReviews'));
export const AnnualReviewDetail = lazy(() => import('@/pages/AnnualReviewDetail'));
export const AugmentationsEtPromotions = lazy(() => import('@/pages/AugmentationsEtPromotions'));
export const PromotionDetail = lazy(() => import('@/pages/PromotionDetail'));
export const CSE = lazy(() => import('@/pages/CSE'));
export const Recruitment = lazy(() => import('@/pages/Recruitment'));
export const BadgeuseRhPage = lazy(() => import('@/pages/BadgeuseRh'));
export const BadgeuseRhScanPage = lazy(() => import('@/pages/BadgeuseRhScan'));
export const Simulation = lazy(() => import('@/pages/Simulation'));
export const NotFound = lazy(() => import('@/pages/NotFound'));
export const GroupDashboard = lazy(() => import('@/pages/GroupDashboard').then((m) => ({ default: m.GroupDashboard })));
export const UserManagement = lazy(() => import('@/pages/UserManagement'));
export const UserProfile = lazy(() => import('@/pages/UserProfile'));
export const UserCreation = lazy(() => import('@/pages/UserCreation'));
export const UserEdit = lazy(() => import('@/pages/UserEdit'));

export const OnboardingPage = lazy(() => import('@/pages/OnboardingPage'));
export const OnboardingHubPage = lazy(() =>
  import('@/pages/OnboardingPage').then((m) => ({ default: m.OnboardingHubPage })),
);
export const EmployeeOnboardingRedirect = lazy(() =>
  import('@/pages/OnboardingPage').then((m) => ({ default: m.EmployeeOnboardingRedirect })),
);

export const EmployeeDashboard = lazy(() => import('@/pages/employee/Dashboard'));
export const ProfilePage = lazy(() => import('@/pages/employee/Profile'));
export const PayslipsPage = lazy(() => import('@/pages/employee/Payslips'));
export const EmployeePayslipDetail = lazy(() => import('@/pages/employee/PayslipDetail'));
export const EmployeeAbsencesPage = lazy(() => import('@/pages/employee/Absences'));
export const EmployeePlanning = lazy(() => import('@/pages/EmployeePlanning'));
export const EmployeeCalendarPage = lazy(() => import('@/pages/employee/Calendar'));
export const EmployeeBadgeusePage = lazy(() => import('@/pages/employee/Badgeuse'));
export const ExpensesPage = lazy(() => import('@/pages/employee/Expenses'));
export const SalaryAdvancesPage = lazy(() => import('@/pages/employee/SalaryAdvances'));
export const EmployeeAnnualReviews = lazy(() => import('@/pages/employee/AnnualReviews'));
export const EmployeeFormationPage = lazy(() => import('@/pages/employee/EmployeeFormationPage'));
export const EmployeeAnnualReviewDetail = lazy(() => import('@/pages/employee/AnnualReviewDetail'));
export const EmployeeCSE = lazy(() => import('@/pages/employee/CSE'));
export const EmployeeMedicalFollowUp = lazy(() => import('@/pages/employee/MedicalFollowUp'));
export const EmployeeCollaboratorDocumentsPage = lazy(() => import('@/pages/employee/Documents'));

export const SuperAdminLayout = lazy(() => import('@/pages/super-admin/SuperAdminLayout'));
export const SuperAdminDashboard = lazy(() => import('@/pages/super-admin/SuperAdminDashboard'));
export const SuperAdminCompanies = lazy(() => import('@/pages/super-admin/Companies'));
export const SuperAdminCompanyDetails = lazy(() => import('@/pages/super-admin/CompanyDetails'));
export const SuperAdminUsers = lazy(() => import('@/pages/super-admin/Users'));
export const SuperAdminMonitoring = lazy(() => import('@/pages/super-admin/Monitoring'));
export const SuperAdminTests = lazy(() => import('@/pages/super-admin/Tests'));
export const SuperAdminReductionFillon = lazy(() => import('@/pages/super-admin/ReductionFillon'));
export const SuperAdminScraping = lazy(() => import('@/pages/super-admin/Scraping'));
export const CollectiveAgreementsCatalog = lazy(() => import('@/pages/super-admin/CollectiveAgreementsCatalog'));
export const CompanyGroups = lazy(() => import('@/pages/super-admin/CompanyGroups'));
export const CompanyGroupDetail = lazy(() => import('@/pages/super-admin/CompanyGroupDetail'));

export const SupportPage = lazy(() => import('@/pages/support/SupportPage'));
export const SupportConfirmationPage = lazy(() => import('@/pages/support/SupportConfirmationPage'));
export const TicketsHistoryPage = lazy(() => import('@/pages/support/TicketsHistoryPage'));
export const FormationPage = lazy(() => import('@/pages/formation/FormationPage'));
export const LeaveRequests = lazy(() => import('@/pages/manager/LeaveRequests'));
export const RhDocumentsPage = lazy(() => import('@/pages/Documents'));
export const MeetingDetailPage = lazy(() => import('@/pages/cse/MeetingDetail'));
export const AnalyticsPage = lazy(() => import('@/pages/Analytics'));
export const AnalyticsPaiePage = lazy(() => import('@/pages/AnalyticsPaie'));
export const AnalyticsGestionPage = lazy(() => import('@/pages/AnalyticsGestion'));

export {
  EmployeeFormationLegacyRedirect,
  RhFormationLegacyRedirect,
} from '@/pages/formation/formationRedirects';
