import { describe, expect, it, vi } from 'vitest';
import { basculeDeLaSociete, debutDeLaPaieMartine } from './basculeCalendrier';

const reprise = { dernier_mois_repris: '2026-09', premier_mois_calcule: '2026-10', logiciel_precedent: 'Quadra' };
const fenetre = (debut: string) => vi.fn(async () => ({ debut }));

describe('debutDeLaPaieMartine', () => {
  it('septembre : la paie d’octobre commence le 21/09, les jours d’avant sont à l’ancien logiciel', async () => {
    const lire = fenetre('2026-09-21');
    const bascule = await debutDeLaPaieMartine(reprise, 2026, 9, lire);
    expect(lire).toHaveBeenCalledWith(2026, 10);
    expect(bascule).toEqual({
      debutMartine: '2026-09-21',
      logiciel: 'Quadra',
      phrase: 'Jours avant le 21/09/2026 : payés par l’ancien logiciel (Quadra), non comptés.',
    });
  });

  it('octobre et après : rien n’est retiré, sans lecture', async () => {
    const lire = fenetre('2026-09-21');
    expect(await debutDeLaPaieMartine(reprise, 2026, 10, lire)).toBeNull();
    expect(await debutDeLaPaieMartine(reprise, 2027, 1, lire)).toBeNull();
    expect(lire).not.toHaveBeenCalled();
  });

  it('sans reprise : rien n’est retiré', async () => {
    expect(await debutDeLaPaieMartine(null, 2026, 9, fenetre('2026-09-21'))).toBeNull();
  });

  it('fenêtre illisible : rien n’est retiré (règle stricte)', async () => {
    const lire = vi.fn(async () => {
      throw new Error('hors ligne');
    });
    expect(await debutDeLaPaieMartine(reprise, 2026, 9, lire)).toBeNull();
  });
});

describe('basculeDeLaSociete (fiche salarié, tous les mois)', () => {
  it('donne le premier jour de la paie Martine, quel que soit le mois affiché', async () => {
    expect(await basculeDeLaSociete(reprise, fenetre('2026-09-21'))).toEqual({
      debutMartine: '2026-09-21',
      logiciel: 'Quadra',
      phrase: 'Jours avant le 21/09/2026 : payés par l’ancien logiciel (Quadra), non comptés.',
    });
  });

  it('sans reprise ou fenêtre illisible : rien n’est retiré', async () => {
    expect(await basculeDeLaSociete(null, fenetre('2026-09-21'))).toBeNull();
    const illisible = vi.fn(async () => {
      throw new Error('hors ligne');
    });
    expect(await basculeDeLaSociete(reprise, illisible)).toBeNull();
  });
});
