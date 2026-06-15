import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  Upload,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  UserPlus,
  ArrowLeft,
  Pencil,
  ChevronDown,
  Building2,
  Users,
  Briefcase,
  X,
  Copy,
  Eye,
  EyeOff,
  Search,
  ExternalLink,
} from 'lucide-react';
import {
  activateImportedEmployee,
  commitDsnImportBatch,
  getDsnImportBatch,
  parseDsnImportFiles,
  revalidateDsnImportBatch,
  DSN_IMPORT_ACTION_LABELS,
  DSN_IMPORT_ITEM_TYPE_LABELS,
  DSN_IMPORT_REVIEW_REASON_LABELS,
  type DsnImportActionsSummary,
  type DsnImportAnomaly,
  type DsnImportBatchDetail,
  type DsnImportBatchStatus,
  type DsnImportCommitResponse,
  type DsnImportItemPreview,
  type DsnImportParseResponse,
  type ImportedEmployeeSummary,
} from '@/api/dsnImport';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { SharkFinBootProgress } from '@/components/SharkFinBootProgress';
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
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';
import { DsnImportHistory } from './DsnImportHistory';
import {
  buildCumulsSummaryFromItems,
  CumulsSummaryCard,
  type CumulsSummary,
} from './CumulsSummaryCard';

type Step = 'upload' | 'preview' | 'committing' | 'result';

type EmployeeFilter = 'all' | 'review' | 'edited';

const STEP_LABELS: Record<'upload' | 'preview' | 'result', string> = {
  upload: 'Dépôt',
  preview: 'Analyse',
  result: 'Import',
};

const STORAGE_KEY = 'eywai.dsn-import.active';

type PersistedState = { batchId: string; step: Step };

function loadPersisted(): PersistedState | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedState;
    return parsed?.batchId ? parsed : null;
  } catch {
    return null;
  }
}

function persistState(state: PersistedState | null): void {
  try {
    if (state) localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* stockage indisponible : on ignore silencieusement */
  }
}

function buildParseResultFromDetail(
  detail: DsnImportBatchDetail,
  batchId: string,
): DsnImportParseResponse | null {
  const preview = (detail.preview ?? {}) as Record<string, unknown>;
  const items = (preview.items as DsnImportItemPreview[] | undefined) ?? [];
  return {
    batch_id: batchId,
    summary: detail.summary ?? {},
    anomalies: (preview.anomalies as DsnImportAnomaly[] | undefined) ?? [],
    items,
    can_commit: Boolean(preview.can_commit),
  };
}

function commitReportFromSummary(summary: Record<string, unknown>): DsnImportCommitResponse | null {
  const report = summary?.commit_report as DsnImportCommitResponse | undefined;
  if (!report) return null;
  return {
    stats: report.stats ?? {},
    errors: report.errors ?? [],
    group_id: report.group_id ?? null,
    companies: report.companies ?? {},
    imported_employees: report.imported_employees ?? [],
  };
}

function activationEmailsFromReport(report: DsnImportCommitResponse): Record<string, string> {
  const emails: Record<string, string> = {};
  (report.imported_employees ?? []).forEach((emp) => {
    const placeholder = emp.placeholder_email ?? '';
    emails[emp.employee_id] = placeholder.includes('@dsn-import.local') ? '' : placeholder;
  });
  return emails;
}

