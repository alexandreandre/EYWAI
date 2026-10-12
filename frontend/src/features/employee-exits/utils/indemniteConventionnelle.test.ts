import { describe, expect, it } from 'vitest';
import {
  LIBELLE_INDEMNITE_CONVENTIONNELLE,
  aideIndemniteConventionnelle,
  indemniteConventionnelleSaisissable,
} from './indemniteConventionnelle';

// BOSS « Indemnités de rupture » (ouvert le 11/10/2026), § 80, 280, 300, 1550,
// 1630, 1640, 1650 : l'indemnité conventionnelle plus favorable remplace la
// légale ; le montant de la convention collective de branche est le seuil de
// la CSG/CRDS et le troisième critère des limites d'exonération.
describe('indemnité conventionnelle saisie sur le départ', () => {
  it('se saisit pour un licenciement, un départ ou une mise à la retraite', () => {
    expect(indemniteConventionnelleSaisissable('licenciement')).toBe(true);
    expect(indemniteConventionnelleSaisissable('depart_retraite')).toBe(true);
    for (const type of ['demission', 'rupture_conventionnelle', 'fin_cdd', 'fin_periode_essai', 'transfert'] as const) {
      expect(indemniteConventionnelleSaisissable(type)).toBe(false);
    }
  });

  it('le libellé dit que c’est le montant de la convention de branche', () => {
    expect(LIBELLE_INDEMNITE_CONVENTIONNELLE).toBe('Indemnité conventionnelle de branche (€)');
  });

  it('l’aide dit le plus élevé versé et le traitement en minimum conventionnel de branche', () => {
    for (const aide of [
      aideIndemniteConventionnelle('licenciement'),
      aideIndemniteConventionnelle('depart_retraite', 'employer'),
    ]) {
      expect(aide).toContain('le plus élevé');
      expect(aide).toContain('minimum conventionnel de branche');
      expect(aide).toContain('CSG/CRDS');
      expect(aide).toContain("limites d'exonération");
    }
  });

  it('pour un départ volontaire, l’aide dit que tout est soumis aux cotisations', () => {
    const aide = aideIndemniteConventionnelle('depart_retraite', 'employee');
    expect(aide).toContain('le plus élevé');
    expect(aide).toContain('soumise aux cotisations pour tout son montant');
    expect(aide).not.toContain("limites d'exonération");
  });
});
