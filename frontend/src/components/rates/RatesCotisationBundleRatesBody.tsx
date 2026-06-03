import { RatesCotisationRatesTable } from '@/components/rates/RatesCotisationRatesTable';
import type { Cotisation } from '@/lib/ratesUtils';
import { cn } from '@/lib/utils';

type RatesCotisationBundleRatesBodyProps = {
  cotisations: Cotisation[];
};

/** Tous les sous-taux d’un lot, visibles d’un coup au déploiement (sans accordéon imbriqué). */
export function RatesCotisationBundleRatesBody({
  cotisations,
}: RatesCotisationBundleRatesBodyProps) {
  return (
    <div className="divide-y divide-border/60">
      {cotisations.map((coti, index) => (
        <div
          key={coti.id}
          className={cn(index === 0 ? '' : 'pt-1')}
        >
          {cotisations.length > 1 ? (
            <p className="px-4 pb-1 pt-3 text-sm font-medium text-foreground">{coti.libelle}</p>
          ) : null}
          <RatesCotisationRatesTable cotisation={coti} />
        </div>
      ))}
    </div>
  );
}
