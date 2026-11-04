import { describe, expect, it } from 'vitest';

import { avecMois, avecRevue, lireParamsVuePaie, moisAffiche } from './vuePaieUrl';

describe('lireParamsVuePaie — l’URL courante décide de l’onglet', () => {
  it('sans paramètre, l’onglet est Par mois (le lien du menu, comme le dit la vidéo)', () => {
    expect(lireParamsVuePaie('')).toEqual({
      view: 'month',
      year: null,
      month: null,
      aRevoir: false,
    });
  });

  it('un salarié dans l’adresse, sans vue, ouvre Par collaborateur (lien « Voir les bulletins »)', () => {
    expect(lireParamsVuePaie('employee=e-1&month=2026-09').view).toBe('employee');
  });

  it('la vue écrite dans l’adresse l’emporte sur le salarié', () => {
    expect(lireParamsVuePaie('view=month&employee=e-1').view).toBe('month');
    expect(lireParamsVuePaie('view=employee').view).toBe('employee');
  });

  it('après navigation vers ?view=month&month=, l’onglet devient Par mois', () => {
    const avant = lireParamsVuePaie('view=employee');
    expect(avant.view).toBe('employee');

    const apresClic = lireParamsVuePaie('view=month&month=2026-09');
    expect(apresClic.view).toBe('month');
    expect(apresClic.year).toBe(2026);
    expect(apresClic.month).toBe(9);
  });

  it('un changement d’URL relit la vue, elle n’est pas figée au premier rendu', () => {
    const premierRendu = lireParamsVuePaie('view=employee');
    const apresLienChecklist = lireParamsVuePaie(
      new URLSearchParams('view=month&month=2026-07')
    );
    expect(premierRendu.view).toBe('employee');
    expect(apresLienChecklist).toEqual({
      view: 'month',
      year: 2026,
      month: 7,
      aRevoir: false,
    });
  });

  it('view autre que month ne force pas l’onglet du mois', () => {
    expect(lireParamsVuePaie('view=employee&month=2026-09').view).toBe('employee');
  });
});

describe('le mois choisi ne se perd plus — revue du 05/10', () => {
  it('le mois choisi s’écrit dans l’adresse, sans toucher au reste', () => {
    const apres = avecMois(new URLSearchParams('view=month&employee=e-1'), 2026, 9);
    expect(apres.get('month')).toBe('2026-09');
    expect(apres.get('view')).toBe('month');
    expect(apres.get('employee')).toBe('e-1');
    expect(lireParamsVuePaie(apres)).toMatchObject({ year: 2026, month: 9 });
  });

  it('« Seulement à revoir » s’écrit aussi : le retour d’un bulletin le garde', () => {
    const active = avecRevue(new URLSearchParams('view=month&month=2026-09'), true);
    expect(lireParamsVuePaie(active).aRevoir).toBe(true);
    expect(active.get('month')).toBe('2026-09');
    expect(lireParamsVuePaie(avecRevue(active, false)).aRevoir).toBe(false);
    expect(avecRevue(active, false).has('revue')).toBe(false);
  });

  it('sans mois dans l’adresse, la page ouvre sur le mois de paie, pas le mois civil', () => {
    // Le 3 octobre, on fait encore la paie de septembre (moisDePaieParDefaut).
    expect(moisAffiche(lireParamsVuePaie(''), new Date(2026, 9, 3))).toEqual({ year: 2026, month: 9 });
    expect(moisAffiche(lireParamsVuePaie(''), new Date(2026, 9, 20))).toEqual({ year: 2026, month: 10 });
  });

  it('le mois de l’adresse l’emporte', () => {
    expect(moisAffiche(lireParamsVuePaie('month=2026-07'), new Date(2026, 9, 3))).toEqual({
      year: 2026,
      month: 7,
    });
    expect(
      moisAffiche(lireParamsVuePaie('month=2026-07'), new Date(2026, 9, 3), { year: 2026, month: 5 }),
    ).toEqual({ year: 2026, month: 7 });
  });

  it('sans mois dans l’adresse, la paie reprend le mois de l’écran précédent (Calendrier, Primes)', () => {
    expect(moisAffiche(lireParamsVuePaie(''), new Date(2026, 10, 4), { year: 2026, month: 9 })).toEqual({
      year: 2026,
      month: 9,
    });
  });
});
