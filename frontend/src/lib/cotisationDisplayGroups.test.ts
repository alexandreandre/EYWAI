import { describe, expect, it } from 'vitest';

import type { RatesSyncSourcesManifest } from '@/api/rates';
import {
  buildCotisationDisplayRows,
  bundleDisplayLabel,
  rowMatchesSearch,
  type CotisationDisplayRow,
} from '@/lib/cotisationDisplayGroups';
import type { Cotisation } from '@/lib/ratesUtils';

const agircManifest: RatesSyncSourcesManifest = {
  all_critical_count: 1,
  rate_categories: [
    {
      rate_key: 'cotisations',
      sources: [{ source_key: 'AGIRC-ARRCO', source_name: 'Agirc-Arrco', is_running: false }],
      cotisation_units: ['ceg_t1', 'ceg_t2', 'cet'].map((id) => ({
        cotisation_id: id,
        sources: [{ source_key: 'AGIRC-ARRCO', source_name: 'Agirc-Arrco', is_running: false }],
      })),
    },
  ],
};

const mmidVieillesseManifest: RatesSyncSourcesManifest = {
  all_critical_count: 2,
  rate_categories: [
    {
      rate_key: 'cotisations',
      sources: [],
      cotisation_units: [
        {
          cotisation_id: 'securite_sociale_maladie',
          sources: [
            { source_key: 'MMID_PATRONAL', source_name: 'MMID patronal', is_running: false },
            { source_key: 'MMID_SALARIAL', source_name: 'MMID salarial', is_running: false },
          ],
        },
        {
          cotisation_id: 'retraite_secu_plafond',
          sources: [
            {
              source_key: 'VIEILLESSE_PATRONAL',
              source_name: 'Vieillesse patronal',
              is_running: false,
            },
            {
              source_key: 'VIEILLESSE_SALARIAL',
              source_name: 'Vieillesse salarial',
              is_running: false,
            },
          ],
        },
        {
          cotisation_id: 'retraite_secu_deplafond',
          sources: [
            {
              source_key: 'VIEILLESSE_PATRONAL',
              source_name: 'Vieillesse patronal',
              is_running: false,
            },
            {
              source_key: 'VIEILLESSE_SALARIAL',
              source_name: 'Vieillesse salarial',
              is_running: false,
            },
          ],
        },
      ],
    },
  ],
};

function coti(id: string, libelle: string): Cotisation {
  return { id, libelle, base: 'brut', salarial: 0.01, patronal: 0.02 };
}

describe('cotisationDisplayGroups', () => {
  it('regroupe les lignes partageant une seule source', () => {
    const rows = buildCotisationDisplayRows(agircManifest, [
      coti('ceg_t2', 'CEG T2'),
      coti('ceg_t1', 'CEG T1'),
      coti('cet', 'CET'),
      coti('csg', 'CSG'),
    ]);
    const bundle = rows.find((r) => r.type === 'bundle' && r.bundleKey.startsWith('source:'));
    const single = rows.find((r) => r.type === 'single');
    expect(bundle?.type).toBe('bundle');
    if (bundle?.type === 'bundle') {
      expect(bundle.cotisations.map((c) => c.id)).toEqual(['ceg_t1', 'ceg_t2', 'cet']);
      expect(bundle.sourceName).toBe('AGIRC ARRCO');
      expect(bundle.sourceKey).toBeDefined();
    }
    expect(single?.type).toBe('single');
  });

  it('regroupe MMID maladie et vieillesse plafonnée/déplafonnée en un lot explicite', () => {
    const rows = buildCotisationDisplayRows(mmidVieillesseManifest, [
      coti('retraite_secu_deplafond', 'Sécurité sociale Vieillesse déplafonnée'),
      coti('retraite_secu_plafond', 'Sécurité sociale Vieillesse plafonnée'),
      coti('securite_sociale_maladie', 'Sécurité sociale - Maladie'),
    ]);
    const explicit = rows.filter(
      (r) => r.type === 'bundle' && r.bundleKey === 'securite_sociale_mmid_vieillesse',
    );
    expect(explicit).toHaveLength(1);
    if (explicit[0]?.type === 'bundle') {
      expect(explicit[0].cotisationIds).toEqual([
        'securite_sociale_maladie',
        'retraite_secu_plafond',
        'retraite_secu_deplafond',
      ]);
      expect(explicit[0].sourceKey).toBeUndefined();
    }
    expect(rows.filter((r) => r.type === 'single')).toHaveLength(0);
  });

  it('bundleDisplayLabel utilise le libellé métier connu', () => {
    expect(bundleDisplayLabel('AGIRC_ARRCO', 'Agirc-Arrco')).toBe('AGIRC ARRCO');
  });

  it('rowMatchesSearch trouve un lot via une ligne enfant', () => {
    const rows = buildCotisationDisplayRows(agircManifest, [
      coti('ceg_t1', 'CEG T1'),
      coti('ceg_t2', 'CEG T2'),
    ]);
    const bundle = rows[0];
    expect(rowMatchesSearch(bundle, 'ceg t1')).toBe(true);
  });

  it('rowMatchesSearch tolère libelle ou base null', () => {
    const row: CotisationDisplayRow = {
      type: 'single',
      cotisation: {
        id: 'retraite_comp_t1',
        libelle: 'Retraite complémentaire T1',
        base: null as unknown as string,
        salarial: 0.01,
        patronal: 0.02,
      },
    };
    expect(() => rowMatchesSearch(row, 'retraite')).not.toThrow();
    expect(rowMatchesSearch(row, 'retraite')).toBe(true);
  });
});
