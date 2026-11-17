import { describe, expect, it } from 'vitest';

import { statutDsnContreditLaFiche } from './statutDsn';

describe('statutDsnContreditLaFiche', () => {
  it('cadre sur la fiche, non-cadre en DSN', () => {
    expect(statutDsnContreditLaFiche('Cadre', { code_statut_dsn: '06' })).toContain('non-cadre');
  });
  it('accord des deux, ou sans code repris : rien', () => {
    expect(statutDsnContreditLaFiche('Non-Cadre', { code_statut_dsn: '06' })).toBeNull();
    expect(statutDsnContreditLaFiche('Cadre', { code_statut_dsn: '05' })).toBeNull();
    expect(statutDsnContreditLaFiche('Cadre', {})).toBeNull();
  });
});
