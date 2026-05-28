import type { RatesSyncSourceUnit } from '@/api/rates';
import { RatesUpdateButton } from '@/components/rates/RatesUpdateButton';

type RatesSourceUpdateListProps = {
  sources: RatesSyncSourceUnit[];
  onUpdateSource: (sourceKey: string) => void;
  isSourceRunning: (sourceKey: string) => boolean;
  compact?: boolean;
  className?: string;
};

export function RatesSourceUpdateList({
  sources,
  onUpdateSource,
  isSourceRunning,
  compact = false,
  className,
}: RatesSourceUpdateListProps) {
  if (sources.length === 0) return null;

  return (
    <div className={`flex flex-wrap gap-2 ${compact ? '' : 'mt-1'} ${className ?? ''}`}>
      {sources.map((src) => (
        <RatesUpdateButton
          key={src.source_key}
          label={src.source_name}
          onClick={() => onUpdateSource(src.source_key)}
          isRunning={isSourceRunning(src.source_key) || src.is_running}
          size="sm"
        />
      ))}
    </div>
  );
}
