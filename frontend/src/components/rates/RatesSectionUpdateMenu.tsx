import type { RatesSyncSourcesManifest } from '@/api/rates';
import { RatesSingleUpdateMenu } from '@/components/rates/RatesActionsMenu';
import { sourcesForRateKeys } from '@/lib/ratesSyncManifest';

type RatesSectionUpdateMenuProps = {
  rateKeys: string[];
  manifest?: RatesSyncSourcesManifest;
  onUpdateSection: (rateKeys: string[]) => void;
  isRunning?: boolean;
  disabled?: boolean;
  compact?: boolean;
  className?: string;
};

/** Menu ⋮ pour lancer la mise à jour de toute une section (plusieurs rate_key). */
export function RatesSectionUpdateMenu({
  rateKeys,
  manifest,
  onUpdateSection,
  isRunning,
  disabled,
  compact = true,
  className,
}: RatesSectionUpdateMenuProps) {
  if (rateKeys.length === 0) return null;
  if (sourcesForRateKeys(manifest, rateKeys).length === 0) return null;

  return (
    <RatesSingleUpdateMenu
      label="Mettre à jour la section"
      onUpdate={() => onUpdateSection(rateKeys)}
      isRunning={isRunning}
      disabled={disabled}
      compact={compact}
      className={className}
    />
  );
}
