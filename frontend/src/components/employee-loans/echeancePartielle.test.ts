import { describe, expect, it } from 'vitest';

import {
  explicationEcheancePartielle,
  legendePeriodesDecalees,
  periodesDesEcheances,
} from './echeancePartielle';

// Rejeu G.3 du 11/10/2026 : le volet du prêt disait seulement « Partielle »
// (prélevé 163,58 €, reliquat 37,50 €), sans dire pourquoi ni ce que devient
// le reliquat.

const echeance = {
  installment_number: 1,
  year: 2026,
  month: 10,
  capital_part: 199.08,
  interest_part: 2,
  total_due: 201.08,
  capital_paid: 161.95,
  interest_paid: 1.63,
  status: 'partial',
};

const espaces = (texte: string | null) => (texte ?? '').replace(/[\u00a0\u202f]/g, ' ');

describe('le volet du prêt explique une échéance retenue en partie', () => {
  it('dit le montant retenu, le montant prévu, la règle et le sort du reliquat', () => {
    expect(espaces(explicationEcheancePartielle(echeance))).toBe(
      'Échéance n° 1 (10/2026) : 163,58 € retenus sur 201,08 € prévus. Chaque mois, ' +
        'la retenue est limitée au dixième du salaire exigible (article L3251-3 du Code ' +
        "du travail), dans la limite du net à payer ; l'alerte du bulletin donne le " +
        'détail. Le reliquat de 37,50 € reste dû : il sera retenu seul sur le bulletin ' +
        "suivant, et les échéances suivantes glissent d'un mois."
    );
  });

  it('compte une échéance « à venir » déjà entamée comme partielle', () => {
    expect(explicationEcheancePartielle({ ...echeance, status: 'pending' })).not.toBeNull();
  });

  it('ne dit rien d’une échéance payée, à venir ou ignorée', () => {
    expect(
      explicationEcheancePartielle({
        ...echeance,
        capital_paid: 199.08,
        interest_paid: 2,
        status: 'paid',
      })
    ).toBeNull();
    expect(
      explicationEcheancePartielle({
        ...echeance,
        capital_paid: 0,
        interest_paid: 0,
        status: 'pending',
      })
    ).toBeNull();
    expect(explicationEcheancePartielle({ ...echeance, status: 'skipped' })).toBeNull();
  });
});

// Rejeu G.3, suite : le texte dit que « les échéances suivantes glissent d'un
// mois », mais le tableau montrait toujours l'échéance n° 2 en 11/2026,
// « À venir ». Rejoué en bac à sable (11/10/2026, rien d'écrit) : le bulletin
// de novembre ne retient que le reliquat de l'échéance n° 1 (37,50 €), un
// bulletin ne retenant qu'une échéance par prêt ; l'échéance n° 2 n'est
// retenue qu'en décembre. À salaire égal, elle l'est en partie à son tour, et
// la n° 3 attend février. Le tableau donne désormais, pour chaque échéance pas
// encore soldée, le premier bulletin qui pourra la retenir.

const echeancier = [1, 2, 3, 4].map((n) => ({
  id: `ech-${n}`,
  installment_number: n,
  year: n === 4 ? 2027 : 2026,
  month: n === 4 ? 1 : 9 + n,
  capital_part: 199.08,
  interest_part: 2,
  total_due: 201.08,
  capital_paid: 0,
  interest_paid: 0,
  status: 'pending',
}));

const retenue = (n: number, year: number, month: number) => ({
  installment_id: `ech-${n}`,
  year,
  month,
});

describe('le tableau du prêt fait glisser les échéances qui suivent une retenue partielle', () => {
  it('après octobre (échéance n° 1 retenue en partie), la n° 2 passe en 12/2026', () => {
    const lignes = echeancier.map((e) =>
      e.installment_number === 1
        ? { ...e, capital_paid: 161.95, interest_paid: 1.63, status: 'partial' }
        : e
    );
    expect(periodesDesEcheances(lignes, [retenue(1, 2026, 10)])).toEqual([
      { periode: '10/2026', prevue: null },
      { periode: '12/2026', prevue: '11/2026' },
      { periode: '01/2027', prevue: '12/2026' },
      { periode: '02/2027', prevue: '01/2027' },
    ]);
  });

  it('après novembre (reliquat de la n° 1 retenu seul), la n° 2 reste en 12/2026', () => {
    const lignes = echeancier.map((e) =>
      e.installment_number === 1
        ? { ...e, capital_paid: 199.08, interest_paid: 2, status: 'paid' }
        : e
    );
    const periodes = periodesDesEcheances(lignes, [retenue(1, 2026, 10), retenue(1, 2026, 11)]);
    expect(periodes[1]).toEqual({ periode: '12/2026', prevue: '11/2026' });
  });

  it('une seconde retenue partielle fait glisser les suivantes d’un mois de plus', () => {
    const lignes = echeancier.map((e) =>
      e.installment_number === 1
        ? { ...e, capital_paid: 199.08, interest_paid: 2, status: 'paid' }
        : e.installment_number === 2
          ? { ...e, capital_paid: 161.95, interest_paid: 1.49, status: 'partial' }
          : e
    );
    const periodes = periodesDesEcheances(lignes, [
      retenue(1, 2026, 10),
      retenue(1, 2026, 11),
      retenue(2, 2026, 12),
    ]);
    expect(periodes[2]).toEqual({ periode: '02/2027', prevue: '12/2026' });
  });

  it('sans retenue partielle, chaque échéance garde sa période', () => {
    const lignes = echeancier.map((e) =>
      e.installment_number === 1
        ? { ...e, capital_paid: 199.08, interest_paid: 2, status: 'paid' }
        : e
    );
    expect(periodesDesEcheances(lignes, [retenue(1, 2026, 10)]).map((p) => p.prevue)).toEqual([
      null,
      null,
      null,
      null,
    ]);
    expect(periodesDesEcheances(echeancier, []).map((p) => p.periode)).toEqual([
      '10/2026',
      '11/2026',
      '12/2026',
      '01/2027',
    ]);
  });

  it('dit sous le tableau pourquoi une période est décalée, et seulement alors', () => {
    expect(espaces(legendePeriodesDecalees([{ periode: '12/2026', prevue: '11/2026' }]))).toBe(
      "Un bulletin ne retient qu'une échéance par prêt : quand une échéance est retenue " +
        'en partie, les suivantes glissent. La période affichée est celle du premier ' +
        "bulletin qui pourra les retenir ; « prévue » rappelle la date de l'échéancier."
    );
    expect(legendePeriodesDecalees([{ periode: '11/2026', prevue: null }])).toBeNull();
  });
});
