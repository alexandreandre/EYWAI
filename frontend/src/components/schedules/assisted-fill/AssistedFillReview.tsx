import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronRight,
  Download,
  Loader2,
  Trash2,
  UserCheck,
  UserX,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { EmployeeAssociateCombobox } from './EmployeeAssociateCombobox';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useToast } from '@/components/ui/use-toast';
import { cn } from '@/lib/utils';
import { downloadBlob } from '@/lib/downloadBlob';
import {
  persistTimesheetBatch,
  waitForTimesheetImportBatchCommitted,
  type AiCalendarProposal,
  type AiEmployeeProposal,
  type DayNature,
  type ReviewStatus,
  type RosterEmployee,
  type TimesheetCommitWarning,
} from '@/api/calendar';

const DAY_TYPES: { value: string; label: string }[] = [
  { value: 'travail', label: 'Travail' },
  { value: 'conge', label: 'Congé' },
  { value: 'ferie', label: 'Férié' },
  { value: 'arret_maladie', label: 'Arrêt maladie' },
  { value: 'absence', label: 'Absence' },
  { value: 'weekend', label: 'Week-end' },
];

const DAY_TYPE_LABELS: Record<string, string> = {
  ...Object.fromEntries(DAY_TYPES.map((t) => [t.value, t.label])),
  conges_payes: 'Congés payés',
  rtt: 'RTT',
};

function dayTypeLabel(type: string | null | undefined): string {
  if (!type) return '';
  return DAY_TYPE_LABELS[type] ?? type;
}

const WEEKDAY_LABELS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

type ReviewFilter = 'all' | 'ready' | 'verify' | 'empty' | 'incomplete';

type QualityIssue = 'extraction_incomplete' | 'weekly_total_gap' | 'match_doubtful' | null;

interface EditableDay {
  jour: number;
  heures: number | null;
  type: string;
  nature: DayNature;
  // Mois/année réels si différents du mois affiché (semaine à cheval sur 2 mois).
  year?: number | null;
  month?: number | null;
}

interface EditableRow {
  key: string;
  rawName: string;
  employeeId: string | null;
  confidence: AiEmployeeProposal['match_confidence'];
  reviewStatus: ReviewStatus;
  matricule: string | null;
  matchedName: string | null;
  warnings: string[];
  days: EditableDay[];
  weeklyTotalPdf: number | null;
  weeklyTotalImported: number | null;
  weeklyTotalGap: number | null;
  daysExpectedCount: number | null;
  daysImportedCount: number | null;
  coverageRatio: number | null;
  qualityIssue: QualityIssue;
  manuallyConfirmed: boolean;
}

export interface AssistedFillApplyMeta {
  focusWeekIndex?: number | null;
  highlightDays?: number[];
}

/** Jour du relevé refusé à l'écriture : une absence validée occupe le planning. */
interface PreservedAbsenceDay {
  employeeLabel: string;
  jour: number;
  message: string | null;
}

interface AssistedFillReviewProps {
  proposal: AiCalendarProposal;
  roster: RosterEmployee[];
  onApplied: (meta?: AssistedFillApplyMeta) => void;
  onBack: () => void;
  batchId?: string | null;
}

const MONTHS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

function formatIsoDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return iso;
  return `${d} ${MONTHS[m - 1]} ${y}`;
}

function weekdayLabel(year: number, month: number, jour: number): string {
  const d = new Date(year, month - 1, jour);
  return WEEKDAY_LABELS[(d.getDay() + 6) % 7];
}

function effectiveQualityIssue(row: EditableRow): QualityIssue {
  if (row.manuallyConfirmed) return null;
  if (row.qualityIssue) return row.qualityIssue;
  const expected = row.daysExpectedCount ?? 5;
  const imported =
    row.daysImportedCount ??
    row.days.filter((d) => d.heures != null && d.heures > 0).length;
  const gap = row.weeklyTotalGap ?? 0;
  if (expected > 0 && imported < expected) return 'extraction_incomplete';
  if (gap > 1) return 'weekly_total_gap';
  return null;
}

function rowQualityIssue(row: EditableRow): QualityIssue {
  return effectiveQualityIssue(row);
}

function rowStatus(row: EditableRow): ReviewStatus {
  if (row.reviewStatus === 'empty') return 'empty';
  if (!row.employeeId || row.reviewStatus === 'error') return 'error';
  const issue = rowQualityIssue(row);
  if (issue === 'match_doubtful') return 'warning';
  if (issue === 'extraction_incomplete' || issue === 'weekly_total_gap') return 'warning';
  if (row.reviewStatus === 'warning' || row.confidence === 'medium') return 'warning';
  return 'ok';
}

