import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
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
  saveDsnWorkforceResolutions,
  fetchDsnCoverage,
  listDsnImportCompanies,
  type DsnImportLaunchConfig,
  type DsnImportMode,
  DSN_IMPORT_ACTION_LABELS,
  DSN_IMPORT_ITEM_TYPE_LABELS,
  DSN_IMPORT_REVIEW_REASON_LABELS,
  type DsnImportActionsSummary,
  type DsnImportAnomaly,
  type DsnImportBatchDetail,
  type DsnImportBatchStatus,
  type DsnImportCommitResponse,
  type DsnImportIssue,
  type DsnImportItemPreview,
  type DsnImportParseResponse,
  type DsnReimportOrphans,
  type ImportedEmployeeSummary,
  type WorkforceReconciliationSummary,
  type WorkforceResolution,
} from '@/api/dsnImport';
import { formatEuroAmount } from '@/lib/careerFormat';
import { applyDsnImportCommitted } from '@/lib/dsnCoverageCache';
import { DsnImportAttributionCard } from './DsnImportAttributionCard';
import {
  DsnCompanyPayrollExtractCard,
  type PayrollField,
} from './DsnCompanyPayrollExtractCard';
import {
  DsnImportCommitStatsCard,
  DsnImportHistoricalCard,
} from './DsnImportHistoricalCard';
import { DsnCoverageTimeline } from './DsnCoverageTimeline';
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
import {
  buildCumulsSummaryFromItems,
  CumulsSummaryCard,
  type CumulsSummary,
} from './CumulsSummaryCard';
import { DsnImportIssueList, normalizeCommitErrors } from './DsnImportIssueList';
import { WorkforceReconciliationStep } from './WorkforceReconciliationStep';
import { WorkforceReconciliationSummary as WorkforceReconciliationSummaryCard } from './WorkforceReconciliationSummary';

type Step = 'upload' | 'preview' | 'reconciliation' | 'committing' | 'result';

type EmployeeFilter = 'all' | 'review' | 'edited';

const STEP_LABELS: Record<'upload' | 'preview' | 'reconciliation' | 'result', string> = {
  upload: 'Dépôt',
  preview: 'Analyse',
  reconciliation: 'Effectifs',
  result: 'Import',
};

const STORAGE_KEY = 'eywai.dsn-import.active';

const IMPORT_ACK_TYPES = new Set([
  'period_mismatch',
  'intended_period_mismatch',
  'company_name_mismatch',
  'siret_mismatch',
]);

type PersistedState = { batchId: string; step: Step };

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
    error_messages: report.error_messages ?? [],
    group_id: report.group_id ?? null,
    companies: report.companies ?? {},
    imported_employees: report.imported_employees ?? [],
    workforce_reconciliation: (report as DsnImportCommitResponse).workforce_reconciliation,
    orphan_removal: (report as DsnImportCommitResponse).orphan_removal,
  };
}

