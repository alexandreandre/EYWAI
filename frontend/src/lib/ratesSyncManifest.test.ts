import { describe, expect, it } from 'vitest';

import type { RatesSyncSourcesManifest } from '@/api/rates';
import {
  sourceKeysForTarget,
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
});
