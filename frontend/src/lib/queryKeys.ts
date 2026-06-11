/** Préfixe commun pour isoler le cache par entreprise active */
export function companyQueryKey(companyId: string | undefined, ...parts: unknown[]) {
  return ['company', companyId ?? 'none', ...parts] as const;
}

export const queryKeys = {
  myCompanies: () => ['my-companies'] as const,
  adminGlobalStats: () => ['admin', 'global-stats'] as const,
  adminCompanies: () => ['admin', 'companies'] as const,
  employees: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'employees'),
  employee: (companyId: string | undefined, employeeId: string | undefined) =>
    companyQueryKey(companyId, 'employee', employeeId ?? 'none'),
  employeePayslips: (companyId: string | undefined, employeeId: string | undefined) =>
    companyQueryKey(companyId, 'employee', employeeId ?? 'none', 'payslips'),
  collectiveAgreements: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'collective-agreements'),
  dashboardAll: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'dashboard', 'all'),
  hrDeadlineCandidates: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'hr-deadline-candidates'),
  residencePermitStats: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'dashboard', 'residence-permit-stats'),
  ribAlerts: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'rib-alerts', { unread: true }),
  medicalSettings: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'medical', 'settings'),
  medicalKpis: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'medical', 'kpis'),
  annualReviews: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'annual-reviews'),
  recruitmentSettings: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'recruitment', 'settings'),
  recruitmentCandidates: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'recruitment', 'candidates'),
  pendingSignaturesRh: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'signatures', 'pending-rh'),
  onboardingHubDashboard: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'onboarding', 'hub', 'dashboard'),
  absences: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'absences'),
  planning: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'planning'),
  planningWeek: (companyId: string | undefined, weekStart: string) =>
    companyQueryKey(companyId, 'planning', 'week', weekStart),
  employeesPlanning: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'planning', 'employees'),
  planningShiftTypes: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'planning', 'shift-types'),
  saisies: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'saisies'),
  rates: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'rates'),
  schedules: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'schedules'),
  salaryAdvances: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'salary-advances'),
  employeeLoans: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'employee-loans'),
  employeeLoansSelf: (userId: string | undefined) =>
    ['employee', userId ?? 'none', 'employee-loans'] as const,
  documents: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'documents'),
  employeeDashboard: (userId: string | undefined) =>
    ['employee', userId ?? 'none', 'dashboard'] as const,
  employeeDashboardAbsences: (
    userId: string | undefined,
    year: number,
    month: number
  ) => ['employee', userId ?? 'none', 'dashboard', 'absences', year, month] as const,
  employeeBadgeuseToday: (userId: string | undefined) =>
    ['employee', userId ?? 'none', 'badgeuse', 'today'] as const,
  employeeSalaryAdvances: (userId: string | undefined) =>
    ['employee', userId ?? 'none', 'salary-advances'] as const,
  formationDashboardCerts: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'formation', 'dashboard', 'cert-counts'),
  formationDashboardOverdue: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'formation', 'dashboard', 'overdue'),
  formationDashboardBudget: (companyId: string | undefined, year: number) =>
    companyQueryKey(companyId, 'formation', 'dashboard', 'budget', year),
  formationDashboardAchievement: (companyId: string | undefined, year: number) =>
    companyQueryKey(companyId, 'formation', 'dashboard', 'achievement', year),
  payrollPreflight: (companyId: string | undefined, year: number, month: number) =>
    companyQueryKey(companyId, 'payroll', 'preflight-anomalies', year, month),
} as const;
