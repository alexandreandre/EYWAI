import { useCallback, useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Eye,
  FileText,
  Loader2,
  Upload,
  UserCheck,
} from 'lucide-react';
import {
  commitCpImport,
  parseCpImportFiles,
  type CpImportParseResponse,
  type CpImportRowPreview,
  type CpReviewStatus,
} from '@/api/adminImport';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Table,
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
import { CpImportBulletinPreviewDialog } from '@/features/admin-import/components/CpImportBulletinPreviewDialog';
import { useCompanySetupStatus } from '@/features/admin-import/hooks/useCompanySetupStatus';

const MAX_FILES = 1000;
const PAGE_SIZE = 50;

type BulletinPreviewState = {
  sourceFile: string;
  pageIndex: number;
  employeeLabel: string;
  periodLabel?: string;
} | null;

type EditableRow = CpImportRowPreview & {
  manuallyConfirmed: boolean;
};

type StatusFilter = 'all' | CpReviewStatus;

function statusBadge(status: CpReviewStatus) {
  if (status === 'ok') {
    return <Badge variant="secondary" className="bg-emerald-100 text-emerald-800">Prêt</Badge>;
  }
  if (status === 'warning') {
    return <Badge variant="secondary" className="bg-amber-100 text-amber-900">À vérifier</Badge>;
  }
  return <Badge variant="destructive">Bloquant</Badge>;
}

function formatSolde(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return `${value.toFixed(2)} j`;
}

function formatDelta(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  if (value === 0) return '0';
  return value > 0 ? `+${value.toFixed(2)}` : value.toFixed(2);
}

function isSavableRow(row: EditableRow, fixedCompanyId?: string): boolean {
  if (!row.employee_id || !row.company_id) return false;
  if (fixedCompanyId && row.company_id !== fixedCompanyId) return false;
  if (row.review_status === 'ok') return true;
  if (row.manuallyConfirmed && row.review_status === 'warning') return true;
  if (row.manuallyConfirmed && row.review_status === 'error' && row.employee_id) return true;
  return false;
}

const COMPANY_MISMATCH_WARNING = 'Entreprise du bulletin différente de la filiale ciblée';

function applyCompanyScope(
  row: CpImportRowPreview,
  fixedCompanyId: string | undefined,
  scopedCompanyName: string | undefined,
): EditableRow {
  const base: EditableRow = {
    ...row,
    manuallyConfirmed: row.review_status === 'ok',
  };
  if (!fixedCompanyId || !row.company_id || row.company_id === fixedCompanyId) {
    return base;
  }
  const label = row.company_name ?? 'autre entreprise';
  const expected = scopedCompanyName ?? 'la filiale sélectionnée';
  const warning = `${COMPANY_MISMATCH_WARNING} (${label}, attendu : ${expected})`;
  return {
    ...base,
    manuallyConfirmed: false,
    review_status: 'error',
    warnings: base.warnings.includes(warning) ? base.warnings : [...base.warnings, warning],
  };
}

