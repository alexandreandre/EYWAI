export const COMPANY_PAGE_TABS = [
  "indicateurs",
  "fiche",
  "paie",
  "mutuelle",
  "modeles",
] as const;

export type CompanyPageTab = (typeof COMPANY_PAGE_TABS)[number];

export const DEFAULT_COMPANY_PAGE_TAB: CompanyPageTab = "fiche";

const LEGACY_HASH_TO_TAB: Record<string, CompanyPageTab> = {
  pilotage: "indicateurs",
  indicateurs: "indicateurs",
  identite: "fiche",
  informations: "fiche",
  coordonnees: "fiche",
  fiche: "fiche",
  paie: "paie",
  parametres: "paie",
  mutuelle: "mutuelle",
  bibliotheque: "modeles",
  modeles: "modeles",
};

export function isCompanyPageTab(value: string | null | undefined): value is CompanyPageTab {
  return COMPANY_PAGE_TABS.includes(value as CompanyPageTab);
}

export function tabFromHash(hash: string): CompanyPageTab | null {
  const key = hash.replace(/^#/, "").trim();
  if (!key) return null;
  return LEGACY_HASH_TO_TAB[key] ?? null;
}

export function tabFromSearchParam(tab: string | null): CompanyPageTab | null {
  if (!tab) return null;
  return LEGACY_HASH_TO_TAB[tab] ?? (isCompanyPageTab(tab) ? tab : null);
}

export function formatCollectiveAgreementLabel(
  collectiveAgreement: string | null | undefined,
  idcc: string | null | undefined,
): { configured: boolean; label: string; idcc: string | null } {
  const idccTrimmed = idcc?.trim() || null;
  const nameTrimmed = collectiveAgreement?.trim() || null;
  const configured = Boolean(idccTrimmed || nameTrimmed);
  if (!configured) {
    return { configured: false, label: "Non configurée", idcc: null };
  }
  const label = nameTrimmed ?? (idccTrimmed ? `IDCC ${idccTrimmed}` : "Convention renseignée");
  return { configured: true, label, idcc: idccTrimmed };
}
