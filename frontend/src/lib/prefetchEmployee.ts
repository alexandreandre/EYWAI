import type { QueryClient } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { getAbsencePageData } from '@/api/absences';
import { getMyAnnualReviews } from '@/api/annualReviews';
import { getMyAdvanceAvailable, getMySalaryAdvances } from '@/api/saisiesAvances';
import { getMyBadgeuseStatusToday } from '@/api/badgeuse';
import { getMyElectedStatus } from '@/api/cse';
import { getMyObligations } from '@/api/medicalFollowUp';
import type { Expense } from '@/api/expenses';
import type { PayslipInfo } from '@/lib/employeeDashboardUtils';
import type { EmployeeProfileData } from '@/lib/employeeProfileUtils';
import type { CumulsData } from '@/hooks/queries/useEmployeeDashboardQueries';
import { MEDICAL_FOLLOW_UP_ME_QUERY_KEY } from '@/lib/employeeMedicalFollowUp';
import { queryKeys } from '@/lib/queryKeys';

function currentMonthParts() {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

/** Données critiques du tableau de bord collaborateur. */
export function prefetchEmployeeCritical(queryClient: QueryClient, userId: string) {
  const { year, month } = currentMonthParts();
  return Promise.allSettled([
    queryClient.prefetchQuery({
      queryKey: [...queryKeys.employeeDashboard(userId), 'payslips'],
      queryFn: async () => {
        const res = await apiClient.get<PayslipInfo[]>('/api/me/payslips');
        return res.data ?? [];
      },
    }),
    queryClient.prefetchQuery({
      queryKey: [...queryKeys.employeeDashboard(userId), 'expenses'],
      queryFn: async () => {
        const res = await apiClient.get<Expense[]>('/api/expenses/me');
        return res.data ?? [];
      },
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.employeeDashboardAbsences(userId, year, month),
      queryFn: async () => {
        const res = await getAbsencePageData(year, month);
        return res.data;
      },
    }),
    queryClient.prefetchQuery({
      queryKey: [...queryKeys.employeeDashboard(userId), 'profile'],
      queryFn: async () => {
        const res = await apiClient.get<EmployeeProfileData>('/api/employees/me');
        return res.data;
      },
    }),
    import('@/pages/employee/Dashboard'),
  ]);
}

/** Chunks et données secondaires collaborateur (après affichage). */
export function prefetchEmployeeSecondary(
  queryClient: QueryClient,
  userId: string,
  companyId?: string,
) {
  const { year, month } = currentMonthParts();
  return Promise.allSettled([
    import('@/pages/employee/Calendar'),
    import('@/pages/employee/Absences'),
    import('@/pages/employee/Payslips'),
    import('@/pages/employee/EmployeeFormationPage'),
    import('@/pages/employee/Badgeuse'),
    import('@/pages/employee/SalaryAdvances'),
    queryClient.prefetchQuery({
      queryKey: queryKeys.employeeSalaryAdvances(userId),
      queryFn: async () => {
        const [advances, available] = await Promise.all([
          getMySalaryAdvances(),
          getMyAdvanceAvailable(),
        ]);
        return { advances, available };
      },
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.employeeBadgeuseToday(userId),
      queryFn: () => getMyBadgeuseStatusToday(),
    }),
    queryClient.prefetchQuery({
      queryKey: ['annual-reviews-me'],
      queryFn: async () => {
        const res = await getMyAnnualReviews();
        return res.data;
      },
    }),
    companyId
      ? queryClient.prefetchQuery({
          queryKey: ['current-employee', companyId, userId],
          queryFn: async () => {
            const res = await apiClient.get('/api/employees/me');
            return res.data;
          },
        })
      : Promise.resolve(),
    queryClient.prefetchQuery({
      queryKey: [...queryKeys.employeeDashboard(userId), 'cumuls'],
      queryFn: async () => {
        const res = await apiClient.get<CumulsData>('/api/me/current-cumuls');
        return res.data;
      },
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.employeeDashboardAbsences(userId, year, month),
      queryFn: async () => {
        const res = await getAbsencePageData(year, month);
        return res.data;
      },
    }),
  ]);
}

/** Précharge chunk + données au survol d'un lien sidebar collaborateur. */
export function prefetchEmployeeRoute(
  queryClient: QueryClient,
  path: string,
  userId?: string,
  companyId?: string,
) {
  if (!userId) return;

  const normalizedPath = path.split('#')[0] || path;
  const { year, month } = currentMonthParts();

  const routePrefetchers: Record<string, () => Promise<unknown>> = {
    '/': () => import('@/pages/employee/Dashboard'),
    '/calendar': () =>
      Promise.all([
        import('@/pages/employee/Calendar'),
        queryClient.prefetchQuery({
          queryKey: [...queryKeys.employeeDashboard(userId), 'profile'],
          queryFn: async () => {
            const res = await apiClient.get<EmployeeProfileData>('/api/employees/me');
            return res.data;
          },
        }),
      ]),
    '/badgeuse': () =>
      Promise.all([
        import('@/pages/employee/Badgeuse'),
        queryClient.prefetchQuery({
          queryKey: queryKeys.employeeBadgeuseToday(userId),
          queryFn: () => getMyBadgeuseStatusToday(),
        }),
      ]),
    '/absences': () =>
      Promise.all([
        import('@/pages/employee/Absences'),
        queryClient.prefetchQuery({
          queryKey: queryKeys.employeeDashboardAbsences(userId, year, month),
          queryFn: async () => {
            const res = await getAbsencePageData(year, month);
            return res.data;
          },
        }),
      ]),
    '/expenses': () =>
      Promise.all([
        import('@/pages/employee/Expenses'),
        queryClient.prefetchQuery({
          queryKey: [...queryKeys.employeeDashboard(userId), 'expenses'],
          queryFn: async () => {
            const res = await apiClient.get<Expense[]>('/api/expenses/me');
            return res.data ?? [];
          },
        }),
      ]),
    '/salary-advances': () =>
      Promise.all([
        import('@/pages/employee/SalaryAdvances'),
        queryClient.prefetchQuery({
          queryKey: queryKeys.employeeSalaryAdvances(userId),
          queryFn: async () => {
            const [advances, available] = await Promise.all([
              getMySalaryAdvances(),
              getMyAdvanceAvailable(),
            ]);
            return { advances, available };
          },
        }),
      ]),
    '/employee/documents': () => import('@/pages/employee/Documents'),
    '/employee/formation': () =>
      Promise.all([
        import('@/pages/employee/EmployeeFormationPage'),
        companyId
          ? queryClient.prefetchQuery({
              queryKey: ['current-employee', companyId, userId],
              queryFn: async () => {
                const res = await apiClient.get('/api/employees/me');
                return res.data;
              },
            })
          : Promise.resolve(),
      ]),
    '/payslips': () =>
      Promise.all([
        import('@/pages/employee/Payslips'),
        queryClient.prefetchQuery({
          queryKey: [...queryKeys.employeeDashboard(userId), 'payslips'],
          queryFn: async () => {
            const res = await apiClient.get<PayslipInfo[]>('/api/me/payslips');
            return res.data ?? [];
          },
        }),
        queryClient.prefetchQuery({
          queryKey: [...queryKeys.employeeDashboard(userId), 'cumuls'],
          queryFn: async () => {
            const res = await apiClient.get<CumulsData>('/api/me/current-cumuls');
            return res.data;
          },
        }),
      ]),
    '/profile': () =>
      Promise.all([
        import('@/pages/employee/Profile'),
        queryClient.prefetchQuery({
          queryKey: [...queryKeys.employeeDashboard(userId), 'profile-page'],
          queryFn: async () => {
            const res = await apiClient.get<EmployeeProfileData>('/api/employees/me');
            return res.data;
          },
        }),
      ]),
    '/medical-follow-up': () =>
      Promise.all([
        import('@/pages/employee/MedicalFollowUp'),
        queryClient.prefetchQuery({
          queryKey: MEDICAL_FOLLOW_UP_ME_QUERY_KEY,
          queryFn: getMyObligations,
        }),
      ]),
    '/cse': () =>
      Promise.all([
        import('@/pages/employee/CSE'),
        queryClient.prefetchQuery({
          queryKey: ['cse', 'my-elected-status'],
          queryFn: () => getMyElectedStatus(),
        }),
      ]),
    '/annual-reviews': () =>
      Promise.all([
        import('@/pages/employee/AnnualReviews'),
        queryClient.prefetchQuery({
          queryKey: ['annual-reviews-me'],
          queryFn: async () => {
            const res = await getMyAnnualReviews();
            return res.data;
          },
        }),
      ]),
  };

  const fn = routePrefetchers[normalizedPath];
  if (fn) void fn().catch(() => undefined);
}
