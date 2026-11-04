import { describe, expect, it } from 'vitest';

import {
  buildDefaultValues,
  buildUpdatePayload,
  optionsDeClassification,
  readWeeklyHours,
} from '@/features/employee-detail/components/employeeProfileFormUtils';
import type { Employee } from '@/features/employee-detail/types';
import type { EmployeeProfileEditFormValues } from '@/features/employee-detail/components/employeeProfileEditSchema';
import { employeeProfileEditSchema } from '@/features/employee-detail/components/employeeProfileEditSchema';

const baseEmployee: Employee = {
  id: 'emp-1',
  first_name: 'Alice',
  last_name: 'Martin',
  job_title: 'Ingénieur R&D',
  contract_type: 'CDI',
  statut: 'Non-Cadre',
  hire_date: '2024-01-15',
  email: 'alice@example.com',
  nir: '123456789012345',
  date_naissance: '1990-05-10',
  lieu_naissance: 'Paris',
  nationalite: 'Française',
  adresse: { rue: '1 rue Test', code_postal: '75001', ville: 'Paris' },
  coordonnees_bancaires: { iban: 'FR7630001007941234567890185', bic: 'BNPAFRPP' },
  salaire_de_base: { valeur: 3500 },
  duree_hebdomadaire: 35,
  specificites_paie: {
    personnel_rd_eligible_jei: true,
    prelevement_a_la_source: { is_personnalise: false, taux: 0 },
    transport: { abonnement_mensuel_total: 0 },
    titres_restaurant: { beneficie: true, nombre_par_mois: 0 },
    mutuelle: { mutuelle_type_ids: [] },
    prevoyance: { adhesion: false },
  },
};

describe('employeeProfileFormUtils JEI', () => {
  it('buildDefaultValues lit personnel_rd_eligible_jei', () => {
    const values = buildDefaultValues(baseEmployee);
    expect(values.specificites_paie.personnel_rd_eligible_jei).toBe(true);
  });

  it('buildDefaultValues défaut à false si absent', () => {
    const values = buildDefaultValues({
      ...baseEmployee,
      specificites_paie: {},
    });
    expect(values.specificites_paie.personnel_rd_eligible_jei).toBe(false);
  });

  it('buildUpdatePayload persiste personnel_rd_eligible_jei', () => {
    const defaults = buildDefaultValues({
      ...baseEmployee,
      specificites_paie: { personnel_rd_eligible_jei: false },
    });
    const values: EmployeeProfileEditFormValues = {
      ...defaults,
      specificites_paie: {
        ...defaults.specificites_paie,
        personnel_rd_eligible_jei: true,
      },
    };
    const payload = buildUpdatePayload(values, baseEmployee);
    expect(payload.specificites_paie?.personnel_rd_eligible_jei).toBe(true);
  });
});

describe('employeeProfileFormUtils transport', () => {
  it('round-trip indemnite_mensuelle_nette', () => {
    const employee: Employee = {
      ...baseEmployee,
      specificites_paie: {
        ...baseEmployee.specificites_paie,
        transport: {
          abonnement_mensuel_total: 80,
          indemnite_mensuelle_nette: 120,
        },
      },
    };
    const values = buildDefaultValues(employee);
    expect(values.specificites_paie.transport.indemnite_mensuelle_nette).toBe(120);

    const payload = buildUpdatePayload(values, employee);
    // Sans date d'effet saisie, le round-trip la déclare explicitement à null :
    // c'est l'absence de date qui est persistée, pas un champ omis.
    expect(payload.specificites_paie?.transport).toEqual({
      abonnement_mensuel_total: 80,
      indemnite_mensuelle_nette: 120,
      indemnite_date_effet: null,
    });
  });
});

