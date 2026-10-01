import { describe, expect, it } from 'vitest';
import { createEmployeeFormSchema } from '@/features/employees/components/createEmployeeFormSchema';
import {
  bandeauNonEnregistre,
  champNumeriqueRefuseParLeNavigateur,
  decisionCreation,
  emailHtmlInvalide,
  estErreurValidationInattendue,
  fusionnerExtractionContrat,
  lireNouveauSalarie,
  memoriserNouveauSalarie,
  MENTION_RIB_A_COMPLETER,
  MESSAGE_FERMETURE_SANS_ENREGISTRER,
  mentionsListeSalarie,
  mettreEnTeteDeListe,
  NOM_DES_ONGLETS,
  payloadJournalEcran,
  pastillesParOnglet,
  raisonEchecCreation,
  saisieNonEnregistree,
  texteDuBoutonCreation,
} from './creationSalarie';

/** Ce que la gestionnaire a sous les yeux : nom, prénom, entrée le 21/09, RIB vide. */
const SAISIE = {
  first_name: 'Jeanne',
  last_name: 'Essai',
  email: '',
  nir: '',
  date_naissance: '',
  lieu_naissance: '',
  nationalite: 'Française',
  adresse: { rue: '', code_postal: '', ville: '' },
  coordonnees_bancaires: { iban: '', bic: '' },
  hire_date: '2026-09-21',
  contract_type: 'CDI',
  statut: 'Non-Cadre',
  is_forfait_jour: false,
  job_title: 'Opératrice',
  has_periode_essai: false,
  is_temps_partiel: false,
  duree_hebdomadaire: 39,
  salaire_de_base: { valeur: 1990.001 },
  classification_conventionnelle: { groupe_emploi: 'C', classe_emploi: 710, coefficient: 710 },
  collective_agreement_id: null,
  avantages_en_nature: {
    repas: { nombre_par_mois: 0 },
    logement: { beneficie: false },
    vehicule: { beneficie: false },
  },
  specificites_paie: {
    is_alsace_moselle: false,
    prelevement_a_la_source: { is_personnalise: true, taux: 1.15 },
    transport: { abonnement_mensuel_total: 0, indemnite_mensuelle_nette: 0 },
    titres_restaurant: { beneficie: false, nombre_par_mois: 0 },
    mutuelle: { mutuelle_type_ids: ['iso-nc'], lignes_specifiques: [] },
    prevoyance: { adhesion: true, lignes_specifiques: [] },
  },
};

describe('cause du blocage : le navigateur refuse avant toute requête', () => {
  it('un salaire au millième n’est pas un multiple de 0,01', () => {
    expect(champNumeriqueRefuseParLeNavigateur(1990.001, 0.01)).toBe(true);
    expect(champNumeriqueRefuseParLeNavigateur(1990, 0.01)).toBe(false);
  });

  it('un taux à 1,15 % n’est pas un multiple de 0,1', () => {
    expect(champNumeriqueRefuseParLeNavigateur(1.15, 0.1)).toBe(true);
    expect(champNumeriqueRefuseParLeNavigateur(1.1, 0.1)).toBe(false);
  });

  it('sans pas imposé, ces valeurs passent', () => {
    expect(champNumeriqueRefuseParLeNavigateur(1990.001, 'any')).toBe(false);
    expect(champNumeriqueRefuseParLeNavigateur(1.15, 'any')).toBe(false);
  });

  it('un e-mail extrait sans @ est refusé à côté du nom', () => {
    expect(emailHtmlInvalide('Jeanne Essai')).toBe(true);
    expect(emailHtmlInvalide('')).toBe(false);
    expect(emailHtmlInvalide('jeanne.essai@example.com')).toBe(false);
  });

  it('Zod accepte la saisie (RIB vide, millième, 1,15 %) : le blocage n’est pas le schéma', () => {
    const r = createEmployeeFormSchema.safeParse(SAISIE);
    expect(r.success).toBe(true);
  });

  it('tant que le navigateur impose un pas, on n’envoie pas', () => {
    const d = decisionCreation(SAISIE, { nombresHorsPas: true });
    expect(d.envoyer).toBe(false);
    expect(d.message).toMatch(/Rémunération|chiffre|numérique/i);
    expect(d.message).not.toMatch(/^Une erreur est survenue/);
    expect(d.onglet).toBe('remuneration');
  });

  it('une fois le pas levé, on peut envoyer', () => {
    const d = decisionCreation(SAISIE);
    expect(d.envoyer).toBe(true);
    expect(d.texteBouton).toBe('Enregistrer le salarié');
    expect(d.message).toBeNull();
  });
});

