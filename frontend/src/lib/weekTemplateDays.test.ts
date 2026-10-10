import { describe, expect, it } from 'vitest';

import { JOURS_MODELE_SEMAINE, cleModeleDuJour, valeurModelePourLeJour } from './weekTemplateDays';

describe('modèle de semaine type', () => {
  it('propose les sept jours, du lundi au dimanche', () => {
    expect(JOURS_MODELE_SEMAINE.map((j) => j.label)).toEqual([
      'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche',
    ]);
  });

  it('range le dimanche sous la clé 7 (getDay() = 0)', () => {
    expect(cleModeleDuJour(0)).toBe(7);
    expect(cleModeleDuJour(6)).toBe(6);
    expect(cleModeleDuJour(3)).toBe(3);
  });

  it('laisse le week-end tel quel tant que le modèle y est vide', () => {
    expect(valeurModelePourLeJour({ 1: '7' }, 6)).toBeUndefined();
    expect(valeurModelePourLeJour({ 6: '' }, 6)).toBeUndefined();
    expect(valeurModelePourLeJour({ 6: '4' }, 6)).toBe('4');
    expect(valeurModelePourLeJour({ 7: '3' }, 0)).toBe('3');
  });

  it('applique toujours un jour de semaine, même vide', () => {
    expect(valeurModelePourLeJour({}, 2)).toBe('');
  });
});
