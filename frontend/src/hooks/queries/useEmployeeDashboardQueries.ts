import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { getAbsencePageData } from '@/api/absences';
import { getMyBadgeuseStatusToday } from '@/api/badgeuse';
import { queryKeys } from '@/lib/queryKeys';
import type { PayslipInfo } from '@/lib/employeeDashboardUtils';
import type { EmployeeProfileData } from '@/lib/employeeProfileUtils';
import type { Expense } from '@/api/expenses';

/** Champs profil utilisés par le tableau de bord (sous-ensemble). */
export interface EmployeeSalaryInfo {
  salaire_de_base?: { valeur?: number } | null;
  job_title?: string | null;
  hire_date?: string | null;
}

/** Alias conservé pour le dashboard et les écrans employé. */
export type ExpenseInfo = Expense;

export interface CumulsData {
  periode?: { annee_en_cours?: number; dernier_mois_calcule?: number };
  cumuls?: {
    brut_total?: number;
    net_imposable?: number;
    impot_preleve_a_la_source?: number;
    heures_remunerees?: number;
    heures_supplementaires_remunerees?: number;
  };
}

export function useEmployeePayslipsQuery(userId: string | undefined) {
  return useQuery({
    queryKey: [...queryKeys.employeeDashboard(userId), 'payslips'],
    queryFn: async () => {
      const res = await apiClient.get<PayslipInfo[]>('/api/me/payslips');
      return res.data ?? [];
    },
    enabled: Boolean(userId),
  });
}

export function useEmployeeExpensesQuery(userId: string | undefined) {
  return useQuery({
    queryKey: [...queryKeys.employeeDashboard(userId), 'expenses'],
    queryFn: async () => {
      const res = await apiClient.get<Expense[]>('/api/expenses/me');
      return res.data ?? [];
    },
    enabled: Boolean(userId),
  });
}

export function useEmployeeAbsencesPageQuery(
  userId: string | undefined,
  year: number,
  month: number
) {
  return useQuery({
    queryKey: queryKeys.employeeDashboardAbsences(userId, year, month),
    queryFn: async () => {
      const res = await getAbsencePageData(year, month);
      return res.data;
    },
    enabled: Boolean(userId),
  });
}

export function useEmployeeCumulsQuery(userId: string | undefined) {
  return useQuery({
    queryKey: [...queryKeys.employeeDashboard(userId), 'cumuls'],
    queryFn: async () => {
      const res = await apiClient.get<CumulsData>('/api/me/current-cumuls');
      return res.data;
    },
    enabled: Boolean(userId),
  });
}

async function fetchMyEmployeeProfile(): Promise<EmployeeProfileData> {
  const res = await apiClient.get<EmployeeProfileData>('/api/employees/me');
  return res.data;
}

export function useEmployeeProfileQuery(userId: string | undefined) {
  return useQuery({
    queryKey: [...queryKeys.employeeDashboard(userId), 'profile'],
    queryFn: fetchMyEmployeeProfile,
    enabled: Boolean(userId),
  });
}

/** Profil complet pour la page Mon Profil (même endpoint, clé dédiée). */
export function useEmployeeProfilePageQuery(userId: string | undefined) {
  return useQuery({
    queryKey: [...queryKeys.employeeDashboard(userId), 'profile-page'],
    queryFn: fetchMyEmployeeProfile,
    enabled: Boolean(userId),
  });
}

export function useEmployeeBadgeuseTodayQuery(userId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.employeeBadgeuseToday(userId),
    queryFn: () => getMyBadgeuseStatusToday(),
    enabled: Boolean(userId),
    staleTime: 30_000,
  });
}
