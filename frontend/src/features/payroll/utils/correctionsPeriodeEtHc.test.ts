import { describe, expect, it } from 'vitest';

import {
  type CotisationRegularisable,
  estTempsPartiel,
  etatInitial,
  gestesDeLaLigne,
  paliersHeuresComplementaires,
  periodeValide,
  regularisationDepuisEcart,
  requeteDeCorrection,
} from './correctionsBulletin';

const chomage: CotisationRegularisable = {
  cotiId: 'assurance_chomage',
  libelle: 'Assurance chômage',
  tauxSalarial: null,
  tauxPatronal: 0.04,
};

describe('période d’une régularisation (page client du 10/11, C1)', () => {
  it('porte la période saisie', () => {
    const regul = regularisationDepuisEcart(chomage, 4, 'les_deux', 'Taux erroné', {
      debut: '2026-07',
      fin: '2026-09',
    });
    expect(regul).toMatchObject({ base: 100, mois_debut: '2026-07', mois_fin: '2026-09' });
    expect(regularisationDepuisEcart(chomage, 4, 'les_deux', 'Taux erroné')).not.toHaveProperty('mois_debut');
  });

  it('refuse une période à l’envers ou postérieure au bulletin', () => {
    expect(periodeValide({ debut: '2026-07', fin: '2026-09' }, '2026-10')).toBe(true);
    expect(periodeValide({ debut: '2026-09', fin: '2026-07' }, '2026-10')).toBe(false);
    expect(periodeValide({ debut: '2026-09', fin: '2026-11' }, '2026-10')).toBe(false);
    expect(periodeValide({ debut: '', fin: '' }, '2026-10')).toBe(false);
  });
});

describe('heures complémentaires du mois (C2)', () => {
  const hc = (pct: number, quantite: number) => ({
    libelle: `Heures complémentaires majorées à ${pct}%`,
    quantite,
    taux: 12 * (1 + pct / 100),
    gain: 1,
  });

  it('lit les paliers et les quantités sur le bulletin', () => {
    const data = { calcul_du_brut: [hc(10, 3), hc(25, 1)] };
    expect(paliersHeuresComplementaires(data)).toEqual([10, 25]);
    expect(paliersHeuresComplementaires({})).toEqual([10, 25]);
    const etat = etatInitial(data, '');
    expect([etat.hc1, etat.hc2]).toEqual([3, 1]);
  });

  it('les heures déclarées font foi', () => {
    const etat = etatInitial({ heures_complementaires_declarees: { hc1: 5, hc2: 0, planning: 3 } }, '');
    expect([etat.hc1, etat.hc2]).toEqual([5, 0]);
  });

  it('envoie les heures changées, ou le retour au planning', () => {
    const initial = etatInitial({ calcul_du_brut: [hc(10, 3)] }, '');
    expect(requeteDeCorrection(initial, { ...initial, hc1: 4 }, null).corrections).toEqual({
      heures_complementaires: { hc1: 4, hc2: 0 },
    });
    expect(requeteDeCorrection(initial, { ...initial, hcAuPlanning: true }, null).corrections).toEqual({
      heures_complementaires_au_planning: true,
    });
    expect(requeteDeCorrection(initial, initial, null).corrections).toEqual({});
  });
});

describe('gestes de chaque ligne de l’onglet Bulletin (C1)', () => {
  it('une cotisation se corrige ou se régularise sur un mois passé', () => {
    const g = gestesDeLaLigne(
      { code: 'cotisation:assurance_chomage', bloc: 'cotisations', libelle: 'Assurance chômage', mode: 'base_ou_taux' },
      1
    );
    expect(g.corriger).toEqual({ carte: 'ligne', code: 'cotisation:assurance_chomage', jeton: 1 });
    expect(g.regulariser).toEqual({ carte: 'cotisation', cotiId: 'assurance_chomage', libelle: 'Assurance chômage', jeton: 1 });
  });

  it('les heures se régularisent au bon palier', () => {
    const heures = (code: string) =>
      gestesDeLaLigne({ code, bloc: 'brut', libelle: 'x', mode: 'base_ou_taux' }, 2).regulariser;
    expect(heures('brut:heures_sup:25')).toMatchObject({ carte: 'heures', nature: 'hs1' });
    expect(heures('brut:heures_sup:50')).toMatchObject({ nature: 'hs2' });
    expect(heures('brut:heures_complementaires:10')).toMatchObject({ nature: 'hc1' });
    expect(heures('brut:heures_complementaires:25')).toMatchObject({ nature: 'hc2' });
    expect(heures('brut:salaire_base')).toMatchObject({ nature: 'normales' });
    expect(heures('brut:prime:prime-de-noel')).toBeNull();
    expect(
      gestesDeLaLigne({ code: 'brut:salaire_base', bloc: 'brut', libelle: 'x', mode: 'base_ou_taux' }, 3, {
        forfaitJours: true,
      }).regulariser
    ).toBeNull();
  });

  it('une ligne qui ne se corrige pas ici n’a pas de geste « Corriger »', () => {
    const g = gestesDeLaLigne({ code: 'brut:arret:x', bloc: 'brut', libelle: 'Arrêt', mode: null }, 4);
    expect(g.corriger).toBeNull();
  });
});

describe('temps partiel (C. trav. L3123-1)', () => {
  it('sous 35 h ou coché sur la fiche', () => {
    expect(estTempsPartiel({ duree_hebdomadaire: 24 })).toBe(true);
    expect(estTempsPartiel({ is_temps_partiel: true, duree_hebdomadaire: 35 })).toBe(true);
    expect(estTempsPartiel({ duree_hebdomadaire: 35 })).toBe(false);
    expect(estTempsPartiel({ duree_hebdomadaire: 39 })).toBe(false);
    expect(estTempsPartiel(null)).toBe(false);
  });
});
