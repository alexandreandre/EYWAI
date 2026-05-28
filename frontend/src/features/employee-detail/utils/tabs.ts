export const TAB_AUGMENTATIONS_PROMOTIONS = "augmentations-promotions";

export function normalizeEmployeeDetailTab(tabParam: string | null | undefined, fallback = "documents"): string {
  const tab = tabParam ?? fallback;
  if (tab === "bulletins") return "documents";
  if (tab === "augmentation" || tab === "promotions") return TAB_AUGMENTATIONS_PROMOTIONS;
  if (tab === "suivi_medical" || tab === "suivi-medical" || tab === "medical") return "suivi_medical";
  return tab;
}
