import { describe, expect, it } from 'vitest';
import { bulletinDuMois, bulletinsDuContratPrecedent } from './bulletinDuMois';

// Le CDD finit le 10/11, le nouveau contrat commence le 17/11 : deux bulletins.
const bulletins = [
  { id: 'ancien', year: 2026, month: 11, contract_period_id: 'periode-1' },
  { id: 'nouveau', year: 2026, month: 11, contract_period_id: null },
  { id: 'octobre', year: 2026, month: 10 },
];

describe('bulletinDuMois', () => {
  it('rend le bulletin du contrat de la fiche, même listé après l’autre', () => {
    expect(bulletinDuMois(bulletins, 2026, 11)?.id).toBe('nouveau');
  });

  it('un mois à un seul contrat rend son bulletin', () => {
    expect(bulletinDuMois(bulletins, 2026, 10)?.id).toBe('octobre');
    expect(bulletinDuMois(bulletins, 2026, 9)).toBeUndefined();
  });
});

describe('bulletinsDuContratPrecedent', () => {
  it('rend le bulletin du contrat rangé du mois partagé', () => {
    expect(bulletinsDuContratPrecedent(bulletins, 2026, 11).map((b) => b.id)).toEqual(['ancien']);
    expect(bulletinsDuContratPrecedent(bulletins, 2026, 10)).toEqual([]);
  });
});
