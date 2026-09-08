import { describe, it, expect } from 'vitest';
import {
  estLigneDeVariableMensuelle,
  lienVariablesDuMois,
} from './payslipDerivedLines';

describe('estLigneDeVariableMensuelle', () => {
  it('reconnaît les heures supplémentaires conjoncturelles', () => {
    expect(estLigneDeVariableMensuelle('Heures suppl. majorées à 25%')).toBe(true);
    expect(estLigneDeVariableMensuelle('Heures suppl. majorées à 50%')).toBe(true);
  });

  it('écarte les heures supplémentaires structurelles (elles viennent du contrat)', () => {
    expect(
      estLigneDeVariableMensuelle('Heures suppl. structurelles majorées à 25%')
    ).toBe(false);
  });

  it('reconnaît les paniers', () => {
    expect(estLigneDeVariableMensuelle('Panier repas')).toBe(true);
    expect(estLigneDeVariableMensuelle('Réintégration panier Panier chantier')).toBe(true);
  });

  it('écarte le salaire de base et les lignes sans libellé', () => {
    expect(estLigneDeVariableMensuelle('Salaire de base')).toBe(false);
    expect(estLigneDeVariableMensuelle('Heures normales travaillées')).toBe(false);
    expect(estLigneDeVariableMensuelle('')).toBe(false);
    expect(estLigneDeVariableMensuelle(undefined)).toBe(false);
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
