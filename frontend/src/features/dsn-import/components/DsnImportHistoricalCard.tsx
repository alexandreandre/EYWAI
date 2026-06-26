import type { DsnImportItemPreview } from '@/api/dsnImport';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

export function DsnImportHistoricalCard({ items }: { items: DsnImportItemPreview[] }) {
  const absences = items.filter((it) => it.item_type === 'absence');
  const exits = items.filter((it) => it.item_type === 'exit');

  if (absences.length === 0 && exits.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Absences et sorties historiques</CardTitle>
        <CardDescription>
          Données issues des blocs G00.41, G00.60 et G00.62 — créées en statut validé / archivé si
          les dates sont passées.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {exits.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Sortie</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Dernier jour</TableHead>
                <TableHead>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {exits.map((it, index) => (
                <TableRow key={`exit:${it.source_ref}:${index}`}>
                  <TableCell>{it.label}</TableCell>
                  <TableCell>{String(it.preview_columns?.exit_type ?? '—')}</TableCell>
                  <TableCell>{String(it.preview_columns?.last_working_day ?? '—')}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{it.action}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
        {absences.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Absence</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Période</TableHead>
                <TableHead>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {absences.map((it, index) => (
                <TableRow key={`abs:${it.source_ref}:${index}`}>
                  <TableCell>{it.label}</TableCell>
                  <TableCell>{String(it.preview_columns?.absence_type ?? '—')}</TableCell>
                  <TableCell>
                    {String(it.preview_columns?.date_debut ?? '—')} →{' '}
                    {String(it.preview_columns?.date_fin ?? '—')}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{it.action}</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

export function DsnImportCommitStatsCard({
  stats,
}: {
  stats?: Record<string, number> | null;
}) {
  if (!stats) return null;
  const rows = [
    { label: 'Champs paie appliqués', value: stats.payroll_fields_applied },
    { label: 'Sorties créées', value: stats.exits_created },
    { label: 'Absences créées', value: stats.absences_created },
  ].filter((r) => r.value);

  if (rows.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Enrichissements DSN</CardTitle>
      </CardHeader>
      <CardContent>
        <ul className="space-y-1 text-sm">
          {rows.map((r) => (
            <li key={r.label} className="flex justify-between gap-4">
              <span className="text-muted-foreground">{r.label}</span>
              <span className="font-semibold tabular-nums">{r.value}</span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
