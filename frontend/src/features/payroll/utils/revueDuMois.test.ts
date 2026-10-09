import { describe, expect, it } from 'vitest';

import {
  SEUIL_ECART_NET_PCT,
  SEUIL_HEURES_SUP,
  ecartAvecMoisPrecedent,
  estARevoir,
  moisPrecedent,
  motifsAlerte,
  phraseSynthese,
  syntheseDuMois,
  type BulletinPourRevue,
  type LigneDuMois,
} from './revueDuMois';

/** Espaces insécables d'Intl ramenées à des espaces simples, pour lire les phrases. */
const lisible = (texte: string) => texte.replace(/[\u00a0\u202f]/g, ' ');

function bulletin(overrides: Partial<BulletinPourRevue> = {}): BulletinPourRevue {
  return {
    year: 2026,
    month: 9,
    salaire_brut: 2000,
    net_a_payer: 1500,
    heures_sup: 0,
    status: 'brouillon',
    origine: 'calcule',
    a_recalculer: false,
    warnings: [],
    ...overrides,
  };
}

const AOUT = bulletin({ month: 8, salaire_brut: 2000, net_a_payer: 1500 });

describe('moisPrecedent', () => {
  it('recule d’un mois, et d’une année en janvier', () => {
    expect(moisPrecedent(2026, 9)).toEqual({ year: 2026, month: 8 });
    expect(moisPrecedent(2026, 1)).toEqual({ year: 2025, month: 12 });
  });
});

describe('ecartAvecMoisPrecedent — l’écart se lit dans la liste, sans ouvrir le bulletin', () => {
  it('écart du net en % sur le mois précédent', () => {
    const ecart = ecartAvecMoisPrecedent(bulletin({ net_a_payer: 1710 }), AOUT);
    expect(ecart.netPct).toBeCloseTo(14, 5);
    expect(ecart.fort).toBe(true);
    expect(ecart.raison).toBe('Net +14 % sur août');
  });

  it('un écart au seuil ou sous le seuil n’est pas fort', () => {
    const auSeuil = 1500 * (1 + SEUIL_ECART_NET_PCT / 100);
    expect(ecartAvecMoisPrecedent(bulletin({ net_a_payer: auSeuil }), AOUT).fort).toBe(false);
    const ecart = ecartAvecMoisPrecedent(bulletin({ net_a_payer: 1560 }), AOUT);
    expect(ecart.fort).toBe(false);
    expect(ecart.raison).toBeNull();
  });

  it('une baisse forte compte aussi', () => {
    const ecart = ecartAvecMoisPrecedent(bulletin({ net_a_payer: 1200 }), AOUT);
    expect(ecart.fort).toBe(true);
    expect(ecart.raison).toBe('Net -20 % sur août');
  });

  it('plus de 20 h sup : fort, même sans écart de net', () => {
    const ecart = ecartAvecMoisPrecedent(bulletin({ heures_sup: SEUIL_HEURES_SUP + 2 }), AOUT);
    expect(ecart.fort).toBe(true);
    expect(ecart.raison).toBe('22 h sup.');
    expect(ecartAvecMoisPrecedent(bulletin({ heures_sup: SEUIL_HEURES_SUP }), AOUT).fort).toBe(false);
  });

  it('sans mois précédent : pas de pourcentage inventé', () => {
    const ecart = ecartAvecMoisPrecedent(bulletin(), undefined);
    expect(ecart.netPct).toBeNull();
    expect(ecart.fort).toBe(false);
    expect(ecartAvecMoisPrecedent(bulletin(), bulletin({ month: 8, net_a_payer: 0 })).netPct).toBeNull();
    expect(ecartAvecMoisPrecedent(bulletin(), bulletin({ month: 8, net_a_payer: null })).netPct).toBeNull();
  });

  it('janvier se compare à décembre', () => {
    const ecart = ecartAvecMoisPrecedent(
      bulletin({ year: 2027, month: 1, net_a_payer: 1800 }),
      bulletin({ year: 2026, month: 12, net_a_payer: 1500 })
    );
    expect(ecart.raison).toBe('Net +20 % sur décembre');
  });
});

describe('estARevoir — ce que montre « Seulement à revoir »', () => {
  const ok: LigneDuMois = { statut: 'success', bulletin: bulletin(), ecart: ecartAvecMoisPrecedent(bulletin(), AOUT) };

  it('un bulletin calme n’est pas à revoir', () => {
    expect(estARevoir(ok)).toBe(false);
  });

  it('sans bulletin, ou en échec : à revoir', () => {
    expect(estARevoir({ statut: 'idle' })).toBe(true);
    expect(estARevoir({ statut: 'error' })).toBe(true);
  });

  it('à recalculer, en alerte ou net négatif : à revoir', () => {
    expect(estARevoir({ ...ok, bulletin: bulletin({ a_recalculer: true }) })).toBe(true);
    expect(estARevoir({ ...ok, alertes: ['Classification manquante.'] })).toBe(true);
    expect(estARevoir({ ...ok, bulletin: bulletin({ net_a_payer: -40 }) })).toBe(true);
  });

  it('écart fort avec le mois précédent : à revoir', () => {
    const fort = ecartAvecMoisPrecedent(bulletin({ net_a_payer: 1800 }), AOUT);
    expect(estARevoir({ ...ok, ecart: fort })).toBe(true);
  });

  it('salarié absent du mois, ou génération en cours : pas à revoir', () => {
    expect(estARevoir({ statut: 'unavailable' })).toBe(false);
    expect(estARevoir({ statut: 'loading', bulletin: bulletin({ a_recalculer: true }) })).toBe(false);
  });
});

