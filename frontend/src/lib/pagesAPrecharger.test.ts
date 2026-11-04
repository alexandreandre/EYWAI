import { describe, expect, it } from 'vitest';

import { pagesCourantesAPrecharger } from './pagesAPrecharger';

describe('pagesCourantesAPrecharger — ne précharger que ce qui s’ouvre', () => {
  it('RH hors mode paie : les sept pages courantes', () => {
    expect(pagesCourantesAPrecharger({ rh: true, modePaie: false })).toEqual([
      '/',
      '/employees',
      '/employees/:id',
      '/leaves',
      '/planning',
      '/payroll',
      '/analytics',
    ]);
  });

  it('mode paie : sans les pages qu’il ne laisse pas ouvrir (planning, analyses)', () => {
    expect(pagesCourantesAPrecharger({ rh: true, modePaie: true })).toEqual([
      '/',
      '/employees',
      '/employees/:id',
      '/leaves',
      '/payroll',
    ]);
  });

  it('un collaborateur ne télécharge aucune page RH', () => {
    expect(pagesCourantesAPrecharger({ rh: false, modePaie: false })).toEqual([]);
  });
});
