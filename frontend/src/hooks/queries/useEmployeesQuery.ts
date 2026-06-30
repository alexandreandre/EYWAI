import { useQuery } from '@tanstack/react-query';
import { fetchEmployees, fetchEmployeesSummary } from '@/api/employees';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from './useCompanyId';
import type { TrialPeriodStatus } from '@/components/TrialPeriodBadge';

export type EmployeeListItem = {
  id: string;
  first_name: string;
  last_name: string;
  job_title?: string | null;
  contract_type?: string | null;
  hire_date?: string | null;
  seniority_reference_date?: string | null;
  employment_status?: string | null;
  current_exit_id?: string | null;
  duree_hebdomadaire?: number | null;
  trial_period_applicable?: boolean | null;
  trial_period_status?: TrialPeriodStatus | null;
  trial_period_end_date?: string | null;
  trial_period_days_remaining?: number | null;
  contract_end_date?: string | null;
  profile_complete?: boolean | null;
  missing_payroll_fields?: string[] | null;
  payroll_eligible?: boolean | null;
};

export function useEmployeesQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.employees(companyId),
    queryFn: fetchEmployees,
    enabled: enabled && Boolean(companyId),
    refetchOnMount: 'always',
  });
}

export function usePayrollEmployeesQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: [...queryKeys.employees(companyId), 'payroll'],
    queryFn: () => fetchEmployeesSummary('payroll'),
    enabled: enabled && Boolean(companyId),
    placeholderData: (previous) => previous,
  });
}

export function useEmployeesSummaryQuery(status: 'all' | 'active' = 'all', enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: [...queryKeys.employees(companyId), 'summary', status],
    queryFn: () => fetchEmployeesSummary(status),
    enabled: enabled && Boolean(companyId),
    placeholderData: (previous) => previous,
  });
}