describe('syntheseDuMois — une ligne au-dessus de la liste', () => {
  it('compte générés, validés, attendus et totalise brut et net', () => {
    const synthese = syntheseDuMois([
      { statut: 'success', bulletin: bulletin({ status: 'valide' }), bulletinPrecedent: AOUT },
      {
        statut: 'success',
        bulletin: bulletin({ salaire_brut: 3000, net_a_payer: 2300 }),
        bulletinPrecedent: bulletin({ month: 8, net_a_payer: 2000 }),
      },
      { statut: 'idle' },
      { statut: 'unavailable' },
    ]);
    expect(synthese).toEqual({
      attendus: 3,
      generes: 2,
      valides: 1,
      totalBrut: 5000,
      totalNet: 3800,
      netPrecedent: 3500,
      ecartNetPct: expect.closeTo((3800 / 3500 - 1) * 100, 5),
    });
  });

  it('un bulletin repris de l’ancien logiciel compte comme validé : il a été payé', () => {
    const synthese = syntheseDuMois([{ statut: 'success', bulletin: bulletin({ origine: 'importe', status: null }) }]);
    expect(synthese.valides).toBe(1);
  });

  it('sans mois précédent, pas d’écart', () => {
    const synthese = syntheseDuMois([{ statut: 'success', bulletin: bulletin() }]);
    expect(synthese.netPrecedent).toBeNull();
    expect(synthese.ecartNetPct).toBeNull();
  });

  it('se dit en une phrase', () => {
    const synthese = syntheseDuMois([
      { statut: 'success', bulletin: bulletin({ status: 'valide' }), bulletinPrecedent: AOUT },
      { statut: 'success', bulletin: bulletin({ net_a_payer: 1800 }), bulletinPrecedent: AOUT },
      { statut: 'idle' },
    ]);
    expect(lisible(phraseSynthese(synthese, 2026, 9))).toBe(
      '2/3 générés · 1 validé · Brut 4 000 € · Net 3 300 € · +10 % sur août'
    );
  });

  it('sans bulletin, la phrase ne parle pas de montants', () => {
    const synthese = syntheseDuMois([{ statut: 'idle' }, { statut: 'idle' }]);
    expect(lisible(phraseSynthese(synthese, 2026, 9))).toBe('0/2 générés · 0 validé');
  });
});

describe('revue du mois — acquittement, validation, motifs', () => {
  const AOUT_NET = bulletin({ month: 8, net_a_payer: 1500 });

  it('un écart fort acquitté (R03) ne rend plus le bulletin à revoir', () => {
    const b = bulletin({ net_a_payer: 1800, alertes_acquittees: ['R03'] });
    const ecart = ecartAvecMoisPrecedent(b, AOUT_NET);
    expect(ecart.fort).toBe(false);
    expect(ecart.raison).toBeNull();
    expect(estARevoir({ statut: 'success', bulletin: b, ecart })).toBe(false);
  });

  it('des heures sup en excès acquittées (R09) ne comptent plus non plus', () => {
    const b = bulletin({ heures_sup: 30, alertes_acquittees: ['R09'] });
    expect(ecartAvecMoisPrecedent(b, AOUT_NET).fort).toBe(false);
  });

  it('acquitter l’un ne cache pas l’autre motif', () => {
    const b = bulletin({ net_a_payer: 1800, heures_sup: 30, alertes_acquittees: ['R03'] });
    const ecart = ecartAvecMoisPrecedent(b, AOUT_NET);
    expect(ecart.fort).toBe(true);
    expect(ecart.raison).toBe('30 h sup.');
  });

  it('un bulletin validé n’est jamais à revoir, même avec un écart fort ou une alerte', () => {
    const b = bulletin({ status: 'valide', net_a_payer: 1800, a_recalculer: true });
    const ecart = ecartAvecMoisPrecedent(b, AOUT_NET);
    expect(estARevoir({ statut: 'success', bulletin: b, ecart, alertes: ['Une alerte.'] })).toBe(false);
  });

  it('dit tous les motifs d’une ligne, pas seulement le premier', () => {
    const b = bulletin({ net_a_payer: -40 });
    expect(
      motifsAlerte({ statut: 'success', bulletin: b, alertes: ['Classification manquante.', 'Mutuelle absente.'] })
    ).toEqual(['Classification manquante.', 'Mutuelle absente.', 'Net à payer négatif.']);
  });

  it('aucun motif sur un bulletin calme', () => {
    expect(motifsAlerte({ statut: 'success', bulletin: bulletin() })).toEqual([]);
  });
});
