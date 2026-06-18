import { useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  closeIjssPeriod,
  commitIjssImportBatch,
  downloadIjssAuditExport,
  getIjssPeriodDashboard,
  IJSS_LINE_STATUS_LABELS,
  importBankRecap,
  importCpamDecompte,
  justifyIjssVariance,
  syncCpamDecomptes,
  syncIjssExpected,
  type IjssDashboardRow,
  type IjssLineStatus,
} from '@/api/ijssTracking';
import { RhPageHeader } from '@/components/layout';
import { PageFetchIndicator } from '@/components/skeletons/PageFetchIndicator';
import { TableSkeleton } from '@/components/skeletons/TableSkeleton';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { useToast } from '@/hooks/use-toast';
import { downloadBlob } from '@/lib/downloadBlob';
import { cn } from '@/lib/utils';
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Download,
  RefreshCw,
  Upload,
} from 'lucide-react';

const MONTHS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
];

function eur(n: number) {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(n);
}

function statusVariant(status: IjssLineStatus) {
  if (status === 'ok' || status === 'justified') return 'default';
  if (status === 'variance' || status === 'partial') return 'destructive';
  return 'secondary';
}

function Kpi({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string;
  value: number;
  icon: typeof CheckCircle2;
  tone?: 'ok' | 'warn' | 'muted';
}) {
  return (
    <div
      className={cn(
        'flex items-center gap-3 rounded-lg border p-4',
        tone === 'ok' && 'border-emerald-500/30 bg-emerald-50/50 dark:bg-emerald-950/20',
        tone === 'warn' && 'border-amber-500/30 bg-amber-50/50 dark:bg-amber-950/20',
      )}
    >
      <Icon className="h-5 w-5 shrink-0 text-muted-foreground" />
      <div>
        <p className="text-sm text-muted-foreground">{label}</p>
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
      </div>
    </div>
  );
}

