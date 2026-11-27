/**
 * Un jour modifié à la main dans la relecture n'est plus « heures retenues
 * du fichier » : la mention disparaît dès qu'une heure, un type ou une
 * nature changent vraiment.
 */
export interface JourModifiable {
  heures?: number | null;
  type?: string;
  nature?: string;
  heures_fixees_par_fichier?: boolean;
}

const CHAMPS_DU_JOUR = ['heures', 'type', 'nature'] as const;

export function modifierLeJour<T extends JourModifiable>(jour: T, patch: Partial<T>): T {
  const change = CHAMPS_DU_JOUR.some(
    (champ) => champ in patch && patch[champ] !== jour[champ],
  );
  return {
    ...jour,
    ...patch,
    ...(change ? { heures_fixees_par_fichier: false } : {}),
  };
}
