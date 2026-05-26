import { Skeleton } from '@/components/ui/skeleton';

export function RouteSkeleton() {
  return (
    <div className="flex min-h-[50vh] w-full flex-col gap-6 p-6 lg:p-8">
      <Skeleton className="h-9 w-64" />
      <Skeleton className="h-4 w-96 max-w-full" />
      <div className="grid gap-4 md:grid-cols-3">
        <Skeleton className="h-28 rounded-lg" />
        <Skeleton className="h-28 rounded-lg" />
        <Skeleton className="h-28 rounded-lg" />
      </div>
      <Skeleton className="h-64 w-full rounded-lg" />
    </div>
  );
}
