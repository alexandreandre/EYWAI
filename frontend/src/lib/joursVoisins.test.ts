import { describe, expect, it } from 'vitest';
import { joursVoisins, numeroDeSemaine } from './joursVoisins';

const court = (j: { jour: number; mois: number }) => `${j.jour}/${j.mois}`;

describe('jours des mois voisins dans la grille', () => {
  it('octobre 2026 commence un jeudi : lundi 28/09 à mercredi 30/09 avant, 1/11 après', () => {
    const { avant, apres } = joursVoisins(2026, 10);
    expect(avant.map(court)).toEqual(['28/9', '29/9', '30/9']);
    expect(apres.map(court)).toEqual(['1/11']);
  });

  it('un mois qui commence un lundi et finit un dimanche n’a aucun voisin', () => {
    // Juin 2026 : lundi 1er, mardi 30 → voisins après seulement.
    expect(joursVoisins(2026, 6).avant).toEqual([]);
    // Février 2027 : lundi 1er, dimanche 28.
    const fev = joursVoisins(2027, 2);
    expect(fev.avant).toEqual([]);
    expect(fev.apres).toEqual([]);
  });

  it('passe l’année : janvier 2027 montre la fin de décembre 2026', () => {
    const { avant } = joursVoisins(2027, 1);
    expect(avant.map((j) => `${j.jour}/${j.mois}/${j.annee}`)).toEqual([
      '28/12/2026',
      '29/12/2026',
      '30/12/2026',
      '31/12/2026',
    ]);
  });

  it('chaque semaine de la grille est complète', () => {
    for (let mois = 1; mois <= 12; mois++) {
      const { avant, apres } = joursVoisins(2026, mois);
      const nb = new Date(2026, mois, 0).getDate();
      expect((avant.length + nb + apres.length) % 7).toBe(0);
    }
  });
});

describe('numéro de semaine', () => {
  it('S40 de 2026 va du lundi 28/09 au dimanche 04/10', () => {
    expect(numeroDeSemaine(new Date(2026, 8, 28))).toBe(40);
    expect(numeroDeSemaine(new Date(2026, 9, 4))).toBe(40);
    expect(numeroDeSemaine(new Date(2026, 9, 5))).toBe(41);
  });

  it('le 1er janvier 2027 (vendredi) est en S53 de 2026', () => {
    expect(numeroDeSemaine(new Date(2027, 0, 1))).toBe(53);
  });
});
