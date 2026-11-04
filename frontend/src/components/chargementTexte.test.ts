import { describe, expect, it } from 'vitest';
import { texteDuChargement } from './chargementTexte';

describe('le texte d’un chargement', () => {
  it('dit ce qui charge', () => {
    expect(texteDuChargement('Chargement des bulletins…')).toBe('Chargement des bulletins…');
    expect(texteDuChargement('  Chargement…  ', null)).toBe('Chargement…');
  });

  it('ajoute le compte quand l’avancement est connu, sans les points de suspension', () => {
    expect(texteDuChargement('Calcul des bulletins…', { faits: 12, total: 42 })).toBe(
      'Calcul des bulletins : 12 sur 42',
    );
    expect(texteDuChargement('Import...', { faits: 3, total: 9 })).toBe('Import : 3 sur 9');
    expect(texteDuChargement('', { faits: 1, total: 2 })).toBe('1 sur 2');
  });

  it('un compte hors bornes ou sans total ne s’affiche pas faux', () => {
    expect(texteDuChargement('Calcul', { faits: 50, total: 42 })).toBe('Calcul : 42 sur 42');
    expect(texteDuChargement('Calcul', { faits: -1, total: 42 })).toBe('Calcul : 0 sur 42');
    expect(texteDuChargement('Calcul…', { faits: 0, total: 0 })).toBe('Calcul…');
  });
});
