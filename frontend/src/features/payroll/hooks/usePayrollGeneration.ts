import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { generatePayslip } from '@/api/payslips';
import {
  getPayrollGenerationErrorMessage,
  PAYROLL_GENERATION_FALLBACK,
  sanitizeBackendMessage,
} from '@/lib/errorMessages';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import {
  monthYearLabel,
  readAverageGenerationMs,
  recordGenerationDuration,
} from '@/features/payroll/utils/payrollMonth';

export type PayrollGenerationJob = {
  employeeId: string;
  employeeName: string;
  year: number;
  month: number;
};

export type PayrollGenerationLogEntry = {
  id: string;
  employeeId: string;
  employeeName: string;
  year: number;
  month: number;
  status: 'success' | 'warning' | 'error';
  error?: string;
  warnings?: string[];
};

export type PayrollGenerationPhase = 'idle' | 'running' | 'done';

const INTRA_CAP = 0.95;

function intraJobFraction(elapsedMs: number, estimatedMs: number): number {
  const raw = Math.min(1, elapsedMs / estimatedMs);
  return Math.min(INTRA_CAP, 1 - (1 - raw) ** 1.6);
}

export function payrollJobKey(
  job: Pick<PayrollGenerationJob, 'employeeId' | 'year' | 'month'>
): string {
  return `${job.employeeId}-${job.year}-${job.month}`;
}

function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') return true;
  if (typeof error === 'object' && error !== null && 'code' in error) {
    return (error as { code?: string }).code === 'ERR_CANCELED';
  }
  return false;
}

