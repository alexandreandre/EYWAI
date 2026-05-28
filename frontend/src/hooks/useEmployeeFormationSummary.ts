import { useQuery } from "@tanstack/react-query";
import { isAxiosError } from "axios";

import { getMyAnnualReviews } from "@/api/annualReviews";
import { getEmployeeCertifications } from "@/api/certifications";
import { getEnrollments } from "@/api/training";
import { getMyOnboarding } from "@/api/onboarding";
import {
  certWatchCount,
  enrollmentPendingCount,
  reviewsActionCount,
} from "@/lib/employeeFormationUtils";

export type FormationSummaryCounts = {
  reviewsAction: number;
  enrollmentsPending: number;
  certsWatch: number;
  onboardingIncomplete: boolean;
  isLoading: boolean;
};

export function useEmployeeFormationSummary(
  employeeId: string | undefined,
  companyId: string | undefined,
): FormationSummaryCounts {
  const reviewsQ = useQuery({
    queryKey: ["annual-reviews-me"],
    queryFn: async () => {
      const res = await getMyAnnualReviews();
      return res.data;
    },
    enabled: Boolean(employeeId),
    staleTime: 60_000,
  });

  const enrollQ = useQuery({
    queryKey: ["formation-enrollments", employeeId],
    queryFn: () => getEnrollments({ employee_id: employeeId! }),
    enabled: Boolean(employeeId),
    staleTime: 60_000,
  });

  const certsQ = useQuery({
    queryKey: ["formation-certs", employeeId],
    queryFn: () => getEmployeeCertifications({ employee_id: employeeId!, include_archived: false }),
    enabled: Boolean(employeeId),
    staleTime: 60_000,
  });

  const onboardingQ = useQuery({
    queryKey: ["onboarding", "me", companyId],
    queryFn: () => getMyOnboarding(companyId!),
    enabled: Boolean(companyId),
    retry: false,
    staleTime: 60_000,
  });

  const isLoading = reviewsQ.isLoading || enrollQ.isLoading || certsQ.isLoading;

  const onboardingIncomplete =
    onboardingQ.isSuccess &&
    onboardingQ.data != null &&
    onboardingQ.data.progress_pct < 100;

  const onboarding404 =
    onboardingQ.isError && isAxiosError(onboardingQ.error) && onboardingQ.error.response?.status === 404;

  return {
    reviewsAction: reviewsActionCount(reviewsQ.data ?? []),
    enrollmentsPending: enrollmentPendingCount(enrollQ.data ?? []),
    certsWatch: certWatchCount(certsQ.data ?? []),
    onboardingIncomplete: onboardingIncomplete && !onboarding404,
    isLoading,
  };
}
