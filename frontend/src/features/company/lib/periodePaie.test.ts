import { describe, expect, it } from 'vitest';

import {
  PAIRE_AVANT_DERNIER_VENDREDI,
  PAIRE_MOIS_CIVIL,
  regimePeriodePaie,
} from './periodePaie';

describe('regimePeriodePaie', () => {
  it('reconnaît le mois civil posé par l’import DSN (31, -1)', () => {
    expect(
      regimePeriodePaie(
        PAIRE_MOIS_CIVIL.paie_jour_de_fin,
        PAIRE_MOIS_CIVIL.paie_occurrence,
      ),
    ).toBe('mois_civil');
  });

  it('traite tout jour hors 0-6 comme mois civil, quelle que soit l’occurrence', () => {
    // Même règle que est_mode_mois_calendaire côté moteur : 28/30 viennent
    // aussi d'imports DSN (jour du mois de versement).
    expect(regimePeriodePaie(28, -1)).toBe('mois_civil');
    expect(regimePeriodePaie(30, 2)).toBe('mois_civil');
  });

  it('reconnaît l’arrêté à l’avant-dernier vendredi (4, -2)', () => {
    expect(
      regimePeriodePaie(
        PAIRE_AVANT_DERNIER_VENDREDI.paie_jour_de_fin,
        PAIRE_AVANT_DERNIER_VENDREDI.paie_occurrence,
      ),
    ).toBe('avant_dernier_vendredi');
  });

  it('assimile (4, null) à l’avant-dernier vendredi, comme le moteur (-2 par défaut)', () => {
    expect(regimePeriodePaie(4, null)).toBe('avant_dernier_vendredi');
    expect(regimePeriodePaie(4, undefined)).toBe('avant_dernier_vendredi');
  });

  it('classe les autres couples jour-de-semaine en personnalisé', () => {
    expect(regimePeriodePaie(4, -1)).toBe('personnalise'); // dernier vendredi
    expect(regimePeriodePaie(0, -1)).toBe('personnalise'); // dernier lundi
    expect(regimePeriodePaie(2, 2)).toBe('personnalise'); // deuxième mercredi
  });

  it('signale l’absence de réglage', () => {
    expect(regimePeriodePaie(null, null)).toBe('non_defini');
    expect(regimePeriodePaie(undefined, -2)).toBe('non_defini');
  });
});
