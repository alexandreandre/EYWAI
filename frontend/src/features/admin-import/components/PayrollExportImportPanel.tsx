import { useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  FileSpreadsheet,
  Loader2,
  Upload,
  Users,
} from 'lucide-react';
import { listDsnImportCompanies, type DsnImportCompany } from '@/api/dsnImport';
import {
  commitPayrollExport,
  parsePayrollExportFile,
  type CompanySetupStatus,
  type PayrollExportParseResponse,
  type PayrollExportRowPreview,
  type PayrollExportReviewStatus,
} from '@/api/adminImport';
import { useCompanySetupStatus } from '@/features/admin-import/hooks/useCompanySetupStatus';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';
import { EmployeeAssociateCombobox } from '@/components/schedules/assisted-fill/EmployeeAssociateCombobox';
import type { RosterEmployee } from '@/api/calendar';
import { getUserErrorMessage } from '@/lib/errorMessages';
import { PayrollExportFormatHelp } from '@/features/admin-import/components/PayrollExportFormatHelp';

type EditableRow = PayrollExportRowPreview & {
  manuallyConfirmed: boolean;
};

function groupCompanies(companies: DsnImportCompany[]) {
  const buckets = new Map<string, { groupName: string; companies: DsnImportCompany[] }>();
  companies.forEach((c) => {
    const key = c.group_id ?? '__none__';
    if (!buckets.has(key)) {
      buckets.set(key, { groupName: c.group_name ?? 'Sans groupe', companies: [] });
    }
    buckets.get(key)!.companies.push(c);
  });
  return Array.from(buckets.values()).sort((a, b) => a.groupName.localeCompare(b.groupName));
}

function companyCommandValue(c: DsnImportCompany): string {
  return [c.company_name, c.siret ?? '', c.siren ?? '', c.group_name ?? ''].join(' ').trim();
}

function statusBadge(status: PayrollExportReviewStatus) {
  if (status === 'ok') {
    return <Badge variant="secondary" className="bg-emerald-100 text-emerald-800">Prêt</Badge>;
  }
  if (status === 'warning') {
    return <Badge variant="secondary" className="bg-amber-100 text-amber-900">À vérifier</Badge>;
  }
  return <Badge variant="destructive">Bloquant</Badge>;
}

function paymentLabel(method?: unknown): string {
  const m = String(method ?? '').toLowerCase();
  if (m === 'cheque') return 'Chèque';
  if (m === 'especes') return 'Espèces';
  if (m === 'virement') return 'Virement';
  return '—';
}

function isSavableRow(row: EditableRow): boolean {
  if (!row.employee_id) return false;
  if (row.review_status === 'ok') return true;
  if (row.manuallyConfirmed && row.review_status === 'warning') return true;
  if (row.manuallyConfirmed && row.review_status === 'error' && row.employee_id) return true;
  return false;
}

