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

describe('payrollWeekOptions — le mois de paie de chaque semaine', () => {
  const fenetreJuilletColorplast = {
    debut: '2026-06-22',
    fin: '2026-07-26',
    mois_civil: ['2026-07-01', '2026-07-31'] as [string, string],
  };

  it('couvre la fenêtre et le mois civil, et nomme la paie des semaines hors fenêtre', async () => {
    const { payrollWeekOptions } = await import('./importWeekOptions');

    const options = payrollWeekOptions(2026, 7, fenetreJuilletColorplast);

    expect(options.map((o) => o.week)).toEqual([26, 27, 28, 29, 30, 31]);
    const s26 = options[0];
    expect(s26.value).toBe('2026-06-22');
    expect(s26.horsFenetre).toBe(false);
    expect(s26.label).toBe('S26 · 22 juin – 28 juin');
    const s31 = options[options.length - 1];
    expect(s31.horsFenetre).toBe(true);
    expect(s31.paieDe).toEqual({ year: 2026, month: 8 });
    expect(s31.label).toBe("S31 · 27 juil. – 2 août → paie d'août");
  });

  it('sans fenêtre, ou en mois civil, rend les semaines du mois comme avant', async () => {
    const { payrollWeekOptions } = await import('./importWeekOptions');

    expect(payrollWeekOptions(2026, 7, null)).toEqual(monthIsoWeekOptions(2026, 7));
    expect(
      payrollWeekOptions(2026, 7, {
        debut: '2026-07-01',
        fin: '2026-07-31',
        mois_civil: ['2026-07-01', '2026-07-31'],
      }),
    ).toEqual(monthIsoWeekOptions(2026, 7));
  });

  it('élide « de » devant une voyelle', async () => {
    const { libellePaieDe } = await import('./importWeekOptions');

    expect(libellePaieDe(8)).toBe("d'août");
    expect(libellePaieDe(4)).toBe("d'avril");
    expect(libellePaieDe(6)).toBe('de juin');
  });
});
