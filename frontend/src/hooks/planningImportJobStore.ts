import {
  cancelPlanningImport,
  getPlanningImportParseJob,
  getPlanningImportBatch,
  type PlanningImportBatchStatus,
  type PlanningImportCommitProgress,
  type PlanningImportParseResponse,
} from '@/api/adminImport';

const POLL_INTERVAL_MS = 1000;

export type PlanningImportJobStatus = string;

export interface PlanningImportJob {
  localId: string;
  kind: 'parse' | 'commit';
  jobId: string | null;
  batchId: string | null;
  companyId: string;
  label: string;
  status: PlanningImportJobStatus;
  progress: PlanningImportCommitProgress | Record<string, unknown> | null;
  parseResult: PlanningImportParseResponse | null;
  employeesProcessed: number | null;
  totalDaysWritten: number | null;
  errorMessage: string | null;
  startedAt: number;
  completedAt: number | null;
  dismissed: boolean;
}

type JobPatch = Partial<
  Pick<
    PlanningImportJob,
    | 'status'
    | 'progress'
    | 'parseResult'
    | 'batchId'
    | 'employeesProcessed'
    | 'totalDaysWritten'
    | 'errorMessage'
    | 'completedAt'
    | 'dismissed'
  >
>;

export type RegisterPlanningImportJobInput = {
  batchId: string;
  companyId: string;
  label: string;
  status?: PlanningImportJobStatus;
};

export type RegisterPlanningImportParseJobInput = {
  jobId: string;
  companyId: string;
  label: string;
  status?: PlanningImportJobStatus;
};

const jobs = new Map<string, PlanningImportJob>();
const pollTimers = new Map<string, ReturnType<typeof setInterval>>();
const listeners = new Set<() => void>();
let cachedSnapshot: PlanningImportJob[] = [];

function isTerminalStatus(status: PlanningImportJobStatus): boolean {
  return (
    status === 'committed' ||
    status === 'completed' ||
    status === 'failed' ||
    status === 'cancelled'
  );
}

function rebuildSnapshot() {
  cachedSnapshot = [...jobs.values()].sort((a, b) => b.startedAt - a.startedAt);
}

function emit() {
  rebuildSnapshot();
  listeners.forEach((listener) => listener());
}

