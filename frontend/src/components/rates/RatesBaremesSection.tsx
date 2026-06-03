import { useEffect, useMemo, useState } from 'react';

import type { RateCategory, RatesResponse, RatesSyncSourcesManifest } from '@/api/rates';
import { Collapsible, CollapsibleContent } from '@/components/ui/collapsible';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionHeaderWithActions,
} from '@/components/ui/accordion';
import {
  RatesAvantagesEnNatureView,
  RatesComplexObject,
  RatesPasView,
} from '@/components/rates/RatesComplexData';
import { RatesHeuresSuppView } from '@/components/rates/RatesHeuresSuppView';
import { RatesPrimesView } from '@/components/rates/RatesPrimesView';
import { RatesLastCheckedMeta } from '@/components/rates/RatesLastCheckedMeta';
import { RatesSectionHeader } from '@/components/rates/RatesSectionHeader';
import { RatesSectionUpdateMenu } from '@/components/rates/RatesSectionUpdateMenu';
import { RatesSourceUpdateList } from '@/components/rates/RatesSourceUpdateList';
import { RatesSingleUpdateMenu } from '@/components/rates/RatesActionsMenu';
import { RatesPanelFooter, ratesPanelSurfaceClass } from '@/components/rates/RatesPanelShell';
import { getCategoryTitle } from '@/lib/ratesUtils';
import { getBaremesRateKeysFromData, sourceLinksForRateKey, sourcesForRateKey } from '@/lib/ratesSyncManifest';
import { cn } from '@/lib/utils';

const KNOWN_KEYS = new Set([
  'smic',
  'pss',
  'ij_plafonds',
  'cotisations',
  'pas',
  'frais_pro',
  'avantages_en_nature',
  'heures_supp',
  'primes',
]);

type BaremeEntry = { key: string; category: RateCategory };

function renderBaremeContent(key: string, category: RateCategory) {
  const cfg = category.config_data as Record<string, unknown>;
  if (key === 'pas') return <RatesPasView configData={cfg} />;
  if (key === 'frais_pro') {
    const frais = cfg.FRAIS_PRO as Array<{ sections?: Record<string, unknown> }> | undefined;
    return <RatesComplexObject obj={frais?.[0]?.sections ?? cfg} />;
  }
  if (key === 'avantages_en_nature') {
    return <RatesAvantagesEnNatureView configData={cfg} />;
  }
  if (key === 'heures_supp') {
    return <RatesHeuresSuppView configData={cfg} />;
  }
  if (key === 'primes') {
    return <RatesPrimesView configData={cfg} />;
  }
  return <RatesComplexObject obj={cfg} />;
}

type RatesBaremesSectionProps = {
  data: RatesResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  highlightedKeys?: Set<string>;
  manifest?: RatesSyncSourcesManifest;
  onUpdateRateKey: (rateKey: string) => void;
  onUpdateSource: (sourceKey: string) => void;
  onUpdateSection: (rateKeys: string[], sectionLabel: string) => void;
  isTargetRunning: (rateKey: string) => boolean;
  isSourceRunning: (sourceKey: string) => boolean;
  updatesLocked?: boolean;
};

export function RatesBaremesSection({
  data,
  open,
  onOpenChange,
  highlightedKeys,
  manifest,
  onUpdateRateKey,
  onUpdateSource,
  onUpdateSection,
  isTargetRunning,
  isSourceRunning,
  updatesLocked,
}: RatesBaremesSectionProps) {
  const sectionRateKeys = useMemo(() => getBaremesRateKeysFromData(data), [data]);
  const sectionRunning = sectionRateKeys.some((k) => isTargetRunning(k));

  const entries = useMemo(() => {
    const items: BaremeEntry[] = [];
    const ordered = ['pas', 'frais_pro', 'avantages_en_nature', 'heures_supp', 'primes'] as const;
    for (const key of ordered) {
      if (data[key]) items.push({ key, category: data[key] });
    }
    for (const [key, cat] of Object.entries(data)) {
      if (!KNOWN_KEYS.has(key) && cat?.config_data) {
        items.push({ key, category: cat });
      }
    }
    return items;
  }, [data]);

  const [openBaremes, setOpenBaremes] = useState<string[]>([]);

  useEffect(() => {
    if (!highlightedKeys?.size) return;
    onOpenChange(true);
    setOpenBaremes((prev) => [...new Set([...prev, ...highlightedKeys])]);
  }, [highlightedKeys, onOpenChange]);

  if (entries.length === 0) return null;

  return (
    <section>
      <Collapsible open={open} onOpenChange={onOpenChange}>
        <RatesSectionHeader
          open={open}
          title="Barèmes & abattements"
          description="Prélèvement à la source, frais professionnels, avantages en nature"
          onToggle={() => onOpenChange(!open)}
          actions={
            <RatesSectionUpdateMenu
              rateKeys={sectionRateKeys}
              manifest={manifest}
              onUpdateSection={(rateKeys) =>
                onUpdateSection(rateKeys, 'Barèmes & abattements')
              }
              isRunning={sectionRunning}
              disabled={updatesLocked}
            />
          }
        />
        <CollapsibleContent>
          <Accordion
            type="multiple"
            value={openBaremes}
            onValueChange={setOpenBaremes}
            className="space-y-3"
          >
            {entries.map(({ key, category }) => {
              const sources = sourcesForRateKey(manifest, key);
              const singleSource = sources.length === 1;

              return (
                <AccordionItem
                  key={key}
                  value={key}
                  className={cn(ratesPanelSurfaceClass(highlightedKeys?.has(key)), 'border-0')}
                >
                  <AccordionHeaderWithActions
                    className="px-4 py-3 hover:no-underline"
                    actions={
                      sources.length > 0 ? (
                        singleSource ? (
                          <RatesSingleUpdateMenu
                            onUpdate={() => onUpdateRateKey(key)}
                            isRunning={isTargetRunning(key)}
                            disabled={updatesLocked}
                            compact
                          />
                        ) : (
                          <RatesSourceUpdateList
                            sources={sources}
                            onUpdateSource={onUpdateSource}
                            isSourceRunning={isSourceRunning}
                            updatesLocked={updatesLocked}
                            compact
                          />
                        )
                      ) : undefined
                    }
                  >
                    <div className="flex min-w-0 flex-col gap-2 text-left">
                      <span className="min-w-0 truncate font-semibold">
                        {getCategoryTitle(key)}
                      </span>
                      <RatesLastCheckedMeta
                        lastCheckedAt={category.last_checked_at}
                      />
                    </div>
                  </AccordionHeaderWithActions>
                  <AccordionContent className="pb-0 pt-0">
                    <div className="border-t border-border/60 px-4 pb-3 pt-3">
                      {renderBaremeContent(key, category)}
                    </div>
                    <RatesPanelFooter
                      category={category}
                      links={sourceLinksForRateKey(manifest, key, category.source_links)}
                    />
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}
