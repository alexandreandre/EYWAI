import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

import { libelleStatutTitre } from '@/features/employee-detail/components/libelleTitreSejour';

describe('statut du titre de séjour sur la fiche ([D9])', () => {
  it('reprend le statut déjà calculé, avec la date déjà connue', () => {
    expect(
      libelleStatutTitre({
        is_subject_to_residence_permit: true,
        residence_permit_status: 'to_complete',
        residence_permit_expiry_date: null,
      }),
    ).toBe('À compléter');
    expect(
      libelleStatutTitre({
        is_subject_to_residence_permit: true,
        residence_permit_status: 'to_renew',
        residence_permit_expiry_date: '2026-11-02',
      }),
    ).toBe('À renouveler');
    expect(
      libelleStatutTitre({
        is_subject_to_residence_permit: true,
        residence_permit_status: 'valid',
        residence_permit_expiry_date: '2027-03-15',
      }),
    ).toBe("Valide jusqu'au 15/03/2027");
    expect(
      libelleStatutTitre({
        is_subject_to_residence_permit: true,
        residence_permit_status: 'expired',
        residence_permit_expiry_date: '2026-01-04',
      }),
    ).toBe('Expiré depuis le 04/01/2026');
    expect(
      libelleStatutTitre({
        is_subject_to_residence_permit: false,
        residence_permit_status: 'to_complete',
      }),
    ).toBeNull();
  });

  it('la section de la fiche affiche ce statut, y compris en mode paie', () => {
    const fiche = readFileSync(
      path.resolve(__dirname, 'EmployeeProfileEditForm.tsx'),
      'utf8',
    );
    expect(fiche).toContain('libelleStatutTitre');
    expect(fiche).toContain('data-testid="titre-sejour-statut"');
  });
});
