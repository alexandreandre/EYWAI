export const TAB_AUGMENTATIONS_PROMOTIONS = "augmentations-promotions";
export const TAB_SOLDE_CONGES = "solde-conges";
export const TAB_SAISIE = "saisie";
export const TAB_CALENDRIER = "calendrier";

/** Onglets d'une fiche collaborateur utiles à la production de paie. */
export const PAYROLL_FOCUS_EMPLOYEE_TABS: readonly string[] = [
  TAB_SAISIE,
  TAB_CALENDRIER,
  TAB_SOLDE_CONGES,
];

export function normalizeEmployeeDetailTab(tabParam: string | null | undefined, fallback = "documents"): string {
  const tab = tabParam ?? fallback;
  if (tab === "bulletins") return "documents";
  if (tab === "augmentation" || tab === "promotions") return TAB_AUGMENTATIONS_PROMOTIONS;
  if (tab === "suivi_medical" || tab === "suivi-medical" || tab === "medical") return "suivi_medical";
  if (tab === "solde_conges" || tab === "soldes-conges" || tab === "conges") return TAB_SOLDE_CONGES;
  return tab;
}

/** En mode paie, tout onglet hors périmètre retombe sur Primes et autres. */
export function coercePayrollFocusEmployeeTab(tab: string): string {
  return PAYROLL_FOCUS_EMPLOYEE_TABS.includes(tab) ? tab : TAB_SAISIE;
}
