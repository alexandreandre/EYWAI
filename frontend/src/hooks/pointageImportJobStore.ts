import {
  cancelTimesheetExtractJob,
  getTimesheetExtractJob,
  type AiCalendarProposal,
  type RosterEmployee,
  type TimesheetExtractJobStatus,
  type TimesheetExtractProgress,
} from '@/api/calendar';

const POLL_INTERVAL_MS = 2000;

export type PointageImportJobStatus = TimesheetExtractJobStatus;

export interface PointageImportJob {
  localId: string;
  jobId: string;
  label: string;
  year: number;
  month: number;
  roster: RosterEmployee[];
  singleEmployee: boolean;
  status: PointageImportJobStatus;
  progress: TimesheetExtractProgress;
  proposal: AiCalendarProposal | null;
  batchId: string | null;
  errorMessage: string | null;
  startedAt: number;
  completedAt: number | null;
  detached: boolean;
  reviewDismissed: boolean;
}

type JobPatch = Partial<
  Pick<
    PointageImportJob,
    | 'status'
    | 'progress'
    | 'proposal'
    | 'batchId'
    | 'errorMessage'
    | 'completedAt'
    | 'detached'
    | 'reviewDismissed'
  >
>;

export type RegisterPointageImportJobInput = {
  jobId: string;
  label: string;
  year: number;
  month: number;
  roster: RosterEmployee[];
  singleEmployee?: boolean;
  detached?: boolean;
};

const jobs = new Map<string, PointageImportJob>();
const pollTimers = new Map<string, ReturnType<typeof setInterval>>();
const listeners = new Set<() => void>();
let cachedSnapshot: PointageImportJob[] = [];

function rebuildSnapshot() {
  cachedSnapshot = [...jobs.values()].sort((a, b) => b.startedAt - a.startedAt);
}

function emit() {
  rebuildSnapshot();
  listeners.forEach((listener) => listener());
}

export function subscribePointageImportJobs(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getPointageImportJobsSnapshot(): PointageImportJob[] {
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
  if (timer) {
    clearInterval(timer);
    pollTimers.delete(localId);
  }
}

async function pollJob(localId: string) {
  const job = jobs.get(localId);
  if (!job || job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
    stopPolling(localId);
    return;
  }

  try {
    const remote = await getTimesheetExtractJob(job.jobId);
    const batchId = remote.progress.batch_id ?? job.batchId;
    patchJob(localId, {
      progress: remote.progress,
      batchId,
      status: remote.status,
      proposal: remote.proposal ?? job.proposal,
      errorMessage: remote.error_message ?? null,
      completedAt:
        remote.status === 'completed' ||
        remote.status === 'failed' ||
        remote.status === 'cancelled'
          ? Date.now()
          : job.completedAt,
    });

    if (remote.status === 'completed' || remote.status === 'failed' || remote.status === 'cancelled') {
      stopPolling(localId);
    }
  } catch {
    // Polling best-effort — on réessaie au prochain tick.
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

export function registerPointageImportJob(
  input: RegisterPointageImportJobInput,
): PointageImportJob {
  const localId = crypto.randomUUID();
  const job: PointageImportJob = {
    localId,
    jobId: input.jobId,
    label: input.label,
    year: input.year,
    month: input.month,
    roster: input.roster,
    singleEmployee: input.singleEmployee ?? false,
    status: 'extracting',
    progress: { phase: 'queued', pages_total: 0, pages_done: 0, current_page: 0 },
    proposal: null,
    batchId: null,
    errorMessage: null,
    startedAt: Date.now(),
    completedAt: null,
    detached: input.detached ?? false,
    reviewDismissed: false,
  };
  jobs.set(localId, job);
  emit();
  startPolling(localId);
  return job;
}

export function detachPointageImportJob(localId: string) {
  patchJob(localId, { detached: true });
}

export function dismissPointageImportReview(localId: string) {
  patchJob(localId, { reviewDismissed: true });
}

export function removePointageImportJob(localId: string) {
  stopPolling(localId);
  jobs.delete(localId);
  emit();
}

export async function cancelPointageImportJob(localId: string) {
  const job = jobs.get(localId);
  if (!job) return;
  stopPolling(localId);
  patchJob(localId, { status: 'cancelled', completedAt: Date.now() });
  try {
    await cancelTimesheetExtractJob(job.jobId);
  } catch {
    // Job peut déjà être terminé.
  }
}

export function progressPercent(progress: TimesheetExtractProgress): number {
  const total = progress.files_total ?? progress.pages_total ?? 0;
  const done = progress.files_done ?? progress.pages_done ?? 0;
  if (total <= 0) return 12;
  return Math.min(99, Math.max(8, Math.round((done / total) * 100)));
}

export function progressLabel(job: PointageImportJob): string {
  const { progress } = job;
  const total = progress.files_total ?? progress.pages_total ?? 0;
  const done = progress.files_done ?? progress.pages_done ?? 0;
  if (job.status === 'completed') return 'Analyse terminée';
  if (job.status === 'failed') return 'Analyse en échec';
  if (job.status === 'cancelled') return 'Analyse annulée';
  if (total > 0) {
    const unit = progress.files_total ? 'fichier' : 'page';
    return `${done}/${total} ${unit}${total > 1 ? 's' : ''} — analyse IA…`;
  }
  return 'Analyse IA en cours…';
}
