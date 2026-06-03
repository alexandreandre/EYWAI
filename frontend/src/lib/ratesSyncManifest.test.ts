import { describe, expect, it } from 'vitest';

import type { RatesSyncSourcesManifest } from '@/api/rates';
import {
  activeSyncCoversRateKey,
  activeSyncCoversSourceKey,
  buildSourceLinksForManifestSources,
  isActiveJobForCotisation,
  isCotisationRunningInSync,
  sourceKeysForTarget,
  sourceLinksForCotisationId,
  sourceLinksForRateKey,
  sourcesForCotisationId,
  syncTargetToRequest,
} from '@/lib/ratesSyncManifest';

const manifest: RatesSyncSourcesManifest = {
  all_critical_count: 2,
  rate_categories: [
    {
      rate_key: 'smic',
      sources: [{ source_key: 'SMIC', source_name: 'SMIC', is_running: false }],
    },
    {
      rate_key: 'cotisations',
      sources: [
        { source_key: 'CSG', source_name: 'CSG', is_running: false },
        { source_key: 'AGIRC-ARRCO', source_name: 'Agirc-Arrco', is_running: false },
      ],
      cotisation_units: [
        {
          cotisation_id: 'csg',
          sources: [{ source_key: 'CSG', source_name: 'CSG', is_running: false }],
        },
      ],
    },
  ],
};

