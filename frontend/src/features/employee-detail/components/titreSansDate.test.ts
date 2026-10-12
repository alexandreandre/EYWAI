import { describe, expect, it } from 'vitest';

import type { Employee } from '@/features/employee-detail/types';

import { employeeProfileEditSchema } from './employeeProfileEditSchema';
import { buildDefaultValues } from './employeeProfileFormUtils';

/**
 * Un titre de séjour sans date n'empêche pas d'enregistrer la fiche (12/10/2026,
 * alerte plutôt que refus) : il se dit « À compléter » partout, et les autres
 * changements de la fiche ne sont plus bloqués par lui.
 */
function erreursTitre(champs: Record<string, unknown>): string[] {
  const valeurs = buildDefaultValues({
    id: 'e1',
    first_name: 'Jeanne',
    last_name: 'Essai',
    statut: 'Non-Cadre',
    contract_type: 'CDI',
    specificites_paie: {},
    salary_payment_method: 'cheque',
    ...champs,
  } as unknown as Employee);
  const resultat = employeeProfileEditSchema.safeParse(valeurs);
  return resultat.success
    ? []
    : resultat.error.issues
        .filter((i) => i.path.join('.') === 'residence_permit_expiry_date')
        .map((i) => i.message);
}

describe('fiche : titre de séjour sans date', () => {
  it('soumis sans date : la fiche s’enregistre', () => {
    expect(
      erreursTitre({ is_subject_to_residence_permit: true, residence_permit_expiry_date: null }),
    ).toEqual([]);
  });

  it('avec sa date : rien ne change', () => {
    expect(
      erreursTitre({ is_subject_to_residence_permit: true, residence_permit_expiry_date: '2027-03-31' }),
    ).toEqual([]);
  });
});