function anomalyAsIssue(anomaly: DsnImportAnomaly): DsnImportIssue {
  return {
    code: anomaly.code || anomaly.type || 'unknown',
    message: anomaly.message,
    hint: anomaly.hint,
    severity: anomaly.severity,
    source_ref: anomaly.source_ref,
    meta: anomaly.meta,
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
  if (field === 'salaire_brut') {
    const n = Number(v.replace(/\s/g, '').replace(',', '.'));
    if (Number.isNaN(n) || n < 0) return 'Montant invalide';
  }
  return null;
}

type PreviewStatusBadge = 'ok' | 'review' | 'blocking';

function getPreviewStatus({
  blockingCount,
  reviewCount,
  anomalyCount,
}: {
  blockingCount: number;
  reviewCount: number;
  anomalyCount: number;
}): { description: string; badge: PreviewStatusBadge | null; badgeLabel?: string } {
  if (blockingCount > 0) {
    return {
      description: `${anomalyCount} point(s) d'attention`,
      badge: 'blocking',
      badgeLabel: `${blockingCount} bloquante${blockingCount > 1 ? 's' : ''}`,
    };
  }
  if (reviewCount > 0) {
    return {
      description: `Import possible — ${reviewCount} salarié${reviewCount > 1 ? 's' : ''} à contrôler`,
      badge: 'review',
      badgeLabel: `${reviewCount} à contrôler`,
    };
  }
  if (anomalyCount > 0) {
    return {
      description: `${anomalyCount} point(s) d'attention`,
      badge: null,
    };
  }
  return {
    description: 'Aucune anomalie — prêt à importer.',
    badge: 'ok',
    badgeLabel: 'OK',
  };
}

function aggregateReviewReasons(
  items: DsnImportItemPreview[],
  overrides: Record<string, string> = {},
  payloadEdits: Record<string, Record<string, string>> = {},
): Record<string, number> {
  const byReason: Record<string, number> = {};
  for (const it of items) {
    if (it.item_type !== 'employee') continue;
    const reasons = effectiveReviewReasons(it, overrides[it.source_ref], payloadEdits[it.source_ref]);
    if (!reasons.length) continue;
    for (const reason of reasons) {
      byReason[reason] = (byReason[reason] ?? 0) + 1;
    }
  }
  return byReason;
}

function effectiveReviewReasons(
  item: DsnImportItemPreview,
  overrideAction?: string,
  edits?: Record<string, string>,
): string[] {
  const hasLocalChanges =
    Boolean(overrideAction) || Boolean(edits && Object.keys(edits).length > 0);
  if (!hasLocalChanges && item.review_reasons?.length) {
    return item.review_reasons;
  }
  const payload = {
    ...(item.mapped_payload as Record<string, unknown>),
    ...(edits ?? {}),
  };
  if (edits?.salaire_brut !== undefined) {
    const n = Number(String(edits.salaire_brut).replace(/\s/g, '').replace(',', '.'));
    payload.salaire_de_base = {
      ...((payload.salaire_de_base as Record<string, unknown>) ?? {}),
      valeur: Number.isNaN(n) ? 0 : n,
    };
  }
  const action = overrideAction ?? item.action ?? 'create';
  const reasons: string[] = [];
  const brut = Number((payload.salaire_de_base as { valeur?: number })?.valeur ?? 0);
  if (brut <= 0 && !(item.is_existing && action === 'skip')) {
    reasons.push('brut_absent');
  }
  if (!payload.nir && (payload.ntt || payload.matricule)) {
    reasons.push('nir_incomplet');
  }
  return reasons;
}

const SECTION_ICONS: Record<string, typeof Building2> = {
  group: Building2,
  establishment: Building2,
  collective_agreement: Briefcase,
  employee: Users,
};

function DsnImportLoadingState({
  variant,
  label,
  detail,
  fileNames,
}: {
  variant: 'resume' | 'analyze';
  label: string;
  detail?: string | null;
  fileNames?: string[];
}) {
  return (
    <Card>
      <CardContent className="space-y-3 py-10">
        {variant === 'analyze' ? (
          <SharkFinBootProgress />
        ) : (
          <Loader2 className="h-5 w-5 animate-spin text-primary" />
        )}
        <div className="space-y-1 text-sm text-muted-foreground">
          <p className="font-medium text-foreground">{label}</p>
          {detail ? <p>{detail}</p> : null}
          {fileNames && fileNames.length > 0 ? (
            <p className="truncate text-xs">
              Fichier{fileNames.length > 1 ? 's' : ''} : {fileNames.join(', ')}
            </p>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function DsnImportWizard({
  launchConfig,
  onResetLaunch,
  onCommitStarted,
  onContinueOnboarding,
  initialFiles,
  embedded = false,
}: {
  launchConfig?: DsnImportLaunchConfig | null;
  onResetLaunch?: () => void;
  onCommitStarted?: (batchId: string) => void;
  onContinueOnboarding?: (companyId: string) => void;
  initialFiles?: File[];
  embedded?: boolean;
}) {
  const queryClient = useQueryClient();
  const importMode: DsnImportMode = launchConfig?.mode ?? 'onboarding';
  const lockedTargetCompanyId = importMode === 'monthly' ? launchConfig?.targetCompanyId ?? null : null;
  const isResumeLaunch = Boolean(launchConfig?.resumeBatchId);
  const isReimportLaunch = Boolean(launchConfig?.reimport);
  const { toast } = useToast();
  const [step, setStep] = useState<Step>('upload');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [parseResult, setParseResult] = useState<DsnImportParseResponse | null>(null);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [payloadEdits, setPayloadEdits] = useState<Record<string, Record<string, string>>>({});
  const [payrollApplyFields, setPayrollApplyFields] = useState<Set<PayrollField>>(new Set());
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
  const [isRestoring, setIsRestoring] = useState(isResumeLaunch);
  const [targetCompanyId, setTargetCompanyId] = useState<string | null>(
    lockedTargetCompanyId ?? launchConfig?.targetCompanyId ?? null,
  );
  const [replaceExistingPeriods, setReplaceExistingPeriods] = useState(
    () => Boolean(launchConfig?.reimport),
  );
  const [removeOrphanImportedEmployees, setRemoveOrphanImportedEmployees] = useState(false);
  const [workforceResolutions, setWorkforceResolutions] = useState<Record<string, WorkforceResolution>>({});
  const [acknowledgedWarnings, setAcknowledgedWarnings] = useState<Record<string, boolean>>({});
  const [resumeBatchId, setResumeBatchId] = useState<string | null>(
    launchConfig?.resumeBatchId ?? null,
  );
  const initialFilesHandled = useRef(false);
  const commitHandledRef = useRef<string | null>(null);
  const rowRefs = useRef<Record<string, HTMLTableRowElement | null>>({});
  const employeesSectionRef = useRef<HTMLDivElement | null>(null);
  const closeLabel = embedded ? 'Fermer' : 'Nouvel import';

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
    mutationFn: (files: File[]) =>
      parseDsnImportFiles(files, {
        importMode,
        targetCompanyId: lockedTargetCompanyId ?? targetCompanyId,
        intendedPeriod: launchConfig?.suggestedPeriod ?? null,
      }),
    onSuccess: (data) => {
      setParseResult(data);
      setAcknowledgedWarnings({});
      const initial: Record<string, string> = {};
      data.items.forEach((it) => {
        initial[it.source_ref] = it.action;
      });
      setOverrides(initial);
      setPayloadEdits({});
      setFieldErrors({});
      setExpandedRows({});
      if (lockedTargetCompanyId) {
        setTargetCompanyId(lockedTargetCompanyId);
      } else if (data.summary?.target_company_id) {
        setTargetCompanyId(data.summary.target_company_id as string);
      } else {
        setTargetCompanyId(null);
      }
      setReplaceExistingPeriods(
        Boolean(
          launchConfig?.reimport
            || (data.summary?.duplicate_periods as string[] | undefined)?.length,
        ),
      );
      const wfStored = (data.summary?.workforce_reconciliation as WorkforceReconciliationSummary | undefined)
        ?.resolutions;
      setWorkforceResolutions(wfStored ? { ...wfStored } : {});
      setEmployeesOpen(true);
      setCumulsOpen(true);
      setActiveBatchId(data.batch_id);
      const wf = data.summary?.workforce_reconciliation as WorkforceReconciliationSummary | undefined;
      const gapsDetected = Boolean(wf?.enabled && (wf.gaps?.length ?? 0) > 0);
      const nextStep: Step =
        importMode === 'monthly' && gapsDetected ? 'reconciliation' : 'preview';
      persistState({ batchId: data.batch_id, step: nextStep });
      setStep(nextStep);
    },
    onError: (err: Error) => {
      toast({ title: 'Erreur', description: err.message, variant: 'destructive' });
    },
  });

  const revalidateMutation = useMutation({
    mutationFn: (vars: {
      edits: Record<string, Record<string, string>>;
      targetCompanyId: string | null;
    }) => {
      if (!parseResult) throw new Error('Aucune analyse');
      return revalidateDsnImportBatch(parseResult.batch_id, vars.edits, vars.targetCompanyId);
    },
    onSuccess: (data) => {
      setParseResult((prev) => {
        if (!prev) return prev;
        // Réconcilie les actions recalculées côté serveur avec les overrides :
        // on adopte les nouvelles actions sauf là où l'utilisateur a choisi
        // manuellement (override différent de l'ancienne action).
        if (data.items?.length) {
          const oldActions: Record<string, string> = {};
          prev.items.forEach((it) => {
            oldActions[it.source_ref] = it.action;
          });
          setOverrides((ov) => {
            const next = { ...ov };
            data.items.forEach((it) => {
              const userChanged =
                ov[it.source_ref] !== undefined && ov[it.source_ref] !== oldActions[it.source_ref];
              if (!userChanged) next[it.source_ref] = it.action;
            });
            return next;
          });
        }
        return {
          ...prev,
          items: data.items?.length ? data.items : prev.items,
          anomalies: data.anomalies,
          can_commit: data.can_commit,
          summary: { ...prev.summary, ...data.summary },
        };
      });
    },
  });

  const saveWorkforceMutation = useMutation({
    mutationFn: (resolutions: WorkforceResolution[]) => {
      if (!parseResult) throw new Error('Aucune analyse en cours');
      return saveDsnWorkforceResolutions(parseResult.batch_id, resolutions);
    },
    onSuccess: (data) => {
      setParseResult((prev) =>
        prev
          ? {
              ...prev,
              summary: { ...prev.summary, ...data.summary },
            }
          : prev,
      );
    },
  });

  const handleWorkforceResolutionChange = useCallback(
    (resolution: WorkforceResolution) => {
      setWorkforceResolutions((prev) => {
        const next = { ...prev, [resolution.gap_id]: resolution };
        if (parseResult?.batch_id) {
          void saveWorkforceMutation.mutateAsync(Object.values(next)).catch(() => {
            /* toast géré par mutation si besoin */
          });
        }
        return next;
      });
    },
    [parseResult?.batch_id, saveWorkforceMutation],
  );

  const handleWorkforceResolutionClear = useCallback(
    (gapId: string) => {
      setWorkforceResolutions((prev) => {
        const next = { ...prev };
        delete next[gapId];
        if (parseResult?.batch_id) {
          void saveWorkforceMutation.mutateAsync(Object.values(next)).catch(() => {});
        }
        return next;
      });
    },
    [parseResult?.batch_id, saveWorkforceMutation],
  );

  const commitMutation = useMutation({
    mutationFn: () => {
      if (!parseResult) throw new Error('Aucune analyse en cours');
      return commitDsnImportBatch(
        parseResult.batch_id,
        overrides,
        payloadEdits,
        lockedTargetCompanyId ?? targetCompanyId,
        {
          importMode,
          replaceExistingPeriods,
          workforceResolutions: workforceResolutionsList,
          removeOrphanImportedEmployees,
        },
      );
    },
    onSuccess: (data) => {
      setConfirmOpen(false);
      setActiveBatchId(data.batch_id);
      onCommitStarted?.(data.batch_id);
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
    if (commitHandledRef.current === batchId) return;
    commitHandledRef.current = batchId;
    const report =
      commitReportFromSummary(detail.summary ?? {}) ?? {
        stats: { created: 0, updated: 0, skipped: 0, failed: 0 },
        errors: status === 'failed'
          ? [{ code: 'unknown', message: "L'import a échoué.", severity: 'error' }]
          : [],
        error_messages: status === 'failed' ? ["L'import a échoué."] : [],
        group_id: null,
        companies: {},
        imported_employees: [],
      };
    finalizeResult(report, batchId);
    if (status === 'committed') {
      void applyDsnImportCommitted(queryClient, detail).then(() => {
        void queryClient.invalidateQueries({
          predicate: (query) =>
            Array.isArray(query.queryKey)
            && query.queryKey[0] === 'company'
            && query.queryKey.includes('employees'),
        });
        void queryClient.invalidateQueries({
          predicate: (query) =>
            Array.isArray(query.queryKey)
            && query.queryKey[0] === 'company'
            && query.queryKey.includes('onboarding'),
        });
      });
      toast({ title: 'Import terminé', description: 'Le dossier a été reconstruit.' });
    } else {
      toast({ title: "Échec de l'import", description: 'Consultez le détail.', variant: 'destructive' });
    }
  }, [pollQuery.data, step, activeBatchId, finalizeResult, toast, queryClient]);

  useEffect(() => {
    if (launchConfig?.resumeBatchId) {
      setResumeBatchId(launchConfig.resumeBatchId);
    }
  }, [launchConfig?.resumeBatchId]);

  // Reprise depuis le launcher (batch previewed / committing).
  useEffect(() => {
    const resumeId = resumeBatchId;
    if (!resumeId || parseResult) return;
    let cancelled = false;
    (async () => {
      try {
        const detail = await getDsnImportBatch(resumeId);
        if (cancelled) return;
        const preview = detail.preview ?? {};
        const items = (preview.items as DsnImportItemPreview[]) ?? [];
        setParseResult({
          batch_id: resumeId,
          summary: detail.summary ?? {},
          anomalies: (preview.anomalies as DsnImportParseResponse['anomalies']) ?? [],
          items,
          can_commit: Boolean(preview.can_commit ?? true),
        });
        const initial: Record<string, string> = {};
        items.forEach((it) => {
          initial[it.source_ref] = it.action;
        });
        setOverrides(initial);
        const wfStored = (detail.summary?.workforce_reconciliation as WorkforceReconciliationSummary | undefined)
          ?.resolutions;
        setWorkforceResolutions(wfStored ? { ...wfStored } : {});
        const wf = detail.summary?.workforce_reconciliation as WorkforceReconciliationSummary | undefined;
        const wfGaps = Boolean(wf?.enabled && (wf.gaps?.length ?? 0) > 0);
        const resumeStep: Step =
          importMode === 'monthly' && wfGaps ? 'reconciliation' : 'preview';
        setTargetCompanyId(
          lockedTargetCompanyId ??
            (detail.summary?.target_company_id as string | undefined) ??
            null,
        );
        setActiveBatchId(resumeId);
        setStep(resumeStep);
        persistState({ batchId: resumeId, step: resumeStep });
      } finally {
        if (!cancelled) setIsRestoring(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [resumeBatchId, lockedTargetCompanyId, parseResult]);

  const coverageCompanyId = targetCompanyId ?? lockedTargetCompanyId;
  const coverageQuery = useQuery({
    queryKey: ['dsn-coverage', coverageCompanyId],
    queryFn: () => fetchDsnCoverage(coverageCompanyId as string),
    enabled: Boolean(coverageCompanyId) && step === 'preview',
  });

  const { data: importCompanies } = useQuery({
    queryKey: ['dsn-import-companies'],
    queryFn: listDsnImportCompanies,
    staleTime: 60_000,
  });

  const lockedCompanyName = useMemo(() => {
    if (!lockedTargetCompanyId) return null;
    return importCompanies?.find((c) => c.id === lockedTargetCompanyId)?.company_name ?? null;
  }, [importCompanies, lockedTargetCompanyId]);

  useEffect(() => {
    if (initialFilesHandled.current || !initialFiles?.length || isRestoring) return;
    initialFilesHandled.current = true;
    setSelectedFiles(initialFiles);
    setAnalyzedFileNames(initialFiles.map((f) => f.name));
    parseMutation.mutate(initialFiles);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialFiles, isRestoring]);

  const duplicatePeriods = useMemo(
    () => (parseResult?.summary?.duplicate_periods as string[] | undefined) ?? [],
    [parseResult],
  );

  const reimportOrphans = useMemo(
    () => (parseResult?.summary?.reimport_orphans as DsnReimportOrphans | undefined) ?? { count: 0, employees: [] },
    [parseResult],
  );

  useEffect(() => {
    if (confirmOpen && isReimportLaunch && reimportOrphans.count > 0) {
      setRemoveOrphanImportedEmployees(true);
    }
  }, [confirmOpen, isReimportLaunch, reimportOrphans.count]);

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
    setTargetCompanyId(lockedTargetCompanyId ?? null);
    setReplaceExistingPeriods(false);
    onResetLaunch?.();
  }, [lockedTargetCompanyId, onResetLaunch]);

  const getPayloadValue = useCallback(
    (item: DsnImportItemPreview, field: string): string => {
      const edit = payloadEdits[item.source_ref]?.[field];
      if (edit !== undefined) return edit;
      if (field === 'salaire_brut') {
        const sb = item.mapped_payload?.salaire_de_base as { valeur?: number } | undefined;
        const val = sb?.valeur;
        return val == null || val === 0 ? '' : String(val);
      }
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
        ['siren', 'siret', 'nir', 'salaire_brut'].includes(f),
      );
    });
    if (!hasKeyEdits) return;
    const timer = setTimeout(() => {
      revalidateMutation.mutate({ edits: payloadEdits, targetCompanyId });
    }, 600);
    return () => clearTimeout(timer);
  }, [payloadEdits, parseResult, targetCompanyId]);

  // Changement de rattachement : on recalcule immédiatement (salariés déjà
  // présents dans l'entreprise cible, actions, compteurs).
  const handleTargetChange = useCallback(
    (companyId: string | null) => {
      setTargetCompanyId(companyId);
      if (parseResult) {
        revalidateMutation.mutate({ edits: payloadEdits, targetCompanyId: companyId });
      }
    },
    [parseResult, payloadEdits, revalidateMutation],
  );

  const blockingCount = useMemo(
    () => parseResult?.anomalies.filter((a) => a.severity === 'blocking').length ?? 0,
    [parseResult],
  );

  const warningCount = useMemo(
    () => parseResult?.anomalies.filter((a) => a.severity !== 'blocking').length ?? 0,
    [parseResult],
  );

  const contextWarnings = useMemo(
    () => parseResult?.anomalies.filter((a) => IMPORT_ACK_TYPES.has(a.type)) ?? [],
    [parseResult?.anomalies],
  );

  const allContextWarningsAcked = useMemo(
    () => contextWarnings.every((a) => acknowledgedWarnings[a.type]),
    [contextWarnings, acknowledgedWarnings],
  );

  const detectedPeriodLabel = useMemo(() => {
    const detected = parseResult?.summary?.detected_period as string | undefined;
    if (detected) return formatPeriod(detected);
    return formatPeriod(
      parseResult?.summary?.period_min as string | undefined,
      parseResult?.summary?.period_max as string | undefined,
    );
  }, [parseResult?.summary]);

  const reviewCount = useMemo(
    () =>
      parseResult?.items.filter(
        (i) =>
          i.item_type === 'employee' &&
          effectiveReviewReasons(i, overrides[i.source_ref], payloadEdits[i.source_ref]).length > 0,
      ).length ?? 0,
    [parseResult, overrides, payloadEdits],
  );

  const reviewReasonCounts = useMemo(() => {
    const computed = aggregateReviewReasons(
      parseResult?.items ?? [],
      overrides,
      payloadEdits,
    );
    if (Object.keys(computed).length > 0) {
      return computed;
    }
    const fromServer = parseResult?.summary?.review_summary as
      | { by_reason?: Record<string, number> }
      | undefined;
    return fromServer?.by_reason ?? {};
  }, [parseResult, overrides, payloadEdits]);

  const previewStatus = useMemo(
    () =>
      getPreviewStatus({
        blockingCount,
        reviewCount,
        anomalyCount: parseResult?.anomalies.length ?? 0,
      }),
    [blockingCount, reviewCount, parseResult?.anomalies.length],
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

  const employeesWithoutBrut = useMemo(() => {
    if (!cumulsSummary?.by_period?.length) return 0;
    return cumulsSummary.by_period.reduce(
      (acc, row) => acc + (row.employees_without_brut ?? 0),
      0,
    );
  }, [cumulsSummary]);

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

  const establishmentItem = useMemo(
    () => parseResult?.items.find((it) => it.item_type === 'establishment') ?? null,
    [parseResult],
  );

  const handlePayrollFieldToggle = useCallback(
    (field: PayrollField, checked: boolean) => {
      setPayrollApplyFields((prev) => {
        const next = new Set(prev);
        if (checked) next.add(field);
        else next.delete(field);
        return next;
      });
      if (!establishmentItem) return;
      const ref = establishmentItem.source_ref;
      const val = establishmentItem.mapped_payload?.[field];
      setPayloadEdits((prev) => {
        const row = { ...(prev[ref] ?? {}) };
        if (checked && val != null && val !== '') row[field] = String(val);
        else delete row[field];
        if (Object.keys(row).length === 0) {
          const { [ref]: _, ...rest } = prev;
          return rest;
        }
        return { ...prev, [ref]: row };
      });
    },
    [establishmentItem],
  );

  const hasScaffoldGroup = useMemo(
    () => parseResult?.items.some((i) => i.item_type === 'group' && i.is_scaffold) ?? false,
    [parseResult],
  );

  const existingEmployees = useMemo(
    () => parseResult?.items.filter((i) => i.item_type === 'employee' && i.is_existing) ?? [],
    [parseResult],
  );

  const existingCount = existingEmployees.length;

  const workforceReconciliation = useMemo((): WorkforceReconciliationSummary | null => {
    const wf = parseResult?.summary?.workforce_reconciliation as WorkforceReconciliationSummary | undefined;
    if (!wf?.enabled) return null;
    return wf;
  }, [parseResult?.summary]);

  const hasWorkforceGaps = Boolean(workforceReconciliation && workforceReconciliation.gaps.length > 0);

  const workforceUnresolvedCount = useMemo(() => {
    if (!workforceReconciliation) return 0;
    return workforceReconciliation.gaps.filter((g) => !workforceResolutions[g.gap_id]).length;
  }, [workforceReconciliation, workforceResolutions]);

  const workforceResolutionsList = useMemo(
    () => Object.values(workforceResolutions),
    [workforceResolutions],
  );

  // Les fiches existantes sont rafraîchies si l'utilisateur a basculé leur
  // action en "update" (sinon "skip" = on ne réécrit pas).
  const updateExisting = useMemo(
    () =>
      existingCount > 0 &&
      existingEmployees.every((e) => (overrides[e.source_ref] ?? e.action) === 'update'),
    [existingEmployees, existingCount, overrides],
  );

  const toggleUpdateExisting = useCallback(
    (next: boolean) => {
      setOverrides((prev) => {
        const updated = { ...prev };
        existingEmployees.forEach((e) => {
          updated[e.source_ref] = next ? 'update' : 'skip';
        });
        return updated;
      });
    },
    [existingEmployees],
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
      list = list.filter(
        (e) => effectiveReviewReasons(e, overrides[e.source_ref], payloadEdits[e.source_ref]).length > 0,
      );
    } else if (employeeFilter === 'edited') {
      list = list.filter((e) => Boolean(payloadEdits[e.source_ref]));
    }
    const q = employeeSearch.trim().toLowerCase();
    if (q) {
      list = list.filter((e) => getItemLabel(e).toLowerCase().includes(q));
    }
    return list;
  }, [groupedItems.employee, employeeFilter, employeeSearch, payloadEdits, overrides, getItemLabel]);

  const focusReviewEmployees = useCallback(() => {
    setEmployeeSearch('');
    setEmployeeFilter('review');
    setEmployeesOpen(true);
    requestAnimationFrame(() => {
      employeesSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      window.setTimeout(() => {
        const employees = groupedItems.employee ?? [];
        const firstReview = employees.find(
          (e) =>
            effectiveReviewReasons(e, overrides[e.source_ref], payloadEdits[e.source_ref]).length >
            0,
        );
        if (firstReview) {
          scrollToRef(firstReview.source_ref);
        }
      }, 150);
    });
  }, [groupedItems.employee, overrides, payloadEdits, scrollToRef]);

  const basePreviewChecks =
    !commitMutation.isPending &&
    !hasFieldErrors &&
    !(blockingCount > 0 && editCount === 0) &&
    (contextWarnings.length === 0 || allContextWarningsAcked);

  const canProceedFromPreview =
    basePreviewChecks && (hasWorkforceGaps || (parseResult?.can_commit ?? true));

  const canCommitPreview =
    basePreviewChecks && (parseResult?.can_commit ?? true) && !hasWorkforceGaps;

  const canCommitReconciliation =
    !commitMutation.isPending &&
    !saveWorkforceMutation.isPending &&
    workforceUnresolvedCount === 0 &&
    workforceResolutionsList.length === (workforceReconciliation?.gaps.length ?? 0);

  const canCommit = step === 'reconciliation' ? canCommitReconciliation : canCommitPreview;

  const previewFooterDisabled = hasWorkforceGaps ? !canProceedFromPreview : !canCommitPreview;

  const commitBlockReason = useMemo(() => {
    if (step === 'reconciliation') {
      if (workforceUnresolvedCount > 0) {
        return `${workforceUnresolvedCount} salarié(s) sans décision — choisissez une action pour chaque écart.`;
      }
      if (workforceResolutionsList.length < (workforceReconciliation?.gaps.length ?? 0)) {
        return 'Enregistrez une décision pour chaque écart effectif.';
      }
      return null;
    }
    if (hasWorkforceGaps) {
      if (!basePreviewChecks) {
        if (hasFieldErrors) return 'Corrigez les champs invalides (SIREN, SIRET, NIR) avant de continuer.';
        if (contextWarnings.length > 0 && !allContextWarningsAcked) {
          return 'Cochez les confirmations période / entreprise ci-dessous avant de continuer.';
        }
        if (blockingCount > 0 && editCount === 0) {
          return `${blockingCount} anomalie(s) bloquante(s) — corrigez ou éditez les lignes concernées.`;
        }
      }
      const gapCount = workforceReconciliation?.gaps.length ?? 0;
      return `${gapCount} écart(s) effectif(s) — une décision est requise pour chaque salarié avant validation.`;
    }
    if (hasFieldErrors) return 'Corrigez les champs invalides (SIREN, SIRET, NIR) avant validation.';
    if (contextWarnings.length > 0 && !allContextWarningsAcked) {
      return 'Cochez les confirmations période / entreprise ci-dessous avant validation.';
    }
    if (blockingCount > 0 && editCount === 0) {
      return `${blockingCount} anomalie(s) bloquante(s) — corrigez ou éditez les lignes concernées.`;
    }
    if (parseResult && !parseResult.can_commit) return 'Import bloqué par des anomalies non résolues.';
    return null;
  }, [
    step,
    workforceUnresolvedCount,
    workforceResolutionsList.length,
    workforceReconciliation?.gaps.length,
    hasWorkforceGaps,
    basePreviewChecks,
    hasFieldErrors,
    contextWarnings.length,
    allContextWarningsAcked,
    blockingCount,
    editCount,
    parseResult,
  ]);

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

  const showAutoAnalyzeLoading =
    Boolean(initialFiles?.length) &&
    step === 'upload' &&
    !parseResult &&
    (parseMutation.isPending || !initialFilesHandled.current);

  const resumeLoadingDetail = useMemo(() => {
    const parts: string[] = [];
    if (lockedCompanyName) parts.push(lockedCompanyName);
    if (launchConfig?.suggestedPeriod) {
      parts.push(`Période ${launchConfig.suggestedPeriod}`);
    }
    return parts.length > 0 ? parts.join(' · ') : null;
  }, [lockedCompanyName, launchConfig?.suggestedPeriod]);

  if (isRestoring) {
    return (
      <DsnImportLoadingState
        variant="resume"
        label="Reprise de l'import en cours…"
        detail={resumeLoadingDetail}
      />
    );
  }

  if (showAutoAnalyzeLoading) {
    return (
      <DsnImportLoadingState
        variant="analyze"
        label={
          (initialFiles?.length ?? 0) > 1
            ? `Analyse des ${initialFiles!.length} fichiers en cours…`
            : 'Analyse du fichier en cours…'
        }
        fileNames={initialFiles?.map((f) => f.name) ?? analyzedFileNames}
      />
    );
  }

  return (
    <TooltipProvider>
      <div className={cn('space-y-6', step === 'preview' && 'pb-24')}>
        <StepIndicator
          current={step}
          fileNames={step === 'preview' ? analyzedFileNames : undefined}
          showReconciliation={hasWorkforceGaps}
        />

        {isReimportLaunch && (step === 'upload' || step === 'preview' || step === 'reconciliation') && (
          <div className="rounded-lg border border-sky-200 bg-sky-50/80 px-4 py-3 text-sm text-sky-950 dark:border-sky-900 dark:bg-sky-950/30 dark:text-sky-100">
            <p className="font-medium">Réimport d&apos;un mois déjà importé</p>
            <p className="mt-1 text-xs text-sky-900/80 dark:text-sky-200/80">
              Les cumuls de{' '}
              {launchConfig?.suggestedPeriod ? (
                <strong>{launchConfig.suggestedPeriod}</strong>
              ) : (
                'ce mois'
              )}{' '}
              seront remplacés. La réconciliation effectifs sera relancée. Les fiches salariés
              existantes ne sont pas supprimées automatiquement
              {reimportOrphans.count > 0 ? (
                <>
                  {' '}
                  — {reimportOrphans.count} salarié(s) fantôme(s) détecté(s), supprimables à la
                  confirmation.
                </>
              ) : (
                '.'
              )}
            </p>
          </div>
        )}

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
                {importMode === 'monthly'
                  ? isReimportLaunch
                    ? `Réimporter${lockedCompanyName ? ` — ${lockedCompanyName}` : ''}${launchConfig?.suggestedPeriod ? ` (${launchConfig.suggestedPeriod})` : ''}`
                    : `Import DSN mensuel${lockedCompanyName ? ` — ${lockedCompanyName}` : ''}`
                  : 'Constituer le dossier paie'}
              </CardTitle>
              <CardDescription>
                {importMode === 'monthly'
                  ? isReimportLaunch
                    ? 'Déposez la nouvelle DSN du même mois. Les cumuls seront remplacés après validation.'
                    : 'Le mois est lu automatiquement dans le fichier DSN — aucune sélection manuelle requise.'
                  : 'Pour un dossier fiable, importez toutes les DSN de l\u2019année depuis janvier jusqu\u2019au dernier mois de paie clôturé. Vous pouvez déposer plusieurs fichiers en une fois.'}
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

            {importMode === 'monthly' && detectedPeriodLabel !== '—' && (
              <Card className="border-primary/30 bg-primary/5">
                <CardContent className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <p className="text-sm">
                    <span className="text-muted-foreground">Mois identifié dans la DSN :</span>{' '}
                    <strong className="text-foreground">{detectedPeriodLabel}</strong>
                  </p>
                  {parseResult.summary.dsn_company_name ? (
                    <p className="text-xs text-muted-foreground">
                      Raison sociale DSN :{' '}
                      <span className="font-medium text-foreground">
                        {String(parseResult.summary.dsn_company_name)}
                      </span>
                    </p>
                  ) : null}
                </CardContent>
              </Card>
            )}

            {contextWarnings.length > 0 && (
              <Card className="border-amber-300/80 bg-amber-50/40">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base text-amber-950">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    Confirmations requises
                  </CardTitle>
                  <CardDescription className="text-amber-900/80">
                    Ces écarts ne bloquent pas l&apos;import, mais vous devez les valider explicitement.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {contextWarnings.map((a) => (
                    <label
                      key={a.type}
                      className="flex cursor-pointer items-start gap-3 rounded-md border border-amber-200/80 bg-background/80 p-3 text-sm"
                    >
                      <input
                        type="checkbox"
                        className="mt-1 rounded border-input"
                        checked={Boolean(acknowledgedWarnings[a.type])}
                        onChange={(e) =>
                          setAcknowledgedWarnings((prev) => ({
                            ...prev,
                            [a.type]: e.target.checked,
                          }))
                        }
                      />
                      <span className="leading-snug text-amber-950">{a.message}</span>
                    </label>
                  ))}
                </CardContent>
              </Card>
            )}

            {workforceReconciliation && hasWorkforceGaps && (
              <div className="space-y-3">
                <WorkforceReconciliationSummaryCard reconciliation={workforceReconciliation} />
                {step === 'preview' && (
                  <Button
                    type="button"
                    onClick={() => {
                      persistState({ batchId: parseResult.batch_id, step: 'reconciliation' });
                      setStep('reconciliation');
                    }}
                  >
                    Traiter les écarts effectifs ({workforceReconciliation.gaps.length})
                  </Button>
                )}
              </div>
            )}

            <DsnImportAttributionCard
              targetCompanyId={targetCompanyId}
              onChange={handleTargetChange}
              detectedExisting={Boolean(parseResult.summary.has_existing_dossier)}
              detectedSiret={parseResult.summary.siret as string | undefined}
              isRevalidating={revalidateMutation.isPending}
              locked={Boolean(lockedTargetCompanyId)}
            />

            <DsnCompanyPayrollExtractCard
              establishmentItem={establishmentItem}
              applyFields={payrollApplyFields}
              onToggleField={handlePayrollFieldToggle}
            />

            <DsnImportHistoricalCard items={parseResult.items} />

            {coverageQuery.data ? (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Couverture DSN</CardTitle>
                  <CardDescription>
                    {importMode === 'onboarding'
                      ? 'Objectif : remplir du premier mois utile au mois clos sans trou.'
                      : 'Mois attendu mis en avant dans la timeline.'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <DsnCoverageTimeline timeline={coverageQuery.data.timeline} />
                </CardContent>
              </Card>
            ) : null}

            <Card>
              <CardHeader className="pb-3">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <CardTitle>Résumé de l&apos;analyse</CardTitle>
                    <CardDescription className="mt-1">{previewStatus.description}</CardDescription>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {parseResult.summary.has_existing_dossier ? (
                      <Badge variant="outline" className="shrink-0 border-amber-300 bg-amber-50 text-amber-900">
                        Dossier existant
                      </Badge>
                    ) : null}
                    {previewStatus.badge === 'ok' ? (
                      <Badge variant="secondary" className="shrink-0 gap-1 bg-emerald-50 text-emerald-800">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        {previewStatus.badgeLabel}
                      </Badge>
                    ) : previewStatus.badge === 'review' ? (
                      <Badge
                        variant="outline"
                        className="shrink-0 gap-1 border-amber-300 bg-amber-50 text-amber-900"
                      >
                        <AlertTriangle className="h-3.5 w-3.5" />
                        {previewStatus.badgeLabel}
                      </Badge>
                    ) : previewStatus.badge === 'blocking' ? (
                      <Badge variant="destructive" className="shrink-0">
                        {previewStatus.badgeLabel}
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
                {existingCount > 0 && (
                  <Stat label="Déjà présents" value={String(existingCount)} />
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

            {reviewCount > 0 && (
              <Card className="border-amber-200/80 bg-amber-50/40">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base text-amber-950">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    Salariés à contrôler ({reviewCount})
                  </CardTitle>
                  <CardDescription className="text-amber-900/80">
                    L&apos;import n&apos;est pas bloqué, mais certaines fiches méritent une relecture
                    avant de vous fier au dossier paie.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-sm text-amber-950">
                  <ul className="list-inside list-disc space-y-1">
                    {Object.entries(reviewReasonCounts).map(([reason, count]) => (
                      <li key={reason}>
                        {count} × {DSN_IMPORT_REVIEW_REASON_LABELS[reason] ?? reason}
                      </li>
                    ))}
                  </ul>
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="h-7 border-amber-300 bg-background/80"
                      onClick={focusReviewEmployees}
                    >
                      Voir le filtre « À vérifier »
                    </Button>
                    {employeesWithoutBrut > 0 && (
                      <span className="text-amber-900/80">
                        {employeesWithoutBrut} salarié{employeesWithoutBrut > 1 ? 's' : ''} sans brut
                        extrait dans les cumuls — consultez le résumé cumuls ci-dessous.
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

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
                    <DsnImportIssueList
                      title="Bloquantes"
                      issues={parseResult.anomalies
                        .filter((a) => a.severity === 'blocking')
                        .map(anomalyAsIssue)}
                      onClickRef={scrollToRef}
                      tone="blocking"
                    />
                  )}
                  {warningCount > 0 && (
                    <DsnImportIssueList
                      title="Avertissements"
                      issues={parseResult.anomalies
                        .filter((a) => a.severity !== 'blocking')
                        .map(anomalyAsIssue)}
                      onClickRef={scrollToRef}
                      tone="warning"
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

            {existingCount > 0 && (
              <Card className="border-sky-200/80 bg-sky-50/40">
                <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
                  <div className="flex items-start gap-2.5 text-sm">
                    <Users className="mt-0.5 h-4 w-4 shrink-0 text-sky-700" />
                    <div>
                      <p className="font-medium text-sky-900">
                        {existingCount} salarié{existingCount > 1 ? 's' : ''} déjà présent
                        {existingCount > 1 ? 's' : ''} dans l&apos;entreprise
                      </p>
                      <p className="text-xs text-sky-800/80">
                        Leur fiche n&apos;est pas réécrite — seuls les cumuls du mois sont importés
                        (idéal pour une DSN mensuelle après une autre).
                      </p>
                    </div>
                  </div>
                  <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-sky-900">
                    <input
                      type="checkbox"
                      checked={updateExisting}
                      onChange={(e) => toggleUpdateExisting(e.target.checked)}
                      className="rounded border"
                    />
                    Mettre à jour les fiches existantes
                  </label>
                </CardContent>
              </Card>
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
                      <div key={type} ref={employeesSectionRef}>
                        <Collapsible open={employeesOpen} onOpenChange={setEmployeesOpen}>
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
                      </div>
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
              onCommit={() => {
                if (hasWorkforceGaps) {
                  persistState({ batchId: parseResult.batch_id, step: 'reconciliation' });
                  setStep('reconciliation');
                  return;
                }
                setConfirmOpen(true);
              }}
              primaryDisabled={previewFooterDisabled}
              primaryLoading={commitMutation.isPending}
              blockReason={commitBlockReason}
              primaryLabel={hasWorkforceGaps ? 'Réconcilier les effectifs' : "Valider l'import"}
            />
          </>
        )}

        {step === 'reconciliation' && parseResult && workforceReconciliation && (
          <WorkforceReconciliationStep
            batchId={parseResult.batch_id}
            reconciliation={workforceReconciliation}
            resolutions={workforceResolutions}
            onResolutionChange={handleWorkforceResolutionChange}
            onResolutionClear={handleWorkforceResolutionClear}
            onBack={() => {
              persistState({ batchId: parseResult.batch_id, step: 'preview' });
              setStep('preview');
            }}
            onCommit={() => setConfirmOpen(true)}
            canCommit={canCommitReconciliation}
            blockReason={commitBlockReason}
            saving={saveWorkforceMutation.isPending}
            committing={commitMutation.isPending}
          />
        )}

        {parseResult &&
          ((step === 'preview' && !hasWorkforceGaps) || step === 'reconciliation') && (
          <CommitConfirmDialog
            open={confirmOpen}
            onOpenChange={setConfirmOpen}
            onConfirm={() => commitMutation.mutate()}
            loading={commitMutation.isPending}
            summary={parseResult.summary}
            actionsSummary={actionsSummary}
            employeeCount={parseResult.summary.employee_count as number}
            reviewCount={reviewCount}
            reviewReasonCounts={reviewReasonCounts}
            existingCount={existingCount}
            updateExisting={updateExisting}
            periodLabel={detectedPeriodLabel}
            duplicatePeriods={duplicatePeriods}
            replaceExistingPeriods={replaceExistingPeriods}
            onReplaceExistingPeriodsChange={setReplaceExistingPeriods}
            reimport={isReimportLaunch}
            reimportOrphans={reimportOrphans}
            removeOrphanImportedEmployees={removeOrphanImportedEmployees}
            onRemoveOrphanImportedEmployeesChange={setRemoveOrphanImportedEmployees}
          />
        )}

        {step === 'result' && commitReport && (
          <>
            <WizardNav onBack={resetWizard} backLabel={closeLabel} />

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
                  {(commitReport.orphan_removal?.removed_count ?? 0) > 0 && (
                    <span>
                      <strong>{commitReport.orphan_removal?.removed_count}</strong> salarié(s) fantôme(s) supprimé(s)
                    </span>
                  )}
                </div>
                <DsnImportCommitStatsCard
                  stats={
                    (commitReport as { dsn_import_stats?: Record<string, number> }).dsn_import_stats
                  }
                />
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
                {importMode === 'onboarding' && onContinueOnboarding && (
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50/80 p-3 space-y-2">
                    <p className="text-sm font-medium text-emerald-900">
                      Suite du parcours onboarding
                    </p>
                    <p className="text-xs text-emerald-800">
                      Enrichissement salariés, RIB, soldes CP et paramètres entreprise.
                    </p>
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => {
                        const cid =
                          commitReport.target_company_id ||
                          Object.values(commitReport.companies)[0];
                        if (cid) onContinueOnboarding(String(cid));
                      }}
                    >
                      Continuer l&apos;onboarding
                    </Button>
                  </div>
                )}
                {normalizeCommitErrors(commitReport.errors, commitReport.error_messages).length > 0 && (
                  <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
                    <DsnImportIssueList
                      title="Erreurs d'import"
                      issues={normalizeCommitErrors(
                        commitReport.errors,
                        commitReport.error_messages,
                      )}
                      onClickRef={scrollToRef}
                      tone="error"
                    />
                  </div>
                )}
                {commitReport.workforce_reconciliation && (
                  <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                      Effectifs réconciliés
                    </p>
                    {(commitReport.workforce_reconciliation.closed?.length ?? 0) > 0 && (
                      <p className="text-sm">
                        <strong>{commitReport.workforce_reconciliation.closed.length}</strong>{' '}
                        départ(s) clôturé(s).
                      </p>
                    )}
                    {(commitReport.workforce_reconciliation.deleted?.length ?? 0) > 0 && (
                      <p className="text-sm text-destructive">
                        <strong>{commitReport.workforce_reconciliation.deleted.length}</strong>{' '}
                        fiche(s) supprimée(s) définitivement.
                      </p>
                    )}
                    {(commitReport.workforce_reconciliation.ignored?.length ?? 0) > 0 && (
                      <p className="text-sm text-muted-foreground">
                        {commitReport.workforce_reconciliation.ignored.length} écart(s) ignoré(s).
                      </p>
                    )}
                    {(commitReport.workforce_reconciliation.acknowledged_new_hires?.length ?? 0) > 0 && (
                      <p className="text-sm text-muted-foreground">
                        {commitReport.workforce_reconciliation.acknowledged_new_hires.length}{' '}
                        embauche(s) récente(s) confirmée(s).
                      </p>
                    )}
                    {(commitReport.workforce_reconciliation.open_exit_deferred?.length ?? 0) > 0 && (
                      <div className="space-y-1">
                        <p className="text-sm">
                          {commitReport.workforce_reconciliation.open_exit_deferred.length}{' '}
                          départ(s) à traiter manuellement :
                        </p>
                        <Button variant="outline" size="sm" asChild>
                          <Link to="/employee-exits">Ouvrir les départs</Link>
                        </Button>
                      </div>
                    )}
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

            <WizardNav onBack={resetWizard} backLabel={closeLabel} />
          </>
        )}
      </div>
    </TooltipProvider>
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
  reviewReasonCounts,
  existingCount,
  updateExisting,
  periodLabel,
  duplicatePeriods = [],
  replaceExistingPeriods = false,
  onReplaceExistingPeriodsChange,
  reimport = false,
  reimportOrphans = { count: 0, employees: [] },
  removeOrphanImportedEmployees = false,
  onRemoveOrphanImportedEmployeesChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  loading: boolean;
  summary: Record<string, unknown>;
  actionsSummary?: DsnImportActionsSummary;
  employeeCount: number;
  reviewCount: number;
  reviewReasonCounts: Record<string, number>;
  existingCount: number;
  updateExisting: boolean;
  periodLabel: string;
  duplicatePeriods?: string[];
  replaceExistingPeriods?: boolean;
  onReplaceExistingPeriodsChange?: (value: boolean) => void;
  reimport?: boolean;
  reimportOrphans?: DsnReimportOrphans;
  removeOrphanImportedEmployees?: boolean;
  onRemoveOrphanImportedEmployeesChange?: (value: boolean) => void;
}) {
  const create = actionsSummary?.totals.create ?? 0;
  const update = actionsSummary?.totals.update ?? 0;
  const showReplaceBlock = reimport || duplicatePeriods.length > 0;
  const periodsToReplace =
    duplicatePeriods.length > 0 ? duplicatePeriods.join(', ') : periodLabel;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {reimport ? 'Confirmer le réimport DSN' : "Confirmer l'import DSN"}
          </DialogTitle>
          <DialogDescription>
            {reimport
              ? 'Les cumuls du mois seront remplacés et la réconciliation effectifs relancée. Les fiches salariés existantes ne sont pas supprimées automatiquement.'
              : 'Cette action est irréversible : elle créera ou mettra à jour le dossier paie en base.'}
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
          {existingCount > 0 && (
            <li className="text-muted-foreground">
              {existingCount} salarié(s) déjà présent(s) —{' '}
              {updateExisting
                ? 'leurs fiches seront mises à jour.'
                : 'leurs fiches sont conservées (seuls les cumuls sont importés).'}
            </li>
          )}
          {reviewCount > 0 && (
            <li className="space-y-1 text-amber-800">
              <p className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                {reviewCount} salarié(s) à contrôler — l&apos;import reste possible.
              </p>
              <ul className="ml-6 list-inside list-disc text-xs">
                {Object.entries(reviewReasonCounts).map(([reason, count]) => (
                  <li key={reason}>
                    {count} × {DSN_IMPORT_REVIEW_REASON_LABELS[reason] ?? reason}
                  </li>
                ))}
              </ul>
            </li>
          )}
          {showReplaceBlock && (
            <li className="space-y-2 rounded-md border border-amber-200 bg-amber-50/80 p-3 text-amber-950">
              <p className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                {reimport
                  ? `Les cumuls de ${periodsToReplace} seront remplacés.`
                  : `Remplacer les cumuls de ${periodsToReplace} ?`}
              </p>
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={replaceExistingPeriods}
                  onChange={(e) => onReplaceExistingPeriodsChange?.(e.target.checked)}
                  className="rounded border-input"
                />
                Écraser les cumuls existants pour {periodsToReplace}
              </label>
            </li>
          )}
          {reimport && reimportOrphans.count > 0 && (
            <li className="space-y-2 rounded-md border border-rose-200 bg-rose-50/60 p-3 text-rose-950">
              <p className="flex items-start gap-2 text-sm">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                {reimportOrphans.count} salarié(s) importé(s) par erreur absent(s) de cette DSN
                — sans compte activé, supprimables en toute sécurité.
              </p>
              {reimportOrphans.employees.length <= 5 && (
                <ul className="ml-6 list-inside list-disc text-xs">
                  {reimportOrphans.employees.map((emp) => (
                    <li key={emp.employee_id}>
                      {emp.employee_name} · NIR {emp.nir_masked}
                    </li>
                  ))}
                </ul>
              )}
              <label className="flex cursor-pointer items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={removeOrphanImportedEmployees}
                  onChange={(e) => onRemoveOrphanImportedEmployeesChange?.(e.target.checked)}
                  className="rounded border-input"
                />
                Supprimer ces {reimportOrphans.count} fiche(s) salarié(s) fantôme(s)
              </label>
            </li>
          )}
        </ul>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={loading}>
            Annuler
          </Button>
          <Button
            onClick={onConfirm}
            disabled={loading}
          >
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
  primaryLabel = "Valider l'import",
}: {
  onBack: () => void;
  onCommit: () => void;
  primaryDisabled: boolean;
  primaryLoading: boolean;
  blockReason: string | null;
  primaryLabel?: string;
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
          {primaryLabel}
        </Button>
      </div>
    </div>
  );
}

function StepIndicator({
  current,
  fileNames,
  showReconciliation = false,
}: {
  current: Step;
  fileNames?: string[];
  showReconciliation?: boolean;
}) {
  const steps: Array<'upload' | 'preview' | 'reconciliation' | 'result'> = showReconciliation
    ? ['upload', 'preview', 'reconciliation', 'result']
    : ['upload', 'preview', 'result'];
  const effective =
    current === 'committing' ? 'result' : current === 'reconciliation' ? 'reconciliation' : current;
  const currentIdx = steps.indexOf(effective as 'upload' | 'preview' | 'reconciliation' | 'result');

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
  const showBoethColumn =
    isEmployeeList &&
    items.some((it) => Boolean(it.preview_columns?.boeth_label ?? it.preview_columns?.boeth_code));

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
                <TableHead className="hidden text-right xl:table-cell w-[90px]">Brut</TableHead>
                {showBoethColumn ? (
                  <TableHead className="hidden lg:table-cell w-[120px]">BOETH</TableHead>
                ) : null}
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
              (isEmployeeList ? 4 + (showBoethColumn ? 1 : 0) : 0) +
              (showActionColumn ? 1 : 0);
            const brutValue = Number((cols.brut ?? getPayloadValue(it, 'salaire_brut')) || 0);
            const hasBrutAbsent = effectiveReviewReasons(
              it,
              overrides[it.source_ref],
              payloadEdits[it.source_ref],
            ).includes('brut_absent');

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
                      <TableCell className="hidden text-right text-xs tabular-nums xl:table-cell">
                        {brutValue > 0 ? (
                          formatEuroAmount(brutValue)
                        ) : hasBrutAbsent ? (
                          <Badge
                            variant="outline"
                            className="font-normal text-[10px] text-amber-800"
                          >
                            —
                          </Badge>
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      {showBoethColumn ? (
                        <TableCell className="hidden max-w-[140px] truncate text-xs lg:table-cell">
                          {String(cols.boeth_label ?? cols.boeth_code ?? '—')}
                        </TableCell>
                      ) : null}
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
                      {it.is_existing && (
                        <Badge
                          variant="outline"
                          className="border-sky-300 bg-sky-50 font-normal text-[10px] text-sky-800"
                        >
                          {(overrides[it.source_ref] ?? it.action) === 'update'
                            ? 'Déjà présent · MAJ'
                            : 'Déjà présent'}
                        </Badge>
                      )}
                      {it.existing_company_name && (
                        <Badge
                          variant="outline"
                          className="border-amber-300 bg-amber-50 font-normal text-[10px] text-amber-900"
                        >
                          Déjà chez {it.existing_company_name}
                        </Badge>
                      )}
                      {effectiveReviewReasons(
                        it,
                        overrides[it.source_ref],
                        payloadEdits[it.source_ref],
                      ).map((reason) => {
                        const isBoethConflict = reason === 'boeth_conflict';
                        const badge = (
                          <Badge
                            key={reason}
                            variant="outline"
                            className={cn(
                              'font-normal text-[10px]',
                              isBoethConflict &&
                                'border-amber-300 bg-amber-50 text-amber-900 cursor-help',
                            )}
                          >
                            {DSN_IMPORT_REVIEW_REASON_LABELS[reason] ?? reason}
                          </Badge>
                        );
                        if (isBoethConflict && it.boeth_conflict) {
                          return (
                            <Tooltip key={reason}>
                              <TooltipTrigger asChild>{badge}</TooltipTrigger>
                              <TooltipContent>
                                <p>
                                  DSN ({it.boeth_conflict.dsn_code}) vs fiche (
                                  {it.boeth_conflict.profile_code}) — le profil manuel sera
                                  conservé à l&apos;import.
                                </p>
                              </TooltipContent>
                            </Tooltip>
                          );
                        }
                        return badge;
                      })}
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
