/** Préfixe commun pour isoler le cache par entreprise active */
export function companyQueryKey(companyId: string | undefined, ...parts: unknown[]) {
  return ['company', companyId ?? 'none', ...parts] as const;
}

export const queryKeys = {
  employees: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'employees'),
  dashboardAll: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'dashboard', 'all'),
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
  absences: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'absences'),
  planning: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'planning'),
  saisies: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'saisies'),
  rates: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'rates'),
  schedules: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'schedules'),
  salaryAdvances: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'salary-advances'),
  documents: (companyId: string | undefined) =>
    companyQueryKey(companyId, 'documents'),
} as const;
