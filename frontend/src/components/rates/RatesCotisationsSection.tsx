import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight, Search } from 'lucide-react';

import type { RateCategory, RatesSyncSourcesManifest } from '@/api/rates';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionHeaderWithActions,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableRow } from '@/components/ui/table';
import { TooltipProvider } from '@/components/ui/tooltip';
import { RatesVersionBadge } from '@/components/rates/RatesVersionBadge';
import { RatesRateValue } from '@/components/rates/RatesRateValue';
import { RatesSourceUpdateList } from '@/components/rates/RatesSourceUpdateList';
import { RatesUpdateButton } from '@/components/rates/RatesUpdateButton';
import { formatRateDate, formatRateKey, getRateDateColor, type Cotisation } from '@/lib/ratesUtils';
import { findCotisationUnit, sourcesForCotisationId, sourcesForRateKey } from '@/lib/ratesSyncManifest';

type RatesCotisationsSectionProps = {
  cotisations: RateCategory;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  highlightedKeys?: Set<string>;
  manifest?: RatesSyncSourcesManifest;
  onUpdateSource: (sourceKey: string) => void;
  onUpdateCotisation: (cotisationId: string) => void;
  isSourceRunning: (sourceKey: string) => boolean;
  isCotisationRunning: (cotisationId: string) => boolean;
};

export function RatesCotisationsSection({
  cotisations,
  open: sectionOpen,
  onOpenChange: setSectionOpen,
  highlightedKeys,
  manifest,
  onUpdateSource,
  onUpdateCotisation,
  isSourceRunning,
  isCotisationRunning,
}: RatesCotisationsSectionProps) {
  const list = (cotisations.config_data as { cotisations?: Cotisation[] }).cotisations || [];
  const [search, setSearch] = useState('');

  const sectionSources = sourcesForRateKey(manifest, 'cotisations');

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return list;
    return list.filter(
      (c) =>
        c.libelle.toLowerCase().includes(q) || c.base.toLowerCase().includes(q),
    );
  }, [list, search]);

  useEffect(() => {
    if (highlightedKeys?.has('cotisations')) setSectionOpen(true);
  }, [highlightedKeys, setSectionOpen]);

  const groupedByBase = useMemo(() => {
    const map = new Map<string, Cotisation[]>();
    for (const coti of filtered) {
      const base = coti.base?.trim() || 'autre';
      const group = map.get(base) ?? [];
      group.push(coti);
      map.set(base, group);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b, 'fr'));
  }, [filtered]);

  return (
    <section>
      <Collapsible open={sectionOpen} onOpenChange={setSectionOpen}>
        <div className="flex flex-col gap-3 mb-4 border-b border-border/70 pb-2">
          <div className="flex flex-wrap justify-between items-end gap-3">
            <CollapsibleTrigger asChild>
              <Button
                variant="ghost"
                className="gap-2 px-0 text-foreground hover:bg-transparent hover:text-foreground"
              >
                {sectionOpen ? (
                  <ChevronDown className="h-5 w-5" />
                ) : (
                  <ChevronRight className="h-5 w-5" />
                )}
                <h2 className="text-2xl font-semibold text-foreground">Cotisations sociales</h2>
                <Badge variant="secondary">{list.length}</Badge>
              </Button>
            </CollapsibleTrigger>
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className={`font-medium ${getRateDateColor(cotisations.last_checked_at)}`}>
                Dernier contrôle : {formatRateDate(cotisations.last_checked_at)}
              </span>
              <TooltipProvider>
                <RatesVersionBadge
                  version={cotisations.version}
                  comment={cotisations.comment}
                />
              </TooltipProvider>
            </div>
          </div>
        </div>

        <CollapsibleContent>
          {sectionSources.length > 0 && (
            <RatesSourceUpdateList
              sources={sectionSources}
              onUpdateSource={onUpdateSource}
              isSourceRunning={isSourceRunning}
              compact
              className="mb-3"
            />
          )}
          <div className="mb-3 max-w-sm relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Rechercher une cotisation…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-8"
            />
          </div>
          <div className="bg-card border rounded-lg p-4 shadow-sm">
            {filtered.length === 0 ? (
              <p className="text-sm text-muted-foreground py-4 text-center">
                Aucune cotisation ne correspond à votre recherche.
              </p>
            ) : (
              <Accordion type="multiple" defaultValue={[]} className="w-full space-y-1">
                {groupedByBase.map(([base, items]) => (
                  <AccordionItem key={base} value={`base-${base}`} className="border rounded-lg px-2">
                    <AccordionTrigger className="hover:no-underline py-3">
                      <span className="font-medium">{formatRateKey(base)}</span>
                      <Badge variant="secondary" className="ml-2 text-xs">
                        {items.length}
                      </Badge>
                    </AccordionTrigger>
                    <AccordionContent className="pb-2">
                      <Accordion type="multiple" defaultValue={[]} className="w-full">
                        {items.map((coti) => {
                          const unit = findCotisationUnit(manifest, coti.id);
                          const rowSources =
                            unit?.sources ?? sourcesForCotisationId(manifest, coti.id);
                          const showRowUpdate = rowSources.length > 0;

                          return (
                            <AccordionItem key={coti.id} value={coti.id} className="border-0 border-t">
                              <AccordionHeaderWithActions
                                className="hover:no-underline py-2"
                                actions={
                                  showRowUpdate ? (
                                    rowSources.length === 1 ? (
                                      <RatesUpdateButton
                                        label="Mettre à jour"
                                        onClick={() => onUpdateCotisation(coti.id)}
                                        isRunning={isCotisationRunning(coti.id)}
                                        size="sm"
                                      />
                                    ) : (
                                      <>
                                        {rowSources.map((src) => (
                                          <RatesUpdateButton
                                            key={src.source_key}
                                            label={src.source_name}
                                            onClick={() => onUpdateSource(src.source_key)}
                                            isRunning={isSourceRunning(src.source_key)}
                                            size="sm"
                                          />
                                        ))}
                                      </>
                                    )
                                  ) : undefined
                                }
                              >
                                <span className="font-medium truncate text-left text-sm pr-2">
                                  {coti.libelle}
                                </span>
                              </AccordionHeaderWithActions>
                              <AccordionContent>
                                <Table>
                                  <TableBody>
                                    {Object.entries(coti)
                                      .filter(
                                        ([key]) =>
                                          key.includes('salarial') || key.includes('patronal'),
                                      )
                                      .map(([key, value]) => (
                                        <TableRow key={key}>
                                          <TableCell className="h-auto p-1.5 text-sm text-muted-foreground">
                                            {formatRateKey(key)}
                                          </TableCell>
                                          <TableCell className="h-auto p-1.5 text-right font-medium">
                                            <RatesRateValue value={value} />
                                          </TableCell>
                                        </TableRow>
                                      ))}
                                  </TableBody>
                                </Table>
                              </AccordionContent>
                            </AccordionItem>
                          );
                        })}
                      </Accordion>
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            )}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}