describe('fusion du contrat PDF', () => {
  it('ne remplace pas un nom saisi par une initiale extraite', () => {
    const fusion = fusionnerExtractionContrat(SAISIE, { last_name: 'M', first_name: 'J' });
    expect(fusion.last_name).toBe('Essai');
    expect(fusion.first_name).toBe('Jeanne');
  });

  it('ne pose pas un e-mail sans @ qui ferait échouer le champ à côté du nom', () => {
    const fusion = fusionnerExtractionContrat(SAISIE, { email: 'Jeanne Essai' });
    expect(fusion.email).toBe('');
  });

  it('garde un nom extrait lisible et un salaire au millième', () => {
    const fusion = fusionnerExtractionContrat(SAISIE, {
      last_name: 'Dupont-Essai',
      salaire_de_base: { valeur: '1 990,001' },
    });
    expect(fusion.last_name).toBe('Dupont-Essai');
    expect(fusion.salaire_de_base.valeur).toBeCloseTo(1990.001);
  });
});

describe('garde-fous d’écran', () => {
  it('le bouton dit combien il reste, et dans quel onglet', () => {
    const d = decisionCreation({ ...SAISIE, job_title: '', hire_date: '' });
    expect(d.envoyer).toBe(false);
    expect(d.texteBouton).toBe('2 informations à compléter (onglet Contrat)');
    expect(d.pastilles.contrat).toBe(2);
    expect(d.resteARemplir[0]?.onglet).toBe('contrat');
  });

  it('pastilles et encadré mènent à l’onglet en erreur', () => {
    const pastilles = pastillesParOnglet([
      { chemin: 'last_name', message: 'Nom requis.' },
      { chemin: 'salaire_de_base.valeur', message: 'Salaire requis.' },
    ]);
    expect(pastilles).toEqual({
      collaborateur: 1,
      contrat: 0,
      remuneration: 1,
      avantages: 0,
      specifiques: 0,
    });
    expect(NOM_DES_ONGLETS.remuneration).toBe('Rémunération');
  });

  it('fermer une saisie non enregistrée demande confirmation', () => {
    expect(saisieNonEnregistree(true, false)).toBe(true);
    expect(saisieNonEnregistree(false, true)).toBe(true);
    expect(saisieNonEnregistree(false, false)).toBe(false);
    expect(MESSAGE_FERMETURE_SANS_ENREGISTRER).toBe(
      "Ce salarié n'est pas enregistré. Fermer sans enregistrer ?",
    );
  });

  it('un échec dit que le salarié n’est pas enregistré, jamais le générique seul', () => {
    expect(bandeauNonEnregistre('le nom est trop court')).toBe(
      'Salarié NON enregistré : le nom est trop court',
    );
    const reseau = raisonEchecCreation({ message: 'Network Error' });
    expect(reseau).toMatch(/NON enregistré/);
    expect(reseau).not.toMatch(/^Une erreur est survenue/);
    const serveur = raisonEchecCreation({
      response: { status: 500, data: { detail: 'traceback boom.py' } },
    });
    expect(serveur).toMatch(/NON enregistré/);
    expect(serveur).not.toMatch(/traceback/i);
    expect(texteDuBoutonCreation({ nb: 1, onglet: 'Collaborateur' })).toBe(
      '1 information à compléter (onglet Collaborateur)',
    );
  });

  it('une validation technique (type inattendu) est inattendue', () => {
    expect(estErreurValidationInattendue('Expected string, received number')).toBe(true);
    expect(estErreurValidationInattendue('Nom requis.')).toBe(false);
  });
});

describe('RIB facultatif et liste', () => {
  it('la mention liste dit « RIB à compléter »', () => {
    expect(mentionsListeSalarie(['Numéro de sécurité sociale', 'Coordonnées bancaires (RIB)'])).toEqual(
      ['Numéro de sécurité sociale', MENTION_RIB_A_COMPLETER],
    );
  });

  it('le salarié créé passe en tête, avec le badge Nouveau', () => {
    memoriserNouveauSalarie('id-nouveau', 1_000);
    expect(lireNouveauSalarie(1_000)).toBe('id-nouveau');
    const liste = mettreEnTeteDeListe(
      [
        { id: 'a', last_name: 'A' },
        { id: 'id-nouveau', last_name: 'B' },
      ],
      'id-nouveau',
    );
    expect(liste[0].id).toBe('id-nouveau');
  });
});

describe('journal des erreurs de l’écran', () => {
  it('ne porte ni nom, ni RIB, ni PDF, et tronque la pile', () => {
    const p = payloadJournalEcran({
      ecran: 'creation-salarie',
      action: 'enregistrer',
      message: 'Nom : Jeanne Essai IBAN FR7630006000011234567890189 fichier contrat.pdf',
      pile: Array.from({ length: 40 }, (_, i) => `ligne ${i}`).join('\n'),
      extra: { last_name: 'Essai', pdf: 'AAAA' },
    });
    expect(p).toEqual({
      ecran: 'creation-salarie',
      action: 'enregistrer',
      message: expect.not.stringMatching(/Jeanne|FR76|contrat\.pdf/i),
      pile: expect.any(String),
    });
    expect(p.pile.split('\n').length).toBeLessThanOrEqual(20);
    expect(Object.keys(p).sort()).toEqual(['action', 'ecran', 'message', 'pile']);
  });
});
