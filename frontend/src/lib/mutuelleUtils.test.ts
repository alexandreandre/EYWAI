import { describe, expect, it } from 'vitest';

import { isEmployeeCadre, normalizeEmployeeStatut } from '@/lib/mutuelleUtils';

describe('mutuelleUtils statut cadre', () => {
  it('isEmployeeCadre reconnaît cadre et forfait jour cadre', () => {
    expect(isEmployeeCadre('Cadre')).toBe(true);
    expect(isEmployeeCadre('Cadre au forfait jour')).toBe(true);
  });

  it('isEmployeeCadre exclut non-cadre', () => {
    expect(isEmployeeCadre('Non-Cadre')).toBe(false);
    expect(isEmployeeCadre('Non-Cadre au forfait jour')).toBe(false);
  });

  it('normalizeEmployeeStatut délègue à isEmployeeCadre', () => {
    expect(normalizeEmployeeStatut('Cadre au forfait jour')).toBe('cadre');
    expect(normalizeEmployeeStatut('Non-Cadre')).toBe('non_cadre');
  });
});
