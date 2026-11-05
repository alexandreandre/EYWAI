import { describe, expect, it } from 'vitest';
import { motifProposeAuDepart } from './motifPropose';

// Un CDD qui finit à son terme est une fin de CDD : Martine le propose d'office,
// la RH peut changer (« des parcours RH simplifiés », jamais de blocage).
describe('motif proposé au départ', () => {
  it("un CDD avec une date de fin : Fin de CDD, à la date de fin, et Martine le dit", () => {
    expect(motifProposeAuDepart({ contract_type: 'CDD', contract_end_date: '2026-09-30' })).toEqual({
      motif: 'fin_cdd',
      dernierJour: '2026-09-30',
      phrase: 'Proposé par Martine : CDD qui finit le 30/09/2026.',
    });
  });

  it('un CDI : rien de proposé', () => {
    expect(motifProposeAuDepart({ contract_type: 'CDI', contract_end_date: null })).toBeNull();
  });

  it('un CDD sans date de fin : rien de proposé', () => {
    expect(motifProposeAuDepart({ contract_type: 'CDD', contract_end_date: null })).toBeNull();
  });

  it('aucun salarié choisi : rien de proposé', () => {
    expect(motifProposeAuDepart(undefined)).toBeNull();
  });
});