function DetailPanel({
  row,
  open,
  onClose,
  onJustified,
}: {
  row: IjssDashboardRow | null;
  open: boolean;
  onClose: () => void;
  onJustified: () => void;
}) {
  const { toast } = useToast();
  const [note, setNote] = useState('');
  const justifyMut = useMutation({
    mutationFn: () => justifyIjssVariance(row!.expected_line_id!, note),
    onSuccess: () => {
      toast({ title: 'Écart justifié' });
      setNote('');
      onJustified();
      onClose();
    },
    onError: (e: Error) => toast({ variant: 'destructive', title: e.message }),
  });

  if (!row) return null;

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="overflow-y-auto sm:max-w-md">
        <SheetHeader>
          <SheetTitle>{row.employee_name}</SheetTitle>
          <SheetDescription>Rapprochement IJSS CPAM</SheetDescription>
        </SheetHeader>
        <dl className="mt-6 space-y-3 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">IJSS théorique</dt>
            <dd className="font-medium tabular-nums">{eur(row.ijss_theorique)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">IJSS bulletin (subrogées)</dt>
            <dd className="font-medium tabular-nums">{eur(row.ijss_subrogees_bulletin)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Décompte CPAM</dt>
            <dd className="font-medium tabular-nums">{eur(row.received_cpam)}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted-foreground">Virement banque</dt>
            <dd className="font-medium tabular-nums">{eur(row.received_bank)}</dd>
          </div>
        </dl>
        {row.line_status === 'variance' && row.expected_line_id && (
          <div className="mt-6 space-y-2">
            <p className="text-sm font-medium">Justifier l&apos;écart</p>
            <Textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Ex. : décalage carence CPAM, arrondi…"
              rows={3}
            />
            <Button
              disabled={note.trim().length < 3 || justifyMut.isPending}
              onClick={() => justifyMut.mutate()}
            >
              Enregistrer la justification
            </Button>
          </div>
        )}
        {row.absence_request_id && (
          <Button variant="link" className="mt-4 px-0" asChild>
            <Link to="/leaves">Voir l&apos;arrêt dans Absences</Link>
          </Button>
        )}
      </SheetContent>
    </Sheet>
  );
}

export default function SuiviIJSSPage() {
  const companyId = useActiveCompanyId();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [selectedRow, setSelectedRow] = useState<IjssDashboardRow | null>(null);
  const bankInputRef = useRef<HTMLInputElement>(null);
  const cpamInputRef = useRef<HTMLInputElement>(null);

  const dashboardQuery = useQuery({
    queryKey: ['ijss-dashboard', companyId, year, month],
    queryFn: () => getIjssPeriodDashboard(year, month),
    enabled: Boolean(companyId),
  });

  const periodId = dashboardQuery.data?.period?.id;

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['ijss-dashboard', companyId, year, month] });

  const syncMut = useMutation({
    mutationFn: () => syncIjssExpected(periodId!),
    onSuccess: (res) => {
      toast({ title: `${res.synced_count} bulletin(s) synchronisé(s)` });
      invalidate();
    },
    onError: (e: Error) => toast({ variant: 'destructive', title: e.message }),
  });

  const cpamSyncMut = useMutation({
    mutationFn: () => syncCpamDecomptes(periodId!),
    onSuccess: (res) => {
      if (res.success) {
        toast({ title: res.message });
      } else {
        toast({
          variant: 'destructive',
          title: 'Sync Net-Entreprises indisponible',
          description: res.message,
        });
      }
      invalidate();
    },
  });

  const closeMut = useMutation({
    mutationFn: () => closeIjssPeriod(periodId!),
    onSuccess: () => {
      toast({ title: 'Période clôturée' });
      invalidate();
    },
    onError: (e: Error) => toast({ variant: 'destructive', title: e.message }),
  });

  const importMut = useMutation({
    mutationFn: async ({ file, kind }: { file: File; kind: 'bank' | 'cpam' }) => {
      const preview =
        kind === 'bank'
          ? await importBankRecap(periodId!, file)
          : await importCpamDecompte(periodId!, file);
      await commitIjssImportBatch(preview.batch_id);
      return preview;
    },
    onSuccess: (res) => {
      toast({
        title: 'Import enregistré',
        description: `${res.preview?.line_count ?? 0} ligne(s) importée(s)`,
      });
      invalidate();
    },
    onError: (e: Error) => toast({ variant: 'destructive', title: e.message }),
  });

  const exportMut = useMutation({
    mutationFn: () => downloadIjssAuditExport(periodId!),
    onSuccess: (blob) => {
      downloadBlob(blob, `suivi_ijss_${year}_${String(month).padStart(2, '0')}.xlsx`);
    },
  });

  const rows = dashboardQuery.data?.rows ?? [];
  const summary = dashboardQuery.data?.summary ?? { ok: 0, variance: 0, pending: 0 };
  const periodClosed = dashboardQuery.data?.period?.status === 'closed';

  const yearOptions = useMemo(
    () => [now.getFullYear() - 1, now.getFullYear(), now.getFullYear() + 1],
    [now],
  );

  return (
    <div className="space-y-6">
      <RhPageHeader
        title="Suivi IJSS / CPAM"
        description="Rapprochez les IJSS théoriques (paie), les décomptes CPAM et les virements reçus sur le compte entreprise."
      />

      <div className="flex flex-wrap items-end gap-3">
        <div>
          <p className="mb-1 text-xs text-muted-foreground">Année</p>
          <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
            <SelectTrigger className="w-[100px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {yearOptions.map((y) => (
                <SelectItem key={y} value={String(y)}>
                  {y}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div>
          <p className="mb-1 text-xs text-muted-foreground">Mois</p>
          <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
            <SelectTrigger className="w-[160px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MONTHS.map((label, i) => (
                <SelectItem key={label} value={String(i + 1)}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-wrap gap-2 ml-auto">
          <Button
            variant="outline"
            size="sm"
            disabled={!periodId || syncMut.isPending || periodClosed}
            onClick={() => syncMut.mutate()}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Sync bulletins
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!periodId || cpamSyncMut.isPending || periodClosed}
            onClick={() => cpamSyncMut.mutate()}
          >
            Sync Net-Entreprises
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!periodId || importMut.isPending || periodClosed}
            onClick={() => bankInputRef.current?.click()}
          >
            <Upload className="mr-2 h-4 w-4" />
            Import virements
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!periodId || importMut.isPending || periodClosed}
            onClick={() => cpamInputRef.current?.click()}
          >
            <Upload className="mr-2 h-4 w-4" />
            Import décompte
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!periodId || exportMut.isPending}
            onClick={() => exportMut.mutate()}
          >
            <Download className="mr-2 h-4 w-4" />
            Export audit
          </Button>
          <Button
            size="sm"
            disabled={!periodId || closeMut.isPending || periodClosed}
            onClick={() => closeMut.mutate()}
          >
            Clôturer le mois
          </Button>
        </div>
      </div>

      <input
        ref={bankInputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) importMut.mutate({ file: f, kind: 'bank' });
          e.target.value = '';
        }}
      />
      <input
        ref={cpamInputRef}
        type="file"
        accept=".csv,.xlsx,.xls"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) importMut.mutate({ file: f, kind: 'cpam' });
          e.target.value = '';
        }}
      />

      <PageFetchIndicator show={dashboardQuery.isFetching && !dashboardQuery.isLoading} />

      <div className="grid gap-4 sm:grid-cols-3">
        <Kpi label="Arrêts OK" value={summary.ok} icon={CheckCircle2} tone="ok" />
        <Kpi label="Écarts à traiter" value={summary.variance} icon={AlertCircle} tone="warn" />
        <Kpi label="En attente CPAM" value={summary.pending} icon={Clock} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            {MONTHS[month - 1]} {year}
            {periodClosed && (
              <Badge variant="outline" className="ml-2">
                Clôturé
              </Badge>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {dashboardQuery.isLoading ? (
            <TableSkeleton rows={6} columns={6} />
          ) : rows.length === 0 ? (
            <p className="text-sm text-muted-foreground py-8 text-center">
              Aucune ligne IJSS pour ce mois. Générez les bulletins puis cliquez sur « Sync bulletins ».
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead className="text-right">Théorique</TableHead>
                  <TableHead className="text-right">Décompte CPAM</TableHead>
                  <TableHead className="text-right">Virement</TableHead>
                  <TableHead>Statut</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow
                    key={row.expected_line_id ?? row.employee_id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => setSelectedRow(row)}
                  >
                    <TableCell className="font-medium">{row.employee_name}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {eur(row.ijss_subrogees_bulletin || row.ijss_theorique)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{eur(row.received_cpam)}</TableCell>
                    <TableCell className="text-right tabular-nums">{eur(row.received_bank)}</TableCell>
                    <TableCell>
                      <Badge variant={statusVariant(row.line_status)}>
                        {IJSS_LINE_STATUS_LABELS[row.line_status]}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card className="border-dashed">
        <CardContent className="pt-6 text-sm text-muted-foreground space-y-2">
          <p className="font-medium text-foreground">Process en 4 étapes</p>
          <ol className="list-decimal list-inside space-y-1">
            <li>Valider les arrêts et générer les bulletins de paie.</li>
            <li>Synchroniser les montants théoriques (« Sync bulletins »).</li>
            <li>Importer le récap virements CPAM (compta) et/ou synchroniser les décomptes Net-Entreprises.</li>
            <li>Contrôler les écarts, justifier si besoin, puis clôturer le mois.</li>
          </ol>
        </CardContent>
      </Card>

      <DetailPanel
        row={selectedRow}
        open={Boolean(selectedRow)}
        onClose={() => setSelectedRow(null)}
        onJustified={invalidate}
      />
    </div>
  );
}
