import { describe, expect, it } from 'vitest';

import type { CompanyDetails } from '@/api/company';
import {
  avertissementJourSolidarite,
  champsNonRelus,
  construireMiseAJour,
  messageApresEnregistrement,
  parametresOntChange,
  repliEffectif,
  resumeParametresPaie,
  saisieInitiale,
} from './parametresPaie';

const ANNEE = new Date().getFullYear();

/** `effectif` est le nombre de comptes (déclencheur de la base) ; l'effectif
 * des seuils se saisit par année dans `settings.effectif_seuils`. */
function societe(champs: Partial<CompanyDetails> = {}): CompanyDetails {
  return {
    effectif: 19,
    taux_at_mp: 3.15,
    paie_jour_de_fin: 4,
    paie_occurrence: -2,
    settings: { compensation_heures_entre_semaines: true, effectif_seuils: { [ANNEE]: 5 } },
    ...champs,
  } as CompanyDetails;
}

describe('saisieInitiale', () => {
  it('reprend les valeurs enregistrées', () => {
    const saisie = saisieInitiale(
      societe({
        effectif: 19,
        settings: {
          taux_assurance_chomage: 2.95,
          date_paiement: 'dernier_jour_du_mois',
          jour_solidarite: '2026-05-25',
          effectif_seuils: { [ANNEE]: 25 },
        },
      }),
    );
    expect(saisie).toEqual({
      tauxChomage: '2.95',
      effectif: '25',
      datePaiement: 'dernier_jour_du_mois',
      jourSolidarite: '2026-05-25',
      compteIban: '',
      compteBic: '',
      compteTitulaire: '',
      miseADisposition: '1',
    });
  });

  it('montre le comportement réel quand rien n’est réglé', () => {
    // Sans réglage, le moteur paie à la date de l'arrêté des variables.
    expect(saisieInitiale(societe({ effectif: 19, settings: undefined }))).toEqual({
      tauxChomage: '',
      effectif: '',
      datePaiement: 'arrete_des_variables',
      jourSolidarite: '',
      compteIban: '',
      compteBic: '',
      compteTitulaire: '',
      miseADisposition: '1',
    });
  });
});

describe('mise à disposition des bulletins', () => {
  const sansReglage = societe();
  const desLaValidation = societe({
    settings: { effectif_seuils: { [ANNEE]: 5 }, bulletins_mise_a_disposition_jour: 0 },
  });

  it('se relit dans la saisie, le 1er du mois suivant par défaut', () => {
    expect(saisieInitiale(sansReglage).miseADisposition).toBe('1');
    expect(saisieInitiale(desLaValidation).miseADisposition).toBe('0');
  });

  it('ne s’envoie que si elle change', () => {
    expect(construireMiseAJour(sansReglage, saisieInitiale(sansReglage)).corps).toEqual({});
    expect(
      construireMiseAJour(sansReglage, { ...saisieInitiale(sansReglage), miseADisposition: '0' })
        .corps,
    ).toEqual({ bulletins_mise_a_disposition_jour: 0 });
    expect(
      construireMiseAJour(desLaValidation, { ...saisieInitiale(desLaValidation), miseADisposition: '5' })
        .corps,
    ).toEqual({ bulletins_mise_a_disposition_jour: 5 });
  });

  it('ne fait pas passer les bulletins « À recalculer », mais confirme l’enregistrement', () => {
    expect(parametresOntChange(sansReglage, desLaValidation)).toBe(false);
    expect(messageApresEnregistrement(sansReglage, desLaValidation).titre).toBe(
      'Paramètres paie enregistrés',
    );
  });

  it('se dit en clair dans le résumé', () => {
    expect(resumeParametresPaie(sansReglage)).toContain('bulletins visibles le 1er du mois suivant');
    expect(resumeParametresPaie(desLaValidation)).toContain('bulletins visibles dès la validation');
  });
});

