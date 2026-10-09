import { describe, expect, it } from 'vitest';

import { dateHeureEnClair, traceAlerte } from './comparaisonAffichage';

describe('date en clair', () => {
  it('écrit le mois en toutes lettres et l’heure de Paris', () => {
    expect(dateHeureEnClair('2026-10-07T07:12:33+00:00')).toBe('7 octobre 2026 à 09:12');
  });

  it('1er du mois en clair', () => {
    expect(dateHeureEnClair('2026-01-01T10:05:00Z')).toBe('1er janvier 2026 à 11:05');
  });

  it('une date illisible n’est pas montrée telle quelle', () => {
    expect(dateHeureEnClair('pas une date')).toBe('');
    expect(dateHeureEnClair(undefined)).toBe('');
  });
});

describe('trace d’un acquittement', () => {
  it('dit qui, quand et le commentaire, sans identifiant ni date ISO', () => {
    const trace = traceAlerte({
      status: 'acquittee',
      acquitted_by: 'Claire Martin',
      acquitted_at: '2026-10-07T07:12:33+00:00',
      comment: 'Prime confirmée',
    });
    expect(trace).toBe('Acquittée par Claire Martin le 7 octobre 2026 à 09:12 · Prime confirmée');
    expect(trace).not.toMatch(/T07:12|\+00:00/);
  });

  it('une alerte ignorée le dit', () => {
    expect(
      traceAlerte({ status: 'ignoree', acquitted_by: 'Claire Martin', acquitted_at: '2026-10-07T07:12:33Z' })
    ).toBe('Ignorée par Claire Martin le 7 octobre 2026 à 09:12');
  });

  it('sans nom connu, ne montre aucune personne', () => {
    expect(traceAlerte({ status: 'acquittee', acquitted_at: '2026-10-07T07:12:33Z' })).toBe(
      'Acquittée le 7 octobre 2026 à 09:12'
    );
  });

  it('une alerte active n’a pas de trace', () => {
    expect(traceAlerte({ status: 'active' })).toBe('');
  });
});
