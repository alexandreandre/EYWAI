import { describe, expect, it } from 'vitest';

import { monthIsoWeekOptions } from './importWeekOptions';

describe('monthIsoWeekOptions', () => {
  it('liste les semaines ISO qui chevauchent juillet 2026 (S27 à S31)', () => {
    const options = monthIsoWeekOptions(2026, 7);

    expect(options.map((o) => o.week)).toEqual([27, 28, 29, 30, 31]);
    expect(options[0].value).toBe('2026-06-29');
    expect(options[options.length - 1].value).toBe('2026-07-27');
    expect(options.every((o) => o.isoYear === 2026)).toBe(true);
  });

  it('étiquette chaque semaine par son numéro et ses bornes lundi–dimanche', () => {
    const [first] = monthIsoWeekOptions(2026, 7);

    expect(first.label).toBe('S27 · 29 juin – 5 juil.');
  });

  it('commence sur le 1er du mois quand il tombe un lundi', () => {
    const options = monthIsoWeekOptions(2026, 6);

    expect(options[0].value).toBe('2026-06-01');
    expect(options[0].week).toBe(23);
    expect(options.map((o) => o.week)).toEqual([23, 24, 25, 26, 27]);
  });

  it("porte l'année ISO de la semaine à cheval sur deux années", () => {
    const options = monthIsoWeekOptions(2027, 1);

    expect(options[0]).toMatchObject({ value: '2026-12-28', isoYear: 2026, week: 53 });
    expect(options[1]).toMatchObject({ value: '2027-01-04', isoYear: 2027, week: 1 });
  });
});
