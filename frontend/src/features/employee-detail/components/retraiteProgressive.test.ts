import { describe, expect, it } from 'vitest';

import {
  RETRAITE_PROGRESSIVE_VIDE,
  erreursRetraiteProgressive,
  joursAttendus,
  quotiteSaisie,
  retraiteProgressiveDuFormulaire,
  retraiteProgressivePourEnvoi,
} from './retraiteProgressive';

const COCHE = {
  ...RETRAITE_PROGRESSIVE_VIDE,
  actif: true,
  quotite: '50',
  date_debut: '2026-10-01',
};

describe('retraite progressive : réglage de la fiche', () => {
  it('lit la quotité en pourcentage et la range en fraction', () => {
    expect(quotiteSaisie('50')).toBe(0.5);
    expect(quotiteSaisie('62,5 %')).toBe(0.625);
    expect(quotiteSaisie('')).toBeNull();
    expect(Number.isNaN(quotiteSaisie('30'))).toBe(true);
    expect(Number.isNaN(quotiteSaisie('moitié'))).toBe(true);
  });

  it('relit une fiche existante', () => {
    const form = retraiteProgressiveDuFormulaire({
      actif: true,
      quotite: 0.5,
      date_debut: '2026-10-01',
      vieillesse_temps_plein: true,
    });
    expect(form).toMatchObject({ actif: true, quotite: '50', date_debut: '2026-10-01', vieillesse_temps_plein: true });
    expect(retraiteProgressiveDuFormulaire(undefined)).toEqual(RETRAITE_PROGRESSIVE_VIDE);
  });

  it('refuse une quotité hors bornes et une date de début vide', () => {
    expect(erreursRetraiteProgressive(COCHE)).toEqual({});
    expect(Object.keys(erreursRetraiteProgressive({ ...COCHE, quotite: '90', date_debut: '' }))).toEqual([
      'quotite',
      'date_debut',
    ]);
    expect(erreursRetraiteProgressive({ ...RETRAITE_PROGRESSIVE_VIDE, quotite: '90' })).toEqual({});
  });

  it("n'écrit rien pour une fiche sans réglage, décoche un réglage existant", () => {
    expect(retraiteProgressivePourEnvoi(RETRAITE_PROGRESSIVE_VIDE, undefined)).toBeUndefined();
    expect(retraiteProgressivePourEnvoi(RETRAITE_PROGRESSIVE_VIDE, { actif: true, quotite: 0.5 })).toEqual({
      actif: false,
      quotite: 0.5,
    });
  });

  it('écrit le réglage complet quand la case est cochée', () => {
    expect(retraiteProgressivePourEnvoi(COCHE, undefined)).toEqual({
      actif: true,
      quotite: 0.5,
      date_debut: '2026-10-01',
      date_fin: null,
      vieillesse_temps_plein: true,
      complementaire_temps_plein: false,
      prise_en_charge_part_salariale: false,
      salaire_temps_plein: null,
    });
  });

  it('donne les jours du forfait attendus (218 à temps plein)', () => {
    expect(joursAttendus(COCHE)).toBe(109);
  });
});
