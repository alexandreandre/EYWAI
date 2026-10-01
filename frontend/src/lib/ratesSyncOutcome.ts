import type { RatesSyncJob, RatesSyncStatusResponse } from '@/api/rates';
import { getCategoryTitle } from '@/lib/ratesLabels';
import { sanitizeBackendMessage } from '@/lib/errorMessages';

const SYNC_GENERIC_ERROR =
  'La mise à jour des taux a échoué. Réessayez ou contactez le support.';

export function humanizeSyncError(message: string | null | undefined): string {
  if (!message?.trim()) {
    return 'Une erreur est survenue lors de la récupération des données.';
  }

  const normalized = message.trim();
  if (normalized.includes('Annulé par')) {
    return 'Mise à jour annulée.';
  }
  if (
    normalized.includes('interrompu') ||
    normalized.includes('délai dépassé') ||
    normalized.includes('Timeout')
  ) {
    return 'La mise à jour a été interrompue (délai dépassé). Réessayez.';
  }
  if (normalized.includes('Script non trouvé') || normalized.includes('.py')) {
    return SYNC_GENERIC_ERROR;
  }
  // Nettoie le message restant : si technique, on retombe sur un message propre.
  return sanitizeBackendMessage(normalized) ?? SYNC_GENERIC_ERROR;
}

export type SyncOutcomePresentation = {
  tone: 'success' | 'warning' | 'error' | 'muted';
  title: string;
  summary: string;
  failedJobs: RatesSyncJob[];
  jobsWithLogs: RatesSyncJob[];
};

function isFailedJob(job: RatesSyncJob): boolean {
  return (
    job.status === 'failed' ||
    (job.status === 'completed' && job.success === false)
  );
}

function formatRateKeyLabels(rateKeys: string[]): string {
  const labels = [...new Set(rateKeys.filter(Boolean))].map(getCategoryTitle);
  if (labels.length === 0) return '';
  if (labels.length === 1) return labels[0];
  if (labels.length === 2) return `${labels[0]} et ${labels[1]}`;
  return `${labels.slice(0, -1).join(', ')} et ${labels[labels.length - 1]}`;
}

function buildBatchSummary(
  outcome: RatesSyncStatusResponse,
  fallback: string,
): string {
  const rateKeys = outcome.target?.rate_keys;
  if (!rateKeys || rateKeys.length <= 1) return fallback;

  const labels = formatRateKeyLabels(rateKeys);
  switch (outcome.status) {
    case 'completed':
      return `Les données de ${labels} ont été contrôlées et sont à jour.`;
    case 'completed_with_errors': {
      const failedJobs = outcome.jobs.filter(isFailedJob);
      const failedLabels = failedJobs
        .flatMap((job) => job.rate_keys ?? [])
        .map(getCategoryTitle);
      const failedText =
        failedLabels.length > 0
          ? formatRateKeyLabels([...new Set(failedLabels)])
          : `${failedJobs.length} source${failedJobs.length > 1 ? 's' : ''}`;
      return `Mise à jour de ${labels} terminée avec des erreurs sur ${failedText}. Les autres éléments ont été traités.`;
    }
    case 'failed':
      return `Impossible de mettre à jour ${labels}.`;
    case 'cancelled':
      return `La mise à jour de ${labels} a été interrompue avant la fin.`;
    default:
      return fallback;
  }
}

function isSucceededJob(job: RatesSyncJob): boolean {
  return job.status === 'completed' && job.success === true;
}

/** Un lot « failed » qui a quand même des sources réussies est une mise à jour partielle. */
export function normalizeSyncOutcome(
  outcome: RatesSyncStatusResponse,
): RatesSyncStatusResponse {
  if (outcome.status !== 'failed') return outcome;
  const succeeded = outcome.jobs.filter(isSucceededJob);
  if (succeeded.length === 0) return outcome;
  return { ...outcome, status: 'completed_with_errors' };
}

