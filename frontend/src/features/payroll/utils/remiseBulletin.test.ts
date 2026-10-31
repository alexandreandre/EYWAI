import { describe, expect, it } from 'vitest';

import { phraseRemise } from './remiseBulletin';

describe('phraseRemise', () => {
  it('dit quand le salarié verra un bulletin validé, et que jusque-là il se corrige', () => {
    expect(phraseRemise({ status: 'valide', remis_le: '2026-11-01', bulletin_remis: false })).toBe(
      'Visible par le salarié le 1er novembre 2026. Jusque-là, il se corrige encore ; ensuite, une erreur se corrige sur le bulletin du mois suivant.',
    );
  });

  it('se tait pour un brouillon, et pour un bulletin remis (le verrou le dit déjà)', () => {
    expect(phraseRemise({ status: 'brouillon', remis_le: null, bulletin_remis: false })).toBeNull();
    expect(phraseRemise({ status: 'valide', remis_le: '2026-11-01', bulletin_remis: true })).toBeNull();
    expect(phraseRemise({ status: 'valide' })).toBeNull();
  });
});
