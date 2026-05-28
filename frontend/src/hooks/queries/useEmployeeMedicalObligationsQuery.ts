import { useQuery } from '@tanstack/react-query';
import { getMyObligations } from '@/api/medicalFollowUp';
import {
  MEDICAL_FOLLOW_UP_ME_QUERY_KEY,
  MEDICAL_ME_STALE_TIME_MS,
} from '@/lib/employeeMedicalFollowUp';

export function useEmployeeMedicalObligationsQuery(enabled = true) {
  return useQuery({
    queryKey: MEDICAL_FOLLOW_UP_ME_QUERY_KEY,
    queryFn: getMyObligations,
    enabled,
    staleTime: MEDICAL_ME_STALE_TIME_MS,
  });
}
