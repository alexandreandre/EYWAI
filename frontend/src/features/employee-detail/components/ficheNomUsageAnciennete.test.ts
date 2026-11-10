import { describe, expect, it } from 'vitest';

import {
  buildDefaultValues,
  buildUpdatePayload,
} from '@/features/employee-detail/components/employeeProfileFormUtils';
import { employeeProfileEditSchema } from '@/features/employee-detail/components/employeeProfileEditSchema';
import type { Employee } from '@/features/employee-detail/types';

// Retour du 10/11/2026 : date d'ancienneté distincte de la date d'entrée
// (mutation dans le groupe, intérim avant l'embauche) et nom d'usage, tous deux
// saisissables dans « Modifier la fiche ».
const fiche: Employee = {
  id: 'emp-1',
  first_name: 'Alice',
  last_name: 'Dupont',
  job_title: 'Ingénieure',
  contract_type: 'CDI',
  statut: 'Non-Cadre',
  hire_date: '2024-01-15',
  email: 'a@example.com',
  nir: '123456789012345',
  date_naissance: '1990-05-10',
  lieu_naissance: 'Paris',
  nationalite: 'Française',
  adresse: { rue: '1 rue Test', code_postal: '75001', ville: 'Paris' },
  coordonnees_bancaires: { iban: 'FR7630001007941234567890185', bic: 'BNPAFRPP' },
  salaire_de_base: { valeur: 3500 },
  duree_hebdomadaire: 35,
  specificites_paie: {
    transport: { abonnement_mensuel_total: 0 },
    titres_restaurant: { beneficie: true, nombre_par_mois: 0 },
    mutuelle: { mutuelle_type_ids: [] },
    prevoyance: { adhesion: false },
  },
};

describe("date d'ancienneté", () => {
  it('se lit sur la fiche', () => {
    const valeurs = buildDefaultValues({ ...fiche, seniority_reference_date: '2019-03-01' });
    expect(valeurs.seniority_reference_date).toBe('2019-03-01');
  });

  it('vide sur une fiche sans reprise : la date d’entrée tient lieu', () => {
    expect(buildDefaultValues(fiche).seniority_reference_date).toBe('');
  });

  it('part à l’enregistrement, et null quand on la vide', () => {
    const valeurs = buildDefaultValues(fiche);
    expect(buildUpdatePayload({ ...valeurs, seniority_reference_date: '2019-03-01' }, fiche).seniority_reference_date).toBe(
      '2019-03-01',
    );
    const avecDate = { ...fiche, seniority_reference_date: '2019-03-01' };
    const vide = { ...buildDefaultValues(avecDate), seniority_reference_date: '' };
    expect(buildUpdatePayload(vide, avecDate).seniority_reference_date).toBeNull();
  });

  it('une fiche sans date n’en reçoit pas', () => {
    const payload = buildUpdatePayload(buildDefaultValues(fiche), fiche);
    expect('seniority_reference_date' in payload).toBe(false);
  });

  it('refusée si postérieure à la date d’entrée', () => {
    const valeurs = { ...buildDefaultValues(fiche), seniority_reference_date: '2024-02-01' };
    const resultat = employeeProfileEditSchema.safeParse(valeurs);
    expect(resultat.success).toBe(false);
    if (!resultat.success) {
      expect(resultat.error.issues.some((i) => i.path.join('.') === 'seniority_reference_date')).toBe(true);
    }
  });
});

describe("nom d'usage", () => {
  it('se lit, part et s’efface', () => {
    const marie = { ...fiche, nom_usage: 'MARTIN' };
    const valeurs = buildDefaultValues(marie);
    expect(valeurs.nom_usage).toBe('MARTIN');
    expect(buildUpdatePayload({ ...valeurs, nom_usage: ' Bernard ' }, marie).nom_usage).toBe('Bernard');
    expect(buildUpdatePayload({ ...valeurs, nom_usage: '' }, marie).nom_usage).toBeNull();
  });

  it('une fiche sans nom d’usage n’en reçoit pas', () => {
    const payload = buildUpdatePayload(buildDefaultValues(fiche), fiche);
    expect('nom_usage' in payload).toBe(false);
  });
});
