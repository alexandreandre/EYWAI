import { describe, expect, it } from 'vitest';

import {
  erreursRecalageCp,
  estLigneCp,
  lireJours,
  messageRecalageCp,
  moisDeRecalage,
} from './recalageCp';

describe('estLigneCp', () => {
  it('ouvre le recalage depuis les trois lignes de congés payés', () => {
    expect(estLigneCp('Congés Payés (période précédente)')).toBe(true);
    expect(estLigneCp('Congés Payés (période en cours)')).toBe(true);
    expect(estLigneCp('Congés Payés')).toBe(true);
  });

  it("laisse l'ancienneté, le fractionnement et les autres compteurs à leur place", () => {
    expect(estLigneCp('Congés Payés (ancienneté)')).toBe(false);
    expect(estLigneCp('Congés Payés (fractionnement)')).toBe(false);
    expect(estLigneCp('RTT')).toBe(false);
  });
});

describe('moisDeRecalage', () => {
  it('ne propose que des mois écoulés, le plus récent en premier', () => {
    const mois = moisDeRecalage(new Date(2026, 9, 5), 3);
    expect(mois.map((m) => m.valeur)).toEqual(['2026-09', '2026-08', '2026-07']);
    expect(mois[0]).toMatchObject({
      year: 2026,
      month: 9,
      libelle: 'septembre 2026',
      dateFin: '30/09/2026',
    });
  });

  it('compte le mois en cours le jour de sa fin', () => {
    const mois = moisDeRecalage(new Date(2026, 9, 31), 2);
    expect(mois.map((m) => m.valeur)).toEqual(['2026-10', '2026-09']);
  });

  it("franchit l'année", () => {
    const mois = moisDeRecalage(new Date(2027, 0, 10), 2);
    expect(mois.map((m) => m.valeur)).toEqual(['2026-12', '2026-11']);
    expect(mois[0].dateFin).toBe('31/12/2026');
  });
});

describe('lireJours', () => {
  it('accepte la virgule et le point', () => {
    expect(lireJours('12,5')).toBe(12.5);
    expect(lireJours(' 6.24 ')).toBe(6.24);
    expect(lireJours('-0,43')).toBe(-0.43);
  });

  it('rend null pour une saisie vide ou illisible', () => {
    expect(lireJours('')).toBeNull();
    expect(lireJours('douze')).toBeNull();
  });
});

describe('erreursRecalageCp', () => {
  it('exige les deux soldes et un commentaire', () => {
    expect(erreursRecalageCp({ n1: '', n: '6,24', note: 'x' })).toEqual([
      'Saisissez le solde CP N-1 (0 s’il est vide).',
    ]);
    expect(erreursRecalageCp({ n1: '27', n: 'abc', note: 'x' })).toEqual([
      'Saisissez le solde CP N (0 s’il est vide).',
    ]);
    expect(erreursRecalageCp({ n1: '27', n: '6,24', note: '   ' })).toEqual([
      'Dites en commentaire pourquoi vous recalez (il reste dans l’historique).',
    ]);
  });

  it('ne dit rien quand tout est saisi', () => {
    expect(erreursRecalageCp({ n1: '27', n: '6,24', note: 'Écart Quadra' })).toEqual([]);
  });
});

describe('messageRecalageCp', () => {
  it('dit ce que le bulletin du mois imprimera et ce qui passe à recalculer', () => {
    expect(
      messageRecalageCp({
        employee_id: 'e1',
        date_reference: '2026-09-30',
        cp_n1_solde: 27,
        cp_n_solde: 6.24,
      }),
    ).toBe(
      'Au 30/09/2026, le bulletin imprime CP N-1 27,00 j et CP N 6,24 j. ' +
        'Les bulletins concernés passent « À recalculer ».',
    );
  });

  it('le dit aussi quand le bulletin de ce mois n’imprime pas de compteur', () => {
    expect(
      messageRecalageCp({
        employee_id: 'e1',
        date_reference: '2026-09-30',
        cp_n1_solde: null,
        cp_n_solde: null,
      }),
    ).toBe(
      'Soldes enregistrés au 30/09/2026. Le bulletin de ce mois n’imprime pas de ' +
        'compteur de congés. Les bulletins concernés passent « À recalculer ».',
    );
  });
});
