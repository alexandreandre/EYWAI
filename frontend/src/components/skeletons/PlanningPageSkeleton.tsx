import { Skeleton } from '@/components/ui/skeleton';

export function PlanningPageSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-9 w-64" />
      </div>
      <Skeleton className="h-10 w-full max-w-xl" />
      <Skeleton className="h-[420px] w-full" />
    </div>
  );
}
