import { describe, expect, it } from 'vitest';
import {
  ACCOUNTING_PROVIDER_CATALOG,
  getProviderMeta,
} from '@/features/accounting-integration/providers';

describe('accounting providers catalog', () => {
  it('expose les fournisseurs principaux', () => {
    expect(ACCOUNTING_PROVIDER_CATALOG.manual.name).toBe('Manuel');
    expect(ACCOUNTING_PROVIDER_CATALOG.cegid_quadra.logoKey).toBe('cegid');
    expect(ACCOUNTING_PROVIDER_CATALOG.sage.brandColor).toBeTruthy();
  });

  it('repli sur manuel pour une clé inconnue', () => {
    expect(getProviderMeta('unknown_provider').key).toBe('manual');
  });
});
