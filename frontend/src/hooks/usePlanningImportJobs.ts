import { useMemo, useSyncExternalStore } from 'react';
import {
  cancelPlanningImportJob,
  dismissPlanningImportJob,
  getPlanningImportJobsSnapshot,
  registerPlanningImportJob,
  registerPlanningImportParseJob,
  removePlanningImportJob,
  subscribePlanningImportJobs,
  type PlanningImportJob,
  type RegisterPlanningImportJobInput,
  type RegisterPlanningImportParseJobInput,
} from '@/hooks/planningImportJobStore';

export function usePlanningImportJobs() {
  const jobs = useSyncExternalStore(
    subscribePlanningImportJobs,
    getPlanningImportJobsSnapshot,
    getPlanningImportJobsSnapshot,
  );

  const activeJobs = useMemo(
    () =>
      jobs.filter(
        (job) =>
          !job.dismissed &&
          job.status !== 'committed' &&
          job.status !== 'completed' &&
          job.status !== 'failed' &&
          job.status !== 'cancelled',
      ),
    [jobs],
  );

  const finishedJobs = useMemo(
    () =>
      jobs.filter(
        (job) =>
          !job.dismissed &&
          (job.status === 'committed' ||
            job.status === 'completed' ||
            job.status === 'failed' ||
            job.status === 'cancelled'),
      ),
    [jobs],
  );

  return {
    jobs,
    activeJobs,
    finishedJobs,
    registerJob: (input: RegisterPlanningImportJobInput) => registerPlanningImportJob(input),
    registerParseJob: (input: RegisterPlanningImportParseJobInput) =>
      registerPlanningImportParseJob(input),
    dismissJob: (localId: string) => dismissPlanningImportJob(localId),
    cancelJob: (localId: string) => cancelPlanningImportJob(localId),
    removeJob: (localId: string) => removePlanningImportJob(localId),
  };
}

export type {
  PlanningImportJob,
  RegisterPlanningImportJobInput,
  RegisterPlanningImportParseJobInput,
};
