import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { History, Loader2, PlayCircle } from 'lucide-react';
import {
  listDsnImportBatches,
  listDsnImportCompanies,
  type DsnImportBatchSummary,
  type DsnImportMode,
} from '@/api/dsnImport';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';

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
  parsed: 'Analyse en cours',
  previewed: 'Non importé',
  committing: 'Import en cours',
  committed: 'Importé',
  failed: 'Échec',
};

const STATUS_TITLES: Record<string, string> = {
  previewed: 'Fichier analysé — aucune donnée n’a été créée dans EYWAI',
  committed: 'Données appliquées dans EYWAI (groupe, établissement, salariés, cumuls)',
  committing: 'Import en cours d’application',
  parsed: 'Parsing et validation en cours',
  failed: 'L’import a échoué',
};

function statusVariant(
  status: string,
): 'secondary' | 'outline' | 'destructive' | 'success' | 'warning' {
  if (status === 'committed') return 'success';
  if (status === 'failed') return 'destructive';
  if (status === 'committing' || status === 'parsed') return 'warning';
  return 'outline';
}

function companyLabel(
  batch: DsnImportBatchSummary,
  companyNames: Map<string, string>,
): string {
  const targetId = batch.summary?.target_company_id as string | undefined;
  if (targetId && companyNames.has(targetId)) {
    return companyNames.get(targetId)!;
  }
  const report = batch.summary?.commit_report as Record<string, unknown> | undefined;
  const committedId = report?.target_company_id as string | undefined;
  if (committedId && companyNames.has(committedId)) {
    return companyNames.get(committedId)!;
  }
  return batch.siren ?? '—';
}

function importModeLabel(batch: DsnImportBatchSummary): string {
  const mode = (batch.summary?.import_mode as DsnImportMode | undefined) ?? 'onboarding';
  return mode === 'monthly' ? 'Mensuel' : 'Onboarding';
}

const STATUS_ORDER: Record<string, number> = {
  committed: 0,
  failed: 1,
  committing: 2,
  previewed: 3,
  parsed: 4,
};

function sortBatches(list: DsnImportBatchSummary[]): DsnImportBatchSummary[] {
  return [...list].sort((a, b) => {
    const rankA = STATUS_ORDER[a.status] ?? 99;
    const rankB = STATUS_ORDER[b.status] ?? 99;
    if (rankA !== rankB) return rankA - rankB;
    const dateA = a.created_at ? Date.parse(a.created_at) : 0;
    const dateB = b.created_at ? Date.parse(b.created_at) : 0;
    return dateB - dateA;
  });
}

type Props = {
  onResume?: (batch: DsnImportBatchSummary) => void;
};

