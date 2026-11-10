/**
 * Ce que dit une case de planning pour un salarié au forfait jours.
 *
 * Le prévu d'un forfait est stocké en heures (7,8 h par jour) ou à 1 : toute valeur
 * positive vaut « jour planifié ». Le réel aussi : toute valeur positive vaut « travaillé ».
 */
export function libelleJourForfait(
  heuresPrevues: number | null | undefined,
  heuresFaites: number | null | undefined,
): 'Travaillé' | 'Prévu' | null {
  // Réel en jours (1) ou recopié en heures (7) : un jour travaillé (retour du 10/11).
  if (Number(heuresFaites ?? 0) > 0) return 'Travaillé';
  if (Number(heuresPrevues ?? 0) > 0) return 'Prévu';
  return null;
}
