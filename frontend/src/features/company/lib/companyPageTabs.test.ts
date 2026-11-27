import { describe, expect, it } from 'vitest';

import { tabFromHash, tabFromSearchParam } from './companyPageTabs';

describe('onglet « Mutuelle et prévoyance » (27/11/2026)', () => {
  it('un lien vers la prévoyance ouvre l’onglet mutuelle', () => {
    expect(tabFromSearchParam('prevoyance')).toBe('mutuelle');
    expect(tabFromHash('#prevoyance')).toBe('mutuelle');
  });

  it('les autres onglets ne bougent pas', () => {
    expect(tabFromSearchParam('mutuelle')).toBe('mutuelle');
    expect(tabFromSearchParam('paie')).toBe('paie');
    expect(tabFromSearchParam('inconnu')).toBeNull();
  });
});