describe('employeeProfileFormUtils prevoyance', () => {
  const prevoyanceLines = [
    {
      id: 'epna',
      libelle: 'Prévoyance Non-cadre TA',
      salarial: 0.00465,
      patronal: 0.00465,
      forfait_social: 0,
    },
    {
      id: 'epnb',
      libelle: 'Prévoyance Non-cadre TB',
      salarial: 0.00465,
      patronal: 0.00465,
      forfait_social: 0,
    },
  ];

  it('buildDefaultValues charge les lignes prévoyance', () => {
    const employee: Employee = {
      ...baseEmployee,
      specificites_paie: {
        ...baseEmployee.specificites_paie,
        prevoyance: { adhesion: true, lignes_specifiques: prevoyanceLines },
      },
    };
    const values = buildDefaultValues(employee);
    expect(values.specificites_paie.prevoyance.adhesion).toBe(true);
    expect(values.specificites_paie.prevoyance.lignes_specifiques).toEqual(prevoyanceLines);
  });

  it('buildUpdatePayload persiste les lignes depuis le formulaire', () => {
    const employee: Employee = {
      ...baseEmployee,
      specificites_paie: {
        ...baseEmployee.specificites_paie,
        prevoyance: { adhesion: true, lignes_specifiques: prevoyanceLines },
      },
    };
    const defaults = buildDefaultValues(employee);
    const values: EmployeeProfileEditFormValues = {
      ...defaults,
      specificites_paie: {
        ...defaults.specificites_paie,
        prevoyance: {
          adhesion: true,
          lignes_specifiques: prevoyanceLines,
        },
      },
    };
    const payload = buildUpdatePayload(values, employee);
    expect(payload.specificites_paie?.prevoyance).toMatchObject({
      adhesion: true,
      lignes_specifiques: prevoyanceLines,
    });
  });

  it('la formule et la base des lignes vont et reviennent (02/11/2026)', () => {
    const lignes = [{ ...prevoyanceLines[0], base: 'tranche_2' }];
    const employee: Employee = {
      ...baseEmployee,
      specificites_paie: {
        ...baseEmployee.specificites_paie,
        prevoyance: { adhesion: true, formule_id: 'f1', lignes_specifiques: lignes },
      },
    };
    const values = buildDefaultValues(employee);
    expect(values.specificites_paie.prevoyance.formule_id).toBe('f1');
    const payload = buildUpdatePayload(values, employee);
    expect(payload.specificites_paie?.prevoyance).toMatchObject({ formule_id: 'f1', lignes_specifiques: lignes });
  });

  it('sans formule, le lien est effacé explicitement', () => {
    const employee: Employee = {
      ...baseEmployee,
      specificites_paie: {
        ...baseEmployee.specificites_paie,
        prevoyance: { adhesion: true, formule_id: 'f1', lignes_specifiques: prevoyanceLines },
      },
    };
    const defaults = buildDefaultValues(employee);
    const values: EmployeeProfileEditFormValues = {
      ...defaults,
      specificites_paie: {
        ...defaults.specificites_paie,
        prevoyance: { ...defaults.specificites_paie.prevoyance, formule_id: null },
      },
    };
    expect(buildUpdatePayload(values, employee).specificites_paie?.prevoyance).toMatchObject({ formule_id: null });
  });

  it('buildUpdatePayload vide les lignes si adhésion décochée', () => {
    const employee: Employee = {
      ...baseEmployee,
      specificites_paie: {
        ...baseEmployee.specificites_paie,
        prevoyance: { adhesion: true, lignes_specifiques: prevoyanceLines },
      },
    };
    const defaults = buildDefaultValues(employee);
    const values: EmployeeProfileEditFormValues = {
      ...defaults,
      specificites_paie: {
        ...defaults.specificites_paie,
        prevoyance: {
          adhesion: false,
          lignes_specifiques: prevoyanceLines,
        },
      },
    };
    const payload = buildUpdatePayload(values, employee);
    expect(payload.specificites_paie?.prevoyance).toMatchObject({
      adhesion: false,
      lignes_specifiques: [],
    });
  });
});

describe('employeeProfileFormUtils deplacement astreinte', () => {
  it('round-trip deplacement_astreinte', () => {
    const employee: Employee = {
      ...baseEmployee,
      specificites_paie: {
        ...baseEmployee.specificites_paie,
        deplacement_astreinte: {
          enabled: true,
          distance_km_one_way: 22.2,
          vehicle_cv: 7,
          vehicle_type: 'voitures',
        },
      },
    };
    const values = buildDefaultValues(employee);
    expect(values.specificites_paie.deplacement_astreinte?.distance_km_one_way).toBe(22.2);

    const payload = buildUpdatePayload(values, employee);
    expect(payload.specificites_paie?.deplacement_astreinte).toEqual({
      enabled: true,
      distance_km_one_way: 22.2,
      vehicle_cv: 7,
      vehicle_type: 'voitures',
    });
  });
});

