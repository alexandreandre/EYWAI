import { useEffect, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { CalendarDays, FileSearch, Loader2 } from 'lucide-react';
import {
  commitPlanningImport,
  getPlanningImportBatch,
  parsePlanningImport,
  startPlanningImportParse,
  type PlanningImportCommitProgress,
  type PlanningImportParseResponse,
  type PlanningPeriodMode,
} from '@/api/adminImport';
import { PlanningImportCommitOverlay } from '@/features/admin-import/components/PlanningImportCommitOverlay';
import { PlanningImportMatchReview } from '@/features/admin-import/components/PlanningImportMatchReview';
import { PlanningImportPreviewSummary } from '@/features/admin-import/components/PlanningImportPreviewSummary';
import {
  registerPlanningImportJob,
  registerPlanningImportParseJob,
} from '@/hooks/planningImportJobStore';
import type { PlanningImportSummary } from '@/api/adminImport';
import type { RosterEmployee } from '@/api/calendar';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { formatMonthLabel } from '@/lib/groupConsolidatedPeriod';
import { getUserErrorMessage } from '@/lib/errorMessages';

type Props = {
  companyId: string;
  initialParseResult?: PlanningImportParseResponse | null;
  onComplete?: () => void;
  onParseStarted?: () => void;
  onCommitStarted?: () => void;
  backgroundCommit?: boolean;
  embedded?: boolean;
};

const PERIOD_MODE_LABELS: Record<PlanningPeriodMode, string> = {
  month: 'Un mois',
  year: '1 an',
  range: 'Plage personnalisée',
  auto: 'Détection automatique',
};

function buildYearOptions(nowYear: number, span = 6): number[] {
  return Array.from({ length: span }, (_, i) => nowYear - 2 + i);
}

export function PlanningImportPanel({
  companyId,
  initialParseResult,
  onComplete,
  onParseStarted,
  onCommitStarted,
  backgroundCommit = false,
  embedded,
}: Props) {
  const { toast } = useToast();
  const now = new Date();
  const [periodMode, setPeriodMode] = useState<PlanningPeriodMode>('year');
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [startYear, setStartYear] = useState(now.getFullYear());
  const [startMonth, setStartMonth] = useState(1);
  const [endYear, setEndYear] = useState(now.getFullYear());
  const [endMonth, setEndMonth] = useState(12);
  const [file, setFile] = useState<File | null>(null);
  const [parseResult, setParseResult] = useState<PlanningImportParseResponse | null>(null);
  const [liveSummary, setLiveSummary] = useState<PlanningImportSummary | null>(null);
  const [commitPhase, setCommitPhase] = useState<'idle' | 'committing' | 'failed'>('idle');
  const [commitProgress, setCommitProgress] = useState<PlanningImportCommitProgress | null>(null);
  const [commitError, setCommitError] = useState<string | null>(null);
  const handledCommitRef = useRef(false);

  const roster: RosterEmployee[] = useMemo(() => {
    if (!parseResult?.roster?.length) return [];
    return parseResult.roster.map((e) => ({
      id: e.id,
      first_name: e.first_name,
      last_name: e.last_name,
      time_tracking_id: e.time_tracking_id ?? undefined,
    }));
  }, [parseResult?.roster]);

  const yearOptions = useMemo(() => buildYearOptions(now.getFullYear()), [now]);

  useEffect(() => {
    if (!initialParseResult) return;
    setParseResult(initialParseResult);
    setLiveSummary(initialParseResult.summary ?? null);
    setCommitPhase('idle');
    setCommitError(null);
    setCommitProgress(null);
  }, [initialParseResult]);

  const periodParams = useMemo(
    () => ({
      periodMode,
      year,
      month: periodMode === 'month' || periodMode === 'auto' ? month : undefined,
      startYear,
      startMonth,
      endYear,
      endMonth,
    }),
    [periodMode, year, month, startYear, startMonth, endYear, endMonth],
  );

  const commitLabel = useMemo(() => {
    if (periodMode === 'year') return "Enregistrer l'année";
    if (periodMode === 'range') return 'Enregistrer la plage';
    if (periodMode === 'auto') return 'Enregistrer la période détectée';
    return 'Enregistrer le mois';
  }, [periodMode]);

  const parseMutation = useMutation({
    mutationFn: async () => {
      if (!companyId || !file) throw new Error('Fichier et entreprise requis.');
      if (backgroundCommit) {
        return startPlanningImportParse(companyId, periodParams, file);
      }
      return parsePlanningImport(companyId, periodParams, file);
    },
    onSuccess: (data) => {
      if ('job_id' in data) {
        registerPlanningImportParseJob({
          jobId: data.job_id,
          companyId,
          label: file?.name ?? 'Calendrier',
          status: data.status || 'parsing',
        });
        toast({
          title: 'Analyse calendrier lancée',
          description: "Vous pouvez quitter le module, l'analyse continue en arrière-plan.",
        });
        onParseStarted?.();
        return;
      }
      setParseResult(data);
      setLiveSummary(data.summary ?? null);
      const s = data.summary;
      toast({
        title: 'Calendrier analysé',
        description: s
          ? `${s.employees_importable} salarié(s) sur ${s.employees_total} — ${s.period_label}`
          : 'Aperçu prêt.',
      });
    },
    onError: (e) => {
      toast({ title: 'Erreur', description: getUserErrorMessage(e), variant: 'destructive' });
    },
  });

  const commitMutation = useMutation({
    mutationFn: async () => {
      if (!parseResult?.batch_id) throw new Error("Analysez un fichier d'abord.");
      return commitPlanningImport(parseResult.batch_id, companyId);
    },
    onSuccess: (data) => {
      if (backgroundCommit) {
        const batchId = data.batch_id || parseResult?.batch_id;
        if (!batchId) {
          toast({
            title: 'Erreur',
            description: "Impossible de suivre l'import calendrier : batch introuvable.",
            variant: 'destructive',
          });
          return;
        }
        registerPlanningImportJob({
          batchId,
          companyId,
          label: liveSummary?.period_label ?? file?.name ?? 'Calendrier',
          status: data.status === 'committed' ? 'committing' : data.status || 'committing',
        });
        toast({
          title: 'Import calendrier lancé',
          description: "L'enregistrement continue en arrière-plan.",
        });
        setParseResult(null);
        setFile(null);
        setLiveSummary(null);
        onCommitStarted?.();
        return;
      }
      handledCommitRef.current = false;
      setCommitPhase('committing');
      setCommitError(null);
      setCommitProgress(null);
    },
    onError: (e) => {
      toast({ title: 'Erreur', description: getUserErrorMessage(e), variant: 'destructive' });
    },
  });

  const commitBatchId = parseResult?.batch_id ?? null;
  const isCommitting = commitPhase === 'committing';

  const commitPollQuery = useQuery({
    queryKey: ['planning-import-commit', commitBatchId, companyId],
    queryFn: () => getPlanningImportBatch(commitBatchId as string, companyId),
    enabled: !backgroundCommit && isCommitting && Boolean(commitBatchId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === 'committed' || status === 'failed' ? false : 800;
    },
  });

  useEffect(() => {
    const data = commitPollQuery.data;
    if (!isCommitting || !data) return;
    if (data.commit_progress) {
      setCommitProgress(data.commit_progress);
    }
    if (data.status === 'committed') {
      if (handledCommitRef.current) return;
      handledCommitRef.current = true;
      const days = data.total_days_written ?? 0;
      const employees = data.employees_processed ?? 0;
      toast({
        title: 'Calendrier enregistré',
        description:
          days > 0
            ? `${employees} salarié(s), ${days.toLocaleString('fr-FR')} jour(s) de calendrier prévu.`
            : 'Import terminé.',
      });
      setCommitPhase('idle');
      setParseResult(null);
      setFile(null);
      setLiveSummary(null);
      setCommitProgress(null);
      onComplete?.();
    }
    if (data.status === 'failed') {
      setCommitPhase('failed');
      setCommitError(data.error_message ?? "L'enregistrement a échoué.");
    }
  }, [commitPollQuery.data, isCommitting, onComplete, toast]);

  if (!companyId) {
    return embedded ? null : (
      <p className="text-sm text-muted-foreground">Sélectionnez une entreprise dans le bandeau.</p>
    );
  }

  const canCommit = liveSummary?.ready_to_commit ?? parseResult?.summary?.ready_to_commit ?? false;
  const showCommitOverlay =
    !backgroundCommit && (commitPhase === 'committing' || commitPhase === 'failed');

  return (
    <Card className="relative">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarDays className="h-4 w-4" />
          Import Calendrier
        </CardTitle>
        <CardDescription>
          Importe les calendriers prévus (Excel/CSV) sur un mois, une année ou une plage libre.
          Le pointage courant reste sur le calendrier RH.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <Label htmlFor="planning-period-mode">Période cible</Label>
          <Select
            value={periodMode}
            onValueChange={(value) => setPeriodMode(value as PlanningPeriodMode)}
          >
            <SelectTrigger id="planning-period-mode">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(PERIOD_MODE_LABELS) as PlanningPeriodMode[]).map((mode) => (
                <SelectItem key={mode} value={mode}>
                  {PERIOD_MODE_LABELS[mode]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {periodMode === 'month' ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="planning-year">Année</Label>
              <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
                <SelectTrigger id="planning-year">
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
            <div className="space-y-1">
              <Label htmlFor="planning-month">Mois</Label>
              <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
                <SelectTrigger id="planning-month">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                    <SelectItem key={m} value={String(m)}>
                      {formatMonthLabel(m)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        ) : null}

        {periodMode === 'year' ? (
          <div className="space-y-1">
            <Label htmlFor="planning-year-full">Année</Label>
            <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
              <SelectTrigger id="planning-year-full">
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
        ) : null}

        {periodMode === 'range' ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2 rounded-md border p-3">
              <p className="text-xs font-medium text-muted-foreground">Début</p>
              <div className="grid grid-cols-2 gap-2">
                <Select value={String(startYear)} onValueChange={(v) => setStartYear(Number(v))}>
                  <SelectTrigger aria-label="Année de début">
                    <SelectValue placeholder="Année" />
                  </SelectTrigger>
                  <SelectContent>
                    {yearOptions.map((y) => (
                      <SelectItem key={y} value={String(y)}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={String(startMonth)} onValueChange={(v) => setStartMonth(Number(v))}>
                  <SelectTrigger aria-label="Mois de début">
                    <SelectValue placeholder="Mois" />
                  </SelectTrigger>
                  <SelectContent>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                      <SelectItem key={m} value={String(m)}>
                        {formatMonthLabel(m)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2 rounded-md border p-3">
              <p className="text-xs font-medium text-muted-foreground">Fin</p>
              <div className="grid grid-cols-2 gap-2">
                <Select value={String(endYear)} onValueChange={(v) => setEndYear(Number(v))}>
                  <SelectTrigger aria-label="Année de fin">
                    <SelectValue placeholder="Année" />
                  </SelectTrigger>
                  <SelectContent>
                    {yearOptions.map((y) => (
                      <SelectItem key={y} value={String(y)}>
                        {y}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select value={String(endMonth)} onValueChange={(v) => setEndMonth(Number(v))}>
                  <SelectTrigger aria-label="Mois de fin">
                    <SelectValue placeholder="Mois" />
                  </SelectTrigger>
                  <SelectContent>
                    {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                      <SelectItem key={m} value={String(m)}>
                        {formatMonthLabel(m)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        ) : null}

        {periodMode === 'auto' ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="planning-hint-year">Année indicative</Label>
              <Select value={String(year)} onValueChange={(v) => setYear(Number(v))}>
                <SelectTrigger id="planning-hint-year">
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
            <div className="space-y-1">
              <Label htmlFor="planning-hint-month">Mois indicatif (optionnel)</Label>
              <Select value={String(month)} onValueChange={(v) => setMonth(Number(v))}>
                <SelectTrigger id="planning-hint-month">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                    <SelectItem key={m} value={String(m)}>
                      {formatMonthLabel(m)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <p className="sm:col-span-2 text-xs text-muted-foreground">
              La période réelle est lue dans le fichier ; l&apos;année/mois servent de repère si les
              dates sont ambiguës.
            </p>
          </div>
        ) : null}

        <div className="space-y-2">
          <Label>Fichier</Label>
          <Input
            type="file"
            accept=".csv,.xlsx,.xls,.pdf"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setParseResult(null);
              setLiveSummary(null);
            }}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            disabled={!file || parseMutation.isPending || isCommitting}
            onClick={() => parseMutation.mutate()}
          >
            {parseMutation.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <FileSearch className="mr-2 h-4 w-4" />
            )}
            Analyser
          </Button>
          {parseResult ? (
            <Button
              type="button"
              variant="default"
              disabled={commitMutation.isPending || isCommitting || !canCommit}
              onClick={() => commitMutation.mutate()}
            >
              {commitMutation.isPending || isCommitting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              {commitLabel}
            </Button>
          ) : null}
        </div>
        {liveSummary ? (
          <>
            <PlanningImportPreviewSummary summary={liveSummary} />
            {parseResult?.batch_id && liveSummary.review_items.length > 0 ? (
              <PlanningImportMatchReview
                batchId={parseResult.batch_id}
                companyId={companyId}
                summary={liveSummary}
                roster={roster}
                onSummaryUpdated={setLiveSummary}
              />
            ) : null}
          </>
        ) : null}
        {showCommitOverlay ? (
          <PlanningImportCommitOverlay
            progress={commitProgress}
            status={commitPhase === 'failed' ? 'failed' : 'committing'}
            errorMessage={commitError}
            onDismiss={
              commitPhase === 'failed'
                ? () => {
                    setCommitPhase('idle');
                    setCommitError(null);
                  }
                : undefined
            }
          />
        ) : null}
      </CardContent>
    </Card>
  );
}
