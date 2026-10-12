import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { ReverseCalculationResult } from './ReverseCalculationResult';
import { PayslipSimulationResult } from './PayslipSimulationResult';

// Rejeu G.9 du 11/10/2026, page « Simulation de Paie » : le détail des
// cotisations du calcul inverse affichait « Retraite Complémentaire Tranche 1
// … 0.03 % … 0,00 € » (taux en fraction lu comme un pourcentage, parts lues
// dans des champs absents), « Écart: -0,32 € », et le bulletin d'essai
// « Salaire brut 2450.00 € ».

/** Le texte rendu, espaces insécables ramenés à des espaces simples. */
function texte(html: string): string {
  return html
    .replace(/<[^>]+>/g, '|')
    .replace(/[\u00a0\u202f]/g, ' ')
    .replace(/&#x27;/g, "'");
}

/** Les cellules de la ligne du tableau qui porte ce libellé. */
function ligneDuTableau(html: string, libelle: string): string[] {
  const ligne = html.split('<tr').find((tr) => tr.includes(libelle));
  if (!ligne) throw new Error(`ligne absente : ${libelle}`);
  return texte(ligne)
    .split('|')
    .map((c) => c.trim())
    .filter((c) => c && !c.startsWith(' class=') && !c.includes('class="'));
}

const calculInverse = {
  brut_calcule: 2343.05,
  net_obtenu: 1799.68,
  ecart: -0.32,
  iterations: 7,
  convergence: true,
  cout_employeur: 3145.45,
  bulletin_complet: {
    synthese_net: { net_social_avant_impot: 2074.77, net_imposable: 1918.23 },
    structure_cotisations: {
      bloc_principales: [
        {
          libelle: 'Retraite Complémentaire Tranche 1',
          base: 2343.05,
          taux_salarial: 0.0315,
          montant_salarial: 73.81,
          taux_patronal: 0.0472,
          montant_patronal: 110.59,
        },
        {
          libelle: 'Sécurité sociale Vieillesse plafonnée',
          base: 2343.05,
          taux_salarial: 0.069,
          montant_salarial: 161.67,
          taux_patronal: 0.0855,
          montant_patronal: 200.33,
        },
        {
          libelle: 'Allocations familiales',
          base: 2343.05,
          taux_salarial: 0,
          montant_salarial: 0,
          taux_patronal: 0.0525,
          montant_patronal: 123.01,
        },
      ],
      bloc_csg_non_deductible: [
        {
          libelle: 'CSG déductible',
          base: 2302.05,
          taux_salarial: 0.068,
          montant_salarial: 156.54,
          montant_patronal: 0,
        },
      ],
      // Le total du moteur, CSG et CRDS comprises (268,28 + 156,54 + 66,76 + 11,51).
      total_salarial: 503.09,
    },
  },
};

describe('calcul inverse : le détail des cotisations dit les vrais taux et montants', () => {
  const html = renderToStaticMarkup(
    createElement(ReverseCalculationResult, { result: calculInverse as never })
  );

  it('affiche le taux en pourcentage et la part en euros, au format français', () => {
    const retraite = ligneDuTableau(html, 'Retraite Complémentaire Tranche 1');
    expect(retraite).toEqual([
      'Retraite Complémentaire Tranche 1',
      '2 343,05 €',
      '3,15 %',
      '73,81 €',
      '4,72 %',
      '110,59 €',
    ]);
    const vieillesse = ligneDuTableau(html, 'Vieillesse plafonnée');
    expect(vieillesse.slice(2)).toEqual(['6,90 %', '161,67 €', '8,55 %', '200,33 €']);
  });

  it('ne donne pas de taux salarial à une cotisation sans part salariale', () => {
    const af = ligneDuTableau(html, 'Allocations familiales');
    expect(af.slice(2)).toEqual(['—', '—', '5,25 %', '123,01 €']);
  });

  it('montre aussi la CSG et la CRDS', () => {
    const csg = ligneDuTableau(html, 'CSG déductible');
    expect(csg.slice(2, 4)).toEqual(['6,80 %', '156,54 €']);
  });

  it('écrit l’écart et les cotisations salariales à la française', () => {
    const t = texte(html);
    expect(t).toContain('Écart : −0,32 €');
    expect(t).toMatch(/Cotisations salariales \(CSG et CRDS comprises\) :\|+−503,09 €/);
    expect(t).not.toMatch(/\d\.\d\d/);
    expect(t).not.toMatch(/[^ ]:/);
  });
});

// Rejeu G.9, suite : le calcul inverse passe désormais par le moteur du
// bulletin. Sa réponse dit la période et le type de contrat retenus (un CDI
// quand l'écran n'en demande pas), et le détail porte la réduction générale.
const calculInverseMoteur = {
  brut_calcule: 2343.05,
  net_obtenu: 1800.2,
  ecart: 0.2,
  iterations: 6,
  convergence: true,
  cout_employeur: 3001.12,
  month: 10,
  year: 2026,
  type_contrat: 'CDI',
  type_contrat_par_defaut: true,
  bulletin_complet: {
    en_tete: { periode: 'Octobre 2026' },
    synthese_net: { net_social_avant_impot: 1838.8 },
    structure_cotisations: {
      bloc_principales: [
        {
          libelle: 'Sécurité sociale Vieillesse plafonnée',
          base: 2343.05,
          taux_salarial: 0.069,
          montant_salarial: 161.67,
          taux_patronal: 0.0855,
          montant_patronal: 200.33,
        },
      ],
      bloc_allegements: [
        {
          libelle: 'Réduction générale de cotisations patronales',
          base: 2343.05,
          taux_salarial: null,
          montant_salarial: 0,
          taux_patronal: 0.1,
          montant_patronal: -234.31,
        },
      ],
      bloc_autres_contributions: { lignes: [], total: 0 },
      bloc_csg_non_deductible: [],
      total_salarial: 504.25,
      total_patronal: 658.07,
    },
  },
};

describe('calcul inverse : la période, le contrat et la réduction générale', () => {
  const html = renderToStaticMarkup(
    createElement(ReverseCalculationResult, { result: calculInverseMoteur as never })
  );
  const t = texte(html);

  it('porte la ligne de réduction générale dans le détail des cotisations', () => {
    expect(ligneDuTableau(html, 'Réduction générale')).toEqual([
      'Réduction générale de cotisations patronales',
      '2 343,05 €',
      '—',
      '—',
      '10,00 %',
      '−234,31 €',
    ]);
  });

  it('dit la période du calcul et le contrat retenu par défaut', () => {
    expect(t).toContain('Calcul sur octobre 2026, pour un CDI (type de contrat retenu par défaut).');
  });

  it('ne parle pas de défaut quand le contrat est connu', () => {
    const cdd = texte(
      renderToStaticMarkup(
        createElement(ReverseCalculationResult, {
          result: { ...calculInverseMoteur, type_contrat: 'CDD', type_contrat_par_defaut: false } as never,
        })
      )
    );
    expect(cdd).toContain('Calcul sur octobre 2026, pour un CDD.');
    expect(cdd).not.toContain('par défaut');
  });

  it('lit les cotisations salariales dans le total du moteur', () => {
    expect(t).toMatch(/Cotisations salariales \(CSG et CRDS comprises\) :\|+−504,25 €/);
  });
});

const bulletinEssai = {
  simulation_id: 'sim-1',
  payslip_data: {
    en_tete: {
      periode: 'Octobre 2026',
      entreprise: { raison_sociale: 'Société fictive', siret: '00000000000000' },
      salarie: { nom_complet: 'Personnage fictif', statut: 'Non-Cadre' },
    },
    salaire_brut: 2450,
    calcul_du_brut: [
      { libelle: 'Salaire de base', gain: 2143.81, perte: null },
      { libelle: 'Heures supplémentaires structurelles', gain: 306.19, perte: null },
      { libelle: 'Absence non rémunérée', gain: null, perte: 12.5 },
    ],
    structure_cotisations: {
      bloc_principales: [
        { libelle: 'Cotisation AGS', montant_salarial: 0, montant_patronal: 6.12 },
        { libelle: 'Retraite AGIRC-ARRCO', montant_salarial: 77.17, montant_patronal: 115.64 },
      ],
      total_salarial: 512.3,
      total_patronal: 1001.45,
    },
    synthese_net: {
      net_social_avant_impot: 1912.6,
      net_imposable: 1758.12,
      impot_prelevement_a_la_source: { base: 1758.12, taux: 2.1, montant: 36.92 },
    },
    net_a_payer: 1974.05,
    pied_de_page: { cout_total_employeur: 3451.45 },
  },
};

describe('bulletin d’essai : les montants au format français', () => {
  const t = texte(
    renderToStaticMarkup(
      createElement(PayslipSimulationResult, { result: bulletinEssai, onReset: () => {} })
    )
  );

  it('écrit brut, net imposable et net à payer avec virgule et espace des milliers', () => {
    expect(t).toContain('2 450,00 €');
    expect(t).toContain('1 758,12 €');
    expect(t).toContain('1 974,05 €');
    expect(t).toContain('3 451,45 €');
  });

  it('écrit le détail du brut et des cotisations à la française', () => {
    expect(t).toContain('+2 143,81 €');
    expect(t).toContain('−12,50 €');
    expect(t).toContain('6,12 €');
    expect(t).toContain('115,64 €');
    expect(t).toContain('−512,30 €');
    expect(t).toContain('2,1 %');
    expect(t).toContain('Période : Octobre 2026');
  });

  it('ne laisse aucun montant à point décimal ni deux-points collé', () => {
    expect(t).not.toMatch(/\d\.\d/);
    expect(t).not.toMatch(/[^ ]:/);
  });
});
