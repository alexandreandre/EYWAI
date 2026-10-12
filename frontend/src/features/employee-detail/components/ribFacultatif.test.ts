import { describe, expect, it } from 'vitest';

import type { Employee } from '@/features/employee-detail/types';

import { employeeProfileEditSchema } from './employeeProfileEditSchema';
import { buildDefaultValues } from './employeeProfileFormUtils';

function fiche(champs: Record<string, unknown>): Employee {
  return {
    id: 'e1',
    first_name: 'Jeanne',
    last_name: 'Essai',
    statut: 'Non-Cadre',
    contract_type: 'CDI',
    specificites_paie: {},
    ...champs,
  } as unknown as Employee;
}

function erreursIban(valeurs: unknown): string[] {
  const resultat = employeeProfileEditSchema.safeParse(valeurs);
  return resultat.success
    ? []
    : resultat.error.issues
        .filter((i) => i.path.join('.') === 'coordonnees_bancaires.iban')
        .map((i) => i.message);
}

describe('le RIB est facultatif pour un salarié payé par chèque ou en espèces', () => {
  it.each(['cheque', 'especes'] as const)('payé en %s : fiche sans IBAN acceptée', (mode) => {
    const valeurs = buildDefaultValues(
      fiche({ salary_payment_method: mode, coordonnees_bancaires: { iban: '', bic: '' } }),
    );
    expect(erreursIban(valeurs)).toEqual([]);
  });

  it('payé par virement : l’IBAN reste exigé', () => {
    const valeurs = buildDefaultValues(
      fiche({ salary_payment_method: 'virement', coordonnees_bancaires: { iban: '', bic: '' } }),
    );
    expect(erreursIban(valeurs)).toEqual(['IBAN vide.']);
  });

  it('un IBAN à la clé fausse n’empêche pas d’enregistrer la fiche (il s’avertit)', () => {
    const valeurs = buildDefaultValues(
      fiche({
        salary_payment_method: 'virement',
        coordonnees_bancaires: { iban: 'FR7630001007941234567890186', bic: '' },
      }),
    );
    expect(erreursIban(valeurs)).toEqual([]);
  });

  it('un IBAN mal formé reste refusé, quel que soit le mode', () => {
    const valeurs = buildDefaultValues(
      fiche({
        salary_payment_method: 'cheque',
        coordonnees_bancaires: { iban: 'FR76 1234', bic: '' },
      }),
    );
    expect(erreursIban(valeurs)).toHaveLength(1);
  });
});
