/**
 * Ce que dit une case de planning pour un salarié au forfait jours.
 *
 * Le prévu d'un forfait est stocké en heures (7,8 h par jour) ou à 1 : toute valeur
 * positive vaut « jour planifié ». Le réel, lui, vaut 1 quand le jour est confirmé.
 */
export function libelleJourForfait(
  heuresPrevues: number | null | undefined,
  heuresFaites: number | null | undefined,
): 'Travaillé' | 'Prévu' | null {
  if (heuresFaites === 1) return 'Travaillé';
  if (Number(heuresPrevues ?? 0) > 0) return 'Prévu';
  return null;
}
