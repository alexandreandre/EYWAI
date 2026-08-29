import { describe, expect, it } from 'vitest';

import { serializeRowsForRefinement } from './aiFillRefinement';

describe('serializeRowsForRefinement', () => {
  it("privilégie le nom rapproché, sinon le nom lu, et conserve les jours dans l'ordre", () => {
    const payload = serializeRowsForRefinement([
      {
        rawName: 'BUGNY',
        matchedName: 'Michel Bugny',
        days: [
          { jour: 1, heures: 8, type: 'travail', nature: 'reel' },
          { jour: 2, heures: null, type: 'weekend', nature: 'reel' },
        ],
      },
      {
        rawName: 'COTTE Léo',
        matchedName: null,
        days: [{ jour: 3, heures: 7.5, type: 'travail', nature: 'prevu' }],
      },
    ]);

    expect(payload.employees).toEqual([
      {
        name: 'Michel Bugny',
        days: [
          { jour: 1, heures: 8, type: 'travail', nature: 'reel' },
          { jour: 2, heures: null, type: 'weekend', nature: 'reel' },
        ],
      },
      {
        name: 'COTTE Léo',
        days: [{ jour: 3, heures: 7.5, type: 'travail', nature: 'prevu' }],
      },
    ]);
  });

  it('conserve une ligne sans jours (contexte utile pour la correction)', () => {
    const payload = serializeRowsForRefinement([
      { rawName: 'X', matchedName: null, days: [] },
    ]);
    expect(payload.employees).toEqual([{ name: 'X', days: [] }]);
  });
});
