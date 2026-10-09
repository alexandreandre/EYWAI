import { describe, expect, it } from 'vitest';

import { alertesAffichees, dateEnClair, dateHeureEnClair, heureParis, nombreActives, pourcentFr, traceAlerte } from './comparaisonAffichage';

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

describe('pourcentages à la française', () => {
  it('une décimale, virgule, espace avant le signe', () => {
    expect(pourcentFr(12.3)).toBe('12,3 %');
    expect(pourcentFr(12.3)).not.toContain('.');
    expect(pourcentFr(-4)).toBe('-4,0 %');
    expect(pourcentFr(0)).toBe('0,0 %');
  });
});

describe('alertes affichées et filtres de niveau', () => {
  const alertes = [
    { rule_id: 'R03', level: 'CRITIQUE', status: 'active' },
    { rule_id: 'R04', level: 'AVERTISSEMENT', status: 'active' },
    { rule_id: 'R07', level: 'INFO', status: 'active' },
    { rule_id: 'R12', level: 'INFO', status: 'active' },
  ] as const;

  it('sans filtre, toutes les alertes sauf R12 (déjà dite par l’encadré « pas de N-1 »)', () => {
    expect(alertesAffichees([...alertes], null).map((a) => a.rule_id)).toEqual(['R03', 'R04', 'R07']);
  });

  it('un filtre ne garde que son niveau', () => {
    expect(alertesAffichees([...alertes], 'CRITIQUE').map((a) => a.rule_id)).toEqual(['R03']);
    expect(alertesAffichees([...alertes], 'INFO').map((a) => a.rule_id)).toEqual(['R07']);
  });

  it('le décompte d’un niveau ne compte pas R12', () => {
    expect(nombreActives([...alertes], 'INFO')).toBe(1);
  });
});

describe('dates et heures de l’écran du bulletin, à l’heure de Paris', () => {
  it('l’historique affiche 22:26 pour 20:26:53 UTC en été', () => {
    expect(heureParis('2026-10-09T20:26:53+00:00')).toBe('22:26');
  });

  it('en hiver, une heure de décalage', () => {
    expect(heureParis('2026-01-09T20:26:53Z')).toBe('21:26');
  });

  it('la date est celle de Paris, pas celle du fuseau UTC', () => {
    expect(dateEnClair('2026-10-09T22:30:00Z')).toBe('10 octobre 2026');
    expect(dateEnClair('2026-11-01T10:00:00Z')).toBe('1er novembre 2026');
  });

  it('une date illisible donne une chaîne vide', () => {
    expect(heureParis('nimporte quoi')).toBe('');
    expect(dateEnClair(null)).toBe('');
  });
});
