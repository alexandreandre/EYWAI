import { describe, expect, it } from 'vitest';
import {
  computeVatBreakdown,
  formatExpenseVatSummary,
  formatVatRateLabel,
  parseVatRateInput,
} from '@/lib/expenseVat';

describe('computeVatBreakdown', () => {
  it('décompose un TTC avec TVA 20 %', () => {
    const { amountHt, vatAmount } = computeVatBreakdown(120, 20);
    expect(amountHt).toBe(100);
    expect(vatAmount).toBe(20);
  });

  it('décompose un TTC avec TVA 10 %', () => {
    const { amountHt, vatAmount } = computeVatBreakdown(55, 10);
    expect(amountHt).toBe(50);
    expect(vatAmount).toBe(5);
  });

  it('taux 0 % → HT = TTC, TVA nulle', () => {
    expect(computeVatBreakdown(42, 0)).toEqual({ amountHt: 42, vatAmount: 0 });
  });

  it('montant négatif ou invalide → 0', () => {
    expect(computeVatBreakdown(-10, 20)).toEqual({ amountHt: 0, vatAmount: 0 });
    expect(computeVatBreakdown(Number.NaN, 20)).toEqual({
      amountHt: 0,
      vatAmount: 0,
    });
  });
});

describe('parseVatRateInput', () => {
  it('accepte la virgule et arrondit', () => {
    expect(parseVatRateInput('5,5')).toBe(5.5);
    expect(parseVatRateInput('20')).toBe(20);
  });

  it('rejette les valeurs hors bornes / vides', () => {
    expect(parseVatRateInput('')).toBeNull();
    expect(parseVatRateInput('-1')).toBeNull();
    expect(parseVatRateInput('101')).toBeNull();
    expect(parseVatRateInput('abc')).toBeNull();
  });
});

describe('formatVatRateLabel', () => {
  it('formate les taux courants', () => {
    expect(formatVatRateLabel(0)).toContain('exonéré');
    expect(formatVatRateLabel(20)).toBe('20 %');
    expect(formatVatRateLabel(5.5)).toContain('5,5');
  });
});

describe('formatExpenseVatSummary', () => {
  it('retourne null sans taux de TVA (legacy)', () => {
    expect(formatExpenseVatSummary({ amount: 100, vat_rate: null })).toBeNull();
  });

  it('inclut le TTC par défaut', () => {
    const summary = formatExpenseVatSummary({
      amount: 120,
      vat_rate: 20,
      amount_ht: 100,
      vat_amount: 20,
    });
    expect(summary).toContain('TTC');
    expect(summary).toContain('HT');
    expect(summary).toContain('TVA');
  });

  it('omet le TTC avec includeTtc=false', () => {
    const summary = formatExpenseVatSummary(
      { amount: 120, vat_rate: 20 },
      { includeTtc: false }
    );
    expect(summary).not.toContain('TTC');
    expect(summary).toContain('HT');
    expect(summary).toContain('TVA');
  });

  it('recalcule HT/TVA si non fournis', () => {
    const summary = formatExpenseVatSummary(
      { amount: 110, vat_rate: 10 },
      { includeTtc: false }
    );
    expect(summary).toContain('100,00');
  });
});
