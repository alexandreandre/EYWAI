import { cn } from '@/lib/utils';

/** Barre discrète en haut de page pendant un refetch (données déjà en cache). */
export function PageFetchIndicator({ isFetching }: { isFetching: boolean }) {
  return (
    <div
      className={cn(
        'pointer-events-none fixed left-0 right-0 top-0 z-50 h-0.5 bg-primary transition-opacity duration-300',
        isFetching ? 'opacity-100 animate-pulse' : 'opacity-0',
      )}
      aria-hidden
    />
  );
}
