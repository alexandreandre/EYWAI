import { describe, expect, it } from 'vitest';
import { AIDE_PENSION_LIQUIDABLE, LIBELLE_PENSION_LIQUIDABLE } from './pensionLiquidable';

// BOSS « Indemnités de rupture » (ouvert le 11/10/2026), § 60, 890 et 940 : un
// salarié qui peut liquider sa retraite reçoit une indemnité de rupture
// conventionnelle imposable dès le premier euro ; son régime social ne change pas.
describe('rupture conventionnelle : salarié qui peut liquider sa retraite', () => {
  it('la case dit de quoi il s’agit', () => {
    expect(LIBELLE_PENSION_LIQUIDABLE).toBe('Le salarié peut liquider une pension de retraite de base');
  });

  it('l’aide dit ce que la case change, et ce qu’elle ne change pas', () => {
    expect(AIDE_PENSION_LIQUIDABLE).toContain('imposable dès le premier euro');
    expect(AIDE_PENSION_LIQUIDABLE).toContain('cotisations');
    expect(AIDE_PENSION_LIQUIDABLE).toContain('40 %');
    expect(AIDE_PENSION_LIQUIDABLE).toContain('ne changent pas');
  });
});