function isSavableRow(row: EditableRow, includeVerify: boolean): boolean {
  if (!row.employeeId || row.days.length === 0) return false;
  const issue = rowQualityIssue(row);
  if (rowStatus(row) === 'error' || rowStatus(row) === 'empty') return false;
  if (rowStatus(row) === 'ok' || row.manuallyConfirmed) return true;
  if (issue === 'extraction_incomplete') return true;
  if (
    issue === 'weekly_total_gap' &&
    row.confidence === 'high' &&
    Boolean(row.matricule)
  ) {
    return true;
  }
  if (includeVerify) return true;
  return false;
}

function isNoiseWarning(message: string): boolean {
  const text = message.trim();
  if (!text) return true;
  return (
    /employee\s*['"].+['"]\s*not found|employee.*not found|not found in (the )?(provided )?text|employé.*introuvable/i.test(
      text,
    ) ||
    /single_channel_extraction|extraction vision seule|extraction texte seule|écart vision\/ocr/i.test(
      text,
    ) ||
    /^for .+, the note\b|\bindicates a (leave|sick leave)\b|\bis unclear\b|\bsuggests a\b|\bpotential issue\b|\bmissing hours\b/i.test(
      text,
    ) ||
    /le total hebdomadaire pour .+ n'est pas visible|légère différence|le calcul des heures individuelles donne/i.test(
      text,
    ) ||
    /PDF de \d+ pages?, seules \d+ pages?|seules \d+ pages? (traitées|OCRisées)/i.test(
      text,
    ) ||
    /cheval sur deux mois/i.test(text)
  );
}

function visibleGlobalWarnings(proposal: AiCalendarProposal): string[] {
  return proposal.warnings.filter((w) => !isNoiseWarning(w));
}

function defaultReviewFilter(summary: {
  ready: number;
  warning: number;
  error: number;
}): ReviewFilter {
  if (summary.warning + summary.error > 0) return 'verify';
  return 'all';
}

/** Filtre « À vérifier » : doute d'identité / match — pas écarts ni extraction incomplète. */
function isMatchVerificationRow(row: EditableRow): boolean {
  const issue = rowQualityIssue(row);
  const status = rowStatus(row);
  if (status === 'error') return true;
  if (issue === 'extraction_incomplete' || issue === 'weekly_total_gap') return false;
  if (issue === 'match_doubtful') return true;
  if (status === 'warning') return true;
  return false;
}

function statusPriority(s: ReviewStatus): number {
  if (s === 'error') return 0;
  if (s === 'warning') return 1;
  if (s === 'ok') return 2;
  return 3;
}

