import type { RateCategory, RatesSyncSourcesManifest } from '@/api/rates';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionHeaderWithActions,
} from '@/components/ui/accordion';
import { RatesCotisationBundleRatesBody } from '@/components/rates/RatesCotisationBundleRatesBody';
import { RatesSingleUpdateMenu } from '@/components/rates/RatesActionsMenu';
import { RatesLastCheckedMeta } from '@/components/rates/RatesLastCheckedMeta';
import { RatesPanelFooter, ratesPanelSurfaceClass } from '@/components/rates/RatesPanelShell';
import { sourceLinksForCotisationId } from '@/lib/ratesSyncManifest';
import { latestCotisationLastCheckedAt, type Cotisation } from '@/lib/ratesUtils';

type RatesCotisationBundleCardProps = {
  bundleKey: string;
  sourceName: string;
  cotisations: Cotisation[];
  category: RateCategory;
  manifest?: RatesSyncSourcesManifest;
  onUpdate: () => void;
  isRunning: boolean;
  highlight?: boolean;
  updatesLocked?: boolean;
};

/** Même présentation qu’une cotisation simple : un déploiement, tous les sous-taux visibles. */
export function RatesCotisationBundleCard({
  bundleKey,
  sourceName,
  cotisations,
  category,
  manifest,
  onUpdate,
  isRunning,
  highlight,
  updatesLocked,
}: RatesCotisationBundleCardProps) {
  const footerLinks = [
    ...new Set(
      cotisations.flatMap((c) =>
        sourceLinksForCotisationId(manifest, c.id, category.source_links),
      ),
    ),
  ];

  return (
    <div className={ratesPanelSurfaceClass(highlight)}>
      <Accordion type="single" collapsible defaultValue="">
        <AccordionItem value={bundleKey} className="border-0">
          <AccordionHeaderWithActions
            className="hover:no-underline px-4 py-3"
            actions={
              <RatesSingleUpdateMenu
                label="Mise à jour"
                onUpdate={onUpdate}
                isRunning={isRunning}
                disabled={updatesLocked}
                compact
              />
            }
          >
            <div className="flex min-w-0 flex-col gap-1 text-left">
              <span className="block min-w-0 font-medium">{sourceName}</span>
              <RatesLastCheckedMeta
                lastCheckedAt={latestCotisationLastCheckedAt(cotisations)}
              />
            </div>
          </AccordionHeaderWithActions>
          <AccordionContent className="border-t border-border/60 px-2 pb-0">
            <RatesCotisationBundleRatesBody cotisations={cotisations} />
            <RatesPanelFooter links={footerLinks.length > 0 ? footerLinks : null} />
          </AccordionContent>
        </AccordionItem>
      </Accordion>
    </div>
  );
}