export function DsnImportHistory({ onResume }: Props) {
  const [statusFilter, setStatusFilter] = useState<string>('committed');
  const [companyFilter, setCompanyFilter] = useState<string>('all');
  const [search, setSearch] = useState('');

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['dsn-import-batches'],
    queryFn: () => listDsnImportBatches(100),
    refetchOnMount: 'always',
  });

  const { data: companies } = useQuery({
    queryKey: ['dsn-import-companies'],
    queryFn: listDsnImportCompanies,
    staleTime: 60_000,
  });

  const companyNames = useMemo(() => {
    const map = new Map<string, string>();
    (companies ?? []).forEach((c) => map.set(c.id, c.company_name));
    return map;
  }, [companies]);

  const batches = useMemo(() => {
    let list = sortBatches(data ?? []);
    if (statusFilter !== 'all') {
      list = list.filter((b) => b.status === statusFilter);
    }
    if (companyFilter !== 'all') {
      list = list.filter((b) => {
        const id =
          (b.summary?.target_company_id as string | undefined)
          ?? ((b.summary?.commit_report as Record<string, unknown> | undefined)?.target_company_id as
              | string
              | undefined);
        return id === companyFilter;
      });
    }
    const q = search.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (b) =>
          (b.siren ?? '').includes(q)
          || (b.file_names ?? []).some((f) => f.toLowerCase().includes(q))
          || companyLabel(b, companyNames).toLowerCase().includes(q),
      );
    }
    return list;
  }, [data, statusFilter, companyFilter, search, companyNames]);

  const committedCount = useMemo(
    () => (data ?? []).filter((b) => b.status === 'committed').length,
    [data],
  );

  const handleRowClick = (batch: DsnImportBatchSummary) => {
    if (batch.status === 'previewed' || batch.status === 'committing') {
      onResume?.(batch);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <History className="h-4 w-4 text-muted-foreground" />
          Historique DSN
        </CardTitle>
        <CardDescription>
          {committedCount > 0
            ? `${committedCount} import${committedCount > 1 ? 's' : ''} réussi${committedCount > 1 ? 's' : ''}. Filtrez par statut ou entreprise.`
            : 'Filtrez par entreprise ou statut. Cliquez une ligne « Non importé » pour reprendre la prévisualisation.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap gap-2">
          <Input
            placeholder="Rechercher SIREN, fichier, entreprise…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 max-w-xs"
          />
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="h-9 w-[160px]">
              <SelectValue placeholder="Statut" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="committed">Importés</SelectItem>
              <SelectItem value="all">Tous statuts</SelectItem>
              <SelectItem value="previewed">Non importé</SelectItem>
              <SelectItem value="committing">En cours</SelectItem>
              <SelectItem value="committed">Importé</SelectItem>
              <SelectItem value="failed">Échec</SelectItem>
            </SelectContent>
          </Select>
          <Select value={companyFilter} onValueChange={setCompanyFilter}>
            <SelectTrigger className="h-9 w-[200px]">
              <SelectValue placeholder="Entreprise" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Toutes entreprises</SelectItem>
              {(companies ?? []).map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.company_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Chargement…
          </div>
        ) : isError ? (
          <div className="space-y-2 py-4">
            <p className="text-sm text-destructive">Impossible de charger l&apos;historique.</p>
            <Button type="button" variant="outline" size="sm" onClick={() => void refetch()}>
              Réessayer
            </Button>
          </div>
        ) : batches.length === 0 ? (
          <p className="py-4 text-sm text-muted-foreground">Aucun import correspondant.</p>
        ) : (
          <div className="max-h-[360px] overflow-y-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Entreprise</TableHead>
                  <TableHead>Période</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Salariés</TableHead>
                  <TableHead>Statut</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {batches.map((b) => {
                  const resumable = b.status === 'previewed' || b.status === 'committing';
                  const stats = (b.summary?.commit_report as Record<string, unknown> | undefined)
                    ?.stats as Record<string, number> | undefined;
                  const employeeCount =
                    (b.summary?.employee_count as number | undefined)
                    ?? stats?.created
                    ?? '—';
                  return (
                    <TableRow
                      key={b.id}
                      className={cn(resumable && onResume && 'cursor-pointer hover:bg-muted/40')}
                      onClick={() => handleRowClick(b)}
                    >
                      <TableCell className="text-xs text-muted-foreground">
                        {b.created_at
                          ? new Date(b.created_at).toLocaleString('fr-FR', {
                              dateStyle: 'short',
                              timeStyle: 'short',
                            })
                          : '—'}
                      </TableCell>
                      <TableCell className="max-w-[140px] truncate text-sm">
                        {companyLabel(b, companyNames)}
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatPeriod(b.period_min, b.period_max)}
                      </TableCell>
                      <TableCell className="text-xs">{importModeLabel(b)}</TableCell>
                      <TableCell className="text-xs tabular-nums">{employeeCount}</TableCell>
                      <TableCell>
                        <Badge
                          variant={statusVariant(b.status)}
                          title={STATUS_TITLES[b.status] ?? undefined}
                          className="gap-1"
                        >
                          {resumable && onResume ? (
                            <PlayCircle className="h-3 w-3" />
                          ) : null}
                          {STATUS_LABELS[b.status] ?? b.status}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
