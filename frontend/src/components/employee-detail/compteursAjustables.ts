import type { CompteurAjustable } from '@/api/leaveSettings';

/**
 * Compteurs que la fiche corrige au crayon, avec une note pour motif : le
 * serveur enregistre l'écart avec le solde affiché. Les congés payés passent
 * par le recalage. Le repos compensateur se corrige en heures (décision du 12/10).
 */
const COMPTEURS_AJUSTABLES: Record<string, { compteur: CompteurAjustable; unite: 'j' | 'h' }> = {
  RTT: { compteur: 'rtt', unite: 'j' },
  JTC: { compteur: 'jtc', unite: 'j' },
  'Repos compensateur': { compteur: 'repos_compensateur', unite: 'h' },
};

export function compteurAjustable(
  typeDeSolde: string,
): { compteur: CompteurAjustable; unite: 'j' | 'h' } | undefined {
  return COMPTEURS_AJUSTABLES[typeDeSolde];
}
