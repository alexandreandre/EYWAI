import type { CompanyCollectiveAgreementWithDetails } from '@/api/collectiveAgreements';

/** CC encore affiliée à l'entreprise (catalogue actif). */
export function isAffiliatedCompanyAgreement(
  agreement: CompanyCollectiveAgreementWithDetails,
): boolean {
  return agreement.agreement_details?.is_active !== false;
}

/** CC affiliées actives, triées par ordre d'ajout (assigned_at croissant). */
export function sortAffiliatedCompanyAgreements(
  agreements: CompanyCollectiveAgreementWithDetails[],
): CompanyCollectiveAgreementWithDetails[] {
  return [...agreements]
    .filter(isAffiliatedCompanyAgreement)
    .sort((a, b) => {
      const ta = Date.parse(a.assigned_at || '') || 0;
      const tb = Date.parse(b.assigned_at || '') || 0;
      return ta - tb;
    });
}

/** Première CC affiliée chronologique, ou null si aucune. */
export function getDefaultCompanyCollectiveAgreementId(
  agreements: CompanyCollectiveAgreementWithDetails[],
): string | null {
  const sorted = sortAffiliatedCompanyAgreements(agreements);
  return sorted[0]?.collective_agreement_id ?? null;
}

/**
 * Conserve currentId s'il pointe encore vers une CC affiliée ;
 * sinon retourne la première CC affiliée chronologique.
 */
export function resolveDefaultCollectiveAgreementId(
  agreements: CompanyCollectiveAgreementWithDetails[],
  currentId?: string | null,
): string | null {
  const affiliated = sortAffiliatedCompanyAgreements(agreements);
  if (affiliated.length === 0) return null;
  if (
    currentId &&
    affiliated.some((a) => a.collective_agreement_id === currentId)
  ) {
    return currentId;
  }
  return affiliated[0].collective_agreement_id;
}
