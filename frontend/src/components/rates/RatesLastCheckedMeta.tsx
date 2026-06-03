import { formatRateDate, getRateDateColor } from '@/lib/ratesUtils';
import { cn } from '@/lib/utils';

type RatesLastCheckedMetaProps = {
  lastCheckedAt: string | null | undefined;
  className?: string;
  /** Libellé avant la date (ex. « Dernier contrôle »). */
  label?: string;
};

export function RatesLastCheckedMeta({
  lastCheckedAt,
  className,
  label = 'Dernier contrôle',
}: RatesLastCheckedMetaProps) {
  return (
    <p className={cn('text-xs', className)}>
      {lastCheckedAt ? (
        <>
          <span className="text-muted-foreground">{label} : </span>
          <span className={cn('font-medium', getRateDateColor(lastCheckedAt))}>
            {formatRateDate(lastCheckedAt)}
          </span>
        </>
      ) : (
        <span className={getRateDateColor(null)}>Aucun contrôle enregistré</span>
      )}
    </p>
  );
}
