import { describe, expect, it } from 'vitest';
import { libelleJourForfait } from './libelleJourForfait';

describe('libelleJourForfait', () => {
  it('dit « Prévu » pour un jour planifié en heures, pas seulement à 1', () => {
    expect(libelleJourForfait(7.8, null)).toBe('Prévu');
    expect(libelleJourForfait(1, undefined)).toBe('Prévu');
  });
  it('dit « Travaillé » dès que le jour est confirmé', () => {
    expect(libelleJourForfait(7.8, 1)).toBe('Travaillé');
  });
  it('ne dit rien pour un jour non planifié', () => {
    expect(libelleJourForfait(0, null)).toBeNull();
    expect(libelleJourForfait(null, 0)).toBeNull();
  });
});

describe('libelleJourForfait, réel en heures (retour du 10/11)', () => {
  it('un réel posé en heures est un jour travaillé', () => {
    expect(libelleJourForfait(7.8, 7.8)).toBe('Travaillé');
    expect(libelleJourForfait(1, 7)).toBe('Travaillé');
  });
});
