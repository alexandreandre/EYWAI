import { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

import type { RateCategory, RatesResponse, RatesSyncSourcesManifest } from '@/api/rates';
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
} from '@/components/ui/accordion';
import { Button } from '@/components/ui/button';
import { TooltipProvider } from '@/components/ui/tooltip';
import { RatesVersionBadge } from '@/components/rates/RatesVersionBadge';
import { RatesComplexObject, RatesPasView } from '@/components/rates/RatesComplexData';
import { RatesSourceLinks } from '@/components/rates/RatesSourceLinks';
import { RatesSourceUpdateList } from '@/components/rates/RatesSourceUpdateList';
import { RatesUpdateButton } from '@/components/rates/RatesUpdateButton';
import { formatRateDate, getCategoryTitle, getRateDateColor } from '@/lib/ratesUtils';
import { sourcesForRateKey } from '@/lib/ratesSyncManifest';
import { cn } from '@/lib/utils';

const KNOWN_KEYS = new Set([
  'smic',
  'pss',
  'ij_plafonds',
  'cotisations',
  'pas',
  'frais_pro',
  'avantages_en_nature',
]);

type BaremeEntry = { key: string; category: RateCategory };

function renderBaremeContent(key: string, category: RateCategory) {
  const cfg = category.config_data as Record<string, unknown>;
  if (key === 'pas') return <RatesPasView configData={cfg} />;
  if (key === 'frais_pro') {
    const frais = cfg.FRAIS_PRO as Array<{ sections?: Record<string, unknown> }> | undefined;
    return <RatesComplexObject obj={frais?.[0]?.sections ?? cfg} />;
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
  isTargetRunning: (rateKey: string) => boolean;
  isSourceRunning: (sourceKey: string) => boolean;
};

export function RatesBaremesSection({
  data,
  open,
  onOpenChange,
  highlightedKeys,
  manifest,
  onUpdateRateKey,
  onUpdateSource,
  isTargetRunning,
  isSourceRunning,
}: RatesBaremesSectionProps) {
  const entries = useMemo(() => {
    const items: BaremeEntry[] = [];
    const ordered = ['pas', 'frais_pro', 'avantages_en_nature'] as const;
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
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="mb-4 w-full justify-start gap-2 rounded-none border-b border-border/70 px-0 pb-2 text-foreground hover:bg-transparent hover:text-foreground"
          >
            {open ? <ChevronDown className="h-5 w-5" /> : <ChevronRight className="h-5 w-5" />}
            <h2 className="text-2xl font-semibold text-foreground">Barèmes & abattements</h2>
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <Accordion
            type="multiple"
            value={openBaremes}
            onValueChange={setOpenBaremes}
            className="space-y-2"
          >
            {entries.map(({ key, category }) => {
              const sources = sourcesForRateKey(manifest, key);
              const singleSource = sources.length === 1;

              return (
                <AccordionItem
                  key={key}
                  value={key}
                  className={cn(
                    'border rounded-lg px-3 bg-card shadow-sm',
                    highlightedKeys?.has(key) && 'ring-2 ring-primary/40',
                  )}
                >
                  <AccordionHeaderWithActions
                    className="hover:no-underline py-3"
                    actions={
                      sources.length > 0 ? (
                        singleSource ? (
                          <RatesUpdateButton
                            label="Mettre à jour"
                            onClick={() => onUpdateRateKey(key)}
                            isRunning={isTargetRunning(key)}
                            size="sm"
                          />
                        ) : (
                          <RatesSourceUpdateList
                            sources={sources}
                            onUpdateSource={onUpdateSource}
                            isSourceRunning={isSourceRunning}
                            compact
                          />
                        )
                      ) : undefined
                    }
                  >
                    <div className="flex flex-1 items-center gap-2 pr-2 text-left">
                      <span className="font-semibold">{getCategoryTitle(key)}</span>
                      <TooltipProvider>
                        <RatesVersionBadge
                          version={category.version}
                          comment={category.comment}
                        />
                      </TooltipProvider>
                    </div>
                  </AccordionHeaderWithActions>
                  <AccordionContent className="pb-4">
                    {renderBaremeContent(key, category)}
                    <RatesSourceLinks links={category.source_links} />
                    <p
                      className={`text-xs mt-4 text-right font-medium ${getRateDateColor(category.last_checked_at)}`}
                    >
                      Contrôlé le : {formatRateDate(category.last_checked_at)}
                    </p>
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
