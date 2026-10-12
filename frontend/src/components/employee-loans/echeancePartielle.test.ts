import { describe, expect, it } from 'vitest';

import { explicationEcheancePartielle } from './echeancePartielle';

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