function StatusBadge({ row }: { row: EditableRow }) {
  const issue = rowQualityIssue(row);
  const status = rowStatus(row);
  if (status === 'ok') {
    return (
      <Badge variant="outline" className="border-emerald-300 bg-emerald-50 text-emerald-700">
        <UserCheck className="mr-1 h-3 w-3" /> Prêt
      </Badge>
    );
  }
  if (issue === 'extraction_incomplete') {
    return (
      <Badge variant="outline" className="border-yellow-400 bg-yellow-50 text-yellow-800">
        <AlertTriangle className="mr-1 h-3 w-3" /> Extraction incomplète
      </Badge>
    );
  }
  if (issue === 'weekly_total_gap') {
    return (
      <Badge variant="outline" className="border-orange-300 bg-orange-50 text-orange-800">
        <AlertTriangle className="mr-1 h-3 w-3" /> Écart heures
      </Badge>
    );
  }
  if (status === 'warning') {
    return (
      <Badge variant="outline" className="border-amber-300 bg-amber-50 text-amber-700">
        <AlertTriangle className="mr-1 h-3 w-3" /> À vérifier
      </Badge>
    );
  }
  if (status === 'empty') {
    return (
      <Badge variant="outline" className="border-slate-300 bg-slate-50 text-slate-600">
        Semaine vide
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="border-destructive/40 bg-destructive/5 text-destructive">
      <UserX className="mr-1 h-3 w-3" /> Non identifié
    </Badge>
  );
}

function NatureToggle({
  nature,
  onChange,
}: {
  nature: DayNature;
  onChange: (n: DayNature) => void;
}) {
  const isPrevu = nature === 'prevu';
  return (
    <button
      type="button"
      onClick={() => onChange(isPrevu ? 'reel' : 'prevu')}
      className={cn(
        'rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide transition-colors',
        isPrevu
          ? 'bg-sky-100 text-sky-700 hover:bg-sky-200'
          : 'bg-violet-100 text-violet-700 hover:bg-violet-200',
      )}
    >
      {isPrevu ? 'Prév.' : 'Fait'}
    </button>
  );
}

function exportProposalCsv(proposal: AiCalendarProposal, rows: EditableRow[]) {
  const lines = ['matricule;nom_releve;employe;jour;heures;type;nature'];
  rows.forEach((row) => {
    const empLabel = row.matchedName ?? row.rawName;
    row.days.forEach((d) => {
      lines.push(
        [
          row.matricule ?? '',
          row.rawName,
          empLabel,
          d.jour,
          d.heures ?? '',
          d.type,
          d.nature,
        ].join(';'),
      );
    });
  });
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' });
  downloadBlob(blob, `import-pointages-${proposal.year}-${proposal.month}.csv`);
}

export function AssistedFillReview({
  proposal,
  roster,
  onApplied,
  onBack,
  batchId = null,
}: AssistedFillReviewProps) {
  const { toast } = useToast();
  const [isSaving, setIsSaving] = useState(false);
  // Jours refusés à l'écriture (absence validée préservée) : récapitulatif
  // affiché après enregistrement, avant fermeture de la revue.
  const [preservedAbsenceDays, setPreservedAbsenceDays] = useState<PreservedAbsenceDay[]>([]);
  const [pendingApplyMeta, setPendingApplyMeta] = useState<AssistedFillApplyMeta | null>(null);
  const [filter, setFilter] = useState<ReviewFilter>(() =>
    defaultReviewFilter(
      proposal.review_summary ?? {
        ready: 0,
        warning: 0,
        error: 0,
        empty: 0,
        total: proposal.employees.length,
      },
    ),
  );
  const [includeEmpty, setIncludeEmpty] = useState(false);
  const [includeOrange, setIncludeOrange] = useState(false);
  // Consigne texte sur 1-3 salariés : les points d'attention sont LA chose à
  // lire — ouverts d'office. Sur un gros import, repliés pour ne pas noyer.
  const [showGlobalWarnings, setShowGlobalWarnings] = useState(
    () => proposal.source === 'texte' && proposal.employees.length <= 3,
  );
  // Salarié unique : sa ligne dépliée d'office — le détail jour par jour est
  // exactement ce que le RH vient vérifier, et il remplit le modal.
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(() =>
    proposal.employees.length === 1
      ? new Set([`0-${proposal.employees[0].raw_name}`])
      : new Set(),
  );
  const [search, setSearch] = useState('');

  const isTabularImport = Boolean(
    proposal.detected_format?.startsWith('tabular'),
  );
  const isTextInstruction = proposal.source === 'texte';
  // Juste ce qu'il faut pour le RH : la barre de filtres/CSV n'a de sens que
  // sur un volume d'import — pas pour une consigne portant sur 1-3 salariés.
  const showToolbar = !isTextInstruction || proposal.employees.length > 3;

  const [rows, setRows] = useState<EditableRow[]>(() =>
    proposal.employees.map((emp, idx) => ({
      key: `${idx}-${emp.raw_name}`,
      rawName: emp.raw_name,
      employeeId: emp.employee_id,
      confidence: emp.match_confidence,
      reviewStatus: emp.review_status ?? 'ok',
      matricule: emp.time_tracking_id ?? null,
      matchedName: emp.matched_name,
      warnings: emp.warnings.filter((w) => !isNoiseWarning(w)),
      days: emp.days.map((d) => ({
        jour: d.jour,
        heures: d.heures,
        type: d.type,
        nature: d.nature,
        year: d.year ?? null,
        month: d.month ?? null,
      })),
      weeklyTotalPdf: emp.weekly_total_pdf ?? null,
      weeklyTotalImported: emp.weekly_total_imported ?? null,
      weeklyTotalGap: emp.weekly_total_gap ?? null,
      daysExpectedCount: emp.days_expected_count ?? null,
      daysImportedCount: emp.days_imported_count ?? null,
      coverageRatio: emp.coverage_ratio ?? null,
      qualityIssue: (emp.quality_issue as QualityIssue) ?? null,
      manuallyConfirmed: false,
    })),
  );

  const summary = useMemo(() => {
    let ready = 0;
    let warning = 0;
    let error = 0;
    let empty = 0;
    let incomplete = 0;
    let gap = 0;
    rows.forEach((r) => {
      const issue = rowQualityIssue(r);
      if (rowStatus(r) === 'empty') empty += 1;
      else if (rowStatus(r) === 'error') error += 1;
      else if (issue === 'extraction_incomplete') incomplete += 1;
      else if (issue === 'weekly_total_gap') gap += 1;
      else if (rowStatus(r) === 'warning') warning += 1;
      else ready += 1;
    });
    return { ready, warning, error, empty, incomplete, gap, total: rows.length };
  }, [rows]);

  const sortedRoster = useMemo(
    () =>
      [...roster].sort((a, b) =>
        `${a.last_name} ${a.first_name}`.localeCompare(
          `${b.last_name} ${b.first_name}`,
          'fr',
        ),
      ),
    [roster],
  );

  const filterCounts = useMemo(() => {
    const withoutEmpty = rows.filter((r) => rowStatus(r) !== 'empty');
    const withEmptyIfChecked = includeEmpty ? rows : withoutEmpty;
    return {
      all: withEmptyIfChecked.length,
      ready: withEmptyIfChecked.filter((r) => rowStatus(r) === 'ok').length,
      verify: withEmptyIfChecked.filter(isMatchVerificationRow).length,
      incomplete: withEmptyIfChecked.filter(
        (r) => rowQualityIssue(r) === 'extraction_incomplete',
      ).length,
      empty: rows.filter((r) => rowStatus(r) === 'empty').length,
    };
  }, [rows, includeEmpty]);

  const filteredRows = useMemo(() => {
    let list = [...rows].sort(
      (a, b) => statusPriority(rowStatus(a)) - statusPriority(rowStatus(b)),
    );
    if (!includeEmpty && filter !== 'empty') {
      list = list.filter((r) => rowStatus(r) !== 'empty');
    }
    if (filter === 'ready') list = list.filter((r) => rowStatus(r) === 'ok');
    if (filter === 'verify') {
      list = list.filter(isMatchVerificationRow);
    }
    if (filter === 'incomplete') {
      list = list.filter((r) => rowQualityIssue(r) === 'extraction_incomplete');
    }
    if (filter === 'empty') list = list.filter((r) => rowStatus(r) === 'empty');
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (r) =>
          r.rawName.toLowerCase().includes(q) ||
          (r.matchedName ?? '').toLowerCase().includes(q) ||
          (r.matricule ?? '').includes(q),
      );
    }
    return list;
  }, [rows, filter, includeEmpty, search]);

  const savableRows = useMemo(() => {
    return rows.filter((r) => isSavableRow(r, includeOrange));
  }, [rows, includeOrange]);

  const totalDaysToSave = savableRows.reduce((acc, r) => acc + r.days.length, 0);

  const takenEmployeeIds = useMemo(
    () => rows.filter((r) => r.employeeId).map((r) => r.employeeId as string),
    [rows],
  );

  const associateEmployee = (rowKey: string, employeeId: string, matchedName: string) => {
    setRows((prev) => {
      const conflicting = prev.find(
        (r) => r.key !== rowKey && r.employeeId === employeeId,
      );
      if (conflicting) {
        toast({
          title: 'Salarié réassigné',
          description: `${matchedName} était déjà associé à « ${conflicting.rawName} » — cette ligne repasse en attente de rapprochement.`,
        });
      }
      return prev.map((r) => {
        if (r.key === rowKey) {
          return {
            ...r,
            employeeId,
            matchedName,
            confidence: 'high' as const,
            reviewStatus: 'ok' as const,
            manuallyConfirmed: true,
            qualityIssue: null,
          };
        }
        if (conflicting && r.key === conflicting.key) {
          return {
            ...r,
            employeeId: null,
            matchedName: null,
            confidence: 'none' as const,
            reviewStatus: 'error' as const,
            manuallyConfirmed: false,
          };
        }
        return r;
      });
    });
  };

  const confirmVerifiedRow = (rowKey: string) => {
    updateRow(rowKey, {
      confidence: 'high',
      reviewStatus: 'ok',
      manuallyConfirmed: true,
      qualityIssue: null,
    });
  };

  const formatDocumentNameHint = (rawName: string) =>
    isTabularImport
      ? `Lu dans le fichier : « ${rawName} ».`
      : `Lu sur le PDF : « ${rawName} » (peut être erroné).`;

  const updateRow = (key: string, patch: Partial<EditableRow>) => {
    setRows((prev) => prev.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  };

  const updateDay = (rowKey: string, jour: number, patch: Partial<EditableDay>) => {
    setRows((prev) =>
      prev.map((r) =>
        r.key === rowKey
          ? { ...r, days: r.days.map((d) => (d.jour === jour ? { ...d, ...patch } : d)) }
          : r,
      ),
    );
  };

  const removeDay = (rowKey: string, jour: number) => {
    setRows((prev) =>
      prev.map((r) =>
        r.key === rowKey ? { ...r, days: r.days.filter((d) => d.jour !== jour) } : r,
      ),
    );
  };

  const toggleExpand = (key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const employeeWarningLabel = (employeeId: string | null | undefined): string => {
    if (employeeId) {
      const row = rows.find((r) => r.employeeId === employeeId);
      if (row) return row.matchedName ?? row.rawName;
      const emp = roster.find((e) => e.id === employeeId);
      if (emp) return `${emp.last_name} ${emp.first_name}`;
    }
    return 'Salarié inconnu';
  };

  /** Ne garde que les refus « absence validée préservée », prêts à afficher. */
  const toPreservedAbsenceDays = (
    raw: TimesheetCommitWarning[] | null | undefined,
  ): PreservedAbsenceDay[] => {
    if (!raw?.length) return [];
    return raw
      .filter((w) => w.code === 'absence_validee_preservee')
      .map((w) => ({
        employeeLabel: employeeWarningLabel(w.employee_id),
        jour: w.jour,
        message:
          w.message ??
          (w.type_avant
            ? `Absence validée (${dayTypeLabel(w.type_avant)}) conservée`
              + (w.type_refuse
                ? ` — « ${dayTypeLabel(w.type_refuse)} » du relevé ignoré.`
                : '.')
            : null),
      }))
      .sort(
        (a, b) =>
          a.employeeLabel.localeCompare(b.employeeLabel, 'fr') || a.jour - b.jour,
      );
  };

  /** Toast final + soit fermeture immédiate, soit récapitulatif des refus. */
  const finishSave = (
    preserved: PreservedAbsenceDay[],
    successDescription: string,
    meta: AssistedFillApplyMeta,
  ) => {
    if (preserved.length > 0) {
      toast({
        title: 'Heures enregistrées — jours préservés',
        description: `${preserved.length} jour(s) laissé(s) en l'état : absence validée (voir détail).`,
        variant: 'warning',
      });
      setPreservedAbsenceDays(preserved);
      setPendingApplyMeta(meta);
      return;
    }
    toast({ title: 'Heures enregistrées', description: successDescription });
    onApplied(meta);
  };

  const handleSave = async () => {
    if (savableRows.length === 0) {
      toast({
        title: 'Rien à enregistrer',
        description: 'Aucun salarié prêt à enregistrer avec les filtres actuels.',
        variant: 'destructive',
      });
      return;
    }
    const lowCoverage = savableRows.some(
      (r) => (r.coverageRatio ?? 1) < 0.4 && rowQualityIssue(r) === 'extraction_incomplete',
    );
    if (lowCoverage && !window.confirm(
      'Certains salariés ont une extraction très incomplète (< 40 % des jours). '
      + 'Les jours non lus resteront vides au planning. Continuer ?',
    )) {
      return;
    }
    setIsSaving(true);
    try {
      const result = await persistTimesheetBatch(
        proposal.year,
        proposal.month,
        savableRows.map((row) => ({
          employee_id: row.employeeId as string,
          days: row.days.map((d) => ({
            jour: d.jour,
            heures: d.heures,
            type: d.type,
            nature: d.nature,
            year: d.year ?? null,
            month: d.month ?? null,
          })),
        })),
        { batchId: batchId ?? undefined, allowPartial: true },
      );

      const applyMeta: AssistedFillApplyMeta = {
        focusWeekIndex: proposal.focus_week_index,
        highlightDays: savableRows.flatMap((r) => r.days.map((d) => d.jour)),
      };

      if (batchId && result.total_days_written === 0) {
        const committed = await waitForTimesheetImportBatchCommitted(batchId);
        const days = committed.preview?.employees.reduce(
          (acc, e) => acc + e.days.length,
          0,
        ) ?? 0;
        // Le commit asynchrone dépose ses refus dans le résumé du batch.
        const preserved = toPreservedAbsenceDays(
          result.warnings?.length
            ? result.warnings
            : committed.summary?.commit_warnings,
        );
        finishSave(
          preserved,
          `${savableRows.length} salarié(s) · ${days} jour(s) mis à jour.`,
          applyMeta,
        );
        return;
      }
      const preserved = toPreservedAbsenceDays(result.warnings);
      const failed = result.results.filter((r) => !r.success);
      if (failed.length > 0) {
        toast({
          title: 'Enregistrement partiel',
          description: `${result.total_days_written} jour(s) · ${failed.length} échec(s).`,
          variant: 'destructive',
        });
        if (preserved.length > 0) {
          setPreservedAbsenceDays(preserved);
          setPendingApplyMeta(applyMeta);
          return;
        }
        onApplied(applyMeta);
        return;
      }
      finishSave(
        preserved,
        `${savableRows.length} salarié(s) · ${result.total_days_written} jour(s) mis à jour.`,
        applyMeta,
      );
    } catch {
      toast({
        title: 'Erreur',
        description: "L'enregistrement a échoué.",
        variant: 'destructive',
      });
    } finally {
      setIsSaving(false);
    }
  };

  const globalWarnings = useMemo(() => visibleGlobalWarnings(proposal), [proposal]);
  const noiseWarningCount = proposal.warnings.length - globalWarnings.length;

  const periodRangeLabel = useMemo(() => {
    if (proposal.detected_period_start && proposal.detected_period_end) {
      return `${formatIsoDate(proposal.detected_period_start)} – ${formatIsoDate(proposal.detected_period_end)}`;
    }
    return null;
  }, [proposal.detected_period_start, proposal.detected_period_end]);

  const formatLabel =
    proposal.detected_format === 'cegid_weekly'
      ? 'Relevé Cegid hebdomadaire'
      : proposal.detected_format === 'hybrid_vision_ocr'
        ? 'IA hybride (vision + OCR)'
        : proposal.extraction_method === 'native_pdf' ||
            proposal.extraction_method === 'native_image'
          ? 'Lecture IA du relevé'
          : proposal.extraction_method === 'native_text_layer'
            ? 'Relevé Cegid (texte)'
            : isTabularImport
              ? proposal.detected_scope === 'weekly'
                ? 'Relevé Excel/CSV hebdomadaire'
                : 'Relevé Excel/CSV'
              : isTextInstruction
                ? 'Consigne texte'
                : proposal.source;

  if (preservedAbsenceDays.length > 0) {
    // Récapitulatif post-enregistrement : jours refusés car absence validée.
    return (
      <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
        <div className="shrink-0 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-amber-900">
          <p className="flex items-center gap-1.5 text-sm font-medium">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {preservedAbsenceDays.length} jour(s) laissé(s) en l&apos;état : absence validée
          </p>
          <p className="mt-1 text-xs">
            Une absence validée occupe déjà ces jours au planning : le relevé ne
            les a pas modifiés. Le reste de l&apos;import a bien été enregistré.
          </p>
        </div>
        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-1 pr-3">
            {preservedAbsenceDays.map((w, i) => (
              <div
                key={`${w.employeeLabel}-${w.jour}-${i}`}
                className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 rounded-md border border-amber-200/70 bg-amber-50/40 px-2 py-1.5 text-xs"
              >
                <span className="font-medium">{w.employeeLabel}</span>
                <span className="tabular-nums text-muted-foreground">
                  jour {w.jour}
                </span>
                {w.message && <span className="text-amber-800">{w.message}</span>}
              </div>
            ))}
          </div>
        </ScrollArea>
        <div className="flex shrink-0 justify-end border-t pt-2">
          <Button
            type="button"
            size="sm"
            onClick={() => onApplied(pendingApplyMeta ?? undefined)}
          >
            <Check className="mr-2 h-4 w-4" />
            Fermer
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-hidden">
      {/* Bandeau synthèse compact */}
      <div className="shrink-0 rounded-md border bg-muted/20 px-3 py-2 text-xs">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          {periodRangeLabel && (
            <span className="font-medium text-sm">{periodRangeLabel}</span>
          )}
          <span className="text-muted-foreground">{formatLabel}</span>
          {proposal.month_auto_corrected && (
            <span className="text-sky-700">· mois auto-ajusté</span>
          )}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          <Badge className="h-5 bg-emerald-600 px-1.5 text-[10px] hover:bg-emerald-600">
            {summary.ready} prêt{summary.ready > 1 ? 's' : ''}
          </Badge>
          {summary.incomplete > 0 && (
            <Badge variant="outline" className="h-5 border-yellow-400 px-1.5 text-[10px] text-yellow-800">
              {summary.incomplete} incomplets
            </Badge>
          )}
          {summary.gap > 0 && (
            <Badge variant="outline" className="h-5 border-orange-300 px-1.5 text-[10px] text-orange-800">
              {summary.gap} écarts h.
            </Badge>
          )}
          {summary.warning > 0 && (
            <Badge variant="outline" className="h-5 border-amber-300 px-1.5 text-[10px] text-amber-800">
              {summary.warning} à vérifier
            </Badge>
          )}
          {summary.error > 0 && (
            <Badge variant="outline" className="h-5 border-destructive/40 px-1.5 text-[10px] text-destructive">
              {summary.error} non identifié{summary.error > 1 ? 's' : ''}
            </Badge>
          )}
          {summary.empty > 0 && (
            <Badge variant="outline" className="h-5 px-1.5 text-[10px] text-muted-foreground">
              {summary.empty} vides
            </Badge>
          )}
          {(proposal.roster_not_in_document_count ?? 0) > 0 && (
            <Badge variant="outline" className="h-5 px-1.5 text-[10px] text-muted-foreground">
              {proposal.roster_not_in_document_count} hors relevé
            </Badge>
          )}
        </div>
        {proposal.affected_months && proposal.affected_months.length > 1 && (
          <p className="mt-1.5 text-[11px] leading-snug text-amber-800">
            Cette semaine touche plusieurs mois :{' '}
            {proposal.affected_months.map((m) => `${m.month}/${m.year}`).join(', ')}.
          </p>
        )}
        {proposal.month_auto_corrected && proposal.month_correction_message && (
          <p className="mt-1.5 text-[11px] leading-snug text-sky-800">
            {proposal.month_correction_message}
          </p>
        )}
        {!proposal.extraction_truncated &&
          (proposal.extraction_pages_processed ?? 0) > 1 &&
          (proposal.extraction_method?.includes('OCR') ||
            proposal.extraction_method?.includes('hybrid')) && (
          <p className="mt-1 text-[10px] text-muted-foreground">
            {proposal.extraction_pages_processed} pages analysées.
          </p>
        )}
        {(proposal.consensus_conflicts ?? 0) > 0 && (
          <p className="mt-1 text-[10px] text-amber-800">
            {proposal.consensus_conflicts} écart(s) vision/OCR — vérifiez les heures signalées.
          </p>
        )}
        {!isTabularImport && !isTextInstruction && (
          <p className="mt-1 text-[10px] text-destructive">
            Import IA — les noms lus sur le PDF peuvent être erronés.
          </p>
        )}
        {isTextInstruction && (
          <p className="mt-1 text-[10px] text-muted-foreground">
            Vérifiez les jours proposés avant d&apos;enregistrer.
          </p>
        )}
        {isTabularImport && (
          <p className="mt-1 text-[10px] text-muted-foreground">
            Import fichier — associez manuellement les salariés non reconnus si besoin.
          </p>
        )}
      </div>

      {/* Barre outils — masquée pour une consigne texte sur peu de salariés */}
      {showToolbar && (
      <div className="flex shrink-0 flex-wrap items-center gap-1.5">
        <Input
          placeholder="Rechercher…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="h-7 max-w-[140px] text-xs"
        />
        {(['all', 'ready', 'verify', 'incomplete', 'empty'] as ReviewFilter[]).map((f) => (
          <Button
            key={f}
            type="button"
            size="sm"
            variant={filter === f ? 'default' : 'outline'}
            className="h-7 px-2 text-[11px]"
            onClick={() => setFilter(f)}
          >
            {f === 'all' && `Tous (${filterCounts.all})`}
            {f === 'ready' && `Prêts (${filterCounts.ready})`}
            {f === 'verify' && `À vérifier (${filterCounts.verify})`}
            {f === 'incomplete' && `Incomplets (${filterCounts.incomplete})`}
            {f === 'empty' && `Vides (${filterCounts.empty})`}
          </Button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <label className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <Checkbox
              className="h-3.5 w-3.5"
              checked={includeOrange}
              onCheckedChange={(v) => setIncludeOrange(v === true)}
            />
            Inclure écarts / match douteux
          </label>
          <label className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <Checkbox
              className="h-3.5 w-3.5"
              checked={includeEmpty}
              onCheckedChange={(v) => setIncludeEmpty(v === true)}
            />
            Vides
          </label>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-[11px]"
            onClick={() => exportProposalCsv(proposal, rows)}
          >
            <Download className="mr-1 h-3 w-3" />
            CSV
          </Button>
        </div>
      </div>
      )}

      {(globalWarnings.length > 0 || noiseWarningCount > 0) && (
        <div className="shrink-0 rounded-md border border-amber-200/80 bg-amber-50/50 px-2 py-1.5 text-[11px] text-amber-900">
          <button
            type="button"
            className="flex w-full items-center gap-1 text-left font-medium"
            onClick={() => setShowGlobalWarnings((v) => !v)}
          >
            {showGlobalWarnings ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
            {globalWarnings.length > 0
              ? `${globalWarnings.length} point${globalWarnings.length > 1 ? 's' : ''} d'attention`
              : `${noiseWarningCount} alerte(s) masquée(s) (salariés hors PDF)`}
          </button>
          {showGlobalWarnings && (
            <div className="mt-1 space-y-0.5 pl-5">
              {globalWarnings.map((w, i) => (
                <p key={i}>{w}</p>
              ))}
              {noiseWarningCount > 0 && (
                <p className="text-muted-foreground">
                  {noiseWarningCount} salarié(s) du roster absents du relevé — normal, non
                  affichés.
                </p>
              )}
            </div>
          )}
        </div>
      )}

      {/* Liste scrollable */}
      <ScrollArea className="min-h-0 flex-1">
        <div className="space-y-1.5 pr-3">
          {filteredRows.map((row) => {
            const status = rowStatus(row);
            const expanded = expandedKeys.has(row.key);
            const daySum = row.days.reduce((a, d) => a + (d.heures ?? 0), 0);
            const needsAssociate = !row.employeeId || status === 'error';
            const canConfirmVerification = !needsAssociate && isMatchVerificationRow(row);
            return (
              <div
                key={row.key}
                className={cn(
                  'rounded-md border px-2 py-1.5',
                  status === 'error' && 'border-destructive/30 bg-destructive/[0.02]',
                  status === 'warning' && 'border-amber-300/60 bg-amber-50/30',
                  status === 'ok' && 'border-border/60',
                )}
              >
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    className="shrink-0 text-muted-foreground"
                    onClick={() => toggleExpand(row.key)}
                    aria-label={expanded ? 'Replier' : 'Déplier'}
                  >
                    {expanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4" />
                    )}
                  </button>
                  <button
                    type="button"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => toggleExpand(row.key)}
                  >
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="truncate text-sm font-medium leading-tight">
                        {row.matchedName ?? row.rawName}
                      </span>
                      {row.matricule && (
                        <span className="text-[10px] text-muted-foreground">{row.matricule}</span>
                      )}
                      <StatusBadge row={row} />
                    </div>
                    <p className="text-[11px] text-muted-foreground">
                      {row.days.length} j · {daySum.toFixed(1)} h
                      {row.daysExpectedCount != null && (
                        <span> · couverture {row.daysImportedCount ?? row.days.length}/{row.daysExpectedCount}</span>
                      )}
                      {row.weeklyTotalGap != null && row.weeklyTotalGap > 0.25 && (
                        <span className="text-amber-700"> · Δ {row.weeklyTotalGap.toFixed(2)} h</span>
                      )}
                    </p>
                  </button>
                  {needsAssociate && (
                    <EmployeeAssociateCombobox
                      roster={sortedRoster}
                      value={row.employeeId}
                      compact
                      placeholder="Associer…"
                      excludeEmployeeIds={takenEmployeeIds}
                      emptyMessage="Tous les salariés proposés sont déjà rapprochés — réassignez depuis leur ligne si besoin."
                      onSelect={(id, label) => associateEmployee(row.key, id, label)}
                    />
                  )}
                  {canConfirmVerification && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-7 shrink-0 border-emerald-300 px-2 text-[11px] text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800"
                      onClick={() => confirmVerifiedRow(row.key)}
                    >
                      <Check className="mr-1 h-3.5 w-3.5" />
                      Valider
                    </Button>
                  )}
                </div>

                {row.warnings.length > 0 && status !== 'ok' && (
                  <p className="mt-0.5 pl-6 text-[11px] text-amber-700">{row.warnings[0]}</p>
                )}
                {needsAssociate && (
                  <p className="mt-0.5 pl-6 text-[11px] text-muted-foreground">
                    {formatDocumentNameHint(row.rawName)}
                  </p>
                )}

                {expanded && (
                  <div className="mt-1.5 space-y-1 border-t pt-1.5 pl-5">
                    {!needsAssociate && (
                      <div className="mb-1 flex justify-end">
                        <EmployeeAssociateCombobox
                          roster={sortedRoster}
                          value={row.employeeId}
                          excludeEmployeeIds={takenEmployeeIds}
                          emptyMessage="Tous les salariés proposés sont déjà rapprochés — réassignez depuis leur ligne si besoin."
                          onSelect={(id, label) => associateEmployee(row.key, id, label)}
                        />
                      </div>
                    )}
                    {row.days.map((day) => (
                      <div
                        key={day.jour}
                        className="flex flex-wrap items-center gap-1.5 rounded bg-muted/30 px-1.5 py-1"
                      >
                        <span className="w-20 text-[11px] font-medium tabular-nums">
                          {weekdayLabel(day.year ?? proposal.year, day.month ?? proposal.month, day.jour)}{' '}
                          {day.jour}
                          {(day.month ?? proposal.month) !== proposal.month && (
                            <span className="text-muted-foreground">
                              /{String(day.month ?? proposal.month).padStart(2, '0')}
                            </span>
                          )}
                        </span>
                        <Input
                          type="number"
                          step="0.25"
                          min="0"
                          value={day.heures ?? ''}
                          onChange={(e) =>
                            updateDay(row.key, day.jour, {
                              heures: e.target.value === '' ? null : Number(e.target.value),
                            })
                          }
                          className="h-7 w-14 px-1 text-xs"
                        />
                        <Select
                          value={day.type}
                          onValueChange={(v) => updateDay(row.key, day.jour, { type: v })}
                        >
                          <SelectTrigger className="h-7 w-[72px] px-1 text-[11px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {DAY_TYPES.map((t) => (
                              <SelectItem key={t.value} value={t.value} className="text-xs">
                                {t.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <NatureToggle
                          nature={day.nature}
                          onChange={(n) => updateDay(row.key, day.jour, { nature: n })}
                        />
                        <button
                          type="button"
                          onClick={() => removeDay(row.key, day.jour)}
                          className="ml-auto text-muted-foreground hover:text-destructive"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          {filteredRows.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Aucun salarié pour ce filtre.
            </p>
          )}
        </div>
      </ScrollArea>

      {/* Pied fixe */}
      <div className="flex shrink-0 items-center justify-between border-t pt-2">
        <Button type="button" variant="ghost" size="sm" onClick={onBack} disabled={isSaving}>
          Retour
        </Button>
        <Button type="button" size="sm" onClick={() => void handleSave()} disabled={isSaving}>
          {isSaving ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Check className="mr-2 h-4 w-4" />
          )}
          Enregistrer ({savableRows.length} · {totalDaysToSave} j)
        </Button>
      </div>
    </div>
  );
}
