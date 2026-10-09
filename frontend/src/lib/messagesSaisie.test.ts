import { describe, expect, it } from 'vitest';
import { messageBadgeuse, pourEmployes } from './messagesSaisie';

describe('pourEmployes', () => {
  it('accorde employé sans « (s) »', () => {
    expect(pourEmployes(1)).toBe('1 employé');
    expect(pourEmployes(3)).toBe('3 employés');
  });
});

describe('messageBadgeuse', () => {
  it('dit qu’aucun pointage de badgeuse n’existe quand rien n’est importé', () => {
    expect(messageBadgeuse({ total_days_updated: 0, employees_processed: 1 })).toBe(
      'Aucun pointage de badgeuse n’existe pour cette période : rien n’a été importé pour 1 employé.',
    );
  });

  it('compte les jours et les employés, pluriels accordés', () => {
    expect(messageBadgeuse({ total_days_updated: 1, employees_processed: 1 })).toBe(
      '1 jour mis à jour pour 1 employé.',
    );
    expect(messageBadgeuse({ total_days_updated: 12, employees_processed: 3 })).toBe(
      '12 jours mis à jour pour 3 employés.',
    );
  });
});
