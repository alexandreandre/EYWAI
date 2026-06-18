import { useRef, useState } from 'react';
import { ChevronDown, HelpCircle, Loader2, Sparkles, Upload } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Progress } from '@/components/ui/progress';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';
import {
  extractTimesheet,
  type AiCalendarProposal,
  type AiEmployeeProposal,
  type DocumentScopeInput,
  type RosterEmployee,
} from '@/api/calendar';
import {
  AssistedFillReview,
  type AssistedFillApplyMeta,
} from './AssistedFillReview';
import { aiFillErrorMessage } from './aiFillUtils';

const MONTHS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

const ACCEPTED = '.pdf,.jpg,.jpeg,.png,.webp,.tif,.tiff';

function mergeEmployeeProposals(
  existing: AiEmployeeProposal[],
  incoming: AiEmployeeProposal[],
): AiEmployeeProposal[] {
  const byKey = new Map<string, AiEmployeeProposal>();
  const keyOf = (e: AiEmployeeProposal) =>
    e.time_tracking_id ?? e.employee_id ?? e.raw_name;

  [...existing, ...incoming].forEach((emp) => {
    const key = keyOf(emp);
    const prev = byKey.get(key);
    if (!prev) {
      byKey.set(key, { ...emp, days: [...emp.days] });
      return;
    }
    const dayMap = new Map(prev.days.map((d) => [d.jour, d]));
    emp.days.forEach((d) => dayMap.set(d.jour, d));
    byKey.set(key, {
      ...prev,
      ...emp,
      days: [...dayMap.values()].sort((a, b) => a.jour - b.jour),
      warnings: [...new Set([...prev.warnings, ...emp.warnings])],
    });
  });
  return [...byKey.values()];
}

function mergeProposals(proposals: AiCalendarProposal[]): AiCalendarProposal {
  const base = proposals[proposals.length - 1];
  let employees: AiEmployeeProposal[] = [];
  const warnings = new Set<string>();
  let ready = 0;
  let warning = 0;
  let error = 0;
  let empty = 0;
  let incomplete = 0;
  let gap = 0;

  proposals.forEach((p) => {
    employees = mergeEmployeeProposals(employees, p.employees);
    p.warnings.forEach((w) => warnings.add(w));
  });

  employees.forEach((e) => {
    if (e.review_status === 'empty') empty += 1;
    else if (e.review_status === 'error' || !e.employee_id) error += 1;
    else if (e.quality_issue === 'extraction_incomplete') incomplete += 1;
    else if (e.quality_issue === 'weekly_total_gap') gap += 1;
    else if (e.review_status === 'warning' || e.match_confidence === 'medium') warning += 1;
    else ready += 1;
  });

  return {
    ...base,
    employees,
    warnings: [...warnings],
    source: `${proposals.length} relevé(s) fusionné(s)`,
    review_summary: {
      ready,
      warning,
      error,
      empty,
      incomplete,
      gap,
      total: employees.length,
    },
    quality_checks: proposals.flatMap((p) => p.quality_checks ?? []),
  };
}

interface PointageImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  year: number;
  month: number;
  roster: RosterEmployee[];
  onApplied: (meta?: AssistedFillApplyMeta) => void;
  singleEmployee?: boolean;
  onNavigateToMonth?: (year: number, month: number) => void;
  onFocusPlanningWeek?: (weekIndex: number) => void;
}

