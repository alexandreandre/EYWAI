import type { DemandeDeConfirmation } from '@/hooks/useConfirmation';

/**
 * La confirmation de « Clôturer le mois » du suivi IJSS : la clôture partait au
 * premier clic, et l'écran n'a pas de route pour rouvrir (audit R1, geste 8).
 */
export function confirmationClotureIjss({
  libelleMois,
  ecarts,
  enAttente,
}: {
  libelleMois: string;
  ecarts: number;
  enAttente: number;
}): Required<Pick<DemandeDeConfirmation, 'titre' | 'confirmer' | 'destructif'>> & { description: string } {
  const restes = [
    ecarts > 0 ? `${ecarts} écart${ecarts > 1 ? 's' : ''} à traiter` : null,
    enAttente > 0 ? `${enAttente} arrêt${enAttente > 1 ? 's' : ''} en attente CPAM` : null,
  ].filter((r): r is string => r !== null);
  const base =
    'Les imports, les synchronisations et « Appliquer validés » seront fermés pour ce mois. L’écran ne permet pas de rouvrir un mois clôturé.';
  return {
    titre: `Clôturer ${libelleMois} ?`,
    description: restes.length > 0 ? `${base} Il reste ${restes.join(' et ')}.` : base,
    confirmer: 'Clôturer le mois',
    destructif: true,
  };
}