export function CpImportPanel({
  embedded = false,
  fixedCompanyId,
  fixedCompanyName,
  onComplete,
}: {
  embedded?: boolean;
  /** Filiale déjà ciblée (parcours guidé / hub) — masque le nom répété et contrôle les bulletins. */
  fixedCompanyId?: string;
  fixedCompanyName?: string;
  onComplete?: () => void;
} = {}) {
  const { toast } = useToast();
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [parseResult, setParseResult] = useState<CpImportParseResponse | null>(null);
  const [rows, setRows] = useState<EditableRow[]>([]);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [page, setPage] = useState(0);
  const [bulletinPreview, setBulletinPreview] = useState<BulletinPreviewState>(null);

  const { data: scopedCompanyStatus } = useCompanySetupStatus(fixedCompanyId ?? '', {
    enabled: Boolean(fixedCompanyId) && !fixedCompanyName,
  });

  const scopedCompanyName = fixedCompanyName ?? scopedCompanyStatus?.company_name;
  const companyScoped = Boolean(fixedCompanyId);

  const fileByName = useMemo(() => {
    const map = new Map<string, File>();
    for (const file of selectedFiles) {
      map.set(file.name, file);
    }
    return map;
  }, [selectedFiles]);

  const previewFile = bulletinPreview ? fileByName.get(bulletinPreview.sourceFile) : null;

  const parseMutation = useMutation({
    mutationFn: () => parseCpImportFiles(selectedFiles),
    onSuccess: (data) => {
      setParseResult(data);
      const scopedRows = data.rows.map((row) =>
        applyCompanyScope(row, fixedCompanyId, scopedCompanyName),
      );
      setRows(scopedRows);
      setPage(0);
      const mismatchCount = fixedCompanyId
        ? scopedRows.filter((r) => r.company_id && r.company_id !== fixedCompanyId).length
        : 0;
      toast({
        title: 'Bulletins analysés',
        description: `${data.summary.total} salarié(s) — ${data.summary.ready} prêt(s), ${data.summary.duplicates_removed} doublon(s) retiré(s).`,
      });
      if (mismatchCount > 0) {
        toast({
          title: 'Entreprise non conforme',
          description: `${mismatchCount} bulletin(s) ne correspondent pas à ${scopedCompanyName ?? 'la filiale ciblée'}.`,
          variant: 'destructive',
        });
      }
      if (data.file_errors.length > 0) {
        toast({
          title: 'Avertissements fichiers',
          description: data.file_errors.slice(0, 2).join(' '),
          variant: 'destructive',
        });
      }
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
      const payload = rows
        .filter((row) => isSavableRow(row, fixedCompanyId))
        .map((row) => ({
          row_index: row.row_index,
          company_id: row.company_id as string,
          employee_id: row.employee_id as string,
          year: row.year,
          month: row.month,
          cp_n1_solde: row.cp_n1_solde,
          cp_n_solde: row.cp_n_solde,
          source_file: row.source_file,
          period_label: row.period_label,
          confirmed: true,
        }));
      if (payload.length === 0) {
        throw new Error('Aucune ligne validée à enregistrer.');
      }
      return commitCpImport({ rows: payload });
    },
    onSuccess: (data) => {
      toast({
        title: 'Import CP terminé',
        description: `${data.applied} solde(s) enregistré(s)${data.skipped ? `, ${data.skipped} ignoré(s)` : ''}.`,
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
      setSelectedFiles([]);
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

  const handleAssociate = useCallback(
    (rowIndex: number, employeeId: string, label: string, companyId: string | null | undefined) => {
      setRows((prev) =>
        prev.map((row) =>
          row.row_index === rowIndex
            ? {
                ...row,
                employee_id: employeeId,
                company_id: companyId ?? row.company_id,
                matched_name: label,
                review_status: row.review_status === 'error' ? 'warning' : row.review_status,
                manuallyConfirmed: false,
                warnings: row.warnings.filter((w) => !w.includes('associez manuellement')),
              }
            : row,
        ),
      );
    },
    [],
  );

  const rosterForRow = useCallback(
    (row: EditableRow): RosterEmployee[] => {
      if (!row.company_id || !parseResult?.rosters_by_company) return [];
      return (parseResult.rosters_by_company[row.company_id] ?? []).map((e) => ({
        id: e.id,
        first_name: e.first_name,
        last_name: e.last_name,
        time_tracking_id: e.time_tracking_id ?? undefined,
      }));
    },
    [parseResult],
  );

  const filteredRows = useMemo(() => {
    if (statusFilter === 'all') return rows;
    return rows.filter((r) => r.review_status === statusFilter);
  }, [rows, statusFilter]);

  const pagedRows = useMemo(() => {
    const start = page * PAGE_SIZE;
    return filteredRows.slice(start, start + PAGE_SIZE);
  }, [filteredRows, page]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE));

  const statusCounts = useMemo(() => {
    let ok = 0;
    let warning = 0;
    let error = 0;
    for (const row of rows) {
      if (row.review_status === 'ok') ok += 1;
      else if (row.review_status === 'warning') warning += 1;
      else if (row.review_status === 'error') error += 1;
    }
    return { all: rows.length, ok, warning, error };
  }, [rows]);

  const statusFilterLabels: Record<StatusFilter | CpReviewStatus, string> = {
    all: `Tous (${statusCounts.all})`,
    ok: `Prêts (${statusCounts.ok})`,
    warning: `À vérifier (${statusCounts.warning})`,
    error: `Erreurs (${statusCounts.error})`,
  };

  const companyMismatchCount = useMemo(() => {
    if (!fixedCompanyId) return 0;
    return rows.filter((r) => r.company_id && r.company_id !== fixedCompanyId).length;
  }, [rows, fixedCompanyId]);

  const savableCount = rows.filter((row) => isSavableRow(row, fixedCompanyId)).length;
  const verifyCount = rows.filter((r) => r.review_status !== 'ok' && r.employee_id).length;

  const handleFilesChange = (fileList: FileList | null) => {
    if (!fileList) return;
    const incoming = Array.from(fileList).filter((f) => f.name.toLowerCase().endsWith('.pdf'));
    const merged = [...selectedFiles, ...incoming].slice(0, MAX_FILES);
    setSelectedFiles(merged);
    setParseResult(null);
    setRows([]);
  };

  return (
    <div className="space-y-4">
      <CpImportBulletinPreviewDialog
        open={bulletinPreview != null}
        onOpenChange={(open) => {
          if (!open) setBulletinPreview(null);
        }}
        file={previewFile ?? null}
        pageNumber={bulletinPreview?.pageIndex ?? 1}
        employeeLabel={bulletinPreview?.employeeLabel}
        sourceFile={bulletinPreview?.sourceFile}
        periodLabel={bulletinPreview?.periodLabel}
      />
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FileText className="h-4 w-4" />
            Import CP
          </CardTitle>
          <CardDescription>
            Bulletins de paie PDF (Cegid clarifié ou EYWAI). L&apos;entreprise est détectée via le
            SIRET, le salarié via matricule ou nom. Jusqu&apos;à {MAX_FILES} fichiers — les lots
            multi-pages sont dédoublonnés automatiquement.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="flex-1 space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Fichiers PDF</p>
            <div className="flex gap-2">
              <Button type="button" variant="outline" className="flex-1" asChild>
                <label className="cursor-pointer">
                  <Upload className="mr-2 h-4 w-4" />
                  {selectedFiles.length === 0
                    ? 'Choisir des bulletins…'
                    : `${selectedFiles.length} fichier(s) sélectionné(s)`}
                  <input
                    type="file"
                    accept=".pdf,application/pdf"
                    multiple
                    className="hidden"
                    onChange={(e) => handleFilesChange(e.target.files)}
                  />
                </label>
              </Button>
              {selectedFiles.length > 0 && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSelectedFiles([]);
                    setParseResult(null);
                    setRows([]);
                  }}
                >
                  Effacer
                </Button>
              )}
              <Button
                type="button"
                disabled={selectedFiles.length === 0 || parseMutation.isPending}
                onClick={() => parseMutation.mutate()}
              >
                {parseMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : null}
                Analyser
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {companyScoped && scopedCompanyName ? (
        <p className="text-sm text-muted-foreground">
          Import pour <span className="font-medium text-foreground">{scopedCompanyName}</span>
          {' '}— les bulletins d&apos;une autre filiale seront signalés.
        </p>
      ) : null}

      {companyMismatchCount > 0 ? (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            {companyMismatchCount} bulletin(s) ne correspondent pas à{' '}
            <strong>{scopedCompanyName ?? 'cette filiale'}</strong>. Retirez-les ou vérifiez le
            SIRET avant d&apos;enregistrer.
          </span>
        </div>
      ) : null}

      {parseResult && (
        <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
          <span>{parseResult.summary.files_processed} fichier(s) traité(s)</span>
          <span>·</span>
          <span>{parseResult.summary.duplicates_removed} doublon(s) retiré(s)</span>
          {parseResult.summary.files_failed > 0 && (
            <>
              <span>·</span>
              <span className="text-destructive">{parseResult.summary.files_failed} échec(s)</span>
            </>
          )}
        </div>
      )}

      {parseResult && rows.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="space-y-3">
              <div className="flex items-start justify-between gap-6">
                <div className="min-w-0">
                  <CardTitle className="text-base">Revue des soldes CP</CardTitle>
                  <CardDescription>
                    {rows.length} salarié(s), {savableCount} prêt(s) à enregistrer
                    {verifyCount > 0 ? `, ${verifyCount} à vérifier` : ''}
                  </CardDescription>
                </div>
                <Button
                  type="button"
                  size="sm"
                  className="h-8 shrink-0"
                  disabled={savableCount === 0 || commitMutation.isPending}
                  onClick={() => commitMutation.mutate()}
                >
                  {commitMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <CheckCircle2 className="mr-2 h-4 w-4" />
                  )}
                  Enregistrer {savableCount} solde(s)
                </Button>
              </div>
              <div
                className="inline-flex flex-wrap gap-1.5 rounded-lg border bg-muted/25 p-1"
                role="group"
                aria-label="Filtrer par statut"
              >
                {(['all', 'ok', 'warning', 'error'] as const).map((f) => (
                  <Button
                    key={f}
                    type="button"
                    size="sm"
                    variant={statusFilter === f ? 'secondary' : 'ghost'}
                    className="h-8"
                    onClick={() => {
                      setStatusFilter(f);
                      setPage(0);
                    }}
                  >
                    {statusFilterLabels[f]}
                  </Button>
                ))}
              </div>
            </div>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">#</TableHead>
                  <TableHead>{companyScoped ? 'Fichier / Période' : 'Fichier / Entreprise'}</TableHead>
                  <TableHead>Salarié détecté</TableHead>
                  <TableHead>CP N-1</TableHead>
                  <TableHead>CP N</TableHead>
                  <TableHead>Actuel / Δ</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="w-24">Bulletin</TableHead>
                  <TableHead className="w-28">Valider</TableHead>
                  <TableHead className="w-48">Associer</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pagedRows.map((row) => {
                  const needsConfirm = row.review_status !== 'ok';
                  const savable = isSavableRow(row, fixedCompanyId);
                  const companyMismatch =
                    Boolean(fixedCompanyId) &&
                    Boolean(row.company_id) &&
                    row.company_id !== fixedCompanyId;
                  const roster = rosterForRow(row);
                  return (
                    <TableRow key={row.row_index} className={cn(!savable && 'opacity-80')}>
                      <TableCell className="text-muted-foreground">{row.row_index}</TableCell>
                      <TableCell>
                        <div className="text-xs text-muted-foreground truncate max-w-[160px]">
                          {row.source_file}
                        </div>
                        {!companyScoped ? (
                          <div className="font-medium">{row.company_name ?? '—'}</div>
                        ) : null}
                        <div className={cn('text-xs', companyScoped ? 'font-medium' : 'text-muted-foreground')}>
                          {row.period_label ?? row.year}
                        </div>
                        {companyMismatch ? (
                          <div className="mt-0.5 text-xs font-medium text-destructive">
                            {row.company_name ?? 'Autre entreprise'}
                          </div>
                        ) : null}
                        {row.has_existing_adjustment && (
                          <Badge variant="outline" className="mt-1 text-xs">
                            Remplacement
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="font-medium">{row.raw_identity || '—'}</div>
                        {row.matricule && (
                          <div className="text-xs text-muted-foreground">Mat. {row.matricule}</div>
                        )}
                        {row.matched_name && (
                          <div className="mt-1 flex items-center gap-1 text-xs text-emerald-700">
                            <UserCheck className="h-3 w-3" />
                            {row.matched_name}
                          </div>
                        )}
                        {row.warnings.length > 0 && (
                          <div className="mt-1 flex items-start gap-1 text-xs text-amber-700">
                            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                            <span>{row.warnings[0]}</span>
                          </div>
                        )}
                      </TableCell>
                      <TableCell>{formatSolde(row.cp_n1_solde)}</TableCell>
                      <TableCell>{formatSolde(row.cp_n_solde)}</TableCell>
                      <TableCell className="text-xs">
                        <div>N-1 : {formatSolde(row.current_cp_n1)}</div>
                        <div>N : {formatSolde(row.current_cp_n)}</div>
                        <div className="text-muted-foreground">
                          Δ {formatDelta(row.delta_cp_n1)} / {formatDelta(row.delta_cp_n)}
                        </div>
                      </TableCell>
                      <TableCell>{statusBadge(row.review_status)}</TableCell>
                      <TableCell>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="h-8 gap-1 text-xs"
                          disabled={!fileByName.has(row.source_file)}
                          onClick={() =>
                            setBulletinPreview({
                              sourceFile: row.source_file,
                              pageIndex: row.page_index,
                              employeeLabel:
                                row.matched_name || row.raw_identity || row.matricule || 'Salarié',
                              periodLabel: row.period_label ?? String(row.year),
                            })
                          }
                        >
                          <Eye className="h-3.5 w-3.5" />
                          Voir
                        </Button>
                      </TableCell>
                      <TableCell>
                        {needsConfirm ? (
                          <label className="flex items-center gap-2 text-xs">
                            <Checkbox
                              checked={row.manuallyConfirmed}
                              disabled={!row.employee_id || !row.company_id}
                              onCheckedChange={(checked) => {
                                setRows((prev) =>
                                  prev.map((r) =>
                                    r.row_index === row.row_index
                                      ? { ...r, manuallyConfirmed: checked === true }
                                      : r,
                                  ),
                                );
                              }}
                            />
                            Confirmer
                          </label>
                        ) : (
                          <Check className="h-4 w-4 text-emerald-600" />
                        )}
                      </TableCell>
                      <TableCell>
                        {row.company_id ? (
                          <EmployeeAssociateCombobox
                            roster={roster}
                            value={row.employee_id ?? null}
                            onSelect={(id, label) =>
                              handleAssociate(row.row_index, id, label, row.company_id)
                            }
                            compact
                          />
                        ) : (
                          <span className="text-xs text-muted-foreground">SIRET inconnu</span>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
            {totalPages > 1 && (
              <div className="mt-4 flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  Page {page + 1} / {totalPages} ({filteredRows.length} lignes)
                </p>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={page === 0}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Précédent
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    disabled={page >= totalPages - 1}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Suivant
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {parseResult && parseResult.file_errors.length > 0 && rows.length === 0 && (
        <Card>
          <CardContent className="py-6 text-sm text-destructive">
            {parseResult.file_errors.join(' · ')}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
