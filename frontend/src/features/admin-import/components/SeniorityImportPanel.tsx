import { useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  AlertTriangle,
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronDown,
  FileSpreadsheet,
  Loader2,
  Upload,
} from 'lucide-react';
import {
  commitSeniorityImport,
  parseSeniorityImportFile,
  type RibImportRosterEmployee,
  type SeniorityImportMissingEmployee,
  type SeniorityImportParseResponse,
  type SeniorityImportRowPreview,
  type RibReviewStatus,
} from '@/api/adminImport';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
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

type EditableRow = SeniorityImportRowPreview & {
  manuallyConfirmed: boolean;
};

type EditableMissingRow = SeniorityImportMissingEmployee & {
  seniority_date: string;
  manuallyConfirmed: boolean;
};

function statusBadge(status: RibReviewStatus) {
  if (status === 'ok') {
    return <Badge variant="secondary" className="bg-emerald-100 text-emerald-800">Prêt</Badge>;
  }
  if (status === 'warning') {
    return <Badge variant="secondary" className="bg-amber-100 text-amber-900">À vérifier</Badge>;
  }
  return <Badge variant="destructive">Bloquant</Badge>;
}

function formatDateFr(iso?: string | null) {
  if (!iso) return '—';
  const [y, m, d] = iso.split('-');
  if (!y || !m || !d) return iso;
  return `${d}/${m}/${y}`;
}

function isSavableRow(row: EditableRow): boolean {
  if (!row.employee_id || !row.seniority_date || row.unchanged) return false;
  if (row.review_status === 'ok') return true;
  if (row.manuallyConfirmed && row.review_status === 'warning') return true;
  if (row.manuallyConfirmed && row.review_status === 'error') return true;
  return false;
}

function isSavableMissingRow(row: EditableMissingRow): boolean {
  if (!row.seniority_date || !row.manuallyConfirmed) return false;
  if (row.current_seniority_date && row.seniority_date === row.current_seniority_date) {
    return false;
  }
  return true;
}

function rosterFromParse(roster: RibImportRosterEmployee[]): RosterEmployee[] {
  return roster.map((e) => ({
    id: e.id,
    first_name: e.first_name,
    last_name: e.last_name,
    time_tracking_id: e.time_tracking_id ?? undefined,
  }));
}

