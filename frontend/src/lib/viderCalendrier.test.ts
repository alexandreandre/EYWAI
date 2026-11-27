import { describe, expect, it } from 'vitest';
import type { PlannedEventData } from '@/api/calendar';
import { jourGardeParLeVidage, messageDuVidage, phraseConfirmationVidage, phraseResultatVidage, viderLeJour } from './viderCalendrier';

const jour = (j: number, type: string, h: number | null = 7, extra: Partial<PlannedEventData> = {}): PlannedEventData => ({
  jour: j,
  type,
  heures_prevues: h,
  ...extra,
});

describe('jourGardeParLeVidage : arrêts, congés et absences posés restent', () => {
  it('garde les absences', () => {
    for (const type of ['conges_payes', 'rtt', 'arret_maladie', 'absence_non_remuneree', 'conge', 'evenement_familial', 'activite_partielle']) {
      expect(jourGardeParLeVidage(jour(5, type))).toBe(true);
    }
    expect(jourGardeParLeVidage(jour(10, 'weekend', 0, { origine: 'absence' }))).toBe(true);
  });

  it('vide le travail, le repos, l’école', () => {
    for (const type of ['travail', 'repos', 'ecole', 'weekend', 'ferie']) {
      expect(jourGardeParLeVidage(jour(5, type))).toBe(false);
    }
  });
});

describe('viderLeJour (éditeur du jour)', () => {
  it('un jour ouvré revient « Travail » sans heures, réel et horaires effacés', () => {
    // 05/10/2026 : lundi.
    expect(viderLeJour(2026, 10, jour(5, 'travail', 7))).toEqual({
      patch: { type: 'travail', heures_prevues: null, heures_faites: null, debut: null, fin: null },
    });
  });

  it('un samedi revient en week-end, un férié reste férié', () => {
    expect(viderLeJour(2026, 10, jour(3, 'travail', 7))).toEqual({
      patch: { type: 'weekend', heures_prevues: null, heures_faites: null, debut: null, fin: null },
    });
    expect(viderLeJour(2026, 11, jour(11, 'ferie', 0))).toMatchObject({ patch: { type: 'ferie' } });
  });

  it('un congé posé ne se vide pas ici, et la raison est dite', () => {
    expect(viderLeJour(2026, 10, jour(5, 'conges_payes', 0))).toEqual({
      refus: 'Absence posée : elle se retire dans Congés ou Arrêts & IJ, pas en vidant le jour.',
    });
  });
});

describe('phrases du vidage du mois', () => {
  it('la confirmation dit combien de jours seront vidés et lesquels restent', () => {
    expect(
      phraseConfirmationVidage({ joursVides: 18, joursAbsence: 3, joursBulletin: 0, salaries: 1, moisLabel: 'octobre 2026' }),
    ).toBe(
      '18 jours d’octobre 2026 seront vidés (prévu et réel). Restent tels quels : 3 jours d’arrêt, de congé ou d’absence posés.',
    );
    expect(
      phraseConfirmationVidage({ joursVides: 40, joursAbsence: 0, joursBulletin: 9, salaries: 2, moisLabel: 'septembre 2026' }),
    ).toBe(
      '40 jours de septembre 2026 seront vidés (prévu et réel) pour 2 salariés. Restent tels quels : 9 jours lus par un bulletin validé.',
    );
  });

  it('rien à vider : le dire', () => {
    expect(
      phraseConfirmationVidage({ joursVides: 0, joursAbsence: 2, joursBulletin: 0, salaries: 1, moisLabel: 'octobre 2026' }),
    ).toBe(
      'Rien à vider en octobre 2026 : aucun jour saisi en dehors des absences posées et des bulletins validés. Restent tels quels : 2 jours d’arrêt, de congé ou d’absence posés.',
    );
  });

  it('le résultat dit ce qui a été fait', () => {
    expect(phraseResultatVidage({ joursVides: 18, joursAbsence: 3, joursBulletin: 0, salaries: 1, moisLabel: 'octobre 2026' })).toBe(
      '18 jours vidés en octobre 2026. Gardés : 3 jours d’arrêt, de congé ou d’absence posés.',
    );
  });
});

describe('messageDuVidage', () => {
  it('le message qui propose « Annuler » reste au moins 30 secondes', () => {
    const m = messageDuVidage({ joursVides: 18, joursAbsence: 0, joursBulletin: 0, salaries: 1, moisLabel: 'octobre 2026' });
    expect(m.title).toBe('Calendrier vidé');
    expect(m.duration).toBeGreaterThanOrEqual(30_000);
  });

  it('rien à vider : message ordinaire', () => {
    const m = messageDuVidage({ joursVides: 0, joursAbsence: 1, joursBulletin: 0, salaries: 1, moisLabel: 'octobre 2026' });
    expect(m.title).toBe('Rien à vider');
  });
});
