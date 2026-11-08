import { describe, expect, it } from 'vitest';
import { arretAvecDateAccident, refusDateAccident } from './dateAccident';

describe('date de l’accident', () => {
  it('concerne les accidents et maladies professionnelles', () => {
    expect(arretAvecDateAccident('arret_maladie_pro')).toBe(true);
    expect(arretAvecDateAccident('arret_at')).toBe(true);
    expect(arretAvecDateAccident('arret_maladie')).toBe(false);
  });
  it('refuse une date après le premier jour d’arrêt', () => {
    expect(refusDateAccident('2026-10-06', '2026-10-05')).toMatch(/premier jour/);
    expect(refusDateAccident('2026-10-05', '2026-10-05')).toBeNull();
    expect(refusDateAccident('2026-09-10', '2026-10-05')).toBeNull();
  });
});
