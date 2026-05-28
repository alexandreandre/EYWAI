import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';

/** Barre discrète en haut de l’écran pendant un refetch (données déjà en cache). */
export function PageFetchIndicator({ isFetching }: { isFetching: boolean }) {
  return createPortal(
    <div
      className={cn(
        'pointer-events-none fixed inset-x-0 top-0 z-[200] h-0.5 bg-primary transition-opacity duration-300',
        isFetching ? 'opacity-100 animate-pulse' : 'opacity-0',
      )}
      aria-hidden
    />,
    document.body,
  );
}
