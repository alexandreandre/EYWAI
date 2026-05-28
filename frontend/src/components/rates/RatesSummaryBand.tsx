import { AlertTriangle, CheckCircle2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { formatRateDate } from '@/lib/ratesUtils';

type RatesSummaryBandProps = {
  categoryCount: number;
  obsoleteCount: number;
  oldestCheck: string | null;
  health: 'ok' | 'warning' | 'critical';
};

export function RatesSummaryBand({
  categoryCount,
  obsoleteCount,
  oldestCheck,
  health,
}: RatesSummaryBandProps) {
  const badge =
    health === 'ok' ? (
      <Badge className="bg-emerald-600 hover:bg-emerald-600">
        <CheckCircle2 className="h-3 w-3 mr-1" />
        À jour
      </Badge>
    ) : health === 'warning' ? (
      <Badge variant="outline" className="border-orange-500 text-orange-600">
        <AlertTriangle className="h-3 w-3 mr-1" />
        Contrôle recommandé
      </Badge>
    ) : (
      <Badge variant="destructive">
        <AlertTriangle className="h-3 w-3 mr-1" />
        Mise à jour urgente
      </Badge>
    );

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/30 px-4 py-3 text-sm">
      {badge}
      <span className="text-muted-foreground">
        {categoryCount} catégorie{categoryCount > 1 ? 's' : ''} active{categoryCount > 1 ? 's' : ''}
      </span>
      {obsoleteCount > 0 && (
        <span className="text-orange-600 font-medium">
          {obsoleteCount} sans contrôle récent (&gt; 14 j)
        </span>
      )}
      {oldestCheck && (
        <span className="text-muted-foreground">
          Contrôle le plus ancien : {formatRateDate(oldestCheck)}
        </span>
      )}
    </div>
  );
}
