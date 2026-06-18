import type { QueryClient } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { fetchEmployeesSummary } from '@/api/employees';
import { getWeekPlanning, getShiftTypes } from '@/api/planning';
import { getAllAnnualReviews } from '@/api/annualReviews';
import { getMedicalSettings, getKPIs } from '@/api/medicalFollowUp';
import { getCandidates, getRecruitmentSettings } from '@/api/recruitment';
import * as ribAlertsApi from '@/api/ribAlerts';
import { getPendingSignaturesRH } from '@/api/signatures';
import { getAdminGlobalStats } from '@/api/adminEYWAI';
import { queryKeys } from '@/lib/queryKeys';
import { currentWeekStartIso } from '@/lib/planningWeek';
import { isPlatformAdmin, type PlatformAdminUser } from '@/lib/platformAdmin';
import type { CompanyAccess } from '@/contexts/CompanyContext';
import {
  prefetchEmployeeCritical,
  prefetchEmployeeSecondary,
} from '@/lib/prefetchEmployee';

type PrefetchUser = PlatformAdminUser & {
  id: string;
  role?: string;
};

export type BootPrefetchProgress = {
  label: string;
  progress: number;
};

function isRhLikeRole(user: PrefetchUser): boolean {
  if (isPlatformAdmin(user)) return true;
  return (
    user.role === 'rh' ||
    user.role === 'admin' ||
    user.role === 'collaborateur_rh' ||
    user.role === 'custom'
  );
}

function isCollaborateurRole(user: PrefetchUser): boolean {
  return user.role === 'collaborateur';
}

/** Données critiques affichées à l’ouverture (dashboard + liste salariés). */
function prefetchRhCritical(queryClient: QueryClient, companyId: string) {
  return Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: queryKeys.dashboardAll(companyId),
      queryFn: async () => (await apiClient.get('/api/dashboard/all')).data,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.employees(companyId),
      queryFn: () => fetchEmployeesSummary('all'),
    }),
  ]);
}

/** Données secondaires RH (widgets dashboard, alertes). */
export function prefetchRhSecondary(queryClient: QueryClient, companyId: string) {
  return Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: queryKeys.residencePermitStats(companyId),
      queryFn: async () =>
        (await apiClient.get('/api/dashboard/residence-permit-stats')).data,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.ribAlerts(companyId),
      queryFn: async () => {
        const res = await ribAlertsApi.getRibAlerts({
          is_read: false,
          is_resolved: false,
          limit: 5,
        });
        return res.data;
      },
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.pendingSignaturesRh(companyId),
      queryFn: getPendingSignaturesRH,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.medicalSettings(companyId),
      queryFn: getMedicalSettings,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.annualReviews(companyId),
      queryFn: async () => (await getAllAnnualReviews()).data,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.recruitmentSettings(companyId),
      queryFn: getRecruitmentSettings,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.absences(companyId),
      queryFn: async () => (await apiClient.get('/api/absences')).data,
    }),
  ]);
}

function prefetchRhDeferred(queryClient: QueryClient, companyId: string) {
  return Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: queryKeys.medicalKpis(companyId),
      queryFn: async () => {
        const settings = await getMedicalSettings();
        if (!settings.enabled) return null;
        return getKPIs();
      },
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.recruitmentCandidates(companyId),
      queryFn: async () => {
        const settings = await getRecruitmentSettings();
        if (!settings.enabled) return [];
        return getCandidates();
      },
    }),
  ]);
}

/** Planning : semaine courante + effectifs (clés alignées sur Planning.tsx). */
export function prefetchPlanningWeek(queryClient: QueryClient, companyId: string) {
  const weekStart = currentWeekStartIso();
  return Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: queryKeys.planningWeek(companyId, weekStart),
      queryFn: () => getWeekPlanning(weekStart),
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.employeesPlanning(companyId),
      queryFn: () => fetchEmployeesSummary('active'),
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.planningShiftTypes(companyId),
      queryFn: getShiftTypes,
    }),
  ]);
}

function prefetchPlatformAdminCritical(queryClient: QueryClient) {
  return queryClient.prefetchQuery({
    queryKey: queryKeys.adminGlobalStats(),
    queryFn: getAdminGlobalStats,
  });
}

function prefetchPlatformAdminSecondary(queryClient: QueryClient) {
  return Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: queryKeys.adminCompanies(),
      queryFn: async () => {
        const res = await apiClient.get('/api/super-admin/companies', {
          params: { limit: 100 },
        });
        return res.data;
      },
    }),
    import('@/pages/admin/eywai/AdminDashboard'),
    import('@/pages/admin/super/Companies'),
  ]);
}

/** Précharge les chunks des pages fréquentes (hors chemin critique). */
function prefetchCommonChunks() {
  return Promise.allSettled([
    import('@/pages/rh/Dashboard'),
    import('@/pages/rh/Employees'),
    import('@/pages/rh/EmployeeDetail'),
    import('@/pages/rh/Absences'),
    import('@/pages/rh/Planning'),
    import('@/pages/rh/Payroll'),
    import('@/pages/rh/Analytics'),
  ]);
}

/**
 * Prefetch bloquant pendant le splash : lot critique uniquement.
 */