describe('employeeProfileFormUtils temps partiel', () => {
  it('readWeeklyHours retombe sur 35 h si absent', () => {
    expect(readWeeklyHours({ ...baseEmployee, duree_hebdomadaire: null })).toBe(35);
  });

  it('buildDefaultValues conserve is_temps_partiel', () => {
    const values = buildDefaultValues({ ...baseEmployee, is_temps_partiel: true, duree_hebdomadaire: 21 });
    expect(values.is_temps_partiel).toBe(true);
    expect(values.duree_hebdomadaire).toBe(21);
  });

  it('buildUpdatePayload envoie is_temps_partiel et duree_hebdomadaire', () => {
    const values = buildDefaultValues({ ...baseEmployee, is_temps_partiel: true, duree_hebdomadaire: 21 });
    const payload = buildUpdatePayload(values, baseEmployee);
    expect(payload.is_temps_partiel).toBe(true);
    expect(payload.duree_hebdomadaire).toBe(21);
  });
});

describe('classification conventionnelle à l’enregistrement (29/09/2026)', () => {
  const classificationDsn = {
    pcs: '674a',
    idcc: '0292',
    coefficient: 700,
    niveau_dsn: '700',
    code_statut_dsn: '06',
    statut_categoriel: 'Non cadre',
    numero_contrat_dsn: '00004',
    taux_at_individuel_dsn: '3.15',
  };
  const fiche = {
    id: 'e1',
    first_name: 'Essai',
    last_name: 'Fiche',
    collective_agreement_id: 'cc-plasturgie',
    classification_conventionnelle: classificationDsn,
  } as unknown as Parameters<typeof buildDefaultValues>[0];

  it('garde les champs de la DSN et n’invente ni groupe ni classe', () => {
    const payload = buildUpdatePayload(buildDefaultValues(fiche), fiche);
    expect(payload.classification_conventionnelle).toEqual(classificationDsn);
  });

  it('écrit le groupe que la gestionnaire a choisi, sans rien perdre', () => {
    const valeurs = buildDefaultValues(fiche);
    valeurs.classification_conventionnelle.groupe_emploi = 'D';
    const payload = buildUpdatePayload(valeurs, fiche);
    expect(payload.classification_conventionnelle).toEqual({ ...classificationDsn, groupe_emploi: 'D' });
  });

  it('met à jour un coefficient déjà présent', () => {
    const valeurs = buildDefaultValues(fiche);
    valeurs.classification_conventionnelle.coefficient = 710;
    const payload = buildUpdatePayload(valeurs, fiche);
    expect(payload.classification_conventionnelle).toMatchObject({ coefficient: 710, taux_at_individuel_dsn: '3.15' });
  });
});

describe('classification reprise de la DSN, montrée dans la liste (27/10/2026)', () => {
  // Fiche importée de la DSN : le coefficient n'est qu'en niveau_dsn (S21.G00.40.041).
  const sansCoefficient = { pcs: '387a', idcc: '0292', niveau_dsn: '910', code_statut_dsn: '04' };
  const fiche = {
    id: 'e2',
    first_name: 'Essai',
    last_name: 'Reprise',
    collective_agreement_id: 'cc-plasturgie',
    classification_conventionnelle: sansCoefficient,
  } as unknown as Parameters<typeof buildDefaultValues>[0];
  const grille = [
    { groupe_emploi: 'Non précisé', classe_emploi: 0, coefficient: 700 },
    { groupe_emploi: 'Non précisé', classe_emploi: 0, coefficient: 710 },
  ];

  it('le formulaire part du niveau de la DSN, sans groupe ni classe inventés', () => {
    expect(buildDefaultValues(fiche).classification_conventionnelle).toEqual({
      groupe_emploi: 'Non précisé',
      classe_emploi: 0,
      coefficient: 910,
    });
  });

  it('un simple enregistrement n’ajoute rien à la classification', () => {
    const payload = buildUpdatePayload(buildDefaultValues(fiche), fiche);
    expect(payload.classification_conventionnelle).toEqual(sansCoefficient);
  });

  it('une fiche sans classification part d’une liste vide, plus de « C / 6 / 240 » (03/11)', () => {
    expect(buildDefaultValues(baseEmployee).classification_conventionnelle).toEqual({
      groupe_emploi: '',
      classe_emploi: undefined,
      coefficient: undefined,
    });
  });

  it('enregistrer une fiche sans classification n’en invente aucune', () => {
    const sansClassification = { ...baseEmployee, collective_agreement_id: 'cc-plasturgie' } as typeof baseEmployee;
    const payload = buildUpdatePayload(buildDefaultValues(sansClassification), sansClassification);
    expect(payload.classification_conventionnelle ?? {}).toEqual({});
  });

  it('la liste propose la classification de la fiche quand la grille ne la connaît pas', () => {
    expect(optionsDeClassification(grille, fiche)).toEqual([
      ...grille,
      { groupe_emploi: 'Non précisé', classe_emploi: 0, coefficient: 910 },
    ]);
  });

  it('sans doublon quand la grille la connaît', () => {
    const ficheConnue = {
      ...fiche,
      classification_conventionnelle: { ...sansCoefficient, niveau_dsn: '710' },
    } as typeof fiche;
    expect(optionsDeClassification(grille, ficheConnue)).toEqual(grille);
  });

  it('rien d’ajouté pour une fiche sans classification', () => {
    expect(optionsDeClassification(grille, baseEmployee)).toEqual(grille);
  });
});

