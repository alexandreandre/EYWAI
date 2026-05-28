import { useIsFetching } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useBoot } from '@/contexts/BootContext';

/**
 * Indicateur discret pendant le chargement des données en arrière-plan (post-boot).
 */
export function BackgroundDataIndicator() {
  const { isBooting } = useBoot();
  const fetchingCount = useIsFetching();

  if (isBooting || fetchingCount === 0) {
    return null;
  }

  return (
    <div
      className="pointer-events-none fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-full border bg-background/95 px-3 py-1.5 text-xs text-muted-foreground shadow-sm backdrop-blur"
      role="status"
      aria-live="polite"
    >
      <Loader2 className="h-3 w-3 animate-spin" />
      Mise à jour des données…
    </div>
  );
}