export function PayrollExportImportPanel({
  fixedCompanyId,
  hideCompanySelector = false,
  embedded = false,
  showContext = false,
  setupStatus: setupStatusProp,
  onComplete,
  onCompanyChange,
}: {
  fixedCompanyId?: string;
  hideCompanySelector?: boolean;
  embedded?: boolean;
  /** Affiche l’état filiale + aide format (parcours guidé / onglet dédié). */
  showContext?: boolean;
  /** Statut partagé (parcours guidé) — évite une requête dupliquée. */
  setupStatus?: CompanySetupStatus;
  onComplete?: () => void;
  onCompanyChange?: (companyId: string) => void;
} = {}) {
  const { toast } = useToast();
  const [companyId, setCompanyId] = useState(fixedCompanyId ?? '');
  const [comboboxOpen, setComboboxOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [parseResult, setParseResult] = useState<PayrollExportParseResponse | null>(null);
  const [rows, setRows] = useState<EditableRow[]>([]);

  useEffect(() => {
    if (fixedCompanyId) setCompanyId(fixedCompanyId);
  }, [fixedCompanyId]);

  const { data: fetchedSetupStatus } = useCompanySetupStatus(companyId, {
    enabled: Boolean(companyId) && showContext && !setupStatusProp,
  });
  const setupStatus = setupStatusProp ?? fetchedSetupStatus;

  const { data: companies = [], isLoading: loadingCompanies } = useQuery({
    queryKey: ['dsn-import-companies'],
    queryFn: listDsnImportCompanies,
    staleTime: 60_000,
  });

  const selectedCompany = useMemo(
    () => companies.find((c) => c.id === companyId) ?? null,
    [companies, companyId],
  );

  const grouped = useMemo(() => groupCompanies(companies), [companies]);

  const roster: RosterEmployee[] = useMemo(() => {
    if (!parseResult?.roster?.length) return [];
    return parseResult.roster.map((e) => ({
      id: e.id,
      first_name: e.first_name,
      last_name: e.last_name,
      time_tracking_id: e.time_tracking_id ?? undefined,
    }));
  }, [parseResult?.roster]);

  const parseMutation = useMutation({
    mutationFn: async () => {
      if (!companyId || !selectedFile) {
        throw new Error('Sélectionnez une entreprise et un fichier.');
      }
      return parsePayrollExportFile(companyId, selectedFile);
    },
    onSuccess: (data) => {
      setParseResult(data);
      setRows(
        data.rows.map((row) => ({
          ...row,
          manuallyConfirmed: row.review_status === 'ok',
        })),
      );
      toast({
        title: 'Export analysé',
        description: `${data.summary.total} ligne(s) — ${data.summary.ready} prête(s), ${data.summary.warning} à vérifier.`,
      });
    },
    onError: (error) => {
      toast({
        title: 'Analyse impossible',
        description: getUserErrorMessage(error),
        variant: 'destructive',
      });
    },
  });

  const commitMutation = useMutation({
    mutationFn: async () => {
      if (!parseResult) throw new Error('Aucune analyse en cours.');
      const payload = rows
        .filter(isSavableRow)
        .map((row) => ({
          row_index: row.row_index,
          employee_id: row.employee_id as string,
          employee_patch: row.employee_patch,
          team_name: row.team_name,
          boeth: row.boeth,
          confirmed: true,
        }));
      if (payload.length === 0) {
        throw new Error('Aucune ligne validée à enregistrer.');
      }
      return commitPayrollExport({
        company_id: parseResult.company_id,
        create_teams_if_missing: true,
        rows: payload,
      });
    },
    onSuccess: (data) => {
      toast({
        title: 'Import salariés terminé',
        description: `${data.applied} fiche(s) enrichie(s)${data.skipped ? `, ${data.skipped} ignorée(s)` : ''}.`,
      });
      if (data.errors.length > 0) {
        toast({
          title: 'Avertissements',
          description: data.errors.slice(0, 3).join(' '),
          variant: 'destructive',
        });
      }
      setParseResult(null);
      setRows([]);
      setSelectedFile(null);
      onComplete?.();
    },
    onError: (error) => {
      toast({
        title: 'Enregistrement impossible',
        description: getUserErrorMessage(error),
        variant: 'destructive',
      });
    },
  });

  const handleAssociate = useCallback((rowIndex: number, employeeId: string, label: string) => {
    setRows((prev) =>
      prev.map((row) =>
        row.row_index === rowIndex
          ? {
              ...row,
              employee_id: employeeId,
              matched_name: label,
              match_method: 'none',
              match_confidence: 'high',
              review_status: row.warnings.length > 0 ? 'warning' : 'ok',
              manuallyConfirmed: true,
            }
          : row,
      ),
    );
  }, []);

  const savableCount = rows.filter(isSavableRow).length;

  const showRibColumn = useMemo(
    () =>
      rows.some((row) => {
        const cols = row.preview_columns ?? {};
        return Boolean(cols.iban_masked ?? cols.rib_raw);
      }),
    [rows],
  );

  const selectAllReady = () => {
    setRows((prev) =>
      prev.map((row) => ({
        ...row,
        manuallyConfirmed: row.review_status === 'ok' || row.review_status === 'warning',
      })),
    );
  };

  const inner = (
    <div className="space-y-4">
        {showContext && setupStatus && setupStatus.blocks.employees.total > 0 ? (
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-md border bg-background px-2 py-1 text-muted-foreground">
              {setupStatus.blocks.employees.profile_complete_pct}% fiches complètes
            </span>
            {setupStatus.blocks.employees.missing_rib_count > 0 ? (
              <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-amber-900">
                {setupStatus.blocks.employees.missing_rib_count} RIB à compléter
              </span>
            ) : (
              <span className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-emerald-800">
                RIB à jour
              </span>
            )}
          </div>
        ) : null}

        {showContext ? <PayrollExportFormatHelp /> : null}

        <div className="flex flex-wrap items-end gap-3">
          {!hideCompanySelector ? (
          <div className="min-w-[280px] flex-1">
            <p className="mb-1 text-sm font-medium">Entreprise</p>
            <Popover open={comboboxOpen} onOpenChange={setComboboxOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  className="w-full justify-between font-normal"
                  disabled={loadingCompanies}
                >
                  {selectedCompany?.company_name ?? 'Choisir une entreprise…'}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[400px] p-0" align="start">
                <Command>
                  <CommandInput placeholder="Rechercher…" />
                  <CommandList>
                    <CommandEmpty>Aucune entreprise.</CommandEmpty>
                    {grouped.map((group) => (
                      <CommandGroup key={group.groupName} heading={group.groupName}>
                        {group.companies.map((c) => (
                          <CommandItem
                            key={c.id}
                            value={companyCommandValue(c)}
                            onSelect={() => {
                              setCompanyId(c.id);
                              onCompanyChange?.(c.id);
                              setComboboxOpen(false);
                              setParseResult(null);
                              setRows([]);
                            }}
                          >
                            <Check
                              className={cn(
                                'mr-2 h-4 w-4',
                                companyId === c.id ? 'opacity-100' : 'opacity-0',
                              )}
                            />
                            {c.company_name}
                            {c.siret ? ` (${c.siret})` : ''}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    ))}
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          </div>
          ) : null}

          <div>
            <p className="mb-1 text-sm font-medium">Fichier</p>
            <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-muted/50">
              <Upload className="h-4 w-4" />
              {selectedFile?.name ?? 'Choisir Excel / CSV'}
              <input
                type="file"
                accept=".xlsx,.xls,.csv"
                className="hidden"
                onChange={(e) => {
                  setSelectedFile(e.target.files?.[0] ?? null);
                  setParseResult(null);
                  setRows([]);
                }}
              />
            </label>
          </div>

          <Button
            type="button"
            disabled={!companyId || !selectedFile || parseMutation.isPending}
            onClick={() => parseMutation.mutate()}
          >
            {parseMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <FileSpreadsheet className="mr-2 h-4 w-4" />
            )}
            Analyser
          </Button>
        </div>

        {parseResult && (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
              <span>
                {parseResult.summary.total} ligne(s) — {parseResult.summary.ready} prête(s),{' '}
                {parseResult.summary.warning} à vérifier, {parseResult.summary.error} bloquante(s)
                {parseResult.summary.unmatched
                  ? `, ${parseResult.summary.unmatched} non rapprochée(s)`
                  : ''}
                {parseResult.summary.rib_rows
                  ? ` · ${parseResult.summary.rib_valid_rows ?? 0}/${parseResult.summary.rib_rows} RIB valide(s)`
                  : ''}
              </span>
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" onClick={selectAllReady}>
                  Sélectionner les lignes prêtes
                </Button>
                <Button
                  type="button"
                  size="sm"
                  disabled={savableCount === 0 || commitMutation.isPending}
                  onClick={() => commitMutation.mutate()}
                >
                  {commitMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                  )}
                  Enregistrer ({savableCount})
                </Button>
              </div>
            </div>

            <div className="overflow-x-auto rounded-md border">
              <table className="w-max min-w-full caption-bottom text-sm">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10" />
                    <TableHead className="min-w-[11rem]">Identité</TableHead>
                    <TableHead className="min-w-[10rem]">Match</TableHead>
                    <TableHead className="min-w-[9rem]">Email</TableHead>
                    <TableHead className="min-w-[7rem]">Tél</TableHead>
                    {showRibColumn ? (
                      <TableHead className="min-w-[8rem] whitespace-nowrap">RIB</TableHead>
                    ) : null}
                    <TableHead className="min-w-[5.5rem] whitespace-nowrap">Paiement</TableHead>
                    <TableHead className="min-w-[4.5rem]">Équipe</TableHead>
                    <TableHead className="min-w-[5rem] whitespace-nowrap">TP</TableHead>
                    <TableHead className="min-w-[12rem]">Statut</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => {
                    const cols = row.preview_columns ?? {};
                    return (
                      <TableRow key={row.row_index}>
                        <TableCell>
                          <Checkbox
                            checked={isSavableRow(row)}
                            disabled={!row.employee_id}
                            onCheckedChange={(checked) => {
                              setRows((prev) =>
                                prev.map((r) =>
                                  r.row_index === row.row_index
                                    ? { ...r, manuallyConfirmed: Boolean(checked) }
                                    : r,
                                ),
                              );
                            }}
                          />
                        </TableCell>
                        <TableCell className="min-w-[11rem]">
                          <div className="font-medium">{row.raw_identity}</div>
                          {row.nir && (
                            <div className="text-xs text-muted-foreground">NIR {row.nir}</div>
                          )}
                        </TableCell>
                        <TableCell>
                          {row.employee_id ? (
                            <span>{row.matched_name}</span>
                          ) : (
                            <EmployeeAssociateCombobox
                              roster={roster}
                              value={null}
                              onSelect={(id, label) =>
                                handleAssociate(row.row_index, id, label)
                              }
                            />
                          )}
                        </TableCell>
                        <TableCell className="text-sm">{String(cols.email ?? row.email ?? '—')}</TableCell>
                        <TableCell className="text-sm">{String(cols.phone ?? '—')}</TableCell>
                        {showRibColumn ? (
                          <TableCell className="text-sm font-mono text-xs">
                            {String(cols.iban_masked ?? '—')}
                          </TableCell>
                        ) : null}
                        <TableCell className="text-sm">
                          {paymentLabel(cols.payment_method ?? row.employee_patch?.salary_payment_method)}
                        </TableCell>
                        <TableCell className="text-sm">{String(row.team_name ?? cols.team_name ?? '—')}</TableCell>
                        <TableCell className="text-sm">
                          {cols.is_temps_partiel
                            ? `${cols.duree_hebdomadaire ?? '?'} h/sem`
                            : '—'}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-1">
                            {statusBadge(row.review_status)}
                            {row.warnings.slice(0, 2).map((w) => (
                              <span
                                key={w}
                                className="flex items-start gap-1 text-xs text-amber-800"
                              >
                                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                                {w}
                              </span>
                            ))}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </table>
            </div>
          </>
        )}
    </div>
  );

  if (embedded) return inner;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Users className="h-5 w-5" />
          Import export paie salariés
        </CardTitle>
        <CardDescription>
          Complète les fiches importées via DSN : contacts, RIB, équipes MOD/MOI, temps partiel,
          BOETH et moyen de paiement. Format Excel/CSV Quadra ou Cegid.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <PayrollExportFormatHelp />
        {inner}
      </CardContent>
    </Card>
  );
}
