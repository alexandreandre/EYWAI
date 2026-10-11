import { describe, expect, it } from 'vitest';
import { clotureRttOuverte } from './clotureRtt';

describe('clôture des RTT', () => {
  it("n'est pas proposée en octobre : la période court jusqu'au 31/12", () => {
    expect(clotureRttOuverte(false, new Date(2026, 9, 10))).toBe(false);
  });

  it("n'est pas proposée en octobre même si le rappel est actif par erreur d'horloge serveur absente", () => {
    expect(clotureRttOuverte(undefined, new Date(2026, 9, 10))).toBe(false);
  });

  it('est proposée en décembre', () => {
    expect(clotureRttOuverte(false, new Date(2026, 11, 2))).toBe(true);
  });

  it('est proposée dès que le rappel de fin d’année est actif', () => {
    expect(clotureRttOuverte(true, new Date(2026, 10, 20))).toBe(true);
  });
});
