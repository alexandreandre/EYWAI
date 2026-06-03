import { useEffect } from 'react';

import type { RatesResponse } from '@/api/rates';
import { Collapsible, CollapsibleContent } from '@/components/ui/collapsible';
import { RatesCategoryCard } from '@/components/rates/RatesCategoryCard';
import { RatesSimpleTable } from '@/components/rates/RatesComplexData';
import { RatesSectionHeader } from '@/components/rates/RatesSectionHeader';
import { RatesSectionUpdateMenu } from '@/components/rates/RatesSectionUpdateMenu';
import {
  buildIjPlafondsDisplaySections,
  buildSmicDisplaySections,
  getCategoryTitle,
  resolvePssSections,
} from '@/lib/ratesUtils';
import { sourcesForRateKey, sourceLinksForRateKey } from '@/lib/ratesSyncManifest';
import type { RatesSyncSourcesManifest } from '@/api/rates';

type RatesKeyParamsSectionProps = {
  data: RatesResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  highlightedKeys?: Set<string>;
  manifest?: RatesSyncSourcesManifest;
  onUpdateRateKey: (rateKey: string) => void;
  onUpdateSection: (rateKeys: string[], sectionLabel: string) => void;
  isTargetRunning: (rateKey: string) => boolean;
  updatesLocked?: boolean;
};

export function RatesKeyParamsSection({
  data,
  open,
  onOpenChange,
  highlightedKeys,
  manifest,
  onUpdateRateKey,
  onUpdateSection,
  isTargetRunning,
  updatesLocked,
}: RatesKeyParamsSectionProps) {
  const keys = ['smic', 'pss', 'ij_plafonds'] as const;
  const sectionRateKeys = keys.filter((k) => data[k]);
  const hasAny = sectionRateKeys.length > 0;
  const sectionRunning = sectionRateKeys.some((k) => isTargetRunning(k));

  useEffect(() => {
    if (keys.some((k) => highlightedKeys?.has(k))) onOpenChange(true);
  }, [highlightedKeys, onOpenChange]);

  if (!hasAny) return null;

  return (
    <section>
      <Collapsible open={open} onOpenChange={onOpenChange}>
        <RatesSectionHeader
          open={open}
          title="Paramètres clés"
          description="SMIC, plafond de la Sécurité sociale, plafonds des indemnités journalières"
          onToggle={() => onOpenChange(!open)}
          actions={
            <RatesSectionUpdateMenu
              rateKeys={[...sectionRateKeys]}
              manifest={manifest}
              onUpdateSection={(rateKeys) => onUpdateSection(rateKeys, 'Paramètres clés')}
              isRunning={sectionRunning}
              disabled={updatesLocked}
            />
          }
        />
        <CollapsibleContent>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {data.smic && (
              <RatesCategoryCard
                title="SMIC"
                rateKey="smic"
                category={data.smic}
                sourceLinks={sourceLinksForRateKey(manifest, 'smic', data.smic.source_links)}
                highlight={highlightedKeys?.has('smic')}
                onUpdate={() => onUpdateRateKey('smic')}
                isUpdating={isTargetRunning('smic')}
                canUpdate={sourcesForRateKey(manifest, 'smic').length > 0}
                disabled={updatesLocked}
              >
                <RatesSimpleTable
                  obj={buildSmicDisplaySections(
                    data.smic.config_data as Record<string, unknown>,
                  )}
                  unit="€/h"
                />
              </RatesCategoryCard>
            )}
            {data.pss && (
              <RatesCategoryCard
                title={getCategoryTitle('pss')}
                rateKey="pss"
                category={data.pss}
                sourceLinks={sourceLinksForRateKey(manifest, 'pss', data.pss.source_links)}
                highlight={highlightedKeys?.has('pss')}
                onUpdate={() => onUpdateRateKey('pss')}
                isUpdating={isTargetRunning('pss')}
                canUpdate={sourcesForRateKey(manifest, 'pss').length > 0}
                disabled={updatesLocked}
              >
                <RatesSimpleTable
                  obj={resolvePssSections(data.pss.config_data as Record<string, unknown>)}
                  unit="€"
                />
              </RatesCategoryCard>
            )}
            {data.ij_plafonds && (
              <RatesCategoryCard
                title={getCategoryTitle('ij_plafonds')}
                rateKey="ij_plafonds"
                category={data.ij_plafonds}
                sourceLinks={sourceLinksForRateKey(
                  manifest,
                  'ij_plafonds',
                  data.ij_plafonds.source_links,
                )}
                highlight={highlightedKeys?.has('ij_plafonds')}
                onUpdate={() => onUpdateRateKey('ij_plafonds')}
                isUpdating={isTargetRunning('ij_plafonds')}
                canUpdate={sourcesForRateKey(manifest, 'ij_plafonds').length > 0}
                disabled={updatesLocked}
              >
                <RatesSimpleTable
                  obj={buildIjPlafondsDisplaySections(
                    data.ij_plafonds.config_data as Record<string, unknown>,
                  )}
                  unit="€/jour"
                />
              </RatesCategoryCard>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}
