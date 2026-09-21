import { describe, expect, it } from 'vitest';
import { libellePlages, regrouperParSemaine } from './joursASaisir';

describe('regrouperParSemaine', () => {
  it('regroupe des dates ISO par semaine ISO, avec des plages lisibles', () => {
    expect(
      regrouperParSemaine([
        '2026-06-22',
        '2026-06-23',
        '2026-06-24',
        '2026-06-25',
        '2026-06-26',
        '2026-06-29',
        '2026-06-30',
        '2026-07-02',
      ]),
    ).toEqual([
      { semaine: 26, annee: 2026, libelle: 'S26 : 22/06–26/06' },
      { semaine: 27, annee: 2026, libelle: 'S27 : 29/06–30/06, 02/07' },
    ]);
  });

  it('rend une liste vide sans dates', () => {
    expect(regrouperParSemaine([])).toEqual([]);
  });
});

describe('libellePlages', () => {
  it('écrit les plages comme le serveur', () => {
    expect(libellePlages(['2026-07-27', '2026-07-28', '2026-07-29', '2026-07-30', '2026-07-31'])).toBe(
      '27/07–31/07',
    );
    expect(libellePlages(['2026-07-10'])).toBe('10/07');
  });
});
