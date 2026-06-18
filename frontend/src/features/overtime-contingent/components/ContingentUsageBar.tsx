import { cn } from '@/lib/utils';
import { getUsageBarColor } from '../lib/contingentStatus';

export function ContingentUsageBar({
  usagePercent,
  className,
}: {
  usagePercent: number;
  className?: string;
}) {
  const clamped = Math.min(Math.max(usagePercent, 0), 100);
  return (
    <div className={cn('space-y-1 min-w-[120px]', className)}>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn('h-full rounded-full transition-all', getUsageBarColor(usagePercent))}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <p className="text-xs text-muted-foreground tabular-nums">{usagePercent.toFixed(1)} %</p>
    </div>
  );
}
