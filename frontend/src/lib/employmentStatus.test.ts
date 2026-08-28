import { describe, expect, it } from 'vitest';

import { filterPresentEmployees, isPresentEmployee } from './employmentStatus';

describe('isPresentEmployee', () => {
  it('garde les salariés en poste', () => {
    expect(isPresentEmployee('actif')).toBe(true);
    expect(isPresentEmployee('active')).toBe(true);
    expect(isPresentEmployee('en_onboarding')).toBe(true);
    expect(isPresentEmployee('en_sortie')).toBe(true);
    expect(isPresentEmployee(undefined)).toBe(true);
    expect(isPresentEmployee(null)).toBe(true);
  });

  it('exclut les salariés partis', () => {
    expect(isPresentEmployee('parti')).toBe(false);
    expect(isPresentEmployee('inactif')).toBe(false);
    expect(isPresentEmployee('sorti')).toBe(false);
  });
});

describe('filterPresentEmployees', () => {
  it('retire les partis de la liste calendrier', () => {
    const kept = filterPresentEmployees([
      { id: '1', employment_status: 'actif' },
      { id: '2', employment_status: 'parti' },
      { id: '3', employment_status: 'en_onboarding' },
      { id: '4', employment_status: 'inactif' },
    ]);
    expect(kept.map((e) => e.id)).toEqual(['1', '3']);
  });
});