export async function runBootPrefetch(
  queryClient: QueryClient,
  user: PrefetchUser | null,
  activeCompany: CompanyAccess | null,
  onProgress?: (p: BootPrefetchProgress) => void,
): Promise<void> {
  if (!user) return;

  const report = (label: string, progress: number) => onProgress?.({ label, progress });

  if (isPlatformAdmin(user) && !activeCompany?.company_id) {
    report('Administration plateforme…', 60);
    await prefetchPlatformAdminCritical(queryClient);
    report('Ouverture…', 90);
    return;
  }

  if (isRhLikeRole(user)) {
    const companyId = activeCompany?.company_id;
    if (companyId) {
      report('Tableau de bord et effectifs…', 55);
      await prefetchRhCritical(queryClient, companyId);
      report('Ouverture de l’application…', 85);
    } else {
      report('Ouverture…', 85);
    }

    if (isPlatformAdmin(user)) {
      report('Administration plateforme…', 90);
      await prefetchPlatformAdminCritical(queryClient);
    }

    report('Prêt', 100);
    return;
  }

  if (isCollaborateurRole(user)) {
    report('Espace collaborateur…', 55);
    await prefetchEmployeeCritical(queryClient, user.id);
    report('Prêt', 100);
    return;
  }

  report('Prêt', 100);
}

/** Suite du prefetch après affichage de l’app (non bloquant). */
export function prefetchInBackground(
  queryClient: QueryClient,
  user: PrefetchUser | null,
  activeCompany: CompanyAccess | null,
): void {
  if (!user) return;

  const run = async () => {
    const companyId = activeCompany?.company_id;

    if (isRhLikeRole(user) && companyId) {
      await prefetchRhSecondary(queryClient, companyId);
      void prefetchRhDeferred(queryClient, companyId);
      void prefetchPlanningWeek(queryClient, companyId);
    }

    if (isPlatformAdmin(user)) {
      await prefetchPlatformAdminSecondary(queryClient);
    }

    if (isCollaborateurRole(user)) {
      void prefetchEmployeeSecondary(queryClient, user.id, companyId);
    }

    void prefetchCommonChunks();
  };

  if (typeof requestIdleCallback !== 'undefined') {
    requestIdleCallback(() => void run(), { timeout: 4000 });
  } else {
    setTimeout(() => void run(), 300);
  }
}

/** @deprecated Utiliser runBootPrefetch — conservé pour compatibilité */
export async function prefetchForUser(
  queryClient: QueryClient,
  user: PrefetchUser | null,
  activeCompany: CompanyAccess | null,
): Promise<void> {
  await runBootPrefetch(queryClient, user, activeCompany);
}

/** Précharge le chunk JS + query principale au survol d'un lien sidebar */
export function prefetchRoute(queryClient: QueryClient, path: string, companyId?: string) {
  const normalizedPath = path.split('#')[0] || path;

  const routePrefetchers: Record<string, () => Promise<unknown>> = {
    '/': () => import('@/pages/rh/Dashboard'),
    '/employees': () => {
      if (companyId) {
        return queryClient.prefetchQuery({
          queryKey: queryKeys.employees(companyId),
          queryFn: () => fetchEmployeesSummary('all'),
        });
      }
      return import('@/pages/rh/Employees');
    },
    '/payroll': () => {
      if (companyId) {
        return queryClient.prefetchQuery({
          queryKey: queryKeys.employees(companyId),
          queryFn: () => fetchEmployeesSummary('all'),
        });
      }
      return import('@/pages/rh/Payroll');
    },
    '/payroll/generate': () => {
      if (companyId) {
        return queryClient.prefetchQuery({
          queryKey: queryKeys.employees(companyId),
          queryFn: () => fetchEmployeesSummary('all'),
        });
      }
      return import('@/pages/rh/PayrollGenerate');
    },
    '/leaves': () => import('@/pages/rh/Absences'),
    '/suivi-contingent-hs': () => import('@/pages/rh/SuiviContingentHs'),
    '/suivi-modulation': () => import('@/pages/rh/SuiviModulation'),
    '/leave-requests': () => import('@/pages/rh/manager/LeaveRequests'),
    '/planning': () => {
      if (companyId) {
        return prefetchPlanningWeek(queryClient, companyId);
      }
      return import('@/pages/rh/Planning');
    },
    '/saisies': () => import('@/pages/rh/Saisies'),
    '/rates': () => import('@/pages/rh/Rates'),
    '/schedules': () => import('@/pages/rh/Schedules'),
    '/salary-advances': () => import('@/pages/rh/SalaryAdvances'),
    '/salary-seizures': () => import('@/pages/rh/SalarySeizures'),
    '/documents': () => import('@/pages/rh/Documents'),
    '/analytics': () => import('@/pages/rh/Analytics'),
    '/analytics-gestion': () => import('@/pages/rh/AnalyticsGestion'),
    '/analytics-paie': () => import('@/pages/rh/AnalyticsPaie'),
    '/formation': () => import('@/pages/rh/formation/FormationPage'),
    '/recruitment': () => import('@/pages/rh/Recruitment'),
    '/onboarding': () => import('@/pages/rh/onboarding/OnboardingPage'),
    '/employee-exits': () => import('@/pages/rh/EmployeeExits'),
    '/teams': () => import('@/pages/rh/Teams'),
    '/residence-permits': () => import('@/pages/rh/ResidencePermits'),
    '/badgeuse-rh': () => import('@/pages/rh/BadgeuseRh'),
    '/augmentations-et-promotions': () => import('@/pages/rh/AugmentationsEtPromotions'),
    '/cse': () => import('@/pages/rh/CSE'),
    '/medical-follow-up': () => import('@/pages/rh/MedicalFollowUp'),
    '/users': () => import('@/pages/rh/UserManagement'),
    '/expenses': () => import('@/pages/rh/Expenses'),
    '/simulation': () => import('@/pages/rh/Simulation'),
    '/exports': () => import('@/pages/rh/Exports'),
    '/company': () => import('@/pages/rh/CompanyPage'),
  };

  const fn = routePrefetchers[normalizedPath];
  if (fn) void fn().catch(() => undefined);
}
