import { Badge } from '@/components/ui/badge';

/**
 * Pastille du site de paie avant sa mise en service définitive, figée au build
 * via VITE_APP_ENV (le nom technique de ce site reste « test »). Absente du
 * bundle de production, pas masquée à l'exécution.
 *
 * Elle dit ce qui est vrai pour la gestionnaire : les données sont réelles et
 * conservées, et quatre envois restent coupés sur ce site (garde-fous de
 * APP_ENV=test : e-mails des salariés redirigés, dépôt de DSN par l'API,
 * signature électronique, transmission automatique au cabinet comptable).
 */
export const TEXTE_PASTILLE = 'Données réelles · envois limités';

export const DETAIL_PASTILLE =
  "Les données de ce site sont réelles et conservées. Jusqu'à la mise en service " +
  'définitive, certains envois sont coupés : les e-mails destinés aux salariés partent ' +
  "vers une boîte de contrôle (ceux de l'équipe RH arrivent normalement), la DSN se " +
  'dépose à la main sur net-entreprises, la signature électronique et la transmission ' +
  'automatique au cabinet comptable sont désactivées.';

export function TestEnvBadge() {
  if (import.meta.env.VITE_APP_ENV !== 'test') {
    return null;
  }

  return (
    <Badge
      variant="warning"
      role="status"
      title={DETAIL_PASTILLE}
      aria-label={`${TEXTE_PASTILLE}. ${DETAIL_PASTILLE}`}
      className="fixed right-0 top-0 z-[60] rounded-none rounded-bl-lg px-2.5 py-0.5 text-[11px] whitespace-nowrap print:hidden shadow-sm"
    >
      {TEXTE_PASTILLE}
    </Badge>
  );
}