describe('employeeProfileFormUtils salaire saisi pour 35 h', () => {
  it('buildDefaultValues lit le réglage de la fiche', () => {
    const values = buildDefaultValues({
      ...baseEmployee,
      specificites_paie: { ...baseEmployee.specificites_paie, salaire_hors_hs_structurelles: true },
    });
    expect(values.specificites_paie.salaire_hors_hs_structurelles).toBe(true);
  });

  it('buildUpdatePayload enregistre le réglage changé à l’écran', () => {
    const defaults = buildDefaultValues(baseEmployee);
    const values: EmployeeProfileEditFormValues = {
      ...defaults,
      specificites_paie: { ...defaults.specificites_paie, salaire_hors_hs_structurelles: true },
    };
    const payload = buildUpdatePayload(values, baseEmployee);
    expect(payload.specificites_paie?.salaire_hors_hs_structurelles).toBe(true);
  });
});

describe('salaire verrouillé par l’historique', () => {
  // La génération remet sur la fiche le salaire de l'historique daté : avec un
  // historique, le formulaire n'envoie pas de salaire, qui se change avec une
  // date d'effet (« Changer le salaire »).
  it('n’envoie pas le salaire quand il est verrouillé', () => {
    const values = buildDefaultValues(baseEmployee);
    const payload = buildUpdatePayload(values, baseEmployee, { salaireVerrouille: true });
    expect(payload).not.toHaveProperty('salaire_de_base');
    expect(payload.first_name).toBe('Alice');
  });

  it('envoie le salaire d’une fiche sans historique', () => {
    const values = buildDefaultValues(baseEmployee);
    expect(buildUpdatePayload(values, baseEmployee).salaire_de_base).toEqual({ valeur: 3500 });
    expect(
      buildUpdatePayload(values, baseEmployee, { salaireVerrouille: false }).salaire_de_base,
    ).toEqual({ valeur: 3500 });
  });
});

describe('prélèvement à la source à l’enregistrement de la fiche ([B1], [B2], 12/10/2026)', () => {
  // Le taux se saisit sur la page « Taux de prélèvement à la source » (crayon,
  // daté, avec son origine) ; la fiche ne l’envoie plus du tout.
  it('une fiche sans taux ne reçoit pas de taux à 0 % en l’enregistrant', () => {
    const employee: Employee = { ...baseEmployee, specificites_paie: {} };
    const payload = buildUpdatePayload(buildDefaultValues(employee), employee);
    expect(payload.specificites_paie?.prelevement_a_la_source).toBeUndefined();
  });

  it('le taux d’une fiche n’est ni renvoyé ni réécrit par l’enregistrement', () => {
    const employee: Employee = {
      ...baseEmployee,
      specificites_paie: {
        prelevement_a_la_source: { taux: 4.3, type_taux: '01', periode: '2026-09' },
      },
    };
    const payload = buildUpdatePayload(buildDefaultValues(employee), employee);
    expect(payload.specificites_paie?.prelevement_a_la_source).toBeUndefined();
  });
});

