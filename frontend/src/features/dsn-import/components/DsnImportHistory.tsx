import { useQuery } from '@tanstack/react-query';
import { History, Loader2 } from 'lucide-react';
import { listDsnImportBatches, type DsnImportBatchSummary } from '@/api/dsnImport';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const MONTHS_FR = [
  'janv.',
  'févr.',
  'mars',
  'avr.',
  'mai',
  'juin',
  'juil.',
  'août',
  'sept.',
  'oct.',
  'nov.',
  'déc.',
];

function formatPeriod(min?: string | null, max?: string | null): string {
  if (!min) return '—';
  const fmt = (iso: string) => {
    const [y, m] = iso.split('-');
    const mi = parseInt(m, 10);
    if (!y || !mi || mi < 1 || mi > 12) return iso;
    return `${MONTHS_FR[mi - 1]} ${y}`;
  };
  if (!max || min === max) return fmt(min);
  return `${fmt(min)} → ${fmt(max)}`;
}

const STATUS_LABELS: Record<string, string> = {
  previewed: 'Analysé',
  committed: 'Importé',
  failed: 'Échec',
  parsed: 'En cours',
};

function statusVariant(status: string): 'secondary' | 'outline' | 'destructive' {
  if (status === 'committed') return 'secondary';
  if (status === 'failed') return 'destructive';
  return 'outline';
}

export function DsnImportHistory() {
  const { data, isLoading } = useQuery({
    queryKey: ['dsn-import-batches'],
    queryFn: () => listDsnImportBatches(20),
  });

  const batches = data ?? [];

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <History className="h-4 w-4 text-muted-foreground" />
          Imports récents
        </CardTitle>
        <CardDescription>Traçabilité des dépôts DSN (lecture seule).</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Chargement…
          </div>
        ) : batches.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">Aucun import enregistré.</p>
        ) : (
          <div className="max-h-[320px] overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>SIREN</TableHead>
                  <TableHead>Période</TableHead>
                  <TableHead>Fichiers</TableHead>
                  <TableHead>Statut</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {batches.map((b: DsnImportBatchSummary) => (
                  <TableRow key={b.id}>
                    <TableCell className="text-xs text-muted-foreground">
                      {b.created_at
                        ? new Date(b.created_at).toLocaleString('fr-FR', {
                            dateStyle: 'short',
                            timeStyle: 'short',
                          })
                        : '—'}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{b.siren ?? '—'}</TableCell>
                    <TableCell className="text-sm">
                      {formatPeriod(b.period_min, b.period_max)}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {(b.file_names ?? []).length || (b.summary?.file_count as number) || 0}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(b.status)}>
                        {STATUS_LABELS[b.status] ?? b.status}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
