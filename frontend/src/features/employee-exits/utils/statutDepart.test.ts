import { describe, expect, it } from 'vitest';
import { libelleStatutDepart } from './statutDepart';

const LE_2_OCTOBRE = new Date(2026, 9, 2, 18, 0);

describe('libelleStatutDepart', () => {
  it("une fin de CDD dont le dernier jour n'est pas passé est prévue, pas effective", () => {
    expect(libelleStatutDepart('demission_effective', '2026-10-31', LE_2_OCTOBRE)).toBe('Prévu le 31/10/2026');
  });

  it('le dernier jour passé ou atteint, le départ est effectif', () => {
    expect(libelleStatutDepart('demission_effective', '2026-09-15', LE_2_OCTOBRE)).toBe('Effective');
    expect(libelleStatutDepart('demission_effective', '2026-10-02', LE_2_OCTOBRE)).toBe('Effective');
  });

  it('les autres statuts gardent leur libellé', () => {
    expect(libelleStatutDepart('demission_recue', '2026-12-31', LE_2_OCTOBRE)).toBe('Reçue');
    expect(libelleStatutDepart('archivee', '2026-12-31', LE_2_OCTOBRE)).toBe('Archivée');
  });

  it('sans dernier jour, le libellé du statut', () => {
    expect(libelleStatutDepart('licenciement_effective', null, LE_2_OCTOBRE)).toBe('Effective');
  });
});
