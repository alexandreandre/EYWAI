import { describe, expect, it } from 'vitest';

import { exitTypeLabels } from './employeeExits';

describe('type de départ « Autre motif »', () => {
  it('a son libellé, pour les motifs de rupture DSN sans équivalent', () => {
    expect((exitTypeLabels as Record<string, string>).autre_motif).toBe('Autre motif');
  });
});
