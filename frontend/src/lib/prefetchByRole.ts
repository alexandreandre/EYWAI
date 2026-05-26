import type { QueryClient } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { getAllAnnualReviews } from '@/api/annualReviews';
import { getMedicalSettings, getKPIs } from '@/api/medicalFollowUp';
import { getCandidates, getRecruitmentSettings } from '@/api/recruitment';
import * as ribAlertsApi from '@/api/ribAlerts';
import { getPendingSignaturesRH } from '@/api/signatures';
import { queryKeys } from '@/lib/queryKeys';
import type { CompanyAccess } from '@/contexts/CompanyContext';

type PrefetchUser = {
  id: string;
  role?: string;
  is_super_admin?: boolean;
};

function isRhLikeRole(user: PrefetchUser): boolean {
  if (user.is_super_admin || user.role === 'super_admin') return false;
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

/** Précharge les données critiques selon le rôle (ne bloque pas l'UI au-delà du timeout BootGate). */
export async function prefetchForUser(
  queryClient: QueryClient,
  user: PrefetchUser | null,
  activeCompany: CompanyAccess | null,
): Promise<void> {
  if (!user) return;

  const companyId = activeCompany?.company_id;
  const tasks: Promise<unknown>[] = [];

  if (isRhLikeRole(user) && companyId) {
    tasks.push(
      queryClient.prefetchQuery({
        queryKey: queryKeys.dashboardAll(companyId),
        queryFn: async () => {
          const res = await apiClient.get('/api/dashboard/all');
          return res.data;
        },
      }),
      queryClient.prefetchQuery({
        queryKey: queryKeys.employees(companyId),
        queryFn: async () => {
          const res = await apiClient.get('/api/employees');
          return res.data;
        },
      }),
      queryClient.prefetchQuery({
        queryKey: queryKeys.residencePermitStats(companyId),
        queryFn: async () => {
          const res = await apiClient.get('/api/dashboard/residence-permit-stats');
          return res.data;
        },
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
        queryFn: async () => {
          const res = await getAllAnnualReviews();
          return res.data;
        },
      }),
      queryClient.prefetchQuery({
        queryKey: queryKeys.recruitmentSettings(companyId),
        queryFn: getRecruitmentSettings,
      }),
    );

    tasks.push(
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
    );
  }

  if (isCollaborateurRole(user)) {
    // Collaborateur : pas de companyId requis pour certaines routes
    tasks.push(
      import('@/pages/employee/Dashboard').catch(() => undefined),
    );
  }

  await Promise.allSettled(tasks);
}

/** Précharge le chunk JS + query principale au survol d'un lien sidebar */
export function prefetchRoute(queryClient: QueryClient, path: string, companyId?: string) {
  const routePrefetchers: Record<string, () => Promise<unknown>> = {
    '/': () => import('@/pages/Dashboard'),
    '/employees': () => {
      if (companyId) {
        return queryClient.prefetchQuery({
          queryKey: queryKeys.employees(companyId),
          queryFn: async () => (await apiClient.get('/api/employees')).data,
        });
      }
      return import('@/pages/Employees');
    },
    '/payroll': () => {
      if (companyId) {
        return queryClient.prefetchQuery({
          queryKey: queryKeys.employees(companyId),
          queryFn: async () => (await apiClient.get('/api/employees')).data,
        });
      }
      return import('@/pages/Payroll');
    },
    '/leaves': () => import('@/pages/Absences'),
    '/planning': () => import('@/pages/Planning'),
    '/saisies': () => import('@/pages/Saisies'),
    '/rates': () => import('@/pages/Rates'),
    '/schedules': () => import('@/pages/Schedules'),
    '/salary-advances': () => import('@/pages/SalaryAdvances'),
    '/documents': () => import('@/pages/Documents'),
    '/analytics': () => import('@/pages/Analytics'),
  };

  const fn = routePrefetchers[path];
  if (fn) void fn().catch(() => undefined);
}
