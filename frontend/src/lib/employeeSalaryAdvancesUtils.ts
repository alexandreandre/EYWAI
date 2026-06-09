import { CheckCircle, CircleX, Clock, CreditCard } from 'lucide-react';
import type { SalaryAdvance, SalaryAdvanceStatus } from '@/api/saisiesAvances';
import type { AdvanceAvailableAmount } from '@/api/saisiesAvances';

export const STATUS_LABELS: Record<SalaryAdvanceStatus, string> = {
  pending: 'En attente',
  approved: 'À verser',
  rejected: 'Rejetée',
  paid: 'Versée',
};

export type SalaryAdvanceStatusFilter = SalaryAdvanceStatus | 'all';

export const VALID_STATUS_FILTERS = new Set<SalaryAdvanceStatusFilter>([
  'all',
  'pending',
  'approved',
  'paid',
  'rejected',
]);

export function filterAdvancesByStatus(
  advances: SalaryAdvance[],
  filter: SalaryAdvanceStatusFilter
): SalaryAdvance[] {
  if (filter === 'all') return advances;
  return advances.filter((a) => a.status === filter);
}

export function hasApprovedAmountDiff(advance: SalaryAdvance): boolean {
  if (advance.approved_amount == null) return false;
  return Number(advance.approved_amount) !== Number(advance.requested_amount);
}

export function showRemainingRepayment(advance: SalaryAdvance): boolean {
  if (advance.status !== 'paid' && advance.status !== 'approved') return false;
  return Number(advance.remaining_amount || 0) > 0;
}

export function formatAdvanceDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR');
}

export function formatAdvanceDateTime(iso: string): string {
  return new Date(iso).toLocaleString('fr-FR');
}

export type StatusBadgeConfig = {
  variant: 'secondary' | 'success' | 'destructive' | 'warning' | 'default';
  icon: typeof Clock;
  label: string;
};

export function getStatusBadgeConfig(status: SalaryAdvanceStatus): StatusBadgeConfig {
  switch (status) {
    case 'paid':
      return { variant: 'success', icon: CheckCircle, label: STATUS_LABELS.paid };
    case 'pending':
      return { variant: 'secondary', icon: Clock, label: STATUS_LABELS.pending };
    case 'approved':
      return { variant: 'warning', icon: CreditCard, label: STATUS_LABELS.approved };
    case 'rejected':
      return { variant: 'destructive', icon: CircleX, label: STATUS_LABELS.rejected };
    default:
      return { variant: 'default', icon: Clock, label: status };
  }
}

export function formatAdvanceNetRatio(data: AdvanceAvailableAmount): string {
  const ratio = Number(data.max_advance_net_ratio || 0.5);
  return `${Math.round(ratio * 100)} %`;
}

export function formatReferencePayslipMonth(
  year?: number | null,
  month?: number | null
): string | null {
  if (!year || !month) return null;
  return new Date(year, month - 1, 1).toLocaleDateString('fr-FR', {
    month: 'long',
    year: 'numeric',
  });
}

/** Ligne courte : plafond 50 % du net du dernier bulletin (mois cité). */
export function formatAdvancePlafondSummary(data: AdvanceAvailableAmount): string {
  const ratio = formatAdvanceNetRatio(data);
  const net = Number(data.reference_net_salary || 0);
  const cap = Number(data.max_advance_from_net || 0);
  const monthLabel = formatReferencePayslipMonth(
    data.reference_payslip_year,
    data.reference_payslip_month
  );

  if (monthLabel) {
    return `${ratio} du net de ${monthLabel}`;
  }
  return `${ratio} du salaire net de référence`;
}
