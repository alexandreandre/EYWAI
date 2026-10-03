import { describe, expect, it } from 'vitest';

import type { CompanyDetails } from '@/api/company';
import {
  avertissementJourSolidarite,
  champsNonRelus,
  construireMiseAJour,
  parametresOntChange,
  resumeParametresPaie,
  saisieInitiale,
} from './parametresPaie';

function societe(champs: Partial<CompanyDetails> = {}): CompanyDetails {
  return {
    effectif: 19,
    taux_at_mp: 3.15,
    paie_jour_de_fin: 4,
    paie_occurrence: -2,
    settings: { compensation_heures_entre_semaines: true },
    ...champs,
  } as CompanyDetails;
}

describe('saisieInitiale', () => {
  it('reprend les valeurs enregistrées', () => {
    const saisie = saisieInitiale(
      societe({
        effectif: 25,
        settings: {
          taux_assurance_chomage: 2.95,
          date_paiement: 'dernier_jour_du_mois',
          jour_solidarite: '2026-05-25',
        },
      }),
    );
    expect(saisie).toEqual({
      tauxChomage: '2.95',
      effectif: '25',
      datePaiement: 'dernier_jour_du_mois',
      jourSolidarite: '2026-05-25',
    });
  });

  it('montre le comportement réel quand rien n’est réglé', () => {
    // Sans réglage, le moteur paie à la date de l'arrêté des variables.
    expect(saisieInitiale(societe({ effectif: null, settings: undefined }))).toEqual({
      tauxChomage: '',
      effectif: '',
      datePaiement: 'arrete_des_variables',
      jourSolidarite: '',
    });
  });
});

describe('construireMiseAJour — taux d’assurance chômage', () => {
  const sansRien = societe();

  it('accepte les bornes du bonus-malus, virgule comprise', () => {
    for (const [saisi, attendu] of [
      ['2,95', 2.95],
      ['4', 4],
      ['5', 5],
      [' 3.4 ', 3.4],
    ] as const) {
      const { corps, erreurs } = construireMiseAJour(sansRien, {
        ...saisieInitiale(sansRien),
        tauxChomage: saisi,
      });
      expect(erreurs).toEqual({});
      expect(corps).toEqual({ taux_assurance_chomage: attendu });
    }
  });

  it('refuse hors de 2,95 % – 5 % et dit quoi faire', () => {
    for (const saisi of ['2,94', '5,01', '5,05', '0', '-1']) {
      const { corps, erreurs } = construireMiseAJour(sansRien, {
        ...saisieInitiale(sansRien),
        tauxChomage: saisi,
      });
      expect(corps).toEqual({});
      expect(erreurs.tauxChomage).toBe(
        'Le taux notifié est compris entre 2,95 % et 5 %. Laissez vide pour le taux normal.',
      );
    }
  });

  it('refuse ce qui n’est pas un nombre', () => {
    const { erreurs } = construireMiseAJour(sansRien, {
      ...saisieInitiale(sansRien),
      tauxChomage: 'deux',
    });
    expect(erreurs.tauxChomage).toBe('Indiquez un nombre, par exemple 4,05.');
  });

  it('vider le champ revient au taux normal (null)', () => {
    const avecTaux = societe({ settings: { taux_assurance_chomage: 2.95 } });
    const { corps, erreurs } = construireMiseAJour(avecTaux, {
      ...saisieInitiale(avecTaux),
      tauxChomage: '',
    });
    expect(erreurs).toEqual({});
    expect(corps).toEqual({ taux_assurance_chomage: null });
  });
});

describe('construireMiseAJour — effectif', () => {
  it('accepte un entier, 0 compris', () => {
    for (const [saisi, attendu] of [
      ['0', 0],
      ['21', 21],
      [' 50 ', 50],
    ] as const) {
      const { corps, erreurs } = construireMiseAJour(societe(), {
        ...saisieInitiale(societe()),
        effectif: saisi,
      });
      expect(erreurs).toEqual({});
      expect(corps).toEqual({ effectif: attendu });
    }
  });

  it('refuse un nombre négatif ou à virgule', () => {
    for (const saisi of ['-1', '12,5', '12.5', 'vingt']) {
      const { corps, erreurs } = construireMiseAJour(societe(), {
        ...saisieInitiale(societe()),
        effectif: saisi,
      });
      expect(corps).toEqual({});
      expect(erreurs.effectif).toBe('Indiquez un nombre entier, 0 ou plus.');
    }
  });

  it('ne laisse pas vider un effectif déjà renseigné', () => {
    const { corps, erreurs } = construireMiseAJour(societe(), {
      ...saisieInitiale(societe()),
      effectif: '',
    });
    expect(corps).toEqual({});
    expect(erreurs.effectif).toBe(
      "L'effectif ne peut pas rester vide : indiquez un nombre entier, 0 ou plus.",
    );
  });

  it('laisse vide un effectif jamais renseigné', () => {
    const vide = societe({ effectif: null });
    expect(construireMiseAJour(vide, saisieInitiale(vide))).toEqual({ corps: {}, erreurs: {} });
  });
});