const MONTHS_FR = [
  'janvier',
  'février',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'août',
  'septembre',
  'octobre',
  'novembre',
  'décembre',
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

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

function truncateNir(nir: unknown): string {
  const s = String(nir ?? '');
  if (!s || s === '—') return '—';
  const clean = s.replace(/\s/g, '');
  if (clean.length <= 4) return clean;
  return `…${clean.slice(-4)}`;
}

function validateFieldInline(itemType: string, field: string, value: string): string | null {
  const v = value.trim();
  if (!v) return null;
  if (field === 'siren') {
    const clean = v.replace(/\s/g, '');
    if (clean.length !== 9 || !/^\d+$/.test(clean)) return 'SIREN : 9 chiffres attendus';
  }
  if (field === 'siret') {
    const clean = v.replace(/\s/g, '');
    if (clean.length !== 14 || !/^\d+$/.test(clean)) return 'SIRET : 14 chiffres attendus';
  }
  if (field === 'nir' && itemType === 'employee') {
    const clean = v.replace(/\s/g, '');
    if (!/^\d+$/.test(clean) || (clean.length !== 13 && clean.length !== 15)) {
      return 'NIR : 13 ou 15 chiffres attendus';
    }
  }
  if (field === 'email' && v && !v.includes('@')) return 'Email invalide';
  return null;
}

const SECTION_ICONS: Record<string, typeof Building2> = {
  group: Building2,
  establishment: Building2,
  collective_agreement: Briefcase,
  employee: Users,
};

export function DsnImportWizard() {
  const { toast } = useToast();
  const [step, setStep] = useState<Step>('upload');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [parseResult, setParseResult] = useState<DsnImportParseResponse | null>(null);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [payloadEdits, setPayloadEdits] = useState<Record<string, Record<string, string>>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, Record<string, string>>>({});
  const [expandedRows, setExpandedRows] = useState<Record<string, boolean>>({});
  const [employeesOpen, setEmployeesOpen] = useState(false);
  const [cumulsOpen, setCumulsOpen] = useState(false);
  const [commitReport, setCommitReport] = useState<DsnImportCommitResponse | null>(null);
  const [activationEmails, setActivationEmails] = useState<Record<string, string>>({});
  const [activatedIds, setActivatedIds] = useState<Record<string, string>>({});
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [employeeFilter, setEmployeeFilter] = useState<EmployeeFilter>('all');
  const [employeeSearch, setEmployeeSearch] = useState('');
  const [showAdvancedActions, setShowAdvancedActions] = useState(false);
  const [analyzedFileNames, setAnalyzedFileNames] = useState<string[]>([]);
  const [activeBatchId, setActiveBatchId] = useState<string | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});

  const finalizeResult = useCallback(
    (report: DsnImportCommitResponse, batchId: string) => {
      setCommitReport(report);
      setActivationEmails(activationEmailsFromReport(report));
      setActivatedIds({});
      setConfirmOpen(false);
      setStep('result');
      persistState({ batchId, step: 'result' });
    },
    [],
  );

  const parseMutation = useMutation({
    mutationFn: (files: File[]) => parseDsnImportFiles(files),
    onSuccess: (data) => {
      setParseResult(data);
      const initial: Record<string, string> = {};
      data.items.forEach((it) => {
        initial[it.source_ref] = it.action;
      });
      setOverrides(initial);
      setPayloadEdits({});
      setFieldErrors({});
      setExpandedRows({});
      setEmployeesOpen(true);
      setCumulsOpen(true);
      setActiveBatchId(data.batch_id);
      persistState({ batchId: data.batch_id, step: 'preview' });
      setStep('preview');
    },
    onError: (err: Error) => {
      toast({ title: 'Erreur', description: err.message, variant: 'destructive' });
    },
  });

  const revalidateMutation = useMutation({
    mutationFn: (edits: Record<string, Record<string, string>>) => {
      if (!parseResult) throw new Error('Aucune analyse');
      return revalidateDsnImportBatch(parseResult.batch_id, edits);
    },
    onSuccess: (data) => {
      setParseResult((prev) =>
        prev
          ? {
              ...prev,
              anomalies: data.anomalies,
              can_commit: data.can_commit,
              summary: { ...prev.summary, ...data.summary },
            }
          : prev,
      );
    },
  });

  const commitMutation = useMutation({
    mutationFn: () => {
      if (!parseResult) throw new Error('Aucune analyse en cours');
      return commitDsnImportBatch(parseResult.batch_id, overrides, payloadEdits);
    },
    onSuccess: (data) => {
      setConfirmOpen(false);
      setActiveBatchId(data.batch_id);
      persistState({ batchId: data.batch_id, step: 'committing' });
      setStep('committing');
      toast({
        title: 'Import lancé',
        description: 'Vous pouvez quitter ou recharger la page : il continue en arrière-plan.',
      });
    },
    onError: (err: Error) => {
      toast({ title: 'Échec du commit', description: err.message, variant: 'destructive' });
    },
  });

  // Suivi de l'import en arrière-plan : on interroge le batch jusqu'à committed | failed.
  const pollQuery = useQuery({
    queryKey: ['dsn-import-poll', activeBatchId],
    queryFn: () => getDsnImportBatch(activeBatchId as string),
    enabled: step === 'committing' && Boolean(activeBatchId),
    refetchInterval: (query) => {
      const status = query.state.data?.batch?.status as DsnImportBatchStatus | undefined;
      return status === 'committed' || status === 'failed' ? false : 2500;
    },
  });

  useEffect(() => {
    if (step !== 'committing') return;
    const detail = pollQuery.data;
    if (!detail) return;
    const status = detail.batch.status as DsnImportBatchStatus;
    if (status !== 'committed' && status !== 'failed') return;
    const batchId = activeBatchId as string;
    const report =
      commitReportFromSummary(detail.summary ?? {}) ?? {
        stats: { created: 0, updated: 0, skipped: 0, failed: 0 },
        errors: status === 'failed' ? ["L'import a échoué."] : [],
        group_id: null,
        companies: {},
        imported_employees: [],
      };
    finalizeResult(report, batchId);
    if (status === 'committed') {
      toast({ title: 'Import terminé', description: 'Le dossier a été reconstruit.' });
    } else {
      toast({ title: "Échec de l'import", description: 'Consultez le détail.', variant: 'destructive' });
    }
  }, [pollQuery.data, step, activeBatchId, finalizeResult, toast]);

  // Restauration au montage : reprise d'un import en cours ou affichage du résultat terminé.
  useEffect(() => {
    const persisted = loadPersisted();
    if (!persisted?.batchId) {
      setIsRestoring(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const detail = await getDsnImportBatch(persisted.batchId);
        if (cancelled) return;
        const status = detail.batch.status as DsnImportBatchStatus;
        setActiveBatchId(persisted.batchId);

        if (status === 'committed' || status === 'failed') {
          const report = commitReportFromSummary(detail.summary ?? {});
          if (report) {
            setCommitReport(report);
            setActivationEmails(activationEmailsFromReport(report));
            setStep('result');
          } else {
            persistState(null);
          }
        } else if (status === 'committing') {
          const pr = buildParseResultFromDetail(detail, persisted.batchId);
          if (pr) setParseResult(pr);
          setStep('committing');
        } else if (status === 'previewed') {
          const pr = buildParseResultFromDetail(detail, persisted.batchId);
          if (pr && pr.items.length) {
            setParseResult(pr);
            const initial: Record<string, string> = {};
            pr.items.forEach((it) => {
              initial[it.source_ref] = it.action;
            });
            setOverrides(initial);
            setEmployeesOpen(true);
            setCumulsOpen(true);
            setStep('preview');
          } else {
            persistState(null);
          }
        } else {
          persistState(null);
        }
      } catch {
        persistState(null);
      } finally {
        if (!cancelled) setIsRestoring(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files ? Array.from(e.target.files) : [];
    setSelectedFiles(list);
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setSelectedFiles(Array.from(e.dataTransfer.files));
  }, []);

  const removeFile = useCallback((index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const goBackToUpload = useCallback(() => {
    persistState(null);
    setActiveBatchId(null);
    setStep('upload');
  }, []);

  const resetWizard = useCallback(() => {
    persistState(null);
    setActiveBatchId(null);
    setStep('upload');
    setParseResult(null);
    setSelectedFiles([]);
    setAnalyzedFileNames([]);
    setCommitReport(null);
    setActivationEmails({});
    setActivatedIds({});
    setConfirmOpen(false);
  }, []);

  const getPayloadValue = useCallback(
    (item: DsnImportItemPreview, field: string): string => {
      const edit = payloadEdits[item.source_ref]?.[field];
      if (edit !== undefined) return edit;
      const val = item.mapped_payload[field];
      return val == null ? '' : String(val);
    },
    [payloadEdits],
  );

  const setPayloadValue = useCallback(
    (item: DsnImportItemPreview, field: string, value: string) => {
      const sourceRef = item.source_ref;
      setPayloadEdits((prev) => ({
        ...prev,
        [sourceRef]: { ...(prev[sourceRef] ?? {}), [field]: value },
      }));
      const err = validateFieldInline(item.item_type, field, value);
      setFieldErrors((prev) => {
        const next = { ...prev, [sourceRef]: { ...(prev[sourceRef] ?? {}) } };
        if (err) next[sourceRef][field] = err;
        else delete next[sourceRef][field];
        if (Object.keys(next[sourceRef]).length === 0) delete next[sourceRef];
        return next;
      });
    },
    [],
  );

  const getItemLabel = useCallback(
    (item: DsnImportItemPreview): string => {
      if (item.item_type === 'employee') {
        const name = `${getPayloadValue(item, 'first_name')} ${getPayloadValue(item, 'last_name')}`.trim();
        if (name) return name;
      }
      if (item.item_type === 'group') {
        return getPayloadValue(item, 'group_name') || item.label || item.source_ref;
      }
      if (item.item_type === 'establishment') {
        return getPayloadValue(item, 'company_name') || item.label || item.source_ref;
      }
      return item.label ?? item.source_ref;
    },
    [getPayloadValue],
  );

  const toggleRow = useCallback((sourceRef: string) => {
    setExpandedRows((prev) => ({ ...prev, [sourceRef]: !prev[sourceRef] }));
  }, []);

  const scrollToRef = useCallback((sourceRef: string) => {
    const el = rowRefs.current[sourceRef];
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      setExpandedRows((prev) => ({ ...prev, [sourceRef]: true }));
    }
  }, []);

  useEffect(() => {
    if (!parseResult || Object.keys(payloadEdits).length === 0) return;
    const hasKeyEdits = Object.entries(payloadEdits).some(([ref, edits]) => {
      const item = parseResult.items.find((i) => i.source_ref === ref);
      if (!item) return false;
      return Object.keys(edits).some((f) =>
        ['siren', 'siret', 'nir'].includes(f),
      );
    });
    if (!hasKeyEdits) return;
    const timer = setTimeout(() => {
      revalidateMutation.mutate(payloadEdits);
    }, 600);
    return () => clearTimeout(timer);
  }, [payloadEdits, parseResult]);

  const blockingCount = useMemo(
    () => parseResult?.anomalies.filter((a) => a.severity === 'blocking').length ?? 0,
    [parseResult],
  );

  const warningCount = useMemo(
    () => parseResult?.anomalies.filter((a) => a.severity !== 'blocking').length ?? 0,
    [parseResult],
  );

  const reviewCount = useMemo(
    () => parseResult?.items.filter((i) => i.item_type === 'employee' && i.needs_review).length ?? 0,
    [parseResult],
  );

  const editCount = useMemo(() => Object.keys(payloadEdits).length, [payloadEdits]);

  const hasFieldErrors = useMemo(
    () => Object.values(fieldErrors).some((fields) => Object.keys(fields).length > 0),
    [fieldErrors],
  );

  const cumulItems = useMemo(
    () => parseResult?.items.filter((i) => i.item_type === 'cumul') ?? [],
    [parseResult],
  );

  const cumulsSummary = useMemo((): CumulsSummary | null => {
    const fromServer = parseResult?.summary?.cumuls_summary as CumulsSummary | undefined;
    if (fromServer?.by_period?.length) return fromServer;
    return buildCumulsSummaryFromItems(cumulItems);
  }, [parseResult, cumulItems]);

  const actionsSummary = parseResult?.summary?.actions_summary as DsnImportActionsSummary | undefined;

  const groupedItems = useMemo(() => {
    if (!parseResult) return {};
    return parseResult.items.reduce<Record<string, DsnImportItemPreview[]>>((acc, it) => {
      if (it.item_type === 'cumul') return acc;
      if (it.item_type === 'group' && it.is_scaffold) return acc;
      acc[it.item_type] = acc[it.item_type] || [];
      acc[it.item_type].push(it);
      return acc;
    }, {});
  }, [parseResult]);

  const hasScaffoldGroup = useMemo(
    () => parseResult?.items.some((i) => i.item_type === 'group' && i.is_scaffold) ?? false,
    [parseResult],
  );

  const sectionOrder = useMemo(() => {
    const base: string[] = ['establishment', 'collective_agreement', 'employee'];
    if ((groupedItems.group?.length ?? 0) > 0) {
      return ['group', ...base];
    }
    return base;
  }, [groupedItems]);

  const filteredEmployees = useMemo(() => {
    const employees = groupedItems.employee ?? [];
    let list = employees;
    if (employeeFilter === 'review') {
      list = list.filter((e) => e.needs_review);
    } else if (employeeFilter === 'edited') {
      list = list.filter((e) => Boolean(payloadEdits[e.source_ref]));
    }
    const q = employeeSearch.trim().toLowerCase();
    if (q) {
      list = list.filter((e) => getItemLabel(e).toLowerCase().includes(q));
    }
    return list;
  }, [groupedItems.employee, employeeFilter, employeeSearch, payloadEdits, getItemLabel]);

  const canCommit =
    !commitMutation.isPending &&
    !hasFieldErrors &&
    (parseResult?.can_commit ?? true) &&
    !(blockingCount > 0 && editCount === 0);

  const commitBlockReason = useMemo(() => {
    if (hasFieldErrors) return 'Corrigez les champs invalides (SIREN, SIRET, NIR) avant validation.';
    if (blockingCount > 0 && editCount === 0) {
      return `${blockingCount} anomalie(s) bloquante(s) — corrigez ou éditez les lignes concernées.`;
    }
    if (parseResult && !parseResult.can_commit) return 'Import bloqué par des anomalies non résolues.';
    return null;
  }, [hasFieldErrors, blockingCount, editCount, parseResult]);

  const commitProgress = (pollQuery.data?.summary?.commit_progress ??
    parseResult?.summary?.commit_progress) as
    | {
        done: number;
        total: number;
        percent: number;
        phase_label?: string;
        label?: string | null;
      }
    | undefined;

  const handleAnalyze = () => {
    setAnalyzedFileNames(selectedFiles.map((f) => f.name));
    parseMutation.mutate(selectedFiles);
  };

  if (isRestoring) {
    return (
      <Card>
        <CardContent className="flex items-center gap-3 py-10 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Reprise de la session d&apos;import…
        </CardContent>
      </Card>
    );
  }

  return (
    <TooltipProvider>
      <div className={cn('space-y-6', step === 'preview' && 'pb-24')}>
        <StepIndicator current={step} fileNames={step === 'preview' ? analyzedFileNames : undefined} />

        {step === 'committing' && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Loader2 className="h-5 w-5 animate-spin text-primary" />
                Import en cours…
              </CardTitle>
              <CardDescription>
                Création du dossier paie (entreprise, salariés, conventions, cumuls). Vous pouvez
                quitter ou recharger cette page : l&apos;import se poursuit en arrière-plan et le
                résultat s&apos;affichera automatiquement à votre retour.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="space-y-2">
                <SharkFinBootProgress
                  value={commitProgress?.percent ?? 0}
                  determinate={Boolean(commitProgress)}
                />
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="flex min-w-0 items-center gap-1.5 text-muted-foreground">
                    {commitProgress?.phase_label ?? 'Préparation…'}
                    {commitProgress?.label && (
                      <span className="truncate text-foreground/70">— {commitProgress.label}</span>
                    )}
                  </span>
                  {commitProgress && (
                    <span className="shrink-0 tabular-nums text-muted-foreground">
                      {commitProgress.done}/{commitProgress.total} • {commitProgress.percent}%
                    </span>
                  )}
                </div>
              </div>

              {parseResult && (
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <Stat label="SIREN" value={String(parseResult.summary.siren ?? '—')} />
                  <Stat
                    label="Période"
                    value={formatPeriod(
                      parseResult.summary.period_min as string | undefined,
                      parseResult.summary.period_max as string | undefined,
                    )}
                  />
                  <Stat label="Salariés" value={String(parseResult.summary.employee_count ?? 0)} />
                  {actionsSummary && (
                    <Stat
                      label="Actions prévues"
                      value={`${actionsSummary.totals.create} créer / ${actionsSummary.totals.update} MAJ`}
                    />
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {step === 'upload' && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-lg">
                <Upload className="h-5 w-5" />
                Déposer les fichiers DSN
              </CardTitle>
              <CardDescription>
                Format plat NEODeS — un ou plusieurs fichiers mensuels acceptés.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div
                className="flex min-h-[180px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed border-muted-foreground/30 bg-muted/20 p-6 text-center transition hover:border-primary/50 hover:bg-muted/30"
                onDragOver={(e) => e.preventDefault()}
                onDrop={onDrop}
                onClick={() => document.getElementById('dsn-import-input')?.click()}
              >
                <FileText className="mb-3 h-10 w-10 text-muted-foreground" />
                <p className="text-sm font-medium">Glissez vos fichiers ici</p>
                <p className="mt-1 text-xs text-muted-foreground">ou cliquez pour parcourir (.txt, .dsn, .edi)</p>
                <input
                  id="dsn-import-input"
                  type="file"
                  multiple
                  accept=".txt,.dsn,.edi"
                  className="hidden"
                  onChange={onFileChange}
                />
              </div>
              {selectedFiles.length > 12 && (
                <p className="text-xs text-muted-foreground">
                  Les cumuls seront reconstruits sur la période couverte par vos fichiers.
                </p>
              )}
              {selectedFiles.length > 0 && (
                <ul className="space-y-1 rounded-md border bg-muted/30 px-3 py-2 text-sm">
                  {selectedFiles.map((f, i) => (
                    <li key={`${f.name}-${i}`} className="flex items-center justify-between gap-2">
                      <span className="truncate text-muted-foreground">{f.name}</span>
                      <span className="flex shrink-0 items-center gap-2 text-xs">
                        <span className="tabular-nums text-muted-foreground/80">{formatFileSize(f.size)}</span>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-6 w-6"
                          onClick={(e) => {
                            e.stopPropagation();
                            removeFile(i);
                          }}
                        >
                          <X className="h-3.5 w-3.5" />
                          <span className="sr-only">Retirer</span>
                        </Button>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              {parseMutation.isPending && (
                <div className="space-y-2 rounded-lg border bg-muted/20 p-4">
                  <SharkFinBootProgress />
                  <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Analyse {selectedFiles.length > 1 ? `des ${selectedFiles.length} fichiers` : 'du fichier'} en cours…
                  </div>
                </div>
              )}
              <div className="flex justify-end">
                <Button disabled={selectedFiles.length === 0 || parseMutation.isPending} onClick={handleAnalyze}>
                  {parseMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Analyser
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {step === 'preview' && parseResult && (
          <>
            <WizardNav onBack={goBackToUpload} backOnly />

            <Card>
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <CardTitle>Résumé de l&apos;analyse</CardTitle>
                    <CardDescription className="mt-1">
                      {parseResult.anomalies.length === 0
                        ? 'Aucune anomalie détectée — prêt à importer.'
                        : `${parseResult.anomalies.length} point(s) d'attention`}
                    </CardDescription>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {parseResult.summary.has_existing_dossier ? (
                      <Badge variant="outline" className="shrink-0 border-amber-300 bg-amber-50 text-amber-900">
                        Dossier existant
                      </Badge>
                    ) : null}
                    {parseResult.anomalies.length === 0 ? (
                      <Badge variant="secondary" className="shrink-0 gap-1 bg-emerald-50 text-emerald-800">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        OK
                      </Badge>
                    ) : blockingCount > 0 ? (
                      <Badge variant="destructive" className="shrink-0">
                        {blockingCount} bloquante{blockingCount > 1 ? 's' : ''}
                      </Badge>
                    ) : null}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
                <Stat label="SIREN" value={String(parseResult.summary.siren ?? '—')} />
                <Stat label="SIRET" value={String(parseResult.summary.siret ?? '—')} />
                <Stat
                  label="Période"
                  value={formatPeriod(
                    parseResult.summary.period_min as string | undefined,
                    parseResult.summary.period_max as string | undefined,
                  )}
                />
                <Stat label="Fichiers" value={String(parseResult.summary.file_count ?? analyzedFileNames.length)} />
                <Stat label="Entreprises" value={String(parseResult.summary.establishment_count ?? 0)} />
                <Stat label="Salariés" value={String(parseResult.summary.employee_count ?? 0)} />
                {parseResult.summary.primary_idcc != null && (
                  <Stat label="IDCC principal" value={String(parseResult.summary.primary_idcc)} />
                )}
                {actionsSummary && (
                  <Stat
                    label="Actions prévues"
                    value={`${actionsSummary.totals.create} créer / ${actionsSummary.totals.update} MAJ`}
                  />
                )}
              </CardContent>
              {(reviewCount > 0 || editCount > 0) && (
                <CardContent className="border-t pt-4">
                  <div className="flex flex-wrap gap-2 text-xs">
                    {reviewCount > 0 && (
                      <Badge variant="outline">{reviewCount} salarié(s) à vérifier</Badge>
                    )}
                    {editCount > 0 && (
                      <Badge variant="secondary">{editCount} modification(s) manuelle(s)</Badge>
                    )}
                  </div>
                </CardContent>
              )}
            </Card>

            {parseResult.anomalies.length > 0 && (
              <Card className="border-amber-200/80 bg-amber-50/30">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    Anomalies ({parseResult.anomalies.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="max-h-48 space-y-3 overflow-y-auto text-sm">
                  {blockingCount > 0 && (
                    <AnomalyGroup
                      title="Bloquantes"
                      anomalies={parseResult.anomalies.filter((a) => a.severity === 'blocking')}
                      onClickRef={scrollToRef}
                    />
                  )}
                  {warningCount > 0 && (
                    <AnomalyGroup
                      title="Avertissements"
                      anomalies={parseResult.anomalies.filter((a) => a.severity !== 'blocking')}
                      onClickRef={scrollToRef}
                    />
                  )}
                </CardContent>
              </Card>
            )}

            {cumulsSummary && (
              <CumulsSummaryCard
                summary={cumulsSummary}
                formatPeriod={formatPeriod}
                open={cumulsOpen}
                onOpenChange={setCumulsOpen}
              />
            )}

            {hasScaffoldGroup && (
              <p className="rounded-md border border-dashed bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                La DSN décrit une <strong className="font-medium text-foreground">entreprise</strong> (SIRET).
                Un conteneur groupe EYWAI est créé automatiquement en arrière-plan pour le rattachement
                plateforme — vous n&apos;avez rien à saisir à ce niveau.
              </p>
            )}

            <>
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-dashed bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                  <div className="flex items-center gap-2">
                    <Pencil className="h-3.5 w-3.5 shrink-0" />
                    Cliquez sur une ligne pour corriger une valeur avant validation.
                  </div>
                  <label className="flex cursor-pointer items-center gap-2 text-foreground">
                    <input
                      type="checkbox"
                      checked={showAdvancedActions}
                      onChange={(e) => setShowAdvancedActions(e.target.checked)}
                      className="rounded border"
                    />
                    Options avancées (actions par ligne)
                  </label>
                </div>

                {sectionOrder.map((type) => {
                  const items = type === 'employee' ? filteredEmployees : groupedItems[type];
                  if (!items?.length && type !== 'employee') return null;
                  if (type === 'employee' && !(groupedItems.employee?.length ?? 0)) return null;

                  const isEmployees = type === 'employee';
                  const SectionIcon = SECTION_ICONS[type] ?? FileText;
                  const totalEmployees = groupedItems.employee?.length ?? 0;

                  const table = (
                    <ItemsTable
                      items={items}
                      expandedRows={expandedRows}
                      payloadEdits={payloadEdits}
                      fieldErrors={fieldErrors}
                      overrides={overrides}
                      getItemLabel={getItemLabel}
                      getPayloadValue={getPayloadValue}
                      setPayloadValue={setPayloadValue}
                      setOverrides={setOverrides}
                      toggleRow={toggleRow}
                      showActionColumn={showAdvancedActions}
                      rowRefs={rowRefs}
                    />
                  );

                  if (isEmployees) {
                    return (
                      <Collapsible key={type} open={employeesOpen} onOpenChange={setEmployeesOpen}>
                        <Card>
                          <CollapsibleTrigger asChild>
                            <button
                              type="button"
                              className="flex w-full items-center justify-between px-6 py-4 text-left hover:bg-muted/30"
                            >
                              <div className="flex items-center gap-2">
                                <SectionIcon className="h-4 w-4 text-muted-foreground" />
                                <span className="font-semibold">
                                  {DSN_IMPORT_ITEM_TYPE_LABELS[type]} ({totalEmployees})
                                </span>
                                {reviewCount > 0 && (
                                  <Badge variant="outline" className="ml-1 font-normal">
                                    {reviewCount} à vérifier
                                  </Badge>
                                )}
                              </div>
                              <ChevronDown
                                className={cn(
                                  'h-4 w-4 text-muted-foreground transition-transform',
                                  employeesOpen && 'rotate-180',
                                )}
                              />
                            </button>
                          </CollapsibleTrigger>
                          <CollapsibleContent>
                            <CardContent className="space-y-3 border-t pt-4">
                              <div className="flex flex-wrap items-center gap-2">
                                <div className="relative min-w-[180px] flex-1">
                                  <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
                                  <Input
                                    placeholder="Rechercher un nom…"
                                    className="h-8 pl-8 text-sm"
                                    value={employeeSearch}
                                    onChange={(e) => setEmployeeSearch(e.target.value)}
                                  />
                                </div>
                                <Select
                                  value={employeeFilter}
                                  onValueChange={(v) => setEmployeeFilter(v as EmployeeFilter)}
                                >
                                  <SelectTrigger className="h-8 w-[160px]">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="all">Tous</SelectItem>
                                    <SelectItem value="review">À vérifier</SelectItem>
                                    <SelectItem value="edited">Modifiés</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                              {filteredEmployees.length === 0 ? (
                                <p className="py-4 text-sm text-muted-foreground">Aucun salarié pour ce filtre.</p>
                              ) : (
                                table
                              )}
                            </CardContent>
                          </CollapsibleContent>
                        </Card>
                      </Collapsible>
                    );
                  }

                  return (
                    <Card key={type}>
                      <CardHeader className="pb-3">
                        <CardTitle className="flex items-center gap-2 text-base">
                          <SectionIcon className="h-4 w-4 text-muted-foreground" />
                          {DSN_IMPORT_ITEM_TYPE_LABELS[type] ?? type} ({items.length})
                        </CardTitle>
                      </CardHeader>
                      <CardContent>{table}</CardContent>
                    </Card>
                  );
                })}
            </>

            <StickyPreviewFooter
              onBack={goBackToUpload}
              onCommit={() => setConfirmOpen(true)}
              primaryDisabled={!canCommit}
              primaryLoading={commitMutation.isPending}
              blockReason={commitBlockReason}
            />

            <CommitConfirmDialog
              open={confirmOpen}
              onOpenChange={setConfirmOpen}
              onConfirm={() => commitMutation.mutate()}
              loading={commitMutation.isPending}
              summary={parseResult.summary}
              actionsSummary={actionsSummary}
              employeeCount={parseResult.summary.employee_count as number}
              reviewCount={reviewCount}
              periodLabel={formatPeriod(
                parseResult.summary.period_min as string | undefined,
                parseResult.summary.period_max as string | undefined,
              )}
            />
          </>
        )}

        {step === 'result' && commitReport && (
          <>
            <WizardNav onBack={resetWizard} backLabel="Nouvel import" />

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  Import terminé
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <div className="flex flex-wrap gap-4">
                  <span>
                    <strong>{commitReport.stats.created ?? 0}</strong> créé(s)
                  </span>
                  <span>
                    <strong>{commitReport.stats.updated ?? 0}</strong> mis à jour
                  </span>
                  <span>
                    <strong>{commitReport.stats.skipped ?? 0}</strong> ignoré(s)
                  </span>
                </div>
                {(commitReport.group_id || Object.keys(commitReport.companies).length > 0) && (
                  <div className="rounded-lg border bg-muted/30 p-3">
                    <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Accès rapide
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {commitReport.group_id && (
                        <Button variant="outline" size="sm" asChild>
                          <Link to={`/super-admin/groups/${commitReport.group_id}`}>
                            <ExternalLink className="mr-2 h-3.5 w-3.5" />
                            Voir le groupe
                          </Link>
                        </Button>
                      )}
                      {Object.entries(commitReport.companies).map(([siret, companyId]) => (
                        <Button key={siret} variant="outline" size="sm" asChild>
                          <Link to={`/super-admin/companies?highlight=${companyId}`}>
                            <ExternalLink className="mr-2 h-3.5 w-3.5" />
                            Établissement {siret.slice(-5)}
                          </Link>
                        </Button>
                      ))}
                    </div>
                  </div>
                )}
                {commitReport.errors.length > 0 && (
                  <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-destructive">
                    {commitReport.errors.map((e, i) => (
                      <p key={i}>{e}</p>
                    ))}
                  </div>
                )}
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

            <WizardNav onBack={resetWizard} backLabel="Nouvel import" />
          </>
        )}

        {step !== 'preview' && <DsnImportHistory />}
      </div>
    </TooltipProvider>
  );
}

function AnomalyGroup({
  title,
  anomalies,
  onClickRef,
}: {
  title: string;
  anomalies: { message: string; severity: string; source_ref?: string | null }[];
  onClickRef: (ref: string) => void;
}) {
  if (!anomalies.length) return null;
  return (
    <div>
      <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      <ul className="space-y-1">
        {anomalies.map((a, i) => (
          <li key={i}>
            {a.source_ref ? (
              <button
                type="button"
                className={cn(
                  'text-left leading-snug underline decoration-dotted underline-offset-2 hover:text-foreground',
                  a.severity === 'blocking' ? 'text-destructive' : 'text-muted-foreground',
                )}
                onClick={() => onClickRef(a.source_ref!)}
              >
                {a.message}
              </button>
            ) : (
              <span
                className={cn(
                  'leading-snug',
                  a.severity === 'blocking' ? 'text-destructive' : 'text-muted-foreground',
                )}
              >
                {a.message}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function CommitConfirmDialog({
  open,
  onOpenChange,
  onConfirm,
  loading,
  summary,
  actionsSummary,
  employeeCount,
  reviewCount,
  periodLabel,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  loading: boolean;
  summary: Record<string, unknown>;
  actionsSummary?: DsnImportActionsSummary;
  employeeCount: number;
  reviewCount: number;
  periodLabel: string;
}) {
  const create = actionsSummary?.totals.create ?? 0;
  const update = actionsSummary?.totals.update ?? 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirmer l&apos;import DSN</DialogTitle>
          <DialogDescription>
            Cette action est irréversible : elle créera ou mettra à jour le dossier paie en base.
          </DialogDescription>
        </DialogHeader>
        <ul className="space-y-2 text-sm">
          <li>
            <strong>Période :</strong> {periodLabel}
          </li>
          <li>
            <strong>SIREN :</strong> {String(summary.siren ?? '—')}
          </li>
          <li>
            <strong>Salariés :</strong> {employeeCount}
          </li>
          <li>
            <strong>Actions :</strong> {create} création(s), {update} mise(s) à jour
          </li>
          {reviewCount > 0 && (
            <li className="flex items-start gap-2 text-amber-800">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              {reviewCount} salarié(s) marqué(s) à vérifier — l&apos;import reste possible.
            </li>
          )}
        </ul>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            Annuler
          </Button>
          <Button onClick={onConfirm} disabled={loading}>
            {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            Confirmer l&apos;import
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function StickyPreviewFooter({
  onBack,
  onCommit,
  primaryDisabled,
  primaryLoading,
  blockReason,
}: {
  onBack: () => void;
  onCommit: () => void;
  primaryDisabled: boolean;
  primaryLoading: boolean;
  blockReason: string | null;
}) {
  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t bg-background/95 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <div className="mx-auto flex max-w-5xl flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" className="-ml-2 h-9 text-muted-foreground" onClick={onBack}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Retour
          </Button>
          {blockReason && primaryDisabled && (
            <p className="text-xs text-destructive">{blockReason}</p>
          )}
        </div>
        <Button disabled={primaryDisabled} onClick={onCommit}>
          {primaryLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Valider l&apos;import
        </Button>
      </div>
    </div>
  );
}

function StepIndicator({
  current,
  fileNames,
}: {
  current: Step;
  fileNames?: string[];
}) {
  const steps: Array<'upload' | 'preview' | 'result'> = ['upload', 'preview', 'result'];
  // 'committing' partage la dernière étape visuelle (« Import »).
  const effective = current === 'committing' ? 'result' : current;
  const currentIdx = steps.indexOf(effective);

  return (
    <div className="space-y-2">
      <nav aria-label="Étapes import DSN" className="flex items-center gap-2">
        {steps.map((s, i) => {
          const done = i < currentIdx;
          const active = s === current;
          return (
            <Fragment key={s}>
              {i > 0 && (
                <div
                  className={cn('h-px flex-1 max-w-8', done || active ? 'bg-primary/40' : 'bg-border')}
                />
              )}
              <div
                className={cn(
                  'flex items-center gap-1.5 text-xs',
                  active ? 'font-medium text-foreground' : 'text-muted-foreground',
                )}
              >
                <span
                  className={cn(
                    'flex h-6 w-6 items-center justify-center rounded-full border text-[11px]',
                    active && 'border-primary bg-primary text-primary-foreground',
                    done && !active && 'border-primary/50 bg-primary/10 text-primary',
                    !active && !done && 'border-muted-foreground/30',
                  )}
                >
                  {done ? '✓' : i + 1}
                </span>
                <span className="hidden sm:inline">{STEP_LABELS[s]}</span>
              </div>
            </Fragment>
          );
        })}
      </nav>
      {fileNames && fileNames.length > 0 && (
        <p className="truncate text-xs text-muted-foreground">
          Fichiers : {fileNames.join(', ')}
        </p>
      )}
    </div>
  );
}

function WizardNav({
  onBack,
  onPrimary,
  primaryLabel,
  primaryDisabled,
  primaryLoading,
  showPrimary = false,
  backOnly = false,
  backLabel = 'Retour',
}: {
  onBack: () => void;
  onPrimary?: () => void;
  primaryLabel?: string;
  primaryDisabled?: boolean;
  primaryLoading?: boolean;
  showPrimary?: boolean;
  backOnly?: boolean;
  backLabel?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <Button variant="ghost" size="sm" className="-ml-2 h-9 text-muted-foreground" onClick={onBack}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        {backLabel}
      </Button>
      {!backOnly && showPrimary && onPrimary && (
        <Button disabled={primaryDisabled} onClick={onPrimary}>
          {primaryLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          {primaryLabel}
        </Button>
      )}
    </div>
  );
}

function ItemsTable({
  items,
  expandedRows,
  payloadEdits,
  fieldErrors,
  overrides,
  getItemLabel,
  getPayloadValue,
  setPayloadValue,
  setOverrides,
  toggleRow,
  showActionColumn,
  rowRefs,
}: {
  items: DsnImportItemPreview[];
  expandedRows: Record<string, boolean>;
  payloadEdits: Record<string, Record<string, string>>;
  fieldErrors: Record<string, Record<string, string>>;
  overrides: Record<string, string>;
  getItemLabel: (item: DsnImportItemPreview) => string;
  getPayloadValue: (item: DsnImportItemPreview, field: string) => string;
  setPayloadValue: (item: DsnImportItemPreview, field: string, value: string) => void;
  setOverrides: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  toggleRow: (sourceRef: string) => void;
  showActionColumn: boolean;
  rowRefs: React.MutableRefObject<Record<string, HTMLTableRowElement | null>>;
}) {
  const isEmployeeList = items[0]?.item_type === 'employee';

  return (
    <div className={cn(isEmployeeList && items.length > 8 && 'max-h-[420px] overflow-y-auto')}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Libellé</TableHead>
            {isEmployeeList && (
              <>
                <TableHead className="w-[72px]">NIR</TableHead>
                <TableHead className="hidden md:table-cell">Poste</TableHead>
                <TableHead className="hidden lg:table-cell w-[100px]">Embauche</TableHead>
              </>
            )}
            {showActionColumn && (
              <TableHead className="w-[168px]">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="cursor-help underline decoration-dotted underline-offset-2">
                      Action
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    Mettre à jour si le SIREN/SIRET/NIR existe déjà en base
                  </TooltipContent>
                </Tooltip>
              </TableHead>
            )}
            <TableHead className="w-[180px]">Info</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((it) => {
            const editable = it.editable_fields ?? {};
            const isExpanded = expandedRows[it.source_ref];
            const hasEdits = Boolean(payloadEdits[it.source_ref]);
            const canEdit = Object.keys(editable).length > 0;
            const cols = it.preview_columns ?? {};
            const colSpan =
              2 +
              (isEmployeeList ? 3 : 0) +
              (showActionColumn ? 1 : 0);

            return (
              <Fragment key={it.source_ref}>
                <TableRow
                  ref={(el) => {
                    rowRefs.current[it.source_ref] = el;
                  }}
                  className={cn(canEdit && 'cursor-pointer hover:bg-muted/40')}
                  onClick={() => canEdit && toggleRow(it.source_ref)}
                >
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{getItemLabel(it)}</span>
                      {hasEdits && (
                        <Badge variant="secondary" className="text-[10px] font-normal">
                          modifié
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  {isEmployeeList && (
                    <>
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        {truncateNir(cols.nir ?? getPayloadValue(it, 'nir'))}
                      </TableCell>
                      <TableCell className="hidden max-w-[140px] truncate text-xs md:table-cell">
                        {String(cols.job_title ?? getPayloadValue(it, 'job_title') ?? '—')}
                      </TableCell>
                      <TableCell className="hidden text-xs lg:table-cell">
                        {String(cols.hire_date ?? getPayloadValue(it, 'hire_date') ?? '—')}
                      </TableCell>
                    </>
                  )}
                  {showActionColumn && (
                    <TableCell onClick={(e) => e.stopPropagation()}>
                      <Select
                        value={overrides[it.source_ref] ?? it.action}
                        onValueChange={(v) =>
                          setOverrides((prev) => ({ ...prev, [it.source_ref]: v }))
                        }
                      >
                        <SelectTrigger className="h-8 w-full">
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
                  )}
                  <TableCell>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {(it.review_reasons ?? []).map((reason) => (
                        <Badge key={reason} variant="outline" className="font-normal text-[10px]">
                          {DSN_IMPORT_REVIEW_REASON_LABELS[reason] ?? reason}
                        </Badge>
                      ))}
                      {!it.review_reasons?.length && it.needs_review && (
                        <Badge variant="outline" className="font-normal">
                          À vérifier
                        </Badge>
                      )}
                      {it.employee_count != null && (
                        <span className="text-xs text-muted-foreground">
                          {it.employee_count} sal.
                        </span>
                      )}
                      {canEdit && (
                        <span
                          className={cn(
                            'inline-flex items-center gap-0.5 text-xs text-muted-foreground',
                            !isExpanded && 'underline decoration-dotted underline-offset-2',
                          )}
                        >
                          <Pencil className="h-3 w-3" />
                          {isExpanded ? 'fermer' : 'éditer'}
                        </span>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
                {isExpanded && canEdit && (
                  <TableRow className="bg-muted/20 hover:bg-muted/20">
                    <TableCell colSpan={colSpan} onClick={(e) => e.stopPropagation()}>
                      <div className="grid gap-3 py-2 sm:grid-cols-2 lg:grid-cols-3">
                        {Object.entries(editable).map(([field, label]) => {
                          const err = fieldErrors[it.source_ref]?.[field];
                          return (
                            <label key={field} className="space-y-1.5">
                              <span className="text-xs font-medium text-muted-foreground">{label}</span>
                              <Input
                                className={cn(
                                  'h-8 border-dashed bg-background text-sm',
                                  err && 'border-destructive',
                                )}
                                value={getPayloadValue(it, field)}
                                onChange={(e) => setPayloadValue(it, field, e.target.value)}
                              />
                              {err && <span className="text-[11px] text-destructive">{err}</span>}
                            </label>
                          );
                        })}
                      </div>
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2.5">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums">{value}</p>
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
  const [search, setSearch] = useState('');
  const [visiblePasswords, setVisiblePasswords] = useState<Record<string, boolean>>({});

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return employees;
    return employees.filter((e) => e.full_name.toLowerCase().includes(q));
  }, [employees, search]);

  const exportCsv = () => {
    const rows = [
      ['Nom', 'Email', 'Statut'],
      ...employees.map((e) => [
        e.full_name,
        emails[e.employee_id] ?? '',
        activatedIds[e.employee_id] ? 'Compte actif' : 'En onboarding',
      ]),
    ];
    const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(';')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'salaries-import-dsn.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

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
        description: `${emp.full_name} — mot de passe généré.`,
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

  const copyPassword = async (password: string) => {
    try {
      await navigator.clipboard.writeText(password);
      toast({ title: 'Copié', description: 'Mot de passe copié dans le presse-papiers.' });
    } catch {
      toast({ title: 'Erreur', description: 'Impossible de copier.', variant: 'destructive' });
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <UserPlus className="h-4 w-4" />
              Activation des comptes salariés ({employees.length})
            </CardTitle>
            <CardDescription>
              Les salariés importés sont en brouillon. Créez leur compte quand vous avez leur email
              professionnel.
            </CardDescription>
          </div>
          <Button variant="outline" size="sm" onClick={exportCsv}>
            Export CSV
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="relative max-w-sm">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            placeholder="Rechercher un salarié…"
            className="h-8 pl-8 text-sm"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="max-h-[480px] overflow-y-auto">
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
              {filtered.map((emp) => {
                const pwd = activatedIds[emp.employee_id];
                const showPwd = visiblePasswords[emp.employee_id];
                return (
                  <TableRow key={emp.employee_id}>
                    <TableCell className="font-medium">{emp.full_name}</TableCell>
                    <TableCell>
                      <Input
                        type="email"
                        placeholder="email@entreprise.fr"
                        className="h-8"
                        value={emails[emp.employee_id] ?? ''}
                        disabled={Boolean(pwd)}
                        onChange={(e) => onEmailChange(emp.employee_id, e.target.value)}
                      />
                    </TableCell>
                    <TableCell>
                      {pwd ? (
                        <Badge variant="secondary">Compte actif</Badge>
                      ) : (
                        <Badge variant="outline">En onboarding</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {pwd ? (
                        <div className="flex items-center gap-1">
                          <span className="max-w-[100px] truncate font-mono text-xs text-muted-foreground">
                            {showPwd ? pwd : '••••••••'}
                          </span>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() =>
                              setVisiblePasswords((prev) => ({
                                ...prev,
                                [emp.employee_id]: !prev[emp.employee_id],
                              }))
                            }
                          >
                            {showPwd ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => copyPassword(pwd)}
                          >
                            <Copy className="h-3.5 w-3.5" />
                          </Button>
                        </div>
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
                );
              })}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
