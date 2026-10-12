import { describe, expect, it } from 'vitest';
import { createEmployeeFormSchema } from './createEmployeeFormSchema';

/** Ce que Gaëlle connaît le jour de l'embauche, et rien de plus. */
const MINIMAL = {
  first_name: 'Jeanne',
  last_name: 'Essai',
  email: '',
  nir: '',
  date_naissance: '',
  lieu_naissance: '',
  nationalite: 'Française',
  adresse: { rue: '', code_postal: '', ville: '' },
  coordonnees_bancaires: { iban: '', bic: '' },
  hire_date: '2026-09-14',
  contract_type: 'CDI',
  statut: 'Non-Cadre',
  is_forfait_jour: false,
  job_title: 'Préparatrice peinture',
  has_periode_essai: false,
  is_temps_partiel: false,
  duree_hebdomadaire: 39,
  salaire_de_base: { valeur: 1990 },
  classification_conventionnelle: { groupe_emploi: 'C', classe_emploi: 710, coefficient: 710 },
  collective_agreement_id: null,
  avantages_en_nature: { repas: { nombre_par_mois: 0 }, logement: { beneficie: false }, vehicule: { beneficie: false } },
  specificites_paie: {
    is_alsace_moselle: false,
    prelevement_a_la_source: { is_personnalise: false, taux: 0 },
    transport: { abonnement_mensuel_total: 0, indemnite_mensuelle_nette: 0 },
    titres_restaurant: { beneficie: false, nombre_par_mois: 0 },
    mutuelle: { mutuelle_type_ids: ['iso-nc'], lignes_specifiques: [] },
    prevoyance: { adhesion: true, lignes_specifiques: [] },
  },
};

const erreurs = (modifs: Record<string, unknown>) => {
  const r = createEmployeeFormSchema.safeParse({ ...MINIMAL, ...modifs });
  return r.success ? [] : r.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`);
};

describe('création : le minimum suffit', () => {
  it("nom, prénom, poste, date d'entrée et salaire suffisent", () => {
    expect(erreurs({})).toEqual([]);
  });

  it('le salaire et la date d’entrée restent obligatoires', () => {
    expect(erreurs({ salaire_de_base: { valeur: '' } })).toEqual(['salaire_de_base.valeur: Salaire requis.']);
    expect(erreurs({ hire_date: '' })).toEqual(["hire_date: Date d'entrée requise."]);
    expect(erreurs({ job_title: ' ' })).toEqual(['job_title: Poste requis.']);
  });

  it('un salaire mensuel absurde est refusé : la virgule a sans doute été perdue', () => {
    expect(erreurs({ salaire_de_base: { valeur: 1990001 } })).toEqual([
      expect.stringMatching(/^salaire_de_base\.valeur: .*virgule/),
    ]);
  });

  it('un champ facultatif rempli doit être juste', () => {
    expect(erreurs({ email: 'jeanne@' })).toEqual(['email: Adresse e-mail invalide.']);
    expect(erreurs({ nir: '29005730080' })).toEqual([
      'nir: Le numéro de sécurité sociale fait 15 caractères.',
    ]);
    expect(erreurs({ coordonnees_bancaires: { iban: 'FR76 1234', bic: '' } })).toEqual([
      'coordonnees_bancaires.iban: IBAN invalide.',
    ]);
  });

  it('une adresse se donne entière ou pas du tout', () => {
    expect(erreurs({ adresse: { rue: '1 rue de l’Essai', code_postal: '', ville: '' } })).toEqual([
      'adresse.code_postal: Adresse incomplète : rue, code postal et ville, ou rien.',
    ]);
    expect(erreurs({ adresse: { rue: '1 rue de l’Essai', code_postal: '01300', ville: 'Belley' } })).toEqual([]);
  });

  it('un CDD demande sa date de fin', () => {
    expect(erreurs({ contract_type: 'CDD' })).toEqual([
      'contract_end_date: Date de fin de contrat requise pour un CDD ou un stage.',
    ]);
    expect(erreurs({ contract_type: 'CDD', contract_end_date: '2027-03-31' })).toEqual([]);
  });

  it('un numéro de sécurité sociale corse ou avec espaces passe', () => {
    expect(erreurs({ nir: '1 85 07 2A 004 123 45' })).toEqual([]);
    expect(erreurs({ nir: '290057300800001' })).toEqual([]);
  });
});

describe('création : salaire saisi en base 35 h', () => {
  it('le réglage survit à la validation du formulaire', () => {
    const valeurs = {
      ...MINIMAL,
      specificites_paie: { ...MINIMAL.specificites_paie, salaire_hors_hs_structurelles: true },
    };
    const res = createEmployeeFormSchema.safeParse(valeurs);
    expect(res.success).toBe(true);
    expect(res.success && res.data.specificites_paie.salaire_hors_hs_structurelles).toBe(true);
  });
});

describe('titres-restaurant : valeur du titre et part patronale ([B5], 12/10/2026)', () => {
  // Le moteur retient (valeur du titre − part patronale) × nombre ; sans ces deux
  // champs à l’écran, la case n’avait aucun effet sur le bulletin.
  const avecTitres = (titres: Record<string, unknown>) => ({
    specificites_paie: {
      ...MINIMAL.specificites_paie,
      titres_restaurant: { beneficie: true, nombre_par_mois: 20, ...titres },
    },
  });

  it('accepte la valeur du titre et la part patronale', () => {
    expect(erreurs(avecTitres({ valeur_faciale: 9, part_patronale: 5.4 }))).toEqual([]);
  });

  it('refuse une part patronale plus grande que la valeur du titre', () => {
    expect(erreurs(avecTitres({ valeur_faciale: 9, part_patronale: 10 }))).toContain(
      'specificites_paie.titres_restaurant.part_patronale: La part patronale ne peut pas dépasser la valeur du titre.',
    );
  });

  it('des titres sans valeur sont refusés : ils ne retiendraient rien', () => {
    expect(erreurs(avecTitres({ valeur_faciale: 0, part_patronale: 0 }))).toContain(
      'specificites_paie.titres_restaurant.valeur_faciale: Indiquez la valeur d’un titre (en euros).',
    );
  });
});

describe('titre de séjour à la création ([D6-1], 12/10/2026)', () => {
  // L’étoile rouge disait « requise », le schéma ne l’exigeait pas : la fiche
  // créée sans date ne pouvait plus être enregistrée ensuite.
  it('soumis à titre de séjour sans date : refusé, comme sur la fiche', () => {
    expect(erreurs({ is_subject_to_residence_permit: true, residence_permit_expiry_date: '' })).toContain(
      "residence_permit_expiry_date: Date d'expiration du titre de séjour requise.",
    );
  });

  it('avec sa date, ou non soumis : accepté', () => {
    expect(erreurs({ is_subject_to_residence_permit: true, residence_permit_expiry_date: '2027-03-31' })).toEqual([]);
    expect(erreurs({ is_subject_to_residence_permit: false, residence_permit_expiry_date: '' })).toEqual([]);
  });
});
