import { describe, expect, it } from 'vitest';

import {
  buildDefaultValues,
  buildUpdatePayload,
  readWeeklyHours,
} from '@/features/employee-detail/components/employeeProfileFormUtils';
import type { Employee } from '@/features/employee-detail/types';
import type { EmployeeProfileEditFormValues } from '@/features/employee-detail/components/employeeProfileEditSchema';

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
