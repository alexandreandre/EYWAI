import { useCallback, useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Upload, FileText, AlertTriangle, CheckCircle2, Loader2, UserPlus } from 'lucide-react';
import {
  activateImportedEmployee,
  commitDsnImportBatch,
  parseDsnImportFiles,
  DSN_IMPORT_ACTION_LABELS,
  DSN_IMPORT_ITEM_TYPE_LABELS,
  type DsnImportCommitResponse,
  type DsnImportItemPreview,
  type DsnImportParseResponse,
  type ImportedEmployeeSummary,
} from '@/api/dsnImport';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';

type Step = 'upload' | 'preview' | 'result';

export function DsnImportWizard() {
  const { toast } = useToast();
  const [step, setStep] = useState<Step>('upload');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [parseResult, setParseResult] = useState<DsnImportParseResponse | null>(null);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [commitReport, setCommitReport] = useState<DsnImportCommitResponse | null>(null);
  const [activationEmails, setActivationEmails] = useState<Record<string, string>>({});
  const [activatedIds, setActivatedIds] = useState<Record<string, string>>({});

  const parseMutation = useMutation({
    mutationFn: (files: File[]) => parseDsnImportFiles(files),
    onSuccess: (data) => {
      setParseResult(data);
      const initial: Record<string, string> = {};
      data.items.forEach((it) => {
        initial[it.source_ref] = it.action;
      });
      setOverrides(initial);
      setStep('preview');
    },
    onError: (err: Error) => {
      toast({ title: 'Erreur', description: err.message, variant: 'destructive' });
    },
  });

  const commitMutation = useMutation({
    mutationFn: () => {
      if (!parseResult) throw new Error('Aucune analyse en cours');
      return commitDsnImportBatch(parseResult.batch_id, overrides);
    },
    onSuccess: (data) => {
      setCommitReport(data);
      const emails: Record<string, string> = {};
      data.imported_employees.forEach((emp) => {
        const placeholder = emp.placeholder_email ?? '';
        emails[emp.employee_id] = placeholder.includes('@dsn-import.local') ? '' : placeholder;
      });
      setActivationEmails(emails);
      setActivatedIds({});
      setStep('result');
      toast({ title: 'Import terminé', description: 'Le dossier a été reconstruit.' });
    },
    onError: (err: Error) => {
      toast({ title: 'Échec du commit', description: err.message, variant: 'destructive' });
    },
  });

  const onFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files ? Array.from(e.target.files) : [];
    setSelectedFiles(list);
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const list = Array.from(e.dataTransfer.files);
    setSelectedFiles(list);
  }, []);

  const blockingCount = useMemo(
    () => parseResult?.anomalies.filter((a) => a.severity === 'blocking').length ?? 0,
    [parseResult],
  );

  const groupedItems = useMemo(() => {
    if (!parseResult) return {};
    return parseResult.items.reduce<Record<string, DsnImportItemPreview[]>>((acc, it) => {
      const key = it.item_type;
      acc[key] = acc[key] || [];
      acc[key].push(it);
      return acc;
    }, {});
  }, [parseResult]);

  return (
    <div className="space-y-6">
      {step === 'upload' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Upload className="h-5 w-5" />
              Déposer les fichiers DSN
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div
              className="flex min-h-[180px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/30 bg-muted/20 p-6 text-center transition hover:border-primary/50"
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop}
              onClick={() => document.getElementById('dsn-import-input')?.click()}
            >
              <FileText className="mb-3 h-10 w-10 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                Glissez un ou plusieurs fichiers DSN (format plat NEODeS) ou cliquez pour parcourir
              </p>
              <input
                id="dsn-import-input"
                type="file"
                multiple
                accept=".txt,.dsn,.edi"
                className="hidden"
                onChange={onFileChange}
              />
            </div>
            {selectedFiles.length > 0 && (
              <ul className="text-sm text-muted-foreground">
                {selectedFiles.map((f) => (
                  <li key={f.name}>{f.name}</li>
                ))}
              </ul>
            )}
            <Button
              disabled={selectedFiles.length === 0 || parseMutation.isPending}
              onClick={() => parseMutation.mutate(selectedFiles)}
            >
              {parseMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Analyser
            </Button>
          </CardContent>
        </Card>
      )}

      {step === 'preview' && parseResult && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Résumé de l&apos;analyse</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Stat label="SIREN" value={String(parseResult.summary.siren ?? '—')} />
              <Stat
                label="Période"
                value={`${parseResult.summary.period_min ?? '?'} → ${parseResult.summary.period_max ?? '?'}`}
              />
              <Stat
                label="Établissements"
                value={String(parseResult.summary.establishment_count ?? 0)}
              />
              <Stat label="Salariés" value={String(parseResult.summary.employee_count ?? 0)} />
            </CardContent>
          </Card>

          {parseResult.anomalies.length > 0 && (
            <Card className="border-amber-200">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  Anomalies ({parseResult.anomalies.length})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm">
                {parseResult.anomalies.map((a, i) => (
                  <p key={i} className={a.severity === 'blocking' ? 'text-destructive' : ''}>
                    {a.message}
                  </p>
                ))}
              </CardContent>
            </Card>
          )}

          {Object.entries(groupedItems).map(([type, items]) => (
            <Card key={type}>
              <CardHeader>
                <CardTitle className="text-base">
                  {DSN_IMPORT_ITEM_TYPE_LABELS[type] ?? type} ({items.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Libellé</TableHead>
                      <TableHead>Action</TableHead>
                      <TableHead>Info</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {items.map((it) => (
                      <TableRow key={it.source_ref}>
                        <TableCell>{it.label ?? it.source_ref}</TableCell>
                        <TableCell>
                          <Select
                            value={overrides[it.source_ref] ?? it.action}
                            onValueChange={(v) =>
                              setOverrides((prev) => ({ ...prev, [it.source_ref]: v }))
                            }
                          >
                            <SelectTrigger className="w-[160px]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {Object.entries(DSN_IMPORT_ACTION_LABELS).map(([k, label]) => (
                                <SelectItem key={k} value={k}>
                                  {label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          {it.needs_review && (
                            <Badge variant="outline">À vérifier</Badge>
                          )}
                          {it.employee_count != null && (
                            <span className="text-muted-foreground text-xs">
                              {it.employee_count} salarié(s)
                            </span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          ))}

          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setStep('upload')}>
              Retour
            </Button>
            <Button
              disabled={!parseResult.can_commit || commitMutation.isPending || blockingCount > 0}
              onClick={() => commitMutation.mutate()}
            >
              {commitMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Valider l&apos;import
            </Button>
          </div>
        </>
      )}

      {step === 'result' && commitReport && (
        <>
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                Import terminé
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p>
                Créés : {commitReport.stats.created ?? 0} — Mis à jour :{' '}
                {commitReport.stats.updated ?? 0} — Ignorés : {commitReport.stats.skipped ?? 0}
              </p>
              {commitReport.errors.length > 0 && (
                <div className="text-destructive">
                  {commitReport.errors.map((e, i) => (
                    <p key={i}>{e}</p>
                  ))}
                </div>
              )}
              <Button
                variant="outline"
                onClick={() => {
                  setStep('upload');
                  setParseResult(null);
                  setSelectedFiles([]);
                  setCommitReport(null);
                  setActivationEmails({});
                  setActivatedIds({});
                }}
              >
                Nouvel import
              </Button>
            </CardContent>
          </Card>

          {commitReport.imported_employees.length > 0 && (
            <ImportedEmployeesActivationPanel
              employees={commitReport.imported_employees}
              emails={activationEmails}
              activatedIds={activatedIds}
              onEmailChange={(id, email) =>
                setActivationEmails((prev) => ({ ...prev, [id]: email }))
              }
              onActivated={(id, password) =>
                setActivatedIds((prev) => ({ ...prev, [id]: password }))
              }
            />
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-card p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  );
}

function ImportedEmployeesActivationPanel({
  employees,
  emails,
  activatedIds,
  onEmailChange,
  onActivated,
}: {
  employees: ImportedEmployeeSummary[];
  emails: Record<string, string>;
  activatedIds: Record<string, string>;
  onEmailChange: (employeeId: string, email: string) => void;
  onActivated: (employeeId: string, generatedPassword: string) => void;
}) {
  const { toast } = useToast();
  const [pendingId, setPendingId] = useState<string | null>(null);

  const activateOne = async (emp: ImportedEmployeeSummary) => {
    const email = (emails[emp.employee_id] ?? '').trim();
    if (!email || !email.includes('@')) {
      toast({
        title: 'Email requis',
        description: `Renseignez un email valide pour ${emp.full_name}.`,
        variant: 'destructive',
      });
      return;
    }
    setPendingId(emp.employee_id);
    try {
      const result = await activateImportedEmployee(emp.employee_id, emp.company_id, email);
      onActivated(emp.employee_id, result.generated_password);
      toast({
        title: 'Compte créé',
        description: `${emp.full_name} — mot de passe généré (communiquez-le au salarié).`,
      });
    } catch (err) {
      toast({
        title: 'Échec',
        description: err instanceof Error ? err.message : 'Activation impossible',
        variant: 'destructive',
      });
    } finally {
      setPendingId(null);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <UserPlus className="h-4 w-4" />
          Activation des comptes salariés ({employees.length})
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-4 text-sm text-muted-foreground">
          Les salariés importés sont en brouillon. Créez leur compte collaborateur quand vous
          disposez de leur email professionnel.
        </p>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Salarié</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {employees.map((emp) => (
              <TableRow key={emp.employee_id}>
                <TableCell>{emp.full_name}</TableCell>
                <TableCell>
                  <Input
                    type="email"
                    placeholder="email@entreprise.fr"
                    value={emails[emp.employee_id] ?? ''}
                    disabled={Boolean(activatedIds[emp.employee_id])}
                    onChange={(e) => onEmailChange(emp.employee_id, e.target.value)}
                  />
                </TableCell>
                <TableCell>
                  {activatedIds[emp.employee_id] ? (
                    <Badge variant="secondary">Compte actif</Badge>
                  ) : (
                    <Badge variant="outline">En onboarding</Badge>
                  )}
                </TableCell>
                <TableCell>
                  {activatedIds[emp.employee_id] ? (
                    <span className="text-xs text-muted-foreground font-mono">
                      {activatedIds[emp.employee_id]}
                    </span>
                  ) : (
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={pendingId === emp.employee_id}
                      onClick={() => activateOne(emp)}
                    >
                      {pendingId === emp.employee_id && (
                        <Loader2 className="mr-2 h-3 w-3 animate-spin" />
                      )}
                      Créer le compte
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
