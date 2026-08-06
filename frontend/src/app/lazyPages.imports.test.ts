import { describe, expect, it } from 'vitest';
import fs from 'fs';
import path from 'path';

/** Module paths that must resolve after pages/ reorganization. */
const PAGE_MODULE_PATHS = [
  '@/pages/rh/auth/Login',
  '@/pages/rh/auth/ForgotPassword',
  '@/pages/rh/auth/ResetPassword',
  '@/pages/rh/Dashboard',
  '@/pages/rh/Employees',
  '@/pages/rh/Teams',
  '@/pages/rh/EmployeeDetail',
  '@/pages/rh/Rates',
  '@/pages/rh/Payroll',
  '@/pages/rh/PayrollDetail',
  '@/pages/rh/PayslipEdit',
  '@/pages/rh/Saisies',
  '@/pages/rh/SalarySeizures',
  '@/pages/rh/SalaryAdvances',
  '@/pages/rh/Absences',
  '@/pages/rh/Planning',
  '@/pages/rh/Expenses',
  '@/pages/rh/Schedules',
  '@/pages/rh/CompanyPage',
  '@/pages/rh/EmployeeExits',
  '@/pages/rh/ExitDocumentEdit',
  '@/pages/rh/Exports',
  '@/pages/rh/ResidencePermits',
  '@/pages/rh/TauxPas',
  '@/pages/rh/TrialPeriods',
  '@/pages/rh/MedicalFollowUp',
  '@/pages/rh/AnnualReviews',
  '@/pages/rh/AnnualReviewDetail',
  '@/pages/rh/AugmentationsEtPromotions',
  '@/pages/rh/PromotionDetail',
  '@/pages/rh/CSE',
  '@/pages/rh/Recruitment',
  '@/pages/rh/BadgeuseRh',
  '@/pages/rh/BadgeuseRhScan',
  '@/pages/rh/Simulation',
  '@/pages/rh/NotFound',
  '@/pages/rh/GroupDashboard',
  '@/pages/rh/UserManagement',
  '@/pages/rh/UserProfile',
  '@/pages/rh/UserCreation',
  '@/pages/rh/UserEdit',
  '@/pages/rh/onboarding/OnboardingPage',
  '@/pages/employee/Dashboard',
  '@/pages/employee/Profile',
  '@/pages/employee/Payslips',
  '@/pages/employee/PayslipDetail',
  '@/pages/employee/Absences',
  '@/pages/employee/EmployeePlanning',
  '@/pages/employee/Calendar',
  '@/pages/employee/Badgeuse',
  '@/pages/employee/Expenses',
  '@/pages/employee/SalaryAdvances',
  '@/pages/employee/AnnualReviews',
  '@/pages/employee/EmployeeFormationPage',
  '@/pages/employee/AnnualReviewDetail',
  '@/pages/employee/CSE',
  '@/pages/employee/MedicalFollowUp',
  '@/pages/employee/Documents',
  '@/pages/admin/super/SuperAdminLayout',
  '@/pages/admin/super/SuperAdminDashboard',
  '@/pages/admin/eywai/ActivityLog',
  '@/pages/admin/eywai/AccessRH',
  '@/pages/admin/eywai/SupportCenter',
  '@/pages/admin/eywai/SuperAdminsPage',
  '@/pages/admin/super/Companies',
  '@/pages/admin/super/CompanyDetails',
  '@/pages/admin/super/Users',
  '@/pages/admin/super/Monitoring',
  '@/pages/admin/super/Tests',
  '@/pages/admin/super/ReductionFillon',
  '@/pages/admin/super/Scraping',
  '@/pages/admin/super/CollectiveAgreementsCatalog',
  '@/pages/admin/super/CompanyGroups',
  '@/pages/admin/super/CompanyGroupDetail',
  '@/pages/rh/support/SupportPage',
  '@/pages/rh/support/SupportConfirmationPage',
  '@/pages/rh/support/TicketsHistoryPage',
  '@/pages/rh/formation/FormationPage',
  '@/pages/rh/manager/LeaveRequests',
  '@/pages/rh/Documents',
  '@/pages/rh/cse/MeetingDetail',
  '@/pages/rh/Analytics',
  '@/pages/rh/AnalyticsPaie',
  '@/pages/rh/AnalyticsGestion',
  '@/features/formation/components/tabs/PilotageTab',
  '@/features/formation/components/tabs/FormationsTab',
  '@/features/formation/components/tabs/ConformiteTab',
  '@/features/formation/components/tabs/DeveloppementTab',
  '@/features/formation/components/tabs/ParametresTab',
];

function toFile(modulePath: string): string {
  const rel = modulePath.replace(/^@\//, '');
  const base = path.resolve(__dirname, '..', rel);
  if (fs.existsSync(`${base}.tsx`)) return `${base}.tsx`;
  if (fs.existsSync(`${base}.ts`)) return `${base}.ts`;
  return `${base}.tsx`;
}

describe('lazyPages module paths', () => {
  for (const modulePath of PAGE_MODULE_PATHS) {
    it(`resolves ${modulePath}`, async () => {
      const file = toFile(modulePath);
      expect(fs.existsSync(file), `missing file for ${modulePath}: ${file}`).toBe(true);
      await expect(import(modulePath)).resolves.toBeDefined();
    });
  }
});