describe('titres-restaurant sur la fiche ([B5], 12/10/2026)', () => {
  it('la valeur du titre et la part patronale font l’aller-retour', () => {
    const employee: Employee = {
      ...baseEmployee,
      specificites_paie: {
        titres_restaurant: { beneficie: true, nombre_par_mois: 20, valeur_faciale: 9, part_patronale: 5.4 },
      },
    };
    const values = buildDefaultValues(employee);
    expect(values.specificites_paie.titres_restaurant).toEqual({
      beneficie: true,
      nombre_par_mois: 20,
      valeur_faciale: 9,
      part_patronale: 5.4,
    });
    const payload = buildUpdatePayload(values, employee);
    expect(payload.specificites_paie?.titres_restaurant).toEqual({
      beneficie: true,
      nombre_par_mois: 20,
      valeur_faciale: 9,
      part_patronale: 5.4,
    });
  });
});

describe('forfait jours réduit sur la fiche (04/11/2026)', () => {
  // Un jour par semaine : 43 jours par an. Le moteur en tire le SMIC de la
  // réduction générale (BOSS § 860) ; vide, c'est le forfait de la société.
  const auForfait: Employee = { ...baseEmployee, statut: 'Cadre', is_forfait_jour: true };

  const avecJours = (jours: string, forfait = true): EmployeeProfileEditFormValues => {
    const defaults = buildDefaultValues(auForfait);
    return {
      ...defaults,
      is_forfait_jour: forfait,
      specificites_paie: { ...defaults.specificites_paie, forfait_annual_days: jours },
    };
  };

  it('le formulaire lit les jours de la fiche', () => {
    const values = buildDefaultValues({
      ...auForfait,
      specificites_paie: { ...auForfait.specificites_paie, forfait_annual_days: 43 },
    });
    expect(values.specificites_paie.forfait_annual_days).toBe('43');
  });

  it('une fiche sans forfait réduit part d’une case vide', () => {
    expect(buildDefaultValues(auForfait).specificites_paie.forfait_annual_days).toBe('');
  });

  it('les jours partent en nombre, virgule comprise', () => {
    expect(buildUpdatePayload(avecJours('43'), auForfait).specificites_paie?.forfait_annual_days).toBe(43);
    expect(buildUpdatePayload(avecJours('43,5'), auForfait).specificites_paie?.forfait_annual_days).toBe(43.5);
  });

  it('une case vide efface le forfait réduit', () => {
    const fiche = { ...auForfait, specificites_paie: { ...auForfait.specificites_paie, forfait_annual_days: 43 } };
    expect(buildUpdatePayload(avecJours(''), fiche).specificites_paie?.forfait_annual_days).toBeNull();
  });

  it('sorti du forfait jours, le forfait réduit est effacé', () => {
    const fiche = { ...auForfait, specificites_paie: { ...auForfait.specificites_paie, forfait_annual_days: 43 } };
    expect(buildUpdatePayload(avecJours('43', false), fiche).specificites_paie?.forfait_annual_days).toBeNull();
  });

  it('une fiche sans forfait réduit s’enregistre sans la clé (empreinte des bulletins inchangée)', () => {
    for (const forfait of [true, false]) {
      const envoye = JSON.parse(JSON.stringify(buildUpdatePayload(avecJours('', forfait), auForfait)));
      expect(Object.keys(envoye.specificites_paie)).not.toContain('forfait_annual_days');
    }
  });

  it.each(['0', 'un jour', '219'])('« %s » est refusé sous le champ', (jours) => {
    const resultat = employeeProfileEditSchema.safeParse(avecJours(jours));
    expect(resultat.success).toBe(false);
    if (!resultat.success) {
      expect(resultat.error.issues.map((i) => i.path.join('.'))).toContain('specificites_paie.forfait_annual_days');
    }
  });

  it('43 jours et une case vide passent la validation du champ', () => {
    for (const jours of ['43', '']) {
      const resultat = employeeProfileEditSchema.safeParse(avecJours(jours));
      const surLeChamp = resultat.success
        ? []
        : resultat.error.issues.filter((i) => i.path.join('.') === 'specificites_paie.forfait_annual_days');
      expect(surLeChamp).toEqual([]);
    }
  });
});
