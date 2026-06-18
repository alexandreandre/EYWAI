import type { ContingentStatus } from '@/api/overtimeContingent';

export const CONTINGENT_STATUS_LABELS: Record<ContingentStatus, string> = {
  ok: 'Dans les clous',
  near_limit: 'Proche du plafond',
  management_exceeded: 'Plafond dépassé',
  cor_exceeded: 'Seuil COR légal dépassé',
};

export function getContingentStatusVariant(
  status: ContingentStatus,
): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'cor_exceeded':
    case 'management_exceeded':
      return 'destructive';
    case 'near_limit':
      return 'secondary';
    default:
      return 'outline';
  }
}

export function getUsageBarColor(usagePercent: number): string {
  if (usagePercent >= 100) return 'bg-destructive';
  if (usagePercent >= 80) return 'bg-amber-500';
  return 'bg-emerald-500';
}

export function formatHours(value: number): string {
  return `${value.toFixed(2).replace('.', ',')} h`;
}

export type ContingentFilter =
  | 'all'
  | 'near_limit'
  | 'management_exceeded'
  | 'cor_exceeded';

export function matchesContingentFilter(
  status: ContingentStatus,
  filter: ContingentFilter,
): boolean {
  if (filter === 'all') return true;
  return status === filter;
}
