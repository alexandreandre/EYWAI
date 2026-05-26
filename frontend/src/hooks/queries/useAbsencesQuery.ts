import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from './useCompanyId';

export type AbsenceRequest = {
  id: string;
  [key: string]: unknown;
};

async function fetchAbsencesByStatus(status: string) {
  const res = await apiClient.get<AbsenceRequest[]>(`/api/absences/?status=${status}`);
  return res.data ?? [];
}

export function useAbsencesQueries(enabled = true) {
  const companyId = useActiveCompanyId();
  const baseEnabled = enabled && Boolean(companyId);

  const pending = useQuery({
    queryKey: [...queryKeys.absences(companyId), 'pending'],
    queryFn: () => fetchAbsencesByStatus('pending'),
    enabled: baseEnabled,
  });

  const validated = useQuery({
    queryKey: [...queryKeys.absences(companyId), 'validated'],
    queryFn: () => fetchAbsencesByStatus('validated'),
    enabled: baseEnabled,
  });

  const rejected = useQuery({
    queryKey: [...queryKeys.absences(companyId), 'rejected'],
    queryFn: () => fetchAbsencesByStatus('rejected'),
    enabled: baseEnabled,
  });

  const isLoading =
    (pending.isLoading && !pending.data) ||
    (validated.isLoading && !validated.data) ||
    (rejected.isLoading && !rejected.data);

  const isFetching =
    pending.isFetching || validated.isFetching || rejected.isFetching;

  return {
    pending: pending.data ?? [],
    validated: validated.data ?? [],
    rejected: rejected.data ?? [],
    isLoading,
    isFetching,
    refetch: async () => {
      await Promise.all([pending.refetch(), validated.refetch(), rejected.refetch()]);
    },
  };
}
