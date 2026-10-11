import { describe, expect, it } from 'vitest';
import { OPTIONS_PREAVIS, PREAVIS_PAR_DEFAUT, typePreavisApresApercu } from './preavis';

// Code du travail L1234-5 et service-public F2883 (ouverts le 11/10/2026) :
// préavis exécuté, dispense à l'initiative de l'employeur (indemnité
// compensatrice), dispense à la demande du salarié (rien n'est dû).
describe('préavis : trois cas, libellés alignés sur le calcul', () => {
  it('propose les trois cas et « Non applicable », chacun dit ce que le calcul verse', () => {
    expect(OPTIONS_PREAVIS).toEqual([
      { value: 'executed', label: 'Exécuté (payé avec le salaire)' },
      { value: 'paid', label: "Dispense à l'initiative de l'employeur (indemnité compensatrice)" },
      { value: 'waived', label: 'Dispense à la demande du salarié (aucune indemnité)' },
      { value: 'not_applicable', label: 'Non applicable' },
    ]);
  });

  it('par défaut, le préavis est exécuté : aucune indemnité ne s’ajoute au salaire', () => {
    expect(PREAVIS_PAR_DEFAUT).toBe('executed');
  });

  it('quand l’aperçu propose un préavis, la valeur revient à « exécuté », jamais à une indemnité', () => {
    expect(typePreavisApresApercu({ applicable: true, notice_period_days: 60 }, 'not_applicable')).toBe(
      'executed'
    );
    expect(typePreavisApresApercu({ applicable: true, notice_period_days: 60 }, 'waived')).toBe('waived');
    expect(typePreavisApresApercu({ applicable: true, notice_period_days: 60 }, 'paid')).toBe('paid');
  });

  it('sans préavis, « Non applicable »', () => {
    expect(typePreavisApresApercu({ applicable: false, notice_period_days: 0 }, 'executed')).toBe(
      'not_applicable'
    );
    expect(typePreavisApresApercu({ applicable: true, notice_period_days: 0 }, 'paid')).toBe(
      'not_applicable'
    );
  });
});
