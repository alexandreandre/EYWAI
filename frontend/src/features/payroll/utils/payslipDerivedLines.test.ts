import { describe, it, expect } from 'vitest';
import {
  estLigneHeuresSupConjoncturelle,
  lienVariablesDuMois,
} from './payslipDerivedLines';

describe('estLigneHeuresSupConjoncturelle', () => {
  it('reconnaît les heures supplémentaires conjoncturelles', () => {
    expect(estLigneHeuresSupConjoncturelle('Heures suppl. majorées à 25%')).toBe(true);
    expect(estLigneHeuresSupConjoncturelle('Heures suppl. majorées à 50%')).toBe(true);
  });

  it('écarte les structurelles : elles viennent du contrat, pas du mois', () => {
    expect(
      estLigneHeuresSupConjoncturelle('Heures suppl. structurelles majorées à 25%')
    ).toBe(false);
  });

  it('écarte les heures complémentaires du temps partiel', () => {
    expect(
      estLigneHeuresSupConjoncturelle('Heures complémentaires majorées à 10%')
    ).toBe(false);
  });

  it('écarte le salaire de base, les primes et les lignes sans libellé', () => {
    expect(estLigneHeuresSupConjoncturelle('Salaire de base')).toBe(false);
    expect(estLigneHeuresSupConjoncturelle('Panier repas')).toBe(false);
    expect(estLigneHeuresSupConjoncturelle("Prime d'ancienneté (3 ans, 2 %)")).toBe(
      false
    );
    expect(estLigneHeuresSupConjoncturelle('')).toBe(false);
    expect(estLigneHeuresSupConjoncturelle(undefined)).toBe(false);
  });
});

describe('lienVariablesDuMois', () => {
  it('cible la page Primes sur le bon mois et le bon salarié', () => {
    expect(lienVariablesDuMois({ employeeId: 'abc', year: 2026, month: 7 })).toBe(
      '/saisies?year=2026&month=7&employee=abc'
    );
  });

  it('reste utilisable sans salarié', () => {
    expect(lienVariablesDuMois({ year: 2026, month: 12 })).toBe(
      '/saisies?year=2026&month=12'
    );
  });
});
