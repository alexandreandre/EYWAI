import { Skeleton } from '@/components/ui/skeleton';

/** Skeleton léger pour la badgeuse kiosque (sans sidebar RH). */
export function BadgeuseTerminalSkeleton() {
  return (
    <div className="min-h-screen bg-background">
      <main className="mx-auto w-full max-w-6xl p-4 sm:p-6 lg:p-8 space-y-4">
        <div className="flex items-center justify-between border-b pb-4">
          <Skeleton className="h-9 w-32" />
          <div className="space-y-2 flex flex-col items-end">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-7 w-36 rounded-full" />
          </div>
        </div>
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-4">
          <Skeleton className="h-[420px] w-full rounded-xl" />
          <div className="space-y-4">
            <Skeleton className="h-48 w-full rounded-xl" />
            <Skeleton className="h-40 w-full rounded-xl" />
          </div>
        </div>
      </main>
    </div>
  );
}
