import { RouteSkeleton } from '@/components/skeletons/RouteSkeleton';
import { Skeleton } from '@/components/ui/skeleton';

/** Affiché pendant auth / entreprises, après le splash boot. */
export function ProtectedAppSkeleton() {
  return (
    <div className="min-h-screen flex w-full bg-muted/40">
      <Skeleton className="hidden md:block w-64 shrink-0 rounded-none" />
      <div className="flex min-w-0 flex-1 flex-col">
        <Skeleton className="h-14 w-full shrink-0 md:hidden" />
        <main className="min-w-0 flex-1 p-6 lg:p-8">
          <RouteSkeleton />
        </main>
      </div>
    </div>
  );
}
