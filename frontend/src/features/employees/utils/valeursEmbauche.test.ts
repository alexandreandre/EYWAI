import { describe, expect, it } from 'vitest';
import type { ValeursEmbauche } from '@/api/employees';
import type { CreateEmployeeFormValues } from '@/features/employees/components/createEmployeeFormSchema';
import { avecValeursDeLaSociete, moisEnClair, mutuellesPourStatut } from './valeursEmbauche';

const COLORPLAST: ValeursEmbauche = {
  statut: 'Non-Cadre',
  contract_type: 'CDI',
  duree_hebdomadaire: 39,
  collective_agreement_id: 'plasturgie',
  classification_conventionnelle: { groupe_emploi: 'C', classe_emploi: 710, coefficient: 710 },
  mutuelle_type_ids_par_statut: { 'Non-Cadre': ['iso-nc'], Cadre: ['iso-c'] },
  prevoyance_adhesion: true,
  titres_restaurant_beneficie: false,
  salaire_hors_hs_structurelles: true,
};

const BASE = {
  statut: 'Non-Cadre',
  contract_type: 'CDI',
  duree_hebdomadaire: 35,
  collective_agreement_id: null,
  classification_conventionnelle: { groupe_emploi: 'C', classe_emploi: 6, coefficient: 240 },
  specificites_paie: {
    titres_restaurant: { beneficie: true, nombre_par_mois: 0 },
    mutuelle: { mutuelle_type_ids: [], lignes_specifiques: [] },
    prevoyance: { adhesion: true, lignes_specifiques: [] },
  },
} as unknown as CreateEmployeeFormValues;

describe('avecValeursDeLaSociete', () => {
  it('remplace les valeurs génériques par celles de la société', () => {
    const v = avecValeursDeLaSociete(BASE, COLORPLAST);
    expect(v.duree_hebdomadaire).toBe(39);
    expect(v.collective_agreement_id).toBe('plasturgie');
    expect(v.classification_conventionnelle).toEqual({ groupe_emploi: 'C', classe_emploi: 710, coefficient: 710 });
    expect(v.specificites_paie.titres_restaurant.beneficie).toBe(false);
    expect(v.specificites_paie.mutuelle.mutuelle_type_ids).toEqual(['iso-nc']);
  });

  it('sans valeurs, rien ne change', () => {
    expect(avecValeursDeLaSociete(BASE, null)).toBe(BASE);
  });

  it('propose le salaire saisi en base 35 h quand les collègues sont payés ainsi', () => {
    expect(avecValeursDeLaSociete(BASE, COLORPLAST).specificites_paie.salaire_hors_hs_structurelles).toBe(true);
    const brutComplet = { ...COLORPLAST, salaire_hors_hs_structurelles: false };
    expect(avecValeursDeLaSociete(BASE, brutComplet).specificites_paie.salaire_hors_hs_structurelles).toBe(false);
  });
});

describe('mutuellesPourStatut', () => {
  it('la mutuelle suit la catégorie', () => {
    expect(mutuellesPourStatut(COLORPLAST, 'Cadre')).toEqual(['iso-c']);
    expect(mutuellesPourStatut(COLORPLAST, 'Non-Cadre')).toEqual(['iso-nc']);
  });
});

describe('moisEnClair', () => {
  it('dit la plage de mois posés', () => {
    expect(moisEnClair(['2026-10', '2026-09', '2026-12', '2026-11'])).toBe('septembre à décembre 2026');
    expect(moisEnClair(['2026-09'])).toBe('septembre 2026');
    expect(moisEnClair([])).toBeNull();
  });
});

import {
  champsFacultatifsPourEnvoi,
  erreursAPlat,
  erreursDansLOrdre,
  grilleAvecClassificationHabituelle,
  libelleDErreur,
  ongletDuChamp,
} from './valeursEmbauche';

describe('grilleAvecClassificationHabituelle', () => {
  const grille = [
    { groupe_emploi: 'Non précisé', classe_emploi: 0, coefficient: 700 },
    { groupe_emploi: 'Non précisé', classe_emploi: 0, coefficient: 710 },
  ];
  it('ajoute la classification de la société quand la grille ne la connaît pas', () => {
    const habituelle = { groupe_emploi: 'C', classe_emploi: 710, coefficient: 710 };
    expect(grilleAvecClassificationHabituelle(grille, habituelle)[0]).toEqual(habituelle);
  });
  it("ne double pas une classification déjà dans la grille", () => {
    expect(grilleAvecClassificationHabituelle(grille, grille[1])).toBe(grille);
    expect(grilleAvecClassificationHabituelle(grille, null)).toBe(grille);
  });
});

describe('erreurs du formulaire', () => {
  const erreurs = {
    salaire_de_base: { valeur: { message: 'Salaire requis.', type: 'too_small', ref: {} } },
    hire_date: { message: "Date d'entrée requise.", type: 'custom' },
  };
  it('se lisent en clair et mènent au bon onglet', () => {
    const aPlat = erreursAPlat(erreurs);
    expect(aPlat.map(libelleDErreur)).toEqual([
      'Salaire de base : Salaire requis.',
      "Date d'entrée : Date d'entrée requise.",
    ]);
    expect(aPlat.map((e) => ongletDuChamp(e.chemin))).toEqual(['remuneration', 'contrat']);
    expect(ongletDuChamp('adresse.rue')).toBe('collaborateur');
    expect(ongletDuChamp('specificites_paie.mutuelle.mutuelle_type_ids')).toBe('specifiques');
  });

  it("se listent dans l'ordre des onglets", () => {
    const desordre = [
      { chemin: 'salaire_de_base.valeur', message: 'Salaire requis.' },
      { chemin: 'job_title', message: 'Poste requis.' },
      { chemin: 'first_name', message: 'Prénom requis.' },
    ];
    expect(erreursDansLOrdre(desordre).map((e) => e.chemin)).toEqual(['first_name', 'job_title', 'salaire_de_base.valeur']);
  });
});

describe('champsFacultatifsPourEnvoi', () => {
  it('envoie null pour ce qui manque', () => {
    const envoi = champsFacultatifsPourEnvoi({
      email: ' ', nir: '', date_naissance: '', lieu_naissance: '', nationalite: 'Française',
      adresse: { rue: '', code_postal: '', ville: '' },
      coordonnees_bancaires: { iban: '', bic: '' },
    });
    expect(envoi).toMatchObject({
      email: null, nir: null, date_naissance: null, lieu_naissance: null, nationalite: 'Française',
      adresse: null, coordonnees_bancaires: null,
    });
  });
  it('nettoie ce qui est renseigné', () => {
    const envoi = champsFacultatifsPourEnvoi({
      email: 'Jeanne.Essai@Example.com', nir: '2 90 05 73 008 000 01',
      adresse: { rue: ' 1 rue de l’Essai ', code_postal: '01300', ville: 'Belley' },
      coordonnees_bancaires: { iban: 'fr76 3000 6000 0112 3456 7890 189', bic: 'agrifrpp' },
    });
    expect(envoi.email).toBe('jeanne.essai@example.com');
    expect(envoi.nir).toBe('290057300800001');
    expect(envoi.adresse).toEqual({ rue: '1 rue de l’Essai', code_postal: '01300', ville: 'Belley' });
    expect(envoi.coordonnees_bancaires).toEqual({ iban: 'FR7630006000011234567890189', bic: 'AGRIFRPP' });
  });
});
