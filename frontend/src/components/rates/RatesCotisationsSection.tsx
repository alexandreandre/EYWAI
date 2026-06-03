import { useEffect, useMemo, useState } from 'react';
import { Search } from 'lucide-react';

import type { RateCategory, RatesSyncSourcesManifest } from '@/api/rates';
import { Collapsible, CollapsibleContent } from '@/components/ui/collapsible';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionHeaderWithActions,
} from '@/components/ui/accordion';
import { Input } from '@/components/ui/input';
import { RatesCotisationBundleCard } from '@/components/rates/RatesCotisationBundleCard';
import { RatesCotisationRatesTable } from '@/components/rates/RatesCotisationRatesTable';
import { RatesLastCheckedMeta } from '@/components/rates/RatesLastCheckedMeta';
import { RatesSectionHeader } from '@/components/rates/RatesSectionHeader';
import { RatesSectionUpdateMenu } from '@/components/rates/RatesSectionUpdateMenu';
import { RatesSingleUpdateMenu } from '@/components/rates/RatesActionsMenu';
import {
  buildCotisationDisplayRows,
  rowMatchesSearch,
} from '@/lib/cotisationDisplayGroups';
import { findCotisationUnit, sourceLinksForCotisationId, sourcesForCotisationId } from '@/lib/ratesSyncManifest';
import {
  resolveCotisationLastCheckedAt,
  shouldShowCotisationInRates,
  type Cotisation,
} from '@/lib/ratesUtils';
import { RatesPanelFooter, ratesPanelSurfaceClass } from '@/components/rates/RatesPanelShell';

type RatesCotisationsSectionProps = {
  cotisations: RateCategory;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  highlightedKeys?: Set<string>;
  manifest?: RatesSyncSourcesManifest;
  onUpdateCotisation: (cotisationId: string) => void;
  onUpdateSource: (sourceKey: string) => void;
  onUpdateCotisationBundle: (cotisationIds: string[]) => void;
  onUpdateSection: (rateKeys: string[], sectionLabel: string) => void;
  isCotisationRunning: (cotisationId: string) => boolean;
  isSourceRunning: (sourceKey: string) => boolean;
  isTargetRunning: (rateKey: string) => boolean;
  updatesLocked?: boolean;
};

export function RatesCotisationsSection({
  cotisations,
  open: sectionOpen,
  onOpenChange: setSectionOpen,
  highlightedKeys,
  manifest,
  onUpdateCotisation,
  onUpdateSource,
  onUpdateCotisationBundle,
  onUpdateSection,
  isCotisationRunning,
  isSourceRunning,
  isTargetRunning,
  updatesLocked,
}: RatesCotisationsSectionProps) {
  const list = (
    (cotisations.config_data as { cotisations?: Cotisation[] }).cotisations || []
  ).filter(shouldShowCotisationInRates);
  const [search, setSearch] = useState('');

  const sectionRateKeys = ['cotisations'];
  const sectionRunning = isTargetRunning('cotisations');

  const displayRows = useMemo(
    () => buildCotisationDisplayRows(manifest, list),
    [manifest, list],
  );

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return displayRows;
    return displayRows.filter((row) => rowMatchesSearch(row, q));
  }, [displayRows, search]);

  useEffect(() => {
    if (highlightedKeys?.has('cotisations')) setSectionOpen(true);
  }, [highlightedKeys, setSectionOpen]);

  return (
    <section>
      <Collapsible open={sectionOpen} onOpenChange={setSectionOpen}>
        <RatesSectionHeader
          open={sectionOpen}
          title="Cotisations sociales"
          description="Taux salariaux et patronaux par base de cotisation"
          onToggle={() => setSectionOpen(!sectionOpen)}
          actions={
            <>
              <RatesSectionUpdateMenu
                rateKeys={sectionRateKeys}
                manifest={manifest}
                onUpdateSection={(rateKeys) =>
                  onUpdateSection(rateKeys, 'Cotisations sociales')
                }
                isRunning={sectionRunning}
                disabled={updatesLocked}
              />
            </>
          }
        />

        <CollapsibleContent>
          <div className="relative mb-4">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Rechercher une cotisation…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8"
            />
          </div>

          {filteredRows.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Aucune cotisation ne correspond à votre recherche.
            </p>
          ) : (
            <div className="space-y-3">
              {filteredRows.map((row) => {
                if (row.type === 'bundle') {
                  const bundleRunning = row.cotisationIds.some((id) =>
                    isCotisationRunning(id),
                  );
                  const onBundleUpdate = row.sourceKey
                    ? () => onUpdateSource(row.sourceKey!)
                    : () => onUpdateCotisationBundle(row.cotisationIds);

                  return (
                    <RatesCotisationBundleCard
                      key={row.bundleKey}
                      bundleKey={row.bundleKey}
                      sourceName={row.sourceName}
                      cotisations={row.cotisations}
                      category={cotisations}
                      manifest={manifest}
                      onUpdate={onBundleUpdate}
                      isRunning={
                        bundleRunning ||
                        Boolean(row.sourceKey && isSourceRunning(row.sourceKey))
                      }
                      updatesLocked={updatesLocked}
                    />
                  );
                }

                const coti = row.cotisation;
                const unit = findCotisationUnit(manifest, coti.id);
                const rowSources =
                  unit?.sources ?? sourcesForCotisationId(manifest, coti.id);
                const showRowUpdate = rowSources.length > 0;

                return (
                  <div key={coti.id} className={ratesPanelSurfaceClass()}>
                    <Accordion type="single" collapsible defaultValue="">
                      <AccordionItem value={coti.id} className="border-0">
                        <AccordionHeaderWithActions
                          className="hover:no-underline px-4 py-3"
                          actions={
                            showRowUpdate ? (
                              <RatesSingleUpdateMenu
                                label="Mise à jour"
                                onUpdate={() => onUpdateCotisation(coti.id)}
                                isRunning={isCotisationRunning(coti.id)}
                                disabled={updatesLocked}
                                compact
                              />
                            ) : undefined
                          }
                        >
                          <div className="flex min-w-0 flex-col gap-1 text-left">
                            <span className="block min-w-0 font-medium">{coti.libelle}</span>
                            <RatesLastCheckedMeta
                              lastCheckedAt={resolveCotisationLastCheckedAt(coti)}
                            />
                          </div>
                        </AccordionHeaderWithActions>
                        <AccordionContent className="border-t border-border/60 px-2 pb-0">
                          <RatesCotisationRatesTable cotisation={coti} />
                          <RatesPanelFooter
                            links={sourceLinksForCotisationId(
                              manifest,
                              coti.id,
                              cotisations.source_links,
                            )}
                          />
                        </AccordionContent>
                      </AccordionItem>
                    </Accordion>
                  </div>
                );
              })}
            </div>
          )}
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}
