import { describe, expect, it } from 'vitest';

import { lireParamsVuePaie } from './vuePaieUrl';

describe('lireParamsVuePaie — l’URL courante décide de l’onglet', () => {
  it('sans paramètre, l’onglet est Par collaborateur', () => {
    expect(lireParamsVuePaie('')).toEqual({
      view: 'employee',
      year: null,
      month: null,
    });
  });

  it('après navigation vers ?view=month&month=, l’onglet devient Par mois', () => {
    const avant = lireParamsVuePaie('');
    expect(avant.view).toBe('employee');

    const apresClic = lireParamsVuePaie('view=month&month=2026-09');
    expect(apresClic.view).toBe('month');
    expect(apresClic.year).toBe(2026);
    expect(apresClic.month).toBe(9);
  });

  it('un changement d’URL relit la vue, elle n’est pas figée au premier rendu', () => {
    const premierRendu = lireParamsVuePaie('');
    const apresLienChecklist = lireParamsVuePaie(
      new URLSearchParams('view=month&month=2026-07')
    );
    expect(premierRendu.view).toBe('employee');
    expect(apresLienChecklist).toEqual({
      view: 'month',
      year: 2026,
      month: 7,
    });
  });

  it('view autre que month ne force pas l’onglet du mois', () => {
    expect(lireParamsVuePaie('view=employee&month=2026-09').view).toBe('employee');
  });
});
