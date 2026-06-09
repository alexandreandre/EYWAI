import { lazy } from 'react';

export const LoginPage = lazy(() => import('@/pages/rh/auth/Login'));
export const ForgotPasswordPage = lazy(() => import('@/pages/rh/auth/ForgotPassword'));
export const ResetPasswordPage = lazy(() => import('@/pages/rh/auth/ResetPassword'));

export const RhDashboard = lazy(() => import('@/pages/rh/Dashboard'));
export const Employees = lazy(() => import('@/pages/rh/Employees'));
export const Teams = lazy(() => import('@/pages/rh/Teams'));
export const EmployeeDetail = lazy(() => import('@/pages/rh/EmployeeDetail'));
export const Rates = lazy(() => import('@/pages/rh/Rates'));
export const Payroll = lazy(() => import('@/pages/rh/Payroll'));
export const PayrollGenerate = lazy(() => import('@/pages/rh/PayrollGenerate'));
export const PayrollDetail = lazy(() => import('@/pages/rh/PayrollDetail'));
export const PayslipEdit = lazy(() => import('@/pages/rh/PayslipEdit'));
export const Saisies = lazy(() => import('@/pages/rh/Saisies'));
export const SalarySeizures = lazy(() => import('@/pages/rh/SalarySeizures'));
export const SalaryAdvances = lazy(() => import('@/pages/rh/SalaryAdvances'));
export const EmployeeLoans = lazy(() => import('@/pages/rh/EmployeeLoans'));
export const RhAbsencesPage = lazy(() => import('@/pages/rh/Absences'));
export const Planning = lazy(() => import('@/pages/rh/Planning'));
export const RhExpensesPage = lazy(() => import('@/pages/rh/Expenses'));
export const RhSchedulesPage = lazy(() => import('@/pages/rh/Schedules'));
export const CompanyPage = lazy(() => import('@/pages/rh/CompanyPage'));
export const EmployeeExits = lazy(() => import('@/pages/rh/EmployeeExits'));
export const ExitDocumentEdit = lazy(() => import('@/pages/rh/ExitDocumentEdit'));
export const Exports = lazy(() => import('@/pages/rh/Exports'));
export const ResidencePermits = lazy(() => import('@/pages/rh/ResidencePermits'));
export const MedicalFollowUp = lazy(() => import('@/pages/rh/MedicalFollowUp'));
export const AnnualReviews = lazy(() => import('@/pages/rh/AnnualReviews'));
export const AnnualReviewDetail = lazy(() => import('@/pages/rh/AnnualReviewDetail'));
export const AugmentationsEtPromotions = lazy(() => import('@/pages/rh/AugmentationsEtPromotions'));
export const PromotionDetail = lazy(() => import('@/pages/rh/PromotionDetail'));
export const CSE = lazy(() => import('@/pages/rh/CSE'));
export const Recruitment = lazy(() => import('@/pages/rh/Recruitment'));
export const BadgeuseRhPage = lazy(() => import('@/pages/rh/BadgeuseRh'));
export const BadgeuseRhScanPage = lazy(() => import('@/pages/rh/BadgeuseRhScan'));
export const Simulation = lazy(() => import('@/pages/rh/Simulation'));
export const NotFound = lazy(() => import('@/pages/rh/NotFound'));
export const GroupDashboard = lazy(() => import('@/pages/rh/GroupDashboard').then((m) => ({ default: m.GroupDashboard })));
export const UserManagement = lazy(() => import('@/pages/rh/UserManagement'));
export const UserProfile = lazy(() => import('@/pages/rh/UserProfile'));
export const UserCreation = lazy(() => import('@/pages/rh/UserCreation'));
export const UserEdit = lazy(() => import('@/pages/rh/UserEdit'));

export const OnboardingPage = lazy(() => import('@/pages/rh/onboarding/OnboardingPage'));
export const OnboardingHubPage = lazy(() =>
  import('@/pages/rh/onboarding/OnboardingPage').then((m) => ({ default: m.OnboardingHubPage })),
);
export const EmployeeOnboardingRedirect = lazy(() =>
  import('@/pages/rh/onboarding/OnboardingPage').then((m) => ({ default: m.EmployeeOnboardingRedirect })),
);

