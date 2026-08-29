import { describe, expect, it } from 'vitest';
import { idsInIndexRange } from './usePaintSelect';

describe('idsInIndexRange', () => {
  const ids = ['a', 'b', 'c', 'd'];

  it('renvoie la plage inclusive dans les deux sens', () => {
    expect(idsInIndexRange(ids, 1, 3)).toEqual(['b', 'c', 'd']);
    expect(idsInIndexRange(ids, 3, 1)).toEqual(['b', 'c', 'd']);
  });

  it('borne les index hors liste', () => {
    expect(idsInIndexRange(ids, -2, 1)).toEqual(['a', 'b']);
    expect(idsInIndexRange([], 0, 2)).toEqual([]);
  });
});