/**
 * Le serveur a perdu le lot en mémoire alors que des jobs avaient déjà un état.
 * On garde les succès et on signale le reste comme non confirmé.
 */
export function recoverInterruptedSync(
  last: RatesSyncStatusResponse,
): RatesSyncStatusResponse {
  const jobs = last.jobs.map((job) => {
    if (isSucceededJob(job) || isFailedJob(job) || job.status === 'cancelled') {
      return job;
    }
    return {
      ...job,
      status: 'failed' as const,
      success: false,
      error_message:
        job.error_message || 'Suivi interrompu avant la fin de cette source.',
    };
  });
  const recovered: RatesSyncStatusResponse = {
    ...last,
    jobs,
    progress: {
      ...last.progress,
      percent: 100,
      done: jobs.length,
      running: 0,
      failed: jobs.filter(isFailedJob).length,
      completed: jobs.filter(isSucceededJob).length,
    },
  };
  const anySuccess = jobs.some(isSucceededJob);
  const anyFailed = jobs.some(isFailedJob);
  if (anySuccess && anyFailed) recovered.status = 'completed_with_errors';
  else if (anySuccess) recovered.status = 'completed';
  else recovered.status = 'failed';
  return recovered;
}

export function buildSyncOutcomePresentation(
  outcome: RatesSyncStatusResponse,
): SyncOutcomePresentation {
  outcome = normalizeSyncOutcome(outcome);
  const failedJobs = outcome.jobs.filter(isFailedJob);
  const cancelledJobs = outcome.jobs.filter((j) => j.status === 'cancelled');
  const jobsWithLogs = outcome.jobs.filter((j) => (j.execution_logs?.length ?? 0) > 0);
  const multiKey = (outcome.target?.rate_keys?.length ?? 0) > 1;

  switch (outcome.status) {
    case 'completed':
      return {
        tone: 'success',
        title: multiKey ? 'Section mise à jour' : 'Mise à jour terminée',
        summary: buildBatchSummary(
          outcome,
          'Les données ont été contrôlées et sont à jour.',
        ),
        failedJobs: [],
        jobsWithLogs,
      };
    case 'completed_with_errors':
      return {
        tone: 'warning',
        title: multiKey ? 'Mise à jour partielle de la section' : 'Mise à jour partielle',
        summary: buildBatchSummary(
          outcome,
          `${failedJobs.length} source${failedJobs.length > 1 ? 's' : ''} n’${failedJobs.length > 1 ? 'ont' : 'a'} pas pu être mise${failedJobs.length > 1 ? 's' : ''} à jour. Les autres référentiels ont été traités.`,
        ),
        failedJobs,
        jobsWithLogs: failedJobs.filter((j) => (j.execution_logs?.length ?? 0) > 0),
      };
    case 'failed':
      return {
        tone: 'error',
        title: multiKey ? 'Échec de la mise à jour de la section' : 'Échec de la mise à jour',
        summary: buildBatchSummary(
          outcome,
          failedJobs.length === 1
            ? `Impossible de mettre à jour ${failedJobs[0].source_name}.`
            : 'Aucune source n’a pu être mise à jour.',
        ),
        failedJobs,
        jobsWithLogs: failedJobs.filter((j) => (j.execution_logs?.length ?? 0) > 0),
      };
    case 'cancelled':
      return {
        tone: 'muted',
        title: multiKey ? 'Mise à jour de section annulée' : 'Mise à jour annulée',
        summary: buildBatchSummary(
          outcome,
          'La mise à jour a été interrompue avant la fin.',
        ),
        failedJobs: cancelledJobs.length > 0 ? cancelledJobs : failedJobs,
        jobsWithLogs: outcome.jobs.filter((j) => (j.execution_logs?.length ?? 0) > 0),
      };
    default:
      return {
        tone: 'muted',
        title: 'Mise à jour',
        summary: '',
        failedJobs,
        jobsWithLogs,
      };
  }
}
