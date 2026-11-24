import type { ShiftType } from '@/api/planning';

/**
 * Types proposés dans la fenêtre d'un shift. Un shift déjà posé garde son type
 * même quand la liste ne le propose plus (poste de convention copié par la
 * société, type désactivé) : sans lui, le sélecteur était vide et une nuit
 * était refusée (« fin avant début »).
 */
export function typesProposesPourLeShift(
  types: ShiftType[],
  typeDuShift: ShiftType | undefined | null,
): ShiftType[] {
  if (!typeDuShift?.id || types.some((t) => t.id === typeDuShift.id)) return types;
  return [...types, typeDuShift];
}
