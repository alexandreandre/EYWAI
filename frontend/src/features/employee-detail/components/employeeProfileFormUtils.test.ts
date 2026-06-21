import { describe, expect, it } from 'vitest';

import {
  buildDefaultValues,
  buildUpdatePayload,
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
    expect(payload.specificites_paie?.transport).toEqual({
      abonnement_mensuel_total: 80,
      indemnite_mensuelle_nette: 120,
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
