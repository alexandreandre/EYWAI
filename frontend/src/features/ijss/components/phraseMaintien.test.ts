import { describe, expect, it } from 'vitest';
import type { ArretDuMois } from '@/api/ijssTracking';
import { phraseMaintien } from './ArretsDuMoisPanel';

const arret = (etat: ArretDuMois['maintien']['etat']) =>
  ({ maintien: { etat, montant_verse: 0, montant_en_attente: 0, motif: null } }) as ArretDuMois;

describe('phraseMaintien', () => {
  it("dit qu'un bulletin calculé avant l'arrêt est à régénérer", () => {
    const p = phraseMaintien(arret('bulletin_a_recalculer'));
    expect(p.texte).toContain("avant l'arrêt");
    expect(p.ton).toBe('attente');
  });

  // Retour d'Elsa du 26/11 : arrêt du 29/09 saisi après la remise de septembre.
  it('ne promet plus un rappel que Martine ne fait pas, et nomme les deux bulletins', () => {
    const p = phraseMaintien(arret('bulletin_remis_avant_l_arret'), { year: 2026, month: 9 });
    expect(p.texte).not.toContain('le rappel se fait');
    expect(p.texte).toContain('Bulletin de septembre remis');
    expect(p.texte).toContain('ne le reporte pas seule');
    expect(p.texte).toContain("sur le bulletin d'octobre");
    expect(p.ton).toBe('attente');
  });

  it('passe de décembre à janvier, et reste juste sans le mois', () => {
    expect(
      phraseMaintien(arret('bulletin_remis_avant_l_arret'), { year: 2026, month: 12 }).texte,
    ).toContain('sur le bulletin de janvier');
    expect(phraseMaintien(arret('bulletin_remis_avant_l_arret')).texte).toContain(
      'sur le bulletin suivant',
    );
  });
});