export function PointageImportDialog({
  open,
  onOpenChange,
  year,
  month,
  roster,
  onApplied,
  singleEmployee = false,
  onNavigateToMonth,
  onFocusPlanningWeek,
}: PointageImportDialogProps) {
  const { toast } = useToast();
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [queueProgress, setQueueProgress] = useState(0);
  const [pageProgress, setPageProgress] = useState<{
    pages_done: number;
    pages_total: number;
    phase: string;
  } | null>(null);
  const [proposal, setProposal] = useState<AiCalendarProposal | null>(null);
  const [documentScope, setDocumentScope] = useState<DocumentScopeInput>('auto');
  const [weekAnchorDate, setWeekAnchorDate] = useState('');
  const [helpOpen, setHelpOpen] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const periodLabel = `${MONTHS[month - 1]} ${year}`;
  const targetName =
    singleEmployee && roster[0]
      ? `${roster[0].first_name} ${roster[0].last_name}`
      : null;

  const reset = () => {
    setFiles([]);
    setProposal(null);
    setIsAnalyzing(false);
    setQueueProgress(0);
    setPageProgress(null);
    setDocumentScope('auto');
    setWeekAnchorDate('');
    setHelpOpen(false);
  };

  const handleClose = (next: boolean) => {
    if (!next) reset();
    onOpenChange(next);
  };

  const showProposal = (result: AiCalendarProposal, fileCount = 1) => {
    if (result.employees.length === 0) {
      toast({
        title: 'Aucune donnée détectée',
        description:
          result.warnings[0] ?? "Rien n'a pu être extrait. Essayez un autre relevé.",
        variant: 'destructive',
      });
      return;
    }
    if (
      result.month_auto_corrected &&
      result.requested_year != null &&
      result.requested_month != null &&
      onNavigateToMonth
    ) {
      onNavigateToMonth(result.year, result.month);
    }
    if (result.focus_week_index != null && onFocusPlanningWeek) {
      onFocusPlanningWeek(result.focus_week_index);
    }

    const formatHint =
      result.detected_format === 'cegid_weekly'
        ? 'Relevé Cegid détecté'
        : result.detected_format === 'hybrid_vision_ocr'
          ? 'Relevé IA hybride (vision + OCR)'
          : 'Relevé analysé';
    const verifyCount = result.review_summary?.warning ?? 0;
    toast({
      title: fileCount > 1 ? `${fileCount} semaines importées` : formatHint,
      description: `${MONTHS[result.month - 1]} ${result.year} · ${result.employees.length} salarié(s)${
        verifyCount > 0 ? ` · ${verifyCount} point(s) à vérifier` : ''
      }`,
    });
    setProposal(result);
  };

  const analyzeFiles = async () => {
    if (files.length === 0) return;
    if (documentScope === 'weekly' && !weekAnchorDate) {
      toast({
        title: 'Date de semaine recommandée',
        description:
          'Pour un relevé hebdomadaire sans dates explicites, indiquez le lundi de la semaine.',
        variant: 'destructive',
      });
      return;
    }
    setIsAnalyzing(true);
    setQueueProgress(0);
    setPageProgress(null);
    try {
      const results: AiCalendarProposal[] = [];
      for (let i = 0; i < files.length; i++) {
        const result = await extractTimesheet(files[i], year, month, roster, {
          singleEmployee,
          documentScope,
          weekAnchorDate: weekAnchorDate || null,
          onProgress: (p) => {
            setPageProgress({
              pages_done: p.pages_done,
              pages_total: p.pages_total,
              phase: p.phase,
            });
          },
        });
        results.push(result);
        setQueueProgress(Math.round(((i + 1) / files.length) * 100));
        setPageProgress(null);
      }
      const merged = results.length === 1 ? results[0] : mergeProposals(results);
      showProposal(merged, files.length);
    } catch (e) {
      toast({
        title: 'Analyse impossible',
        description: aiFillErrorMessage(e),
        variant: 'destructive',
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleApplied = (meta?: AssistedFillApplyMeta) => {
    onApplied(meta);
    handleClose(false);
  };

  const addFiles = (incoming: FileList | File[]) => {
    const list = Array.from(incoming);
    setFiles((prev) => {
      const names = new Set(prev.map((f) => f.name));
      return [...prev, ...list.filter((f) => !names.has(f.name))];
    });
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent
        className={cn(
          'flex h-[90dvh] max-h-[90dvh] w-full max-w-3xl translate-y-0 flex-col gap-0 overflow-hidden p-0 top-[5dvh]',
          proposal && 'max-w-4xl',
        )}
      >
        <DialogHeader className="shrink-0 space-y-1 border-b px-5 py-3">
          <DialogTitle className="flex items-center gap-2 text-base">
            <Upload className="h-4 w-4 text-primary" />
            {proposal
              ? `Revue import — ${MONTHS[proposal.month - 1]} ${proposal.year}`
              : `Importer des pointages — ${periodLabel}`}
          </DialogTitle>
          {!proposal && (
            <DialogDescription className="text-xs">
              {targetName ? (
                <>Relevé de {targetName} — fusion partielle par jour.</>
              ) : (
                <>
                  {roster.length} salariés · hebdo ou mensuel · plusieurs PDF possibles.
                </>
              )}
            </DialogDescription>
          )}
        </DialogHeader>

        <div className="flex min-h-0 flex-1 flex-col overflow-hidden px-5 py-3">
          {proposal ? (
            <AssistedFillReview
              proposal={proposal}
              roster={roster}
              onApplied={handleApplied}
              onBack={() => setProposal(null)}
            />
          ) : (
            <div className="max-h-full space-y-3 overflow-y-auto pr-1">
            <Collapsible open={helpOpen} onOpenChange={setHelpOpen}>
              <CollapsibleTrigger asChild>
                <button
                  type="button"
                  className="flex w-full items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-left text-sm text-muted-foreground hover:bg-muted/50"
                >
                  <HelpCircle className="h-4 w-4 shrink-0" />
                  <span className="flex-1 font-medium text-foreground">Aide import</span>
                  <ChevronDown
                    className={cn('h-4 w-4 transition-transform', helpOpen && 'rotate-180')}
                  />
                </button>
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2 space-y-2 rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
                <ol className="list-decimal space-y-1 pl-4">
                  <li>Le mois affiché est ajusté automatiquement si le PDF concerne un autre mois.</li>
                  <li>Format Cegid « Pointages retenu » : extraction IA hybride vision + OCR par page.</li>
                  <li>Déposez plusieurs PDF d&apos;un coup (S19–S22) : traitement séquentiel puis revue unique.</li>
                </ol>
              </CollapsibleContent>
            </Collapsible>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="document-scope" className="text-xs">
                  Type de relevé
                </Label>
                <Select
                  value={documentScope}
                  onValueChange={(v) => setDocumentScope(v as DocumentScopeInput)}
                >
                  <SelectTrigger id="document-scope" className="h-9">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Détection automatique</SelectItem>
                    <SelectItem value="weekly">Hebdomadaire</SelectItem>
                    <SelectItem value="monthly">Mensuel</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {(documentScope === 'weekly' || documentScope === 'auto') && (
                <div className="space-y-1.5">
                  <Label htmlFor="week-anchor" className="text-xs">
                    Semaine commençant le
                    {documentScope === 'weekly' ? ' *' : ' (optionnel)'}
                  </Label>
                  <Input
                    id="week-anchor"
                    type="date"
                    value={weekAnchorDate}
                    onChange={(e) => setWeekAnchorDate(e.target.value)}
                    className="h-9"
                  />
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={(e) => {
                e.preventDefault();
                setIsDragging(false);
                if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files);
              }}
              className={cn(
                'flex w-full flex-col items-center gap-2 rounded-lg border-2 border-dashed py-8 text-sm transition-colors',
                isDragging ? 'border-primary bg-primary/5' : 'border-muted-foreground/25',
              )}
            >
              <Upload className="h-7 w-7 text-muted-foreground" />
              {files.length > 0 ? (
                <span className="font-medium">
                  {files.length} fichier(s) sélectionné(s)
                </span>
              ) : (
                <>
                  <span className="font-medium">Glissez un ou plusieurs relevés</span>
                  <span className="text-xs text-muted-foreground">PDF, JPG ou PNG (max 15 Mo)</span>
                </>
              )}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPTED}
              multiple
              className="hidden"
              onChange={(e) => {
                if (e.target.files?.length) addFiles(e.target.files);
              }}
            />

            {files.length > 0 && (
              <ul className="max-h-24 overflow-y-auto rounded border px-2 py-1 text-xs">
                {files.map((f) => (
                  <li key={f.name} className="truncate py-0.5">
                    {f.name}
                  </li>
                ))}
              </ul>
            )}

            {isAnalyzing && (
              <div className="space-y-1">
                {files.length > 1 && <Progress value={queueProgress} className="h-2" />}
                {pageProgress && pageProgress.pages_total > 0 ? (
                  <Progress
                    value={Math.round(
                      (pageProgress.pages_done / pageProgress.pages_total) * 100,
                    )}
                    className="h-2"
                  />
                ) : null}
                <p className="text-xs text-muted-foreground">
                  {pageProgress && pageProgress.pages_total > 0
                    ? `Page ${pageProgress.pages_done} / ${pageProgress.pages_total} — analyse IA…`
                    : files.length > 1
                      ? `Analyse en cours… ${queueProgress}%`
                      : 'Analyse IA en cours (1 à 3 min selon le nombre de pages)…'}
                </p>
              </div>
            )}

            <div className="flex justify-end gap-2">
              {files.length > 0 && (
                <Button type="button" variant="ghost" onClick={() => setFiles([])}>
                  Retirer
                </Button>
              )}
              <Button
                type="button"
                onClick={() => void analyzeFiles()}
                disabled={files.length === 0 || isAnalyzing}
              >
                {isAnalyzing ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="mr-2 h-4 w-4" />
                )}
                Analyser {files.length > 1 ? `(${files.length})` : 'le relevé'}
              </Button>
            </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