describe('compte bancaire de la société', () => {
  const IBAN = 'FR7630001007941234567890185';
  const avecCompte = societe({
    settings: {
      effectif_seuils: { [ANNEE]: 5 },
      compte_bancaire: { iban: IBAN, bic: 'BNPAFRPP', titulaire: 'SAS Exemple' },
    },
  });
  const sansCompte = societe();

  it('se relit dans la saisie', () => {
    expect(saisieInitiale(avecCompte)).toMatchObject({
      compteIban: IBAN,
      compteBic: 'BNPAFRPP',
      compteTitulaire: 'SAS Exemple',
    });
  });

  it('s’envoie normalisé quand l’IBAN est juste', () => {
    const { corps, erreurs } = construireMiseAJour(sansCompte, {
      ...saisieInitiale(sansCompte),
      compteIban: 'fr76 3000 1007 9412 3456 7890 185',
      compteBic: 'bnpa frpp',
      compteTitulaire: ' SAS Exemple ',
    });
    expect(erreurs).toEqual({});
    expect(corps.compte_bancaire).toEqual({ iban: IBAN, bic: 'BNPAFRPP', titulaire: 'SAS Exemple' });
  });

  it('refuse une clé fausse en disant pourquoi, sans rien envoyer', () => {
    const { corps, erreurs } = construireMiseAJour(sansCompte, {
      ...saisieInitiale(sansCompte),
      compteIban: 'FR7630001007941234567890186',
    });
    expect(erreurs.compteIban).toContain('Clé de contrôle');
    expect(corps.compte_bancaire).toBeUndefined();
  });

  it('refuse un BIC incomplet', () => {
    const { erreurs } = construireMiseAJour(sansCompte, {
      ...saisieInitiale(sansCompte),
      compteIban: IBAN,
      compteBic: 'BNPA',
    });
    expect(erreurs.compteBic).toBe('BIC invalide : 8 ou 11 caractères, par exemple BNPAFRPP.');
  });

  it('exige l’IBAN dès qu’un autre champ du compte est rempli', () => {
    const { erreurs } = construireMiseAJour(sansCompte, {
      ...saisieInitiale(sansCompte),
      compteTitulaire: 'SAS Exemple',
    });
    expect(erreurs.compteIban).toContain('obligatoire');
  });

  it('retire le compte quand les trois champs sont vidés', () => {
    const { corps, erreurs } = construireMiseAJour(avecCompte, {
      ...saisieInitiale(avecCompte),
      compteIban: '',
      compteBic: '',
      compteTitulaire: '',
    });
    expect(erreurs).toEqual({});
    expect(corps.compte_bancaire).toBeNull();
  });

  it('n’envoie rien quand rien ne change, espaces compris', () => {
    const saisie = { ...saisieInitiale(avecCompte), compteIban: 'FR76 3000 1007 9412 3456 7890 185' };
    expect(construireMiseAJour(avecCompte, saisie)).toEqual({ corps: {}, erreurs: {} });
  });

  it('ne fait pas passer les bulletins « À recalculer »', () => {
    expect(parametresOntChange(sansCompte, avecCompte)).toBe(false);
  });

  it('nomme le compte quand la base ne l’a pas gardé', () => {
    const { corps } = construireMiseAJour(sansCompte, {
      ...saisieInitiale(sansCompte),
      compteIban: IBAN,
    });
    expect(champsNonRelus(corps, sansCompte)).toEqual(['Compte bancaire de la société']);
    const relue = societe({
      settings: { effectif_seuils: { [ANNEE]: 5 }, compte_bancaire: { iban: IBAN } },
    });
    expect(champsNonRelus(corps, relue)).toEqual([]);
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
      expect(corps).toEqual({ effectif: attendu, effectif_annee: ANNEE });
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
    const vide = societe({ settings: {} });
    expect(construireMiseAJour(vide, saisieInitiale(vide))).toEqual({ corps: {}, erreurs: {} });
  });

  it('ne prend jamais le nombre de comptes pour l’effectif', () => {
    // 19 comptes dans Martine, rien de saisi : le champ reste vide.
    expect(saisieInitiale(societe({ effectif: 19, settings: {} })).effectif).toBe('');
  });
});

