import { Badge } from '@/components/ui/badge';

/**
 * Pastille « environnement de test », figée au build via VITE_APP_ENV.
 * Absente du bundle de production, pas masquée à l'exécution.
 */
export function TestEnvBadge() {
  if (import.meta.env.VITE_APP_ENV !== 'test') {
    return null;
  }

  return (
    <Badge
      variant="warning"
      role="status"
      title="Les données sont une copie de la production"
      className="fixed right-0 top-0 z-[60] rounded-none rounded-bl-lg px-2.5 py-0.5 text-[11px] whitespace-nowrap print:hidden shadow-sm"
    >
      Environnement de test
    </Badge>
  );
}
