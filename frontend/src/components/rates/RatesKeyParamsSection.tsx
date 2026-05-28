import { useEffect } from 'react';

import type { RatesResponse } from '@/api/rates';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { RatesCategoryCard } from '@/components/rates/RatesCategoryCard';
import { RatesSimpleTable } from '@/components/rates/RatesComplexData';
import { getCategoryTitle } from '@/lib/ratesUtils';
import { sourcesForRateKey } from '@/lib/ratesSyncManifest';
import type { RatesSyncSourcesManifest } from '@/api/rates';

type RatesKeyParamsSectionProps = {
  data: RatesResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  highlightedKeys?: Set<string>;
  manifest?: RatesSyncSourcesManifest;
  onUpdateRateKey: (rateKey: string) => void;
  isTargetRunning: (rateKey: string) => boolean;
};

export function RatesKeyParamsSection({
  data,
  open,
  onOpenChange,
  highlightedKeys,
  manifest,
  onUpdateRateKey,
  isTargetRunning,
}: RatesKeyParamsSectionProps) {
  const keys = ['smic', 'pss', 'ij_plafonds'] as const;
  const hasAny = keys.some((k) => data[k]);

  useEffect(() => {
    if (keys.some((k) => highlightedKeys?.has(k))) onOpenChange(true);
  }, [highlightedKeys, onOpenChange]);

  if (!hasAny) return null;

  return (
    <section>
      <Collapsible open={open} onOpenChange={onOpenChange}>
        <div className="flex items-center justify-between border-b border-border/70 pb-2 mb-4">
          <CollapsibleTrigger asChild>
            <Button
              variant="ghost"
              className="gap-2 px-0 text-foreground hover:bg-transparent hover:text-foreground"
            >
              {open ? <ChevronDown className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
              <h2 className="text-2xl font-semibold text-foreground">Paramètres clés</h2>
            </Button>
          </CollapsibleTrigger>
        </div>
        <CollapsibleContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {data.smic && (
              <RatesCategoryCard
                title="SMIC"
                category={data.smic}
                highlight={highlightedKeys?.has('smic')}
                onUpdate={() => onUpdateRateKey('smic')}
                isUpdating={isTargetRunning('smic')}
                canUpdate={sourcesForRateKey(manifest, 'smic').length > 0}
              >
                <RatesSimpleTable
                  obj={
                    (data.smic.config_data as { smic_horaire?: Record<string, unknown> })
                      .smic_horaire ||
                    (data.smic.config_data as Record<string, unknown>)
                  }
                  unit="€/h"
                />
              </RatesCategoryCard>
            )}
            {data.pss && (
              <RatesCategoryCard
                title={getCategoryTitle('pss')}
                category={data.pss}
                highlight={highlightedKeys?.has('pss')}
                onUpdate={() => onUpdateRateKey('pss')}
                isUpdating={isTargetRunning('pss')}
                canUpdate={sourcesForRateKey(manifest, 'pss').length > 0}
              >
                <RatesSimpleTable
                  obj={
                    (data.pss.config_data as { pss?: Record<string, unknown> }).pss ||
                    (data.pss.config_data as Record<string, unknown>)
                  }
                  unit="€"
                />
              </RatesCategoryCard>
            )}
            {data.ij_plafonds && (
              <RatesCategoryCard
                title={getCategoryTitle('ij_plafonds')}
                category={data.ij_plafonds}
                highlight={highlightedKeys?.has('ij_plafonds')}
                onUpdate={() => onUpdateRateKey('ij_plafonds')}
                isUpdating={isTargetRunning('ij_plafonds')}
                canUpdate={sourcesForRateKey(manifest, 'ij_plafonds').length > 0}
              >
                <RatesSimpleTable
                  obj={
                    (
                      data.ij_plafonds.config_data as {
                        plafonds_indemnites_journalieres?: Record<string, unknown>;
                      }
                    ).plafonds_indemnites_journalieres ||
                    (data.ij_plafonds.config_data as Record<string, unknown>)
                  }
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