describe('repliEffectif', () => {
  it('se tait quand l’année est saisie', () => {
    expect(repliEffectif(societe(), ANNEE)).toBeNull();
  });

  it('dit quelle année est reprise', () => {
    const avant = societe({ settings: { effectif_seuils: { [ANNEE - 1]: 7 } } });
    expect(repliEffectif(avant, ANNEE)).toBe(
      `Non saisi pour ${ANNEE} : Martine reprend celui de ${ANNEE - 1} (7).`,
    );
  });

  it('dit que le nombre de comptes n’est pas l’effectif légal', () => {
    expect(repliEffectif(societe({ effectif: 19, settings: {} }), ANNEE)).toBe(
      `Non saisi pour ${ANNEE} : Martine compte les comptes de la société (19), qui ne sont pas l'effectif légal.`,
    );
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
      settings: {
        taux_assurance_chomage: 2.95,
        date_paiement: 'dernier_jour_du_mois',
        jour_solidarite: '2026-05-25',
        effectif_seuils: { [ANNEE]: 25 },
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
      effectif: 19,
      settings: {
        taux_assurance_chomage: 2.95,
        date_paiement: 'dernier_jour_du_mois',
        effectif_seuils: { [ANNEE]: 21 },
      },
    });
    expect(
      champsNonRelus(
        {
          effectif: 21,
          effectif_annee: ANNEE,
          taux_assurance_chomage: 2.95,
          date_paiement: 'dernier_jour_du_mois',
        },
        relue,
      ),
    ).toEqual([]);
  });

  it('nomme chaque réglage que la base n’a pas gardé', () => {
    const relue = societe({ effectif: 21, settings: {} });
    expect(
      champsNonRelus(
        { effectif: 21, effectif_annee: ANNEE, taux_assurance_chomage: 2.95, jour_solidarite: null },
        relue,
      ),
    ).toEqual(['Effectif retenu pour les seuils', "Taux d'assurance chômage"]);
  });
});

describe('parametresOntChange', () => {
  it('voit un changement de réglage qui touche le calcul', () => {
    expect(
      parametresOntChange(societe(), societe({ settings: { effectif_seuils: { [ANNEE]: 21 } } })),
    ).toBe(true);
    expect(
      parametresOntChange(societe(), societe({ settings: { taux_assurance_chomage: 2.95 } })),
    ).toBe(true);
    expect(parametresOntChange(societe(), societe({ taux_at_mp: 3.4 }))).toBe(true);
  });

  it('ignore une relecture identique', () => {
    expect(parametresOntChange(societe(), societe())).toBe(false);
  });

  it('ignore un compte créé : le nombre de comptes n’entre pas dans le calcul', () => {
    expect(parametresOntChange(societe(), societe({ effectif: 20 }))).toBe(false);
  });
});

describe('resumeParametresPaie', () => {
  it('relit les valeurs enregistrées en clair', () => {
    expect(
      resumeParametresPaie(
        societe({
          effectif: 19,
          settings: {
            taux_assurance_chomage: 2.95,
            date_paiement: 'dernier_jour_du_mois',
            jour_solidarite: '2026-05-25',
            effectif_seuils: { [ANNEE]: 21 },
          },
        }),
      ),
    ).toBe(
      `Effectif ${ANNEE} : 21 · chômage 2,95 % · paiement le dernier jour du mois · solidarité le 25/05/2026 · bulletins visibles le 1er du mois suivant`,
    );
  });

  it('dit ce qui s’applique quand rien n’est réglé', () => {
    expect(resumeParametresPaie(societe({ effectif: 19, settings: {} }))).toBe(
      `Effectif ${ANNEE} non saisi · chômage au taux normal · paiement le jour de l'arrêté des variables · solidarité le lundi de Pentecôte · bulletins visibles le 1er du mois suivant`,
    );
  });
});


describe('message après « Enregistrer » ([B10], 12/10/2026)', () => {
  it('rien de changé : il le dit, au lieu de « Paramètres paie enregistrés »', () => {
    const avant = societe();
    expect(messageApresEnregistrement(avant, societe()).titre).toBe('Aucun changement à enregistrer');
  });

  it('un réglage du calcul : les brouillons passent « À recalculer », un validé n’est pas touché', () => {
    const avant = societe();
    const apres = societe({ taux_at_mp: 2.5 });
    const message = messageApresEnregistrement(avant, apres);
    expect(message.titre).toBe('Paramètres paie enregistrés');
    expect(message.description).toContain(
      'Les brouillons déjà calculés passent « À recalculer » ; un bulletin validé n’est pas touché.',
    );
  });

  it('le compte bancaire seul : enregistré, aucun bulletin à recalculer', () => {
    const avant = societe();
    const apres = societe({
      settings: { effectif_seuils: { [ANNEE]: 5 }, compte_bancaire: { iban: 'FR7630001007941234567890185' } },
    });
    const message = messageApresEnregistrement(avant, apres);
    expect(message.titre).toBe('Paramètres paie enregistrés');
    expect(message.description).not.toContain('À recalculer');
  });
});
