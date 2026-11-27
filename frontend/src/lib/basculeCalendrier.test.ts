import { describe, expect, it, vi } from 'vitest';
import { debutDeLaPaieMartine } from './basculeCalendrier';

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

  it('fenêtre illisible : la paie Martine commence le 1er du premier mois calculé', async () => {
    const lire = vi.fn(async () => {
      throw new Error('hors ligne');
    });
    const bascule = await debutDeLaPaieMartine(reprise, 2026, 9, lire);
    expect(bascule?.debutMartine).toBe('2026-10-01');
  });
});
