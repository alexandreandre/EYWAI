import { useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  AlertTriangle,
  Check,
  CheckCircle2,
  FileSpreadsheet,
  Loader2,
  Upload,
  UserCheck,
} from 'lucide-react';
import { listDsnImportCompanies, type DsnImportCompany } from '@/api/dsnImport';
import {
  commitRibImport,
  parseRibImportFile,
  type RibImportParseResponse,
  type RibImportRowPreview,
  type RibReviewStatus,
} from '@/api/adminImport';
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

type EditableRow = RibImportRowPreview & {
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

function statusBadge(status: RibReviewStatus) {
  if (status === 'ok') {
    return <Badge variant="secondary" className="bg-emerald-100 text-emerald-800">Prêt</Badge>;
  }
  if (status === 'warning') {
    return <Badge variant="secondary" className="bg-amber-100 text-amber-900">À vérifier</Badge>;
  }
  return <Badge variant="destructive">Bloquant</Badge>;
}

function maskIban(iban: string): string {
  const clean = iban.replace(/\s/g, '');
  if (clean.length < 8) return clean;
  return `${clean.slice(0, 4)} **** **** ${clean.slice(-4)}`;
}

function isSavableRow(row: EditableRow): boolean {
  if (!row.employee_id || !row.iban_valid) return false;
  if (row.review_status === 'ok') return true;
  if (row.manuallyConfirmed && row.review_status === 'warning') return true;
  if (row.manuallyConfirmed && row.review_status === 'error' && row.employee_id) return true;
  return false;
}

export function RibImportPanel({
  fixedCompanyId,
  hideCompanySelector = false,
  embedded = false,
  onComplete,
  onCompanyChange,
}: {
  fixedCompanyId?: string;
  hideCompanySelector?: boolean;
  embedded?: boolean;
  onComplete?: () => void;
  onCompanyChange?: (companyId: string) => void;
} = {}) {
  const { toast } = useToast();
  const [companyId, setCompanyId] = useState(fixedCompanyId ?? '');
  const [comboboxOpen, setComboboxOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [parseResult, setParseResult] = useState<RibImportParseResponse | null>(null);
  const [rows, setRows] = useState<EditableRow[]>([]);

  useEffect(() => {
    if (fixedCompanyId) setCompanyId(fixedCompanyId);
  }, [fixedCompanyId]);

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
      return parseRibImportFile(companyId, selectedFile);
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
        title: 'Fichier analysé',
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
          iban: row.iban,
          bic: row.bic || null,
          confirmed: true,
        }));
      if (payload.length === 0) {
        throw new Error('Aucune ligne validée à enregistrer.');
      }
      return commitRibImport({ company_id: parseResult.company_id, rows: payload });
    },
    onSuccess: (data) => {
      toast({
        title: 'Import RIB terminé',
        description: `${data.applied} RIB enregistré(s)${data.skipped ? `, ${data.skipped} ignoré(s)` : ''}.`,
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
              review_status: row.iban_valid ? 'warning' : row.review_status,
              manuallyConfirmed: false,
              warnings: row.warnings.filter((w) => !w.includes('associez manuellement')),
            }
          : row,
      ),
    );
  }, []);

  const savableCount = rows.filter(isSavableRow).length;
  const verifyCount = rows.filter((r) => r.review_status !== 'ok' && r.employee_id).length;

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <FileSpreadsheet className="h-4 w-4" />
            Import RIB
          </CardTitle>
          <CardDescription>
            Fichier Excel ou CSV avec une colonne <strong>RIB</strong> (IBAN). Les colonnes Nom,
            Prénom, Matricule ou Email sont détectées automatiquement pour rapprocher chaque
            salarié. Les correspondances douteuses demandent une validation manuelle.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-end">
          {!hideCompanySelector ? (
          <div className="flex-1 space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Entreprise</p>
            <Popover open={comboboxOpen} onOpenChange={setComboboxOpen}>
              <PopoverTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  role="combobox"
                  className="w-full justify-between font-normal"
                  disabled={loadingCompanies}
                >
                  {selectedCompany?.company_name ?? 'Choisir une entreprise…'}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[420px] p-0" align="start">
                <Command>
                  <CommandInput placeholder="Rechercher une entreprise…" />
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

          <div className="flex-1 space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">Fichier</p>
            <div className="flex gap-2">
              <Button type="button" variant="outline" className="flex-1" asChild>
                <label className="cursor-pointer">
                  <Upload className="mr-2 h-4 w-4" />
                  {selectedFile?.name ?? 'Choisir un fichier…'}
                  <input
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0] ?? null;
                      setSelectedFile(file);
                      setParseResult(null);
                      setRows([]);
                    }}
                  />
                </label>
              </Button>
              <Button
                type="button"
                disabled={!companyId || !selectedFile || parseMutation.isPending}
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

      {parseResult && rows.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="text-base">Revue des correspondances</CardTitle>
                <CardDescription>
                  {parseResult.company_name} — {rows.length} ligne(s), {savableCount} prête(s) à
                  enregistrer
                  {verifyCount > 0 ? `, ${verifyCount} nécessitent une vérification` : ''}
                </CardDescription>
              </div>
              <Button
                type="button"
                disabled={savableCount === 0 || commitMutation.isPending}
                onClick={() => commitMutation.mutate()}
              >
                {commitMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                )}
                Enregistrer {savableCount} RIB
              </Button>
            </div>
          </CardHeader>
          <CardContent className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">Ligne</TableHead>
                  <TableHead>Identité fichier</TableHead>
                  <TableHead>RIB (IBAN)</TableHead>
                  <TableHead>Employé EYWAI</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="w-28">Valider</TableHead>
                  <TableHead className="w-48">Associer</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => {
                  const needsConfirm = row.review_status !== 'ok';
                  const savable = isSavableRow(row);
                  return (
                    <TableRow key={row.row_index} className={cn(!savable && 'opacity-80')}>
                      <TableCell className="text-muted-foreground">{row.row_index}</TableCell>
                      <TableCell>
                        <div className="font-medium">{row.raw_identity || '—'}</div>
                        {row.matricule && (
                          <div className="text-xs text-muted-foreground">Mat. {row.matricule}</div>
                        )}
                        {row.warnings.length > 0 && (
                          <div className="mt-1 flex items-start gap-1 text-xs text-amber-700">
                            <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                            <span>{row.warnings[0]}</span>
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="font-mono text-xs">
                          {row.iban_valid ? maskIban(row.iban) : row.rib_raw.slice(0, 24)}
                        </div>
                        {row.current_iban_masked && (
                          <div className="text-xs text-muted-foreground">
                            Actuel : {row.current_iban_masked}
                          </div>
                        )}
                      </TableCell>
                      <TableCell>
                        {row.matched_name ? (
                          <div className="flex items-center gap-1">
                            <UserCheck className="h-3.5 w-3.5 text-muted-foreground" />
                            {row.matched_name}
                          </div>
                        ) : (
                          <span className="text-muted-foreground">Non identifié</span>
                        )}
                      </TableCell>
                      <TableCell>{statusBadge(row.review_status)}</TableCell>
                      <TableCell>
                        {needsConfirm ? (
                          <label className="flex items-center gap-2 text-xs">
                            <Checkbox
                              checked={row.manuallyConfirmed}
                              disabled={!row.employee_id || !row.iban_valid}
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
                        <EmployeeAssociateCombobox
                          roster={roster}
                          value={row.employee_id ?? null}
                          onSelect={(id, label) => handleAssociate(row.row_index, id, label)}
                          compact
                        />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
