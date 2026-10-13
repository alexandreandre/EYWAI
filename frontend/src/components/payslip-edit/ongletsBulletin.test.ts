import { describe, expect, it } from 'vitest';

import { ONGLET_D_OUVERTURE } from './ongletsBulletin';

describe('ONGLET_D_OUVERTURE', () => {
  it('ouvre un bulletin sur sa lecture, pas sur la correction', () => {
    expect(ONGLET_D_OUVERTURE).toBe('bulletin');
  });
});
