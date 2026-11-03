import { describe, expect, it } from 'vitest';
import { PAYROLL_REQUIRED_FIELD_LABELS } from './constants';

describe('PAYROLL_REQUIRED_FIELD_LABELS', () => {
  it('reprend les champs exigés par le serveur, type de contrat compris', () => {
    // Même liste et même ordre que PAYROLL_REQUIRED_FIELDS (backend onboarding/profile).
    expect(PAYROLL_REQUIRED_FIELD_LABELS).toEqual([
      'Numéro de sécurité sociale',
      'Date de naissance',
      'Adresse postale',
      'Coordonnées bancaires (RIB)',
      'Rémunération',
      'Type de contrat',
    ]);
  });
});
