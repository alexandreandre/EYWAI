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
import { RatesVmrrView } from '@/components/rates/RatesVmrrView';
import { getCategoryTitle } from '@/lib/ratesUtils';
import {
  getBaremesRateKeysFromData,
  isBaremesRateKeyPending,
  listBaremesSectionKeys,
  sourceLinksForRateKey,
  sourcesForRateKey,
} from '@/lib/ratesSyncManifest';
import { cn } from '@/lib/utils';

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
  if (key === 'taux_vmrr') {
    return <RatesVmrrView configData={category.config_data} />;
  }
  return <RatesComplexObject obj={cfg} />;
}

function buildManifestLinks(sources: { primary_url?: string | null }[]): string[] {
  const links: string[] = [];
  for (const src of sources) {
    const url = src.primary_url?.trim();
    if (url) links.push(url);
  }
  return links;
}

function renderPendingBaremeContent(key: string, canUpdate: boolean) {
  if (key === 'taux_vmrr') {
    if (!canUpdate) {
      return (
        <p className="text-sm leading-relaxed text-muted-foreground">
          Source « Versement mobilité » absente du référentiel scraping. Contactez
          l&apos;administrateur plateforme ou lancez une{' '}
          <span className="font-medium text-foreground">Mise à jour complète</span> après
          déploiement des sources.
        </p>
      );
    }
    return <RatesVmrrView configData={null} />;
  }
  return (
    <p className="text-sm leading-relaxed text-muted-foreground">
      Référentiel non chargé. Cliquez sur{' '}
      <span className="font-medium text-foreground">⋮</span> puis{' '}
      <span className="font-medium text-foreground">Mise à jour</span>.
    </p>
  );
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
  const sectionRateKeys = useMemo(
    () => getBaremesRateKeysFromData(data, manifest),
    [data, manifest],
  );
  const sectionRunning = sectionRateKeys.some((k) => isTargetRunning(k));

  const sectionKeys = useMemo(
    () => listBaremesSectionKeys(data, manifest),
    [data, manifest],
  );

  const [openBaremes, setOpenBaremes] = useState<string[]>([]);

  useEffect(() => {
    if (!highlightedKeys?.size) return;
    onOpenChange(true);
    setOpenBaremes((prev) => [...new Set([...prev, ...highlightedKeys])]);
  }, [highlightedKeys, onOpenChange]);

  if (sectionKeys.length === 0) return null;

  return (
    <section>
      <Collapsible open={open} onOpenChange={onOpenChange}>
        <RatesSectionHeader
          open={open}
          title="Barèmes & abattements"
          description="Prélèvement à la source, frais professionnels, versement mobilité, avantages en nature"
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
            {sectionKeys.map((key) => {
              const category = data[key];
              const pending = isBaremesRateKeyPending(data, key);
              const sources = sourcesForRateKey(manifest, key);
              const singleSource = sources.length === 1;
              const canUpdate = sources.length > 0;

              return (
                <AccordionItem
                  key={key}
                  value={key}
                  className={cn(ratesPanelSurfaceClass(highlightedKeys?.has(key)), 'border-0')}
                >
                  <AccordionHeaderWithActions
                    className="px-4 py-3 hover:no-underline"
                    actions={
                      canUpdate ? (
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
                      {pending ? (
                        <span className="text-xs font-medium text-amber-700 dark:text-amber-400">
                          Non synchronisé — lancez la mise à jour
                        </span>
                      ) : (
                        category && (
                          <RatesLastCheckedMeta lastCheckedAt={category.last_checked_at} />
                        )
                      )}
                    </div>
                  </AccordionHeaderWithActions>
                  <AccordionContent className="pb-0 pt-0">
                    <div className="border-t border-border/60 px-4 pb-3 pt-3">
                      {category && !pending
                        ? renderBaremeContent(key, category)
                        : renderPendingBaremeContent(key, canUpdate)}
                    </div>
                    {category ? (
                      <RatesPanelFooter
                        category={category}
                        links={sourceLinksForRateKey(manifest, key, category.source_links)}
                      />
                    ) : sources.length > 0 ? (
                      <RatesPanelFooter links={buildManifestLinks(sources)} />
                    ) : null}
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