describe('construireMiseAJour — date de paiement et journée de solidarité', () => {
  it('n’écrit pas le choix par défaut tant qu’il n’est pas changé', () => {
    // Écrire « arrete_des_variables » à la place de « rien » ne changerait pas
    // la date, mais ferait passer tous les bulletins « À recalculer ».
    const rien = societe();
    expect(construireMiseAJour(rien, saisieInitiale(rien))).toEqual({ corps: {}, erreurs: {} });
  });

  it('écrit le dernier jour du mois quand on le choisit', () => {
    const rien = societe();
    expect(
      construireMiseAJour(rien, { ...saisieInitiale(rien), datePaiement: 'dernier_jour_du_mois' })
        .corps,
    ).toEqual({ date_paiement: 'dernier_jour_du_mois' });
  });

  it('écrit, change et retire la journée de solidarité', () => {
    const rien = societe();
    expect(
      construireMiseAJour(rien, { ...saisieInitiale(rien), jourSolidarite: '2027-05-17' }).corps,
    ).toEqual({ jour_solidarite: '2027-05-17' });

    const avec = societe({ settings: { jour_solidarite: '2026-05-25' } });
    expect(
      construireMiseAJour(avec, { ...saisieInitiale(avec), jourSolidarite: '' }).corps,
    ).toEqual({ jour_solidarite: null });
  });

  it('refuse une date impossible', () => {
    const rien = societe();
    const { corps, erreurs } = construireMiseAJour(rien, {
      ...saisieInitiale(rien),
      jourSolidarite: '2027-02-30',
    });
    expect(corps).toEqual({});
    expect(erreurs.jourSolidarite).toBe('Date invalide : choisissez un jour du calendrier.');
  });
});

describe('construireMiseAJour — rien ne change', () => {
  it('renvoyer les valeurs enregistrées ne produit aucun champ', () => {
    const reglee = societe({
      effectif: 25,
      settings: {
        taux_assurance_chomage: 2.95,
        date_paiement: 'dernier_jour_du_mois',
        jour_solidarite: '2026-05-25',
      },
    });
    expect(construireMiseAJour(reglee, saisieInitiale(reglee))).toEqual({
      corps: {},
      erreurs: {},
    });
    // « 2,95 » et « 2.95 » sont le même taux.
    expect(
      construireMiseAJour(reglee, { ...saisieInitiale(reglee), tauxChomage: '2,95' }).corps,
    ).toEqual({});
  });
});

describe('avertissementJourSolidarite', () => {
  it('prévient quand la date n’est pas de l’année en cours', () => {
    expect(avertissementJourSolidarite('2026-05-25', 2027)).toBe(
      'Cette date est en 2026 : indiquez celle de 2027.',
    );
  });

  it('se tait pour l’année en cours ou un champ vide', () => {
    expect(avertissementJourSolidarite('2027-05-17', 2027)).toBeNull();
    expect(avertissementJourSolidarite('', 2027)).toBeNull();
  });
});

describe('champsNonRelus', () => {
  it('ne signale rien quand la base renvoie ce qui a été envoyé', () => {
    const relue = societe({
      effectif: 21,
      settings: { taux_assurance_chomage: 2.95, date_paiement: 'dernier_jour_du_mois' },
    });
    expect(
      champsNonRelus(
        { effectif: 21, taux_assurance_chomage: 2.95, date_paiement: 'dernier_jour_du_mois' },
        relue,
      ),
    ).toEqual([]);
  });

  it('nomme chaque réglage que la base n’a pas gardé', () => {
    const relue = societe({ effectif: 19, settings: {} });
    expect(
      champsNonRelus({ effectif: 21, taux_assurance_chomage: 2.95, jour_solidarite: null }, relue),
    ).toEqual(['Effectif retenu pour les seuils', "Taux d'assurance chômage"]);
  });
});

describe('parametresOntChange', () => {
  it('voit un changement de réglage qui touche le calcul', () => {
    expect(parametresOntChange(societe(), societe({ effectif: 21 }))).toBe(true);
    expect(
      parametresOntChange(societe(), societe({ settings: { taux_assurance_chomage: 2.95 } })),
    ).toBe(true);
    expect(parametresOntChange(societe(), societe({ taux_at_mp: 3.4 }))).toBe(true);
  });

  it('ignore une relecture identique', () => {
    expect(parametresOntChange(societe(), societe())).toBe(false);
  });
});

describe('resumeParametresPaie', () => {
  it('relit les valeurs enregistrées en clair', () => {
    expect(
      resumeParametresPaie(
        societe({
          effectif: 21,
          settings: {
            taux_assurance_chomage: 2.95,
            date_paiement: 'dernier_jour_du_mois',
            jour_solidarite: '2026-05-25',
          },
        }),
      ),
    ).toBe(
      'Effectif 21 · chômage 2,95 % · paiement le dernier jour du mois · solidarité le 25/05/2026',
    );
  });

  it('dit ce qui s’applique quand rien n’est réglé', () => {
    expect(resumeParametresPaie(societe({ effectif: null, settings: {} }))).toBe(
      "Effectif non renseigné · chômage au taux normal · paiement le jour de l'arrêté des variables · solidarité le lundi de Pentecôte",
    );
  });
});
