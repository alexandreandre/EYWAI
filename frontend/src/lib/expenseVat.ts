import type { ExpenseType } from '@/api/expenses';

export const STANDARD_VAT_RATES = [20, 10, 5.5, 2.1, 0] as const;

export type StandardVatRate = (typeof STANDARD_VAT_RATES)[number];

export type VatRatePreset = StandardVatRate | 'custom';

/** Taux TVA suggéré par type de dépense (usages courants en France). */
export const DEFAULT_VAT_BY_EXPENSE_TYPE: Record<ExpenseType, number> = {
  Restaurant: 10,
  Transport: 10,
  Hôtel: 10,
  Fournitures: 20,
  Autre: 20,
};

export function formatVatRateLabel(rate: number): string {
  if (rate === 0) return '0 % (exonéré)';
  const rounded = Math.round(rate * 10) / 10;
  return Number.isInteger(rounded) ? `${rounded} %` : `${rounded.toLocaleString('fr-FR')} %`;
}

export function computeVatBreakdown(
  amountTtc: number,
  vatRate: number
): { amountHt: number; vatAmount: number } {
  if (!Number.isFinite(amountTtc) || amountTtc < 0) {
    return { amountHt: 0, vatAmount: 0 };
  }
  if (!Number.isFinite(vatRate) || vatRate <= 0) {
    const ttc = Math.round(amountTtc * 100) / 100;
    return { amountHt: ttc, vatAmount: 0 };
  }
  const ht = amountTtc / (1 + vatRate / 100);
  const amountHt = Math.round(ht * 100) / 100;
  const vatAmount = Math.round((amountTtc - amountHt) * 100) / 100;
  return { amountHt, vatAmount };
}

export function parseVatRateInput(value: string): number | null {
  const normalized = value.replace(',', '.').trim();
  if (!normalized) return null;
  const n = Number(normalized);
  if (!Number.isFinite(n) || n < 0 || n > 100) return null;
  return Math.round(n * 100) / 100;
}

/**
 * Résumé TVA d'une dépense.
 * @param includeTtc inclure le rappel du montant TTC (faux quand le TTC est déjà
 *   affiché dans une colonne/ligne voisine, pour éviter la redondance).
 */
export function formatExpenseVatSummary(
  expense: {
    amount: number;
    vat_rate?: number | null;
    amount_ht?: number | null;
    vat_amount?: number | null;
  },
  options?: { includeTtc?: boolean }
): string | null {
  if (expense.vat_rate == null) return null;
  const includeTtc = options?.includeTtc ?? true;
  const fmt = (n: number) =>
    n.toLocaleString('fr-FR', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  const ht =
    expense.amount_ht ??
    computeVatBreakdown(expense.amount, expense.vat_rate).amountHt;
  const vat =
    expense.vat_amount ??
    computeVatBreakdown(expense.amount, expense.vat_rate).vatAmount;
  const parts = [
    `HT ${fmt(ht)} €`,
    `TVA ${formatVatRateLabel(expense.vat_rate)} (${fmt(vat)} €)`,
  ];
  if (includeTtc) {
    parts.unshift(`TTC ${fmt(expense.amount)} €`);
  }
  return parts.join(' · ');
}
