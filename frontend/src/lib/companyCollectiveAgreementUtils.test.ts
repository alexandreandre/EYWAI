import { describe, expect, it } from 'vitest';

import type { CompanyCollectiveAgreementWithDetails } from '@/api/collectiveAgreements';
import {
  getDefaultCompanyCollectiveAgreementId,
  resolveDefaultCollectiveAgreementId,
  sortAffiliatedCompanyAgreements,
} from '@/lib/companyCollectiveAgreementUtils';

function agreement(
  id: string,
  assignedAt: string,
  isActive = true,
): CompanyCollectiveAgreementWithDetails {
  return {
    id: `row-${id}`,
    company_id: 'company-1',
    collective_agreement_id: id,
    assigned_at: assignedAt,
    agreement_details: {
      id,
      created_at: assignedAt,
      updated_at: assignedAt,
      name: `CC ${id}`,
      idcc: id,
      is_active: isActive,
    },
  };
}

describe('companyCollectiveAgreementUtils', () => {
  it('tri chronologique et ignore les CC désactivées du catalogue', () => {
    const sorted = sortAffiliatedCompanyAgreements([
      agreement('cc-2', '2024-06-01T00:00:00Z'),
      agreement('cc-1', '2024-01-01T00:00:00Z'),
      agreement('cc-3', '2024-03-01T00:00:00Z', false),
    ]);

    expect(sorted.map((a) => a.collective_agreement_id)).toEqual(['cc-1', 'cc-2']);
  });

  it('retourne la première CC affiliée chronologique', () => {
    const defaultId = getDefaultCompanyCollectiveAgreementId([
      agreement('cc-b', '2024-06-01T00:00:00Z'),
      agreement('cc-a', '2024-01-01T00:00:00Z'),
    ]);

    expect(defaultId).toBe('cc-a');
  });

  it('conserve une CC affiliée déjà sélectionnée', () => {
    const agreements = [
      agreement('cc-a', '2024-01-01T00:00:00Z'),
      agreement('cc-b', '2024-06-01T00:00:00Z'),
    ];

    expect(resolveDefaultCollectiveAgreementId(agreements, 'cc-b')).toBe('cc-b');
  });

  it('remplace une CC non affiliée par la première chronologique', () => {
    const agreements = [
      agreement('cc-a', '2024-01-01T00:00:00Z'),
      agreement('cc-old', '2023-01-01T00:00:00Z', false),
    ];

    expect(resolveDefaultCollectiveAgreementId(agreements, 'cc-old')).toBe('cc-a');
    expect(resolveDefaultCollectiveAgreementId(agreements, null)).toBe('cc-a');
  });
});
