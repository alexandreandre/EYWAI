import { RefreshCw } from 'lucide-react';
import type { DsnCoverage } from '@/api/dsnImport';
import {
  DsnCoverageTimeline,
  dsnStatusLabel,
  dsnStatusVariant,
} from '@/features/dsn-import/components/DsnCoverageTimeline';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export function CompanyDsnCoverageBand({
  coverage,
}: {
  coverage: DsnCoverage;
}): JSX.Element | null {
  if (!coverage) return null;

  const isNative = coverage.dsn_sync_mode === 'native';

  return (
    <Card className="border-muted/60">
      <CardHeader className="pb-2">
        <CardTitle className="flex flex-wrap items-center gap-2 text-base">
          <RefreshCw className="h-4 w-4 text-muted-foreground" />
          Couverture DSN
          <Badge variant={dsnStatusVariant(coverage.status)}>{dsnStatusLabel(coverage.status)}</Badge>
        </CardTitle>
        <CardDescription>
          {isNative
            ? 'Les cumuls sont maintenus par la paie EYWAI — import DSN optionnel.'
            : 'Suivi des imports mensuels depuis votre logiciel de paie externe.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <DsnCoverageTimeline timeline={coverage.timeline} compact />
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {coverage.last_period ? (
            <span>Dernier mois importé : {coverage.last_period}</span>
          ) : null}
          {coverage.last_import_at ? (
            <span>
              Dernier import :{' '}
              {new Date(coverage.last_import_at).toLocaleDateString('fr-FR', {
                day: 'numeric',
                month: 'short',
                year: 'numeric',
              })}
            </span>
          ) : null}
          {coverage.gaps.length > 0 ? (
            <span className="text-amber-800">Mois manquants : {coverage.gaps.join(', ')}</span>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
