import type { RatesSyncSourceUnit } from '@/api/rates';
import { RatesActionsMenu } from '@/components/rates/RatesActionsMenu';
import { cn } from '@/lib/utils';

type RatesSourceUpdateListProps = {
  sources: RatesSyncSourceUnit[];
  onUpdateSource: (sourceKey: string) => void;
  isSourceRunning: (sourceKey: string) => boolean;
  updatesLocked?: boolean;
  compact?: boolean;
  className?: string;
};

export function RatesSourceUpdateList({
  sources,
  onUpdateSource,
  isSourceRunning,
  updatesLocked,
  compact = false,
  className,
}: RatesSourceUpdateListProps) {
  if (sources.length === 0) return null;

  const menuLabel = (src: RatesSyncSourceUnit): string => {
    if (sources.length === 1) return 'Mise à jour';
    const key = src.source_key.toUpperCase();
    if (key.includes('PATRONAL')) return 'Mise à jour — patronal';
    if (key.includes('SALARIAL')) return 'Mise à jour — salarial';
    return src.source_name;
  };

  const items = sources.map((src) => ({
    id: src.source_key,
    label: menuLabel(src),
    onSelect: () => onUpdateSource(src.source_key),
    isRunning: isSourceRunning(src.source_key),
    disabled: updatesLocked,
  }));

  return (
    <div className={cn('flex', compact ? '' : 'justify-end', className)}>
      <RatesActionsMenu items={items} compact={compact} />
    </div>
  );
}
