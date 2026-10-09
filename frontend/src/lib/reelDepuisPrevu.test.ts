import { describe, expect, it } from 'vitest';
import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import { completerReelDepuisPrevu, messageReelDepuisPrevu } from './reelDepuisPrevu';

const prevu = (jour: number, type: string, heures_prevues: number | null): PlannedEventData => ({
  jour,
  type,
  heures_prevues,
});
const reel = (jour: number, heures_faites: number | null, type = 'travail'): ActualHoursData => ({
  jour,
  type,
  heures_faites,
});

describe('completerReelDepuisPrevu', () => {
  it('remplit un jour prévu sans heures réelles avec le prévu', () => {
    const r = completerReelDepuisPrevu([prevu(1, 'travail', 7)], []);
    expect(r.actual).toEqual([{ jour: 1, type: 'travail', heures_faites: 7 }]);
    expect(r.completes).toBe(1);
    expect(r.gardes).toBe(0);
  });

  it('garde les heures réelles déjà saisies, corrigées à la main ou importées', () => {
    const r = completerReelDepuisPrevu(
      [prevu(1, 'travail', 7), prevu(2, 'travail', 7)],
      [reel(1, 6)],
    );
    expect(r.actual).toEqual([
      { jour: 1, type: 'travail', heures_faites: 6 },
      { jour: 2, type: 'travail', heures_faites: 7 },
    ]);
    expect(r.completes).toBe(1);
    expect(r.gardes).toBe(1);
  });

  it('traite une entrée sans heures comme un jour vide', () => {
    const r = completerReelDepuisPrevu([prevu(1, 'travail', 7)], [reel(1, null)]);
    expect(r.actual).toEqual([{ jour: 1, type: 'travail', heures_faites: 7 }]);
    expect(r.completes).toBe(1);
  });

  it('n’écrit rien sur un jour sans prévu ni sur un week-end ou une absence', () => {
    const r = completerReelDepuisPrevu(
      [prevu(3, 'weekend', 0), prevu(4, 'travail', null), prevu(5, 'conges_payes', 0)],
      [],
    );
    expect(r.actual).toEqual([]);
    expect(r.completes).toBe(0);
  });

  it('garde un 0 h déjà posé, y compris un week-end', () => {
    const r = completerReelDepuisPrevu([prevu(3, 'weekend', 0)], [reel(3, 0, 'weekend')]);
    expect(r.actual).toEqual([{ jour: 3, type: 'weekend', heures_faites: 0 }]);
  });
});

describe('messageReelDepuisPrevu', () => {
  it('dit combien de jours complétés et combien gardés', () => {
    expect(messageReelDepuisPrevu(1, 12, 3)).toBe(
      'Réel = prévu pour 1 salarié : 12 jours complétés, 3 jours déjà saisis gardés.',
    );
  });
  it('accorde au singulier et omet les gardés quand il n’y en a pas', () => {
    expect(messageReelDepuisPrevu(2, 1, 0)).toBe('Réel = prévu pour 2 salariés : 1 jour complété.');
  });
});