export const EmployeeDashboard = lazy(() => import('@/pages/employee/Dashboard'));
export const ProfilePage = lazy(() => import('@/pages/employee/Profile'));
export const PayslipsPage = lazy(() => import('@/pages/employee/Payslips'));
export const EmployeePayslipDetail = lazy(() => import('@/pages/employee/PayslipDetail'));
export const EmployeeAbsencesPage = lazy(() => import('@/pages/employee/Absences'));
export const EmployeePlanning = lazy(() => import('@/pages/employee/EmployeePlanning'));
export const EmployeeCalendarPage = lazy(() => import('@/pages/employee/Calendar'));
export const EmployeeBadgeusePage = lazy(() => import('@/pages/employee/Badgeuse'));
export const ExpensesPage = lazy(() => import('@/pages/employee/Expenses'));
export const SalaryAdvancesPage = lazy(() => import('@/pages/employee/SalaryAdvances'));
export const EmployeeLoansPage = lazy(() => import('@/pages/employee/EmployeeLoans'));
export const EmployeeAnnualReviews = lazy(() => import('@/pages/employee/AnnualReviews'));
export const EmployeeFormationPage = lazy(() => import('@/pages/employee/EmployeeFormationPage'));
export const EmployeeAnnualReviewDetail = lazy(() => import('@/pages/employee/AnnualReviewDetail'));
export const EmployeeCSE = lazy(() => import('@/pages/employee/CSE'));
export const EmployeeMedicalFollowUp = lazy(() => import('@/pages/employee/MedicalFollowUp'));
export const EmployeeCollaboratorDocumentsPage = lazy(() => import('@/pages/employee/Documents'));

export const SuperAdminLayout = lazy(() => import('@/pages/admin/super/SuperAdminLayout'));
export const SuperAdminDashboard = lazy(() => import('@/pages/admin/super/SuperAdminDashboard'));
export const AdminActivityLog = lazy(() => import('@/pages/admin/eywai/ActivityLog'));
export const AdminAccessRH = lazy(() => import('@/pages/admin/eywai/AccessRH'));
export const AdminSupportCenter = lazy(() => import('@/pages/admin/eywai/SupportCenter'));
export const AdminSuperAdminsPage = lazy(() => import('@/pages/admin/eywai/SuperAdminsPage'));
export const SuperAdminCompanies = lazy(() => import('@/pages/admin/super/Companies'));
export const SuperAdminCompanyDetails = lazy(() => import('@/pages/admin/super/CompanyDetails'));
export const SuperAdminUsers = lazy(() => import('@/pages/admin/super/Users'));
export const SuperAdminMonitoring = lazy(() => import('@/pages/admin/super/Monitoring'));
export const SuperAdminTests = lazy(() => import('@/pages/admin/super/Tests'));
export const SuperAdminReductionFillon = lazy(() => import('@/pages/admin/super/ReductionFillon'));
export const AdminRates = lazy(() => import('@/pages/admin/eywai/RatesAdmin'));
export const SuperAdminScraping = lazy(() => import('@/pages/admin/super/Scraping'));
export const SuperAdminDsnTransmissions = lazy(() => import('@/pages/admin/eywai/DsnTransmissions'));
export const SuperAdminEmailSettings = lazy(() => import('@/pages/admin/eywai/EmailSettings'));
export const CollectiveAgreementsCatalog = lazy(() => import('@/pages/admin/super/CollectiveAgreementsCatalog'));
export const CompanyGroups = lazy(() => import('@/pages/admin/super/CompanyGroups'));
export const CompanyGroupDetail = lazy(() => import('@/pages/admin/super/CompanyGroupDetail'));

export const SupportPage = lazy(() => import('@/pages/rh/support/SupportPage'));
export const SupportConfirmationPage = lazy(() => import('@/pages/rh/support/SupportConfirmationPage'));
export const TicketsHistoryPage = lazy(() => import('@/pages/rh/support/TicketsHistoryPage'));
export const FormationPage = lazy(() => import('@/pages/rh/formation/FormationPage'));
export const LeaveRequests = lazy(() => import('@/pages/rh/manager/LeaveRequests'));
export const RhDocumentsPage = lazy(() => import('@/pages/rh/Documents'));
export const MeetingDetailPage = lazy(() => import('@/pages/rh/cse/MeetingDetail'));
export const AnalyticsPage = lazy(() => import('@/pages/rh/Analytics'));
export const AnalyticsPaiePage = lazy(() => import('@/pages/rh/AnalyticsPaie'));
export const AnalyticsGestionPage = lazy(() => import('@/pages/rh/AnalyticsGestion'));

export {
  EmployeeFormationLegacyRedirect,
  RhFormationLegacyRedirect,
} from '@/pages/rh/formation/formationRedirects';
