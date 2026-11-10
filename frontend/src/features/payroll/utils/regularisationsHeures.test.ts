import { describe, expect, it } from 'vitest';

import {
  etatInitial,
  heuresRegulariseesDuBulletin,
  moisAffiche,
  moisPrecedent,
  requeteDeCorrection,
} from './correctionsBulletin';

const ligne = {
  libelle: 'Régularisation heures sup 25 % – 09/2026',
  quantite: 3.5,
  taux: 15.4942,
  gain: 54.23,
  regularisation_heures: { saisie_id: 's1', motif: 'Semaine 38 oubliée', nature: 'hs1', mois_origine: '2026-09' },
};

describe('régularisations d’heures', () => {
  it('relit les heures régularisées imprimées sur le bulletin', () => {
    expect(heuresRegulariseesDuBulletin({ calcul_du_brut: [ligne, { libelle: 'Salaire de base' }] })).toEqual([
      {
        saisieId: 's1',
        libelle: 'Régularisation heures sup 25 % – 09/2026',
        motif: 'Semaine 38 oubliée',
        quantite: 3.5,
        taux: 15.4942,
        montant: 54.23,
      },
    ]);
    expect(heuresRegulariseesDuBulletin(null)).toEqual([]);
  });

  it('envoie les heures ajoutées et retirées au serveur', () => {
    const initial = etatInitial({ calcul_du_brut: [ligne] }, '');
    const courant = {
      ...initial,
      heuresRegulariseesAjoutees: [
        { nature: 'normales' as const, mois_origine: '2026-08', quantite: 2, motif: 'Heures du contrat', taux_horaire: null },
      ],
      heuresRegulariseesRetirees: ['s1'],
    };
    const requete = requeteDeCorrection(initial, courant, null);
    expect(requete.corrections.regularisations_heures_ajoutees).toHaveLength(1);
    expect(requete.corrections.regularisations_heures_retirees).toEqual(['s1']);
    expect(Object.keys(requeteDeCorrection(initial, initial, null).corrections)).toHaveLength(0);
  });

  it('écrit les mois comme sur le bulletin', () => {
    expect(moisAffiche('2026-09')).toBe('09/2026');
    expect(moisPrecedent(2026, 1)).toBe('2025-12');
    expect(moisPrecedent(2026, 10)).toBe('2026-09');
  });
});