export function subscribePlanningImportJobs(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getPlanningImportJobsSnapshot(): PlanningImportJob[] {
  return cachedSnapshot;
}

function patchJob(localId: string, patch: JobPatch) {
  const current = jobs.get(localId);
  if (!current) return;
  jobs.set(localId, { ...current, ...patch });
  emit();
}

function stopPolling(localId: string) {
  const timer = pollTimers.get(localId);
  if (!timer) return;
  clearInterval(timer);
  pollTimers.delete(localId);
}

function patchCommitFromRemote(
  localId: string,
  job: PlanningImportJob,
  remote: PlanningImportBatchStatus,
) {
  const isDone = isTerminalStatus(remote.status);
  patchJob(localId, {
    status: remote.status,
    progress: remote.commit_progress ?? job.progress,
    employeesProcessed: remote.employees_processed ?? job.employeesProcessed,
    totalDaysWritten: remote.total_days_written ?? job.totalDaysWritten,
    errorMessage: remote.error_message ?? null,
    completedAt: isDone ? job.completedAt ?? Date.now() : job.completedAt,
  });
  if (isDone) stopPolling(localId);
}

async function pollJob(localId: string) {
  const job = jobs.get(localId);
  if (!job || isTerminalStatus(job.status)) {
    stopPolling(localId);
    return;
  }

  try {
    if (job.kind === 'parse') {
      if (!job.jobId) {
        stopPolling(localId);
        return;
      }
      const remote = await getPlanningImportParseJob(job.jobId, job.companyId);
      const isDone = isTerminalStatus(remote.status);
      patchJob(localId, {
        status: remote.status,
        progress: remote.progress ?? job.progress,
        parseResult: remote.result ?? job.parseResult,
        batchId: remote.result?.batch_id ?? job.batchId,
        errorMessage: remote.error_message ?? null,
        completedAt: isDone ? job.completedAt ?? Date.now() : job.completedAt,
      });
      if (isDone) stopPolling(localId);
      return;
    }

    if (!job.batchId) {
      stopPolling(localId);
      return;
    }
    const remote = await getPlanningImportBatch(job.batchId, job.companyId);
    patchCommitFromRemote(localId, job, remote);
  } catch {
    // Polling best-effort : l'import continue côté serveur, on retente au prochain tick.
  }
}

function startPolling(localId: string) {
  if (pollTimers.has(localId)) return;
  void pollJob(localId);
  pollTimers.set(
    localId,
    setInterval(() => {
      void pollJob(localId);
    }, POLL_INTERVAL_MS),
  );
}

export function registerPlanningImportJob(
  input: RegisterPlanningImportJobInput,
): PlanningImportJob {
  const existing = [...jobs.values()].find(
    (job) =>
      job.kind === 'commit' &&
      job.batchId === input.batchId &&
      job.companyId === input.companyId,
  );
  if (existing) {
    const nextStatus = input.status ?? existing.status;
    patchJob(existing.localId, {
      status: nextStatus,
      dismissed: false,
    });
    if (!isTerminalStatus(nextStatus)) startPolling(existing.localId);
    return jobs.get(existing.localId) ?? existing;
  }

  const localId = crypto.randomUUID();
  const job: PlanningImportJob = {
    localId,
    kind: 'commit',
    jobId: null,
    batchId: input.batchId,
    companyId: input.companyId,
    label: input.label,
    status: input.status ?? 'committing',
    progress: null,
    parseResult: null,
    employeesProcessed: null,
    totalDaysWritten: null,
    errorMessage: null,
    startedAt: Date.now(),
    completedAt: null,
    dismissed: false,
  };
  jobs.set(localId, job);
  emit();
  if (!isTerminalStatus(job.status)) startPolling(localId);
  return job;
}

export function registerPlanningImportParseJob(
  input: RegisterPlanningImportParseJobInput,
): PlanningImportJob {
  const existing = [...jobs.values()].find(
    (job) =>
      job.kind === 'parse' &&
      job.jobId === input.jobId &&
      job.companyId === input.companyId,
  );
  if (existing) {
    const nextStatus = input.status ?? existing.status;
    patchJob(existing.localId, {
      status: nextStatus,
      dismissed: false,
    });
    if (!isTerminalStatus(nextStatus)) startPolling(existing.localId);
    return jobs.get(existing.localId) ?? existing;
  }

  const localId = crypto.randomUUID();
  const job: PlanningImportJob = {
    localId,
    kind: 'parse',
    jobId: input.jobId,
    batchId: null,
    companyId: input.companyId,
    label: input.label,
    status: input.status ?? 'parsing',
    progress: { phase: 'queued', label: 'Analyse en attente', percent: 8 },
    parseResult: null,
    employeesProcessed: null,
    totalDaysWritten: null,
    errorMessage: null,
    startedAt: Date.now(),
    completedAt: null,
    dismissed: false,
  };
  jobs.set(localId, job);
  emit();
  if (!isTerminalStatus(job.status)) startPolling(localId);
  return job;
}

export function dismissPlanningImportJob(localId: string) {
  patchJob(localId, { dismissed: true });
}

export async function cancelPlanningImportJob(localId: string) {
  const job = jobs.get(localId);
  if (!job) return;
  if (isTerminalStatus(job.status)) return;
  patchJob(localId, { status: 'cancelling' });
  if (job.kind !== 'commit' || !job.batchId) {
    // Pas de cancel serveur sur l'analyse — on marque local et on stoppe le polling.
    stopPolling(localId);
    patchJob(localId, { status: 'cancelled', completedAt: Date.now() });
    return;
  }
  try {
    await cancelPlanningImport(job.batchId, job.companyId);
  } catch {
    // Le job est peut-être déjà terminé côté serveur : on laisse le polling refléter l'état réel.
  }
}

export function removePlanningImportJob(localId: string) {
  stopPolling(localId);
  jobs.delete(localId);
  emit();
}

export function planningImportProgressPercent(job: PlanningImportJob): number {
  const progress = job.progress;
  if (job.status === 'committed' || job.status === 'completed') return 100;
  if (job.status === 'failed') return 0;
  const percent = Number(progress?.percent);
  if (Number.isFinite(percent)) return Math.min(99, Math.max(8, percent));
  const total = Number(progress?.total);
  const done = Number(progress?.done);
  if (Number.isFinite(total) && Number.isFinite(done) && total > 0) {
    return Math.min(99, Math.max(8, Math.round((done / total) * 100)));
  }
  return 12;
}

export function planningImportProgressLabel(job: PlanningImportJob): string {
  if (job.kind === 'parse') {
    if (job.status === 'completed') return 'Analyse terminée';
    if (job.status === 'failed') return job.errorMessage ?? "L'analyse a échoué.";
    const label = job.progress?.label;
    return typeof label === 'string' && label.trim()
      ? label
      : 'Analyse du calendrier en cours…';
  }
  if (job.status === 'committed') return 'Enregistrement terminé';
  if (job.status === 'cancelled') return 'Import annulé';
  if (job.status === 'cancelling') return 'Annulation en cours…';
  if (job.status === 'failed') return job.errorMessage ?? "L'enregistrement a échoué.";
  const progress = job.progress;
  const phaseLabel = progress?.phase_label;
  const label = progress?.label;
  if (typeof phaseLabel === 'string' && phaseLabel.trim()) {
    return typeof label === 'string' && label.trim() ? `${phaseLabel} — ${label}` : phaseLabel;
  }
  const total = Number(progress?.total);
  const done = Number(progress?.done);
  if (Number.isFinite(total) && Number.isFinite(done) && total > 0) {
    return `${done}/${total} salarié(s) — enregistrement…`;
  }
  return 'Enregistrement du calendrier en cours…';
}
