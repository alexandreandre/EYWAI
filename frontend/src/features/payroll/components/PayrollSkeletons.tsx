import { Skeleton } from '@/components/ui/skeleton';

export function PayrollEmployeeListSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-1 px-1" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="flex items-center gap-2 rounded-md px-3 py-2.5"
        >
          <Skeleton className="h-7 w-7 shrink-0 rounded-full" />
          <div className="min-w-0 flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-[70%]" />
            <Skeleton className="h-3 w-[45%]" />
          </div>
          <Skeleton className="h-5 w-6 shrink-0 rounded-full" />
        </div>
      ))}
    </div>
  );
}

export function PayrollMonthListSkeleton({ rows = 12 }: { rows?: number }) {
  return (
    <ul className="divide-y divide-border/60" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <li
          key={i}
          className="flex flex-col gap-2 rounded-md border border-transparent p-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex min-w-0 flex-1 items-start gap-3">
            <Skeleton className="mt-0.5 h-5 w-5 shrink-0 rounded-sm" />
            <div className="min-w-0 flex-1 space-y-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-3 w-12" />
              <div className="flex gap-2">
                <Skeleton className="h-5 w-16 rounded-full" />
                <Skeleton className="h-3 w-20" />
              </div>
            </div>
          </div>
          <Skeleton className="h-8 w-20 shrink-0 rounded-md" />
        </li>
      ))}
    </ul>
  );
}
