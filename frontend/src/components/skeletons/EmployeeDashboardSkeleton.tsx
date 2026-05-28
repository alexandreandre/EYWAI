import { Skeleton } from '@/components/ui/skeleton';

export function EmployeeDashboardSkeleton() {
  return (
    <div className="space-y-6" aria-hidden>
      <div className="space-y-2">
        <Skeleton className="h-9 w-64" />
        <Skeleton className="h-4 w-48" />
      </div>
      <Skeleton className="h-28 w-full rounded-xl" />
      <div className="space-y-4">
        <Skeleton className="h-5 w-24" />
        <div className="flex gap-4 overflow-hidden">
          <Skeleton className="h-28 min-w-[85%] shrink-0 rounded-xl sm:min-w-[45%] lg:min-w-0 lg:flex-1" />
          <Skeleton className="h-28 min-w-[85%] shrink-0 rounded-xl sm:min-w-[45%] lg:hidden" />
        </div>
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="hidden gap-4 lg:grid lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-28 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-36 rounded-xl" />
          <Skeleton className="h-32 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
        </div>
        <div className="space-y-6">
          <Skeleton className="h-40 rounded-xl" />
          <Skeleton className="h-80 rounded-xl" />
        </div>
      </div>
    </div>
  );
}