describe('ratesSyncManifest', () => {
  it('maps rate_key target to request', () => {
    expect(syncTargetToRequest({ scope: 'rate_key', rateKey: 'smic' })).toEqual({
      rate_keys: ['smic'],
    });
  });

  it('resolves source keys for cotisation', () => {
    expect(sourcesForCotisationId(manifest, 'csg')).toHaveLength(1);
    expect(sourceKeysForTarget(manifest, { scope: 'cotisation_id', cotisationId: 'csg' })).toEqual([
      'CSG',
    ]);
  });

  it('résout les sources CFP sans tenir compte de la casse', () => {
    const withCfp: RatesSyncSourcesManifest = {
      all_critical_count: 1,
      rate_categories: [
        {
          rate_key: 'cotisations',
          sources: [{ source_key: 'CFP', source_name: 'CFP', is_running: false }],
          cotisation_units: [
            {
              cotisation_id: 'CFP',
              sources: [{ source_key: 'CFP', source_name: 'CFP', is_running: false }],
            },
          ],
        },
      ],
    };
    expect(sourcesForCotisationId(withCfp, 'cfp')).toHaveLength(1);
    expect(sourcesForCotisationId(withCfp, 'CFP')).toHaveLength(1);
  });

  it('spinner ceg_t1 ne concerne pas ceg_t2 ni dialogue social (même source AGIRC)', () => {
    const m: RatesSyncSourcesManifest = {
      all_critical_count: 2,
      rate_categories: [
        {
          rate_key: 'cotisations',
          sources: [
            { source_key: 'AGIRC-ARRCO', source_name: 'Agirc', is_running: false },
            { source_key: 'DIALOGUE_SOCIAL', source_name: 'Dialogue', is_running: false },
          ],
          cotisation_units: [
            {
              cotisation_id: 'ceg_t1',
              sources: [{ source_key: 'AGIRC-ARRCO', source_name: 'Agirc', is_running: false }],
            },
            {
              cotisation_id: 'ceg_t2',
              sources: [{ source_key: 'AGIRC-ARRCO', source_name: 'Agirc', is_running: false }],
            },
            {
              cotisation_id: 'dialogue_social',
              sources: [
                { source_key: 'DIALOGUE_SOCIAL', source_name: 'Dialogue', is_running: false },
              ],
            },
          ],
        },
      ],
    };
    const params = {
      target: { scope: 'cotisation_id' as const, cotisationId: 'ceg_t1' },
      jobs: [
        {
          source_key: 'AGIRC-ARRCO',
          status: 'running',
          cotisation_ids: ['ceg_t1'],
        },
      ],
    };
    expect(isCotisationRunningInSync(m, params, 'ceg_t1')).toBe(true);
    expect(isCotisationRunningInSync(m, params, 'ceg_t2')).toBe(false);
    expect(isCotisationRunningInSync(m, params, 'dialogue_social')).toBe(false);
    expect(isCotisationRunningInSync(m, params, 'apec')).toBe(false);
  });

  it('cible cotisation_id + job sans cotisation_ids : seule la ligne ciblée tourne', () => {
    const m: RatesSyncSourcesManifest = {
      all_critical_count: 1,
      rate_categories: [
        {
          rate_key: 'cotisations',
          sources: [{ source_key: 'AGIRC-ARRCO', source_name: 'Agirc', is_running: false }],
          cotisation_units: [
            {
              cotisation_id: 'ceg_t1',
              sources: [{ source_key: 'AGIRC-ARRCO', source_name: 'Agirc', is_running: false }],
            },
            {
              cotisation_id: 'ceg_t2',
              sources: [{ source_key: 'AGIRC-ARRCO', source_name: 'Agirc', is_running: false }],
            },
          ],
        },
      ],
    };
    const params = {
      target: { scope: 'cotisation_id' as const, cotisationId: 'ceg_t1' },
      jobs: [{ source_key: 'AGIRC-ARRCO', status: 'running' }],
    };
    expect(isCotisationRunningInSync(m, params, 'ceg_t1')).toBe(true);
    expect(isCotisationRunningInSync(m, params, 'ceg_t2')).toBe(false);
  });

  it('activeSyncCoversRateKey ignore une sync cotisation_id', () => {
    expect(
      activeSyncCoversRateKey({ scope: 'cotisation_id', cotisationId: 'ceg_t1' }, 'smic'),
    ).toBe(false);
    expect(
      activeSyncCoversRateKey({ scope: 'rate_key', rateKey: 'smic' }, 'smic'),
    ).toBe(true);
  });

  it('activeSyncCoversSourceKey ne matche que source_key explicite', () => {
    expect(
      activeSyncCoversSourceKey({ scope: 'cotisation_id', cotisationId: 'ceg_t1' }, 'AGIRC-ARRCO'),
    ).toBe(false);
    expect(
      activeSyncCoversSourceKey({ scope: 'source_key', sourceKey: 'AGIRC-ARRCO' }, 'AGIRC-ARRCO'),
    ).toBe(true);
  });

  it('job sans cotisation_ids active toutes les lignes de la source', () => {
    const m: RatesSyncSourcesManifest = {
      all_critical_count: 1,
      rate_categories: [
        {
          rate_key: 'cotisations',
          sources: [{ source_key: 'AGIRC-ARRCO', source_name: 'Agirc', is_running: false }],
          cotisation_units: [
            {
              cotisation_id: 'ceg_t1',
              sources: [{ source_key: 'AGIRC-ARRCO', source_name: 'Agirc', is_running: false }],
            },
            {
              cotisation_id: 'ceg_t2',
              sources: [{ source_key: 'AGIRC-ARRCO', source_name: 'Agirc', is_running: false }],
            },
          ],
        },
      ],
    };
    const job = { source_key: 'AGIRC-ARRCO', status: 'running' };
    expect(isActiveJobForCotisation(m, job, 'ceg_t1')).toBe(true);
    expect(isActiveJobForCotisation(m, job, 'ceg_t2')).toBe(true);
  });

  it('assemble les URLs officielles et LegiSocial pour une cotisation', () => {
    const m: RatesSyncSourcesManifest = {
      all_critical_count: 1,
      rate_categories: [
        {
          rate_key: 'cotisations',
          sources: [],
          cotisation_units: [
            {
              cotisation_id: 'csg',
              sources: [
                {
                  source_key: 'CSG',
                  source_name: 'CSG',
                  primary_url:
                    'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html',
                  is_running: false,
                },
              ],
            },
          ],
        },
      ],
    };
    const categoryLinks = [
      'https://www.legisocial.fr/reperes-sociaux/taux-cotisations-sociales-urssaf-2026.html',
    ];
    expect(sourceLinksForCotisationId(m, 'csg', categoryLinks)).toEqual([
      'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/taux-cotisations-secteur-prive.html',
      'https://www.legisocial.fr/reperes-sociaux/taux-cotisations-sociales-urssaf-2026.html',
    ]);
  });

  it('repli sur source_links catégorie si manifest sans primary_url', () => {
    const links = sourceLinksForRateKey(manifest, 'smic', [
      'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/montant-smic.html',
    ]);
    expect(links).toEqual([
      'https://www.urssaf.fr/accueil/outils-documentation/taux-baremes/montant-smic.html',
    ]);
  });

  it('buildSourceLinksForManifestSources déduplique les primary_url', () => {
    const links = buildSourceLinksForManifestSources(
      [
        {
          source_key: 'A',
          source_name: 'A',
          primary_url: 'https://www.urssaf.fr/a',
          is_running: false,
        },
        {
          source_key: 'B',
          source_name: 'B',
          primary_url: 'https://www.urssaf.fr/a',
          is_running: false,
        },
      ],
      null,
    );
    expect(links).toHaveLength(1);
  });
});
