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

  // Retour d'Elsa du 26/11 : arrêt du 29/09 saisi après la validation de septembre.
  it("dit que l'arrêt est reporté sur le bulletin d'octobre", () => {
    const p = phraseMaintien(arret('reporte_sur_le_bulletin_suivant'), { year: 2026, month: 9 });
    expect(p.texte).toBe("Reporté sur le bulletin d'octobre");
    expect(p.ton).toBe('ok');
  });

  it("annonce le report au calcul d'octobre, ou demande de le recalculer", () => {
    expect(
      phraseMaintien(arret('report_au_prochain_calcul'), { year: 2026, month: 9 }).texte,
    ).toBe("Bulletin de septembre validé avant l'arrêt : le bulletin d'octobre le reprendra à son calcul");
    expect(phraseMaintien(arret('report_a_recalculer'), { year: 2026, month: 9 }).texte).toContain(
      "recalculez le bulletin d'octobre",
    );
  });

  it('ne promet rien quand le bulletin suivant était validé lui aussi', () => {
    const p = phraseMaintien(arret('bulletin_remis_avant_l_arret'), { year: 2026, month: 9 });
    expect(p.texte).not.toContain('le rappel se fait');
    expect(p.texte).toContain("Bulletins de septembre et d'octobre validés");
    expect(p.texte).toContain('ne le reporte pas seule');
    expect(p.texte).toContain('sur le bulletin de novembre');
  });

  it('passe de décembre à janvier, et reste juste sans le mois', () => {
    expect(
      phraseMaintien(arret('reporte_sur_le_bulletin_suivant'), { year: 2026, month: 12 }).texte,
    ).toBe('Reporté sur le bulletin de janvier');
    expect(phraseMaintien(arret('report_au_prochain_calcul')).texte).toContain('le bulletin suivant');
  });

  it("ne demande rien quand l'arrêt est déjà retenu ou déjà porté à la main", () => {
    const mois = { year: 2026, month: 9 };
    expect(phraseMaintien(arret('compte_par_le_bulletin'), mois).texte).toBe(
      'Compté par le bulletin de septembre',
    );
    expect(phraseMaintien(arret('porte_a_la_main'), mois).texte).toBe(
      "Déjà porté à la main sur le bulletin d'octobre",
    );
    expect(phraseMaintien(arret('dans_la_periode_suivante'), mois).texte).toBe(
      "Dans la période de paie d'octobre : compté par le bulletin d'octobre",
    );
  });
});
