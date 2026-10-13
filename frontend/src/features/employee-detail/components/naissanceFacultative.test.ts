import { describe, expect, it } from 'vitest';

import type { Employee } from '@/features/employee-detail/types';
import { avertissementNaissanceDsn } from '@/features/employees/utils/avertissementNaissanceDsn';

import { employeeProfileEditSchema } from './employeeProfileEditSchema';
import { buildDefaultValues } from './employeeProfileFormUtils';

function erreurs(champs: Record<string, unknown>): string[] {
  const fiche = {
    id: 'e1',
    first_name: 'Jeanne',
    last_name: 'Essai',
    statut: 'Non-Cadre',
    contract_type: 'CDI',
    specificites_paie: {},
    ...champs,
  } as unknown as Employee;
  const resultat = employeeProfileEditSchema.safeParse(buildDefaultValues(fiche));
  return resultat.success
    ? []
    : resultat.error.issues
        .filter((i) => ['lieu_naissance', 'nationalite'].includes(i.path.join('.')))
        .map((i) => `${i.path.join('.')}: ${i.message}`);
}

describe('lieu de naissance et nationalité sont facultatifs sur la fiche', () => {
  it('une fiche sans lieu de naissance ni nationalité s’enregistre', () => {
    expect(erreurs({ lieu_naissance: '', nationalite: '' })).toEqual([]);
  });
});

describe('avertissementNaissanceDsn', () => {
  it('prévient que la DSN demandera ce qui manque', () => {
    expect(avertissementNaissanceDsn({ lieu_naissance: '', nationalite: '' })).toBe(
      'La DSN demandera le lieu de naissance et la nationalité : à compléter avant son dépôt.',
    );
    expect(avertissementNaissanceDsn({ lieu_naissance: '', nationalite: 'Française' })).toBe(
      'La DSN demandera le lieu de naissance : à compléter avant son dépôt.',
    );
    expect(avertissementNaissanceDsn({ lieu_naissance: '75001 Paris', nationalite: ' ' })).toBe(
      'La DSN demandera la nationalité : à compléter avant son dépôt.',
    );
  });

  it('se tait quand les deux sont renseignés', () => {
    expect(avertissementNaissanceDsn({ lieu_naissance: '75001 Paris', nationalite: 'Française' })).toBeNull();
  });
});
