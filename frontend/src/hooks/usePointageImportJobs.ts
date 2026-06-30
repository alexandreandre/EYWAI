import { useMemo, useSyncExternalStore } from 'react';
import {
  cancelPointageImportJob,
  detachPointageImportJob,
  dismissPointageImportReview,
  getPointageImportJobsSnapshot,
  registerPointageImportJob,
  removePointageImportJob,
  subscribePointageImportJobs,
  type PointageImportJob,
  type RegisterPointageImportJobInput,
} from '@/hooks/pointageImportJobStore';

export function usePointageImportJobs() {
  const jobs = useSyncExternalStore(
    subscribePointageImportJobs,
    getPointageImportJobsSnapshot,
    getPointageImportJobsSnapshot,
  );

  const activeJobs = useMemo(
    () =>
      jobs.filter(
        (job) =>
          job.detached &&
          (job.status === 'queued' || job.status === 'extracting'),
      ),
    [jobs],
  );

  const reviewJobs = useMemo(
    () =>
      jobs.filter(
        (job) =>
          job.detached &&
          job.status === 'completed' &&
          job.proposal &&
          job.proposal.employees.length > 0 &&
          !job.reviewDismissed,
      ),
    [jobs],
  );

  return {
    jobs,
    activeJobs,
    reviewJobs,
    registerJob: (input: RegisterPointageImportJobInput) =>
      registerPointageImportJob(input),
    detachJob: (localId: string) => detachPointageImportJob(localId),
    dismissReview: (localId: string) => dismissPointageImportReview(localId),
    cancelJob: (localId: string) => cancelPointageImportJob(localId),
    removeJob: (localId: string) => removePointageImportJob(localId),
  };
}

export type { PointageImportJob, RegisterPointageImportJobInput };