export function usePayrollGeneration() {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();

  const [phase, setPhase] = useState<PayrollGenerationPhase>('idle');
  const [log, setLog] = useState<PayrollGenerationLogEntry[]>([]);
  const [currentJob, setCurrentJob] = useState<PayrollGenerationJob | null>(null);
  const [queuedJobs, setQueuedJobs] = useState<PayrollGenerationJob[]>([]);
  const [progress, setProgress] = useState(0);
  const [estimatedRemainingSec, setEstimatedRemainingSec] = useState<number | null>(null);
  const [totalJobs, setTotalJobs] = useState(0);
  const [failedJobs, setFailedJobs] = useState<Record<string, string>>({});

  const abortRef = useRef(false);
  const tickRef = useRef<number | null>(null);
  const dismissTimerRef = useRef<number | null>(null);
  const jobStartRef = useRef<number>(0);
  const completedCountRef = useRef(0);
  const totalRef = useRef(0);
  const estimatedMsRef = useRef(readAverageGenerationMs());
  const queueRef = useRef<PayrollGenerationJob[]>([]);
  const processingRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const logRef = useRef<PayrollGenerationLogEntry[]>([]);

  const stopTick = useCallback(() => {
    if (tickRef.current != null) {
      window.clearInterval(tickRef.current);
      tickRef.current = null;
    }
  }, []);

  const clearDismissTimer = useCallback(() => {
    if (dismissTimerRef.current != null) {
      window.clearTimeout(dismissTimerRef.current);
      dismissTimerRef.current = null;
    }
  }, []);

  const invalidatePayslips = useCallback(
    async (employeeId: string) => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.employeePayslips(companyId, employeeId),
      });
    },
    [companyId, queryClient]
  );

  const updateProgress = useCallback((completed: number, intraFraction: number) => {
    const total = totalRef.current;
    if (total <= 0) {
      setProgress(0);
      return;
    }
    const value = ((completed + intraFraction) / total) * 100;
    setProgress(Math.min(99.5, value));
  }, []);

  const startTick = useCallback(() => {
    stopTick();
    tickRef.current = window.setInterval(() => {
      const elapsed = Date.now() - jobStartRef.current;
      const estimated = estimatedMsRef.current;
      const intra = intraJobFraction(elapsed, estimated);
      updateProgress(completedCountRef.current, intra);

      const jobsLeft = totalRef.current - completedCountRef.current;
      const currentRemaining = Math.max(0, estimated - elapsed);
      const futureJobs = Math.max(0, jobsLeft - 1);
      const totalRemainingMs = currentRemaining + futureJobs * estimated;
      setEstimatedRemainingSec(Math.ceil(totalRemainingMs / 1000));
    }, 80);
  }, [stopTick, updateProgress]);

  const processQueue = useCallback(async () => {
    if (processingRef.current) return;
    processingRef.current = true;

    try {
      while (queueRef.current.length > 0 && !abortRef.current) {
        const job = queueRef.current.shift()!;
        setQueuedJobs([...queueRef.current]);
        setCurrentJob(job);
        jobStartRef.current = Date.now();
        startTick();

        const controller = new AbortController();
        abortControllerRef.current = controller;

        let entry: PayrollGenerationLogEntry;
        try {
          const response = await generatePayslip(
            {
              employee_id: job.employeeId,
              year: job.year,
              month: job.month,
            },
            controller.signal
          );

          const duration = Date.now() - jobStartRef.current;
          recordGenerationDuration(duration);
          estimatedMsRef.current = readAverageGenerationMs();

          if (response.status === 'success') {
            const warnings = response.warnings ?? [];
            entry = {
              id: payrollJobKey(job),
              employeeId: job.employeeId,
              employeeName: job.employeeName,
              year: job.year,
              month: job.month,
              status: warnings.length > 0 ? 'warning' : 'success',
              warnings,
              error: warnings.length > 0 ? warnings.join(' · ') : undefined,
            };
            setFailedJobs((prev) => {
              const next = { ...prev };
              delete next[payrollJobKey(job)];
              return next;
            });
          } else {
            const errorMessage =
              sanitizeBackendMessage(response.message) || PAYROLL_GENERATION_FALLBACK;
            entry = {
              id: payrollJobKey(job),
              employeeId: job.employeeId,
              employeeName: job.employeeName,
              year: job.year,
              month: job.month,
              status: 'error',
              error: errorMessage,
            };
            setFailedJobs((prev) => ({ ...prev, [payrollJobKey(job)]: errorMessage }));
          }
        } catch (error: unknown) {
          if (abortRef.current || controller.signal.aborted || isAbortError(error)) {
            stopTick();
            break;
          }
          const errorMessage = getPayrollGenerationErrorMessage(error);
          entry = {
            id: payrollJobKey(job),
            employeeId: job.employeeId,
            employeeName: job.employeeName,
            year: job.year,
            month: job.month,
            status: 'error',
            error: errorMessage,
          };
          setFailedJobs((prev) => ({ ...prev, [payrollJobKey(job)]: errorMessage }));
        } finally {
          abortControllerRef.current = null;
        }

        stopTick();

        if (abortRef.current) break;

        completedCountRef.current += 1;
        logRef.current = [...logRef.current, entry];
        setLog(logRef.current);
        updateProgress(completedCountRef.current, 0);
        await invalidatePayslips(job.employeeId);
      }
    } finally {
      stopTick();
      setCurrentJob(null);
      processingRef.current = false;

      if (abortRef.current) {
        queueRef.current = [];
        setQueuedJobs([]);
        abortRef.current = false;
        setPhase('idle');
        setEstimatedRemainingSec(null);
      } else if (queueRef.current.length > 0) {
        void processQueue();
      } else {
        setProgress(100);
        setEstimatedRemainingSec(0);
        setPhase('done');
      }
    }
  }, [invalidatePayslips, startTick, stopTick, updateProgress]);

  const enqueueJobs = useCallback(
    (jobs: PayrollGenerationJob[]) => {
      if (jobs.length === 0) return;

      const inFlightKeys = new Set<string>();
      if (currentJob) inFlightKeys.add(payrollJobKey(currentJob));
      for (const queued of queueRef.current) inFlightKeys.add(payrollJobKey(queued));

      const newJobs = jobs.filter((job) => !inFlightKeys.has(payrollJobKey(job)));
      if (newJobs.length === 0) return;

      const startingFresh = phase === 'idle' && !processingRef.current;
      if (startingFresh) {
        clearDismissTimer();
        logRef.current = [];
        setLog([]);
        setFailedJobs({});
        completedCountRef.current = 0;
        totalRef.current = 0;
        setProgress(0);
        setEstimatedRemainingSec(null);
        estimatedMsRef.current = readAverageGenerationMs();
      }

      totalRef.current += newJobs.length;
      setTotalJobs(totalRef.current);
      queueRef.current.push(...newJobs);
      setQueuedJobs([...queueRef.current]);
      setPhase('running');
      abortRef.current = false;

      if (!processingRef.current) {
        void processQueue();
      }
    },
    [phase, currentJob, clearDismissTimer, processQueue]
  );

  const reset = useCallback(() => {
    abortRef.current = true;
    abortControllerRef.current?.abort();
    stopTick();
    clearDismissTimer();
    queueRef.current = [];
    setQueuedJobs([]);
    logRef.current = [];
    setPhase('idle');
    setLog([]);
    setCurrentJob(null);
    setProgress(0);
    setEstimatedRemainingSec(null);
    setTotalJobs(0);
    setFailedJobs({});
    completedCountRef.current = 0;
    totalRef.current = 0;
    processingRef.current = false;
    abortRef.current = false;
  }, [stopTick, clearDismissTimer]);

  const cancel = useCallback(() => {
    abortRef.current = true;
    abortControllerRef.current?.abort();
    queueRef.current = [];
    setQueuedJobs([]);
    stopTick();
  }, [stopTick]);

  const dismiss = useCallback(() => {
    reset();
  }, [reset]);

  useEffect(() => {
    if (phase !== 'done') return;

    const hasErrors = log.some((entry) => entry.status === 'error');
    const hasWarnings = log.some((entry) => entry.status === 'warning');
    if (hasErrors || hasWarnings) return;

    const delayMs = totalJobs <= 1 ? 3500 : 6000;
    dismissTimerRef.current = window.setTimeout(() => {
      dismissTimerRef.current = null;
      reset();
    }, delayMs);

    return clearDismissTimer;
  }, [phase, log, totalJobs, reset, clearDismissTimer]);

  useEffect(
    () => () => {
      stopTick();
      clearDismissTimer();
    },
    [stopTick, clearDismissTimer]
  );

  const currentLabel = currentJob
    ? `Génération du bulletin de ${monthYearLabel(currentJob.month, currentJob.year)} — ${currentJob.employeeName}…`
    : null;

  const isRunning = phase === 'running';

  const generateJobs = useCallback(
    (jobs: PayrollGenerationJob[]) => {
      enqueueJobs(jobs);
    },
    [enqueueJobs]
  );

  const completedCount = log.length;

  return {
    phase,
    log,
    currentJob,
    queuedJobs,
    currentLabel,
    progress,
    estimatedRemainingSec,
    totalJobs,
    completedCount,
    isRunning,
    generateJobs,
    failedJobs,
    reset,
    cancel,
    dismiss,
  };
}
