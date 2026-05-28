import type { Expense, ExpenseStatus } from '@/api/expenses';

export const EXPENSE_STATUS_LABELS: Record<ExpenseStatus, string> = {
  pending: 'En attente',
  validated: 'Validée',
  rejected: 'Refusée',
};

export function countExpensesByStatus(expenses: Expense[]) {
  return {
    pending: expenses.filter((e) => e.status === 'pending').length,
    validated: expenses.filter((e) => e.status === 'validated').length,
    rejected: expenses.filter((e) => e.status === 'rejected').length,
  };
}

export function formatExpenseDate(iso: string): string {
  return new Date(iso).toLocaleDateString('fr-FR');
}

export function truncateDescription(text: string | null | undefined, max = 48): string {
  if (!text?.trim()) return '—';
  const trimmed = text.trim();
  if (trimmed.length <= max) return trimmed;
  return `${trimmed.slice(0, max)}…`;
}