export function SeniorityImportPanel({
  companyId,
  onComplete,
  standalone = false,
}: {
  companyId?: string;
  onComplete?: () => void;
  /** Plein écran (onglet / étape parcours) — sans repli. */
  standalone?: boolean;
}) {
  const { toast } = useToast();
  const [open, setOpen] = useState(true);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [parseResult, setParseResult] = useState<SeniorityImportParseResponse | null>(null);
  const [rows, setRows] = useState<EditableRow[]>([]);
  const [missingRows, setMissingRows] = useState<EditableMissingRow[]>([]);

  useEffect(() => {
    setParseResult(null);
    setRows([]);
    setMissingRows([]);
    setSelectedFile(null);
  }, [companyId]);

  const roster = useMemo(
    () => (parseResult?.roster ? rosterFromParse(parseResult.roster) : []),
    [parseResult?.roster],
  );

  const savableCount = useMemo(
    () => rows.filter(isSavableRow).length + missingRows.filter(isSavableMissingRow).length,
    [rows, missingRows],
  );

  const parseMutation = useMutation({
    mutationFn: async () => {
      if (!companyId || !selectedFile) {
        throw new Error('Sélectionnez un fichier.');
      }
      return parseSeniorityImportFile(companyId, selectedFile);
    },
    onSuccess: (data) => {
      setParseResult(data);
      setRows(
        data.rows.map((row) => ({
          ...row,
          manuallyConfirmed: row.review_status === 'ok' && !row.unchanged,
        })),
      );
      setMissingRows(
        data.missing_employees.map((emp) => ({
          ...emp,
          seniority_date: '',
          manuallyConfirmed: false,
        })),
      );
      setOpen(true);
      toast({
        title: 'Fichier analysé',
        description: `${data.summary.total} ligne(s) — ${data.summary.ready} prête(s).`,
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
      const payload = [
        ...rows.filter(isSavableRow).map((row) => ({
          row_index: row.row_index,
          employee_id: row.employee_id as string,
          seniority_date: row.seniority_date as string,
          confirmed: true,
        })),
        ...missingRows.filter(isSavableMissingRow).map((row, index) => ({
          row_index: -(index + 1),
          employee_id: row.employee_id,
          seniority_date: row.seniority_date,
          confirmed: true,
        })),
      ];
      if (payload.length === 0) {
        throw new Error('Aucune ligne validée à enregistrer.');
      }
      return commitSeniorityImport({ company_id: parseResult.company_id, rows: payload });
    },
    onSuccess: (data) => {
      toast({
        title: 'Dates d\'ancienneté enregistrées',
        description: `${data.applied} fiche(s) mise(s) à jour.`,
      });
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

  const updateRowEmployee = useCallback((rowIndex: number, employeeId: string | null) => {
    setRows((prev) =>
      prev.map((row) => {
        if (row.row_index !== rowIndex) return row;
        const matched = roster.find((e) => e.id === employeeId);
        return {
          ...row,
          employee_id: employeeId,
          matched_name: matched
            ? `${matched.first_name} ${matched.last_name}`.trim()
            : row.matched_name,
          manuallyConfirmed: Boolean(employeeId),
          review_status: employeeId && row.seniority_date ? 'warning' : 'error',
        };
      }),
    );
  }, [roster]);

  const hasCompany = Boolean(companyId);

  const body = (
    <div className="space-y-4">
      {!hasCompany ? (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          Sélectionnez d&apos;abord une filiale dans le sélecteur en haut de page (« Filiale
          existante »).
        </p>
      ) : null}
      <p className="text-sm text-muted-foreground">
        Fichier Excel ou CSV avec colonnes <strong>NOM</strong>, <strong>PRENOM</strong> et{' '}
        <strong>Date ancienneté</strong> (tableau prime LEWIS / métallurgie). Seule la date est
        importée — les montants restent calculés par EYWAI.
      </p>
        <div className="flex flex-wrap items-center gap-3">
          <label
            className={cn(
              'inline-flex items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm',
              hasCompany ? 'cursor-pointer hover:bg-muted/50' : 'cursor-not-allowed opacity-50',
            )}
          >
            <Upload className="h-4 w-4" />
            {selectedFile ? selectedFile.name : 'Choisir un fichier'}
            <input
              type="file"
              accept=".xlsx,.xls,.csv"
              className="sr-only"
              disabled={!hasCompany}
              onChange={(e) => {
                setSelectedFile(e.target.files?.[0] ?? null);
                setParseResult(null);
                setRows([]);
                setMissingRows([]);
              }}
            />
          </label>
          <Button
            type="button"
            size="sm"
            disabled={!hasCompany || !selectedFile || parseMutation.isPending}
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

        {parseResult ? (
          <>
            <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              {parseResult.summary.total} salarié(s) · {parseResult.summary.ready} prêt(s) ·{' '}
              {parseResult.summary.warning} à vérifier · {parseResult.summary.error} bloquant(s)
              {parseResult.summary.skipped_junk
                ? ` · ${parseResult.summary.skipped_junk} note(s) ignorée(s)`
                : null}
              {parseResult.summary.unchanged
                ? ` · ${parseResult.summary.unchanged} déjà à jour`
                : null}
            </div>
            {parseResult.summary.active_employees != null ? (
              <p className="text-sm text-muted-foreground">
                Couverture effectif actif :{' '}
                <strong>
                  {parseResult.summary.matched_employees ?? 0}/
                  {parseResult.summary.active_employees}
                </strong>{' '}
                salarié(s) repéré(s) dans le fichier.
              </p>
            ) : null}
            {missingRows.length > 0 ? (
              <div className="space-y-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-950">
                <div>
                  <p className="font-medium">
                    {missingRows.length} salarié(s) actif(s) absent(s) du fichier
                  </p>
                  <p className="mt-1 text-xs text-amber-900/90">
                    Saisissez leur date d&apos;ancienneté pour compléter l&apos;import et vérifier
                    la prime.
                  </p>
                </div>
                <div className="overflow-auto rounded-md border border-amber-200/80 bg-background">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-10" />
                        <TableHead>Salarié EYWAI</TableHead>
                        <TableHead>Date actuelle</TableHead>
                        <TableHead>Date à enregistrer</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {missingRows.map((row) => {
                        const unchanged =
                          Boolean(row.seniority_date) &&
                          row.seniority_date === row.current_seniority_date;
                        return (
                          <TableRow key={row.employee_id}>
                            <TableCell>
                              <Checkbox
                                checked={row.manuallyConfirmed && !unchanged}
                                disabled={!row.seniority_date || unchanged}
                                onCheckedChange={(checked) => {
                                  setMissingRows((prev) =>
                                    prev.map((r) =>
                                      r.employee_id === row.employee_id
                                        ? { ...r, manuallyConfirmed: checked === true }
                                        : r,
                                    ),
                                  );
                                }}
                              />
                            </TableCell>
                            <TableCell className="text-sm font-medium">
                              {`${row.first_name} ${row.last_name}`.trim()}
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {formatDateFr(row.current_seniority_date ?? row.current_hire_date)}
                            </TableCell>
                            <TableCell>
                              <Input
                                type="date"
                                className="h-8 w-[11rem] text-sm"
                                value={row.seniority_date}
                                onChange={(e) => {
                                  const value = e.target.value;
                                  setMissingRows((prev) =>
                                    prev.map((r) =>
                                      r.employee_id === row.employee_id
                                        ? {
                                            ...r,
                                            seniority_date: value,
                                            manuallyConfirmed: false,
                                          }
                                        : r,
                                    ),
                                  );
                                }}
                              />
                              {unchanged ? (
                                <p className="mt-1 text-xs text-amber-800">
                                  Identique à la fiche — aucune modification.
                                </p>
                              ) : null}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              </div>
            ) : null}
            <div className="max-h-[min(360px,50vh)] overflow-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10" />
                    <TableHead>Identité fichier</TableHead>
                    <TableHead>Salarié EYWAI</TableHead>
                    <TableHead>Date import</TableHead>
                    <TableHead>Date actuelle</TableHead>
                    <TableHead>Statut</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rows.map((row) => (
                    <TableRow key={row.row_index}>
                      <TableCell>
                        <Checkbox
                          checked={isSavableRow(row) || row.manuallyConfirmed}
                          disabled={!row.seniority_date || row.unchanged}
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
                      </TableCell>
                      <TableCell className="text-sm">{row.raw_identity}</TableCell>
                      <TableCell>
                        {row.employee_id && row.review_status !== 'error' ? (
                          <span className="text-sm">{row.matched_name}</span>
                        ) : (
                          <EmployeeAssociateCombobox
                            roster={roster}
                            value={row.employee_id ?? null}
                            onChange={(id) => updateRowEmployee(row.row_index, id)}
                          />
                        )}
                      </TableCell>
                      <TableCell className="text-sm">
                        {formatDateFr(row.seniority_date)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDateFr(row.current_seniority_date ?? row.current_hire_date)}
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          {statusBadge(row.review_status)}
                          {row.warnings.slice(0, 2).map((w) => (
                            <p
                              key={w}
                              className="flex items-start gap-1 text-xs text-amber-800"
                            >
                              <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                              {w}
                            </p>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
            <div className="flex justify-end">
              <Button
                type="button"
                disabled={savableCount === 0 || commitMutation.isPending}
                onClick={() => commitMutation.mutate()}
              >
                {commitMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Check className="mr-2 h-4 w-4" />
                )}
                Enregistrer {savableCount} date(s)
              </Button>
            </div>
          </>
        ) : null}
    </div>
  );

  if (standalone) {
    return body;
  }

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="rounded-lg border border-primary/20 bg-primary/[0.03] shadow-sm"
    >
      <CollapsibleTrigger asChild>
        <button
          type="button"
          className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-primary/[0.06]"
        >
          <span className="flex items-center gap-2 text-sm font-semibold">
            <CalendarClock className="h-4 w-4 text-primary" />
            Import dates d&apos;ancienneté (reprise / prime)
          </span>
          <ChevronDown className={cn('h-4 w-4 shrink-0 transition-transform', open && 'rotate-180')} />
        </button>
      </CollapsibleTrigger>
      <CollapsibleContent className="border-t px-4 py-4">{body}</CollapsibleContent>
    </Collapsible>
  );
}
