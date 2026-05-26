import { Skeleton } from '@/components/ui/skeleton';

type TableSkeletonProps = {
  rows?: number;
  columns?: number;
};

export function TableSkeleton({ rows = 8, columns = 4 }: TableSkeletonProps) {
  return (
    <div className="space-y-3" aria-hidden>
      <div className="flex gap-4 border-b pb-3">
        {Array.from({ length: columns }).map((_, i) => (
          <Skeleton key={i} className="h-4 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, row) => (
        <div key={row} className="flex gap-4 py-2">
          {Array.from({ length: columns }).map((_, col) => (
            <Skeleton key={col} className="h-8 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}
