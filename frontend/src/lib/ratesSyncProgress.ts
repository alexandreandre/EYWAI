import type { RatesSyncJob, RatesSyncStatusResponse } from '@/api/rates';

export function formatSyncEta(seconds: number | null | undefined): string | null {
  if (seconds == null || seconds <= 0) return null;
  if (seconds < 60) return `~${seconds} s restantes`;
  const min = Math.ceil(seconds / 60);
  if (min === 1) return '~1 min restante';
  return `~${min} min restantes`;
}

export function syncProgressLabel(status: RatesSyncStatusResponse | null | undefined): string {
  const p = status?.progress;
  if (!p) return 'Initialisation…';

  const parts: string[] = [];
  if (p.current_source) {
    parts.push(p.current_source);
  }
  if (p.current_step) {
    parts.push(p.current_step);
  }
  if (parts.length > 0) return parts.join(' — ');

  return `${p.done} / ${p.total} source${p.total > 1 ? 's' : ''}`;
}

export function jobStatusLabel(job: RatesSyncJob): string {
  if (job.status === 'completed' && job.success !== false) return 'Terminé';
  if (job.status === 'failed' || job.success === false) return 'Échec';
  if (job.status === 'cancelled') return 'Annulé';
  if (job.status === 'pending') return 'En attente';
  return job.current_step || 'En cours';
}

export function jobProgressPercent(job: RatesSyncJob): number {
  if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
    return 100;
  }
  const frac = job.progress_fraction ?? 0;
  return Math.round(Math.min(99, frac * 100));
}
