import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, ExternalLink, Trash2, UserMinus } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { exitTypeLabels, type ExitType } from '@/api/employeeExits';
import type { WorkforceGap, WorkforceResolution } from '@/api/dsnImport';
import { cn } from '@/lib/utils';
import { WorkforceNewHireGapRow } from './WorkforceNewHireGapRow';

const DEPARTURE_GAP_LABELS: Record<'missing_from_dsn' | 'contract_end_in_dsn', string> = {
  missing_from_dsn: 'Absent de la DSN du mois',
  contract_end_in_dsn: 'Fin de contrat dans la DSN',
};

const IGNORE_REASONS = [
  { value: 'dsn_incomplete', label: 'DSN incomplète / erreur fichier' },
  { value: 'other_establishment', label: 'Autre établissement' },
  { value: 'already_handled', label: 'Déjà traité ailleurs' },
  { value: 'other', label: 'Autre motif' },
] as const;

const EXIT_TYPES: { value: ExitType; label: string }[] = [
  { value: 'demission', label: exitTypeLabels.demission },
  { value: 'rupture_conventionnelle', label: exitTypeLabels.rupture_conventionnelle },
  { value: 'licenciement', label: exitTypeLabels.licenciement },
  { value: 'depart_retraite', label: exitTypeLabels.depart_retraite },
  { value: 'fin_periode_essai', label: exitTypeLabels.fin_periode_essai },
];

const MONTHS_FR = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

function formatGapPeriodLabel(period?: string | null): string {
  if (!period) return 'ce mois';
  const [y, m] = period.split('-');
  const mi = parseInt(m, 10);
  if (!y || !mi || mi < 1 || mi > 12) return period;
  return `${MONTHS_FR[mi - 1]} ${y}`;
}

function formatDateFr(iso?: string | null): string {
  if (!iso) return '—';
  try {
    return new Date(iso.slice(0, 10)).toLocaleDateString('fr-FR');
  } catch {
    return iso;
  }
}

function ignoreReasonLabel(value?: string | null): string {
  return IGNORE_REASONS.find((r) => r.value === value)?.label ?? value ?? '—';
}

function exitTypeLabel(value?: string | null): string {
  if (!value) return 'Départ';
  return exitTypeLabels[value as ExitType] ?? value;
}

function describeResolution(resolution: WorkforceResolution): {
  title: string;
  detail: string;
  tone: 'default' | 'destructive' | 'muted';
} {
  switch (resolution.action) {
    case 'close_departure':
      return {
        title: 'Clôture au moment de l’import',
        detail: `Un départ « ${exitTypeLabel(resolution.exit_type)} » sera créé et le salarié passera en « parti » (dernier jour : ${formatDateFr(resolution.last_working_day)}). Vous pourrez compléter documents et solde ensuite.`,
        tone: 'default',
      };
    case 'open_exit':
      return {
        title: 'Départ à traiter plus tard',
        detail: `La décision « ${exitTypeLabel(resolution.exit_type)} » (${formatDateFr(resolution.last_working_day)}) sera enregistrée, mais la fiche restera active jusqu’à ce que vous finalisiez le parcours Départs.`,
        tone: 'muted',
      };
    case 'ignore':
      return {
        title: 'Écart ignoré',
        detail: `Motif : ${ignoreReasonLabel(resolution.ignore_reason)}. Aucun changement sur la fiche — l’import se poursuit.`,
        tone: 'muted',
      };
    case 'delete_permanently':
      return {
        title: 'Suppression définitive prévue',
        detail: 'La fiche sera supprimée à la validation de l’import.',
        tone: 'destructive',
      };
    default:
      return {
        title: 'Décision enregistrée',
        detail: 'Vous pourrez modifier ce choix avant de valider l’import.',
        tone: 'default',
      };
  }
}

type Props = {
  gap: WorkforceGap;
  batchId: string;
  resolution?: WorkforceResolution;
  onResolutionChange: (resolution: WorkforceResolution) => void;
  onResolutionClear?: (gapId: string) => void;
};

function ActionHint({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <p className={cn('text-xs leading-snug text-muted-foreground', className)}>{children}</p>
  );
}

function WorkforceDepartureGapRow({
  gap,
  batchId,
  resolution,
  onResolutionChange,
  onResolutionClear,
}: Props) {
  const defaultDate =
    gap.suggested_last_working_day?.slice(0, 10)
    ?? gap.contract_end_date?.slice(0, 10)
    ?? '';
  const [exitType, setExitType] = useState<ExitType>(
    (resolution?.exit_type as ExitType | undefined) ?? 'demission',
  );
  const [lastWorkingDay, setLastWorkingDay] = useState(
    resolution?.last_working_day?.slice(0, 10) ?? defaultDate,
  );
  const [ignoreReason, setIgnoreReason] = useState(resolution?.ignore_reason ?? 'dsn_incomplete');
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const gapLabel =
    gap.gap_type === 'missing_from_dsn' || gap.gap_type === 'contract_end_in_dsn'
      ? DEPARTURE_GAP_LABELS[gap.gap_type]
      : 'Écart effectif';
  const isAbsentFromDsn = gap.gap_type === 'missing_from_dsn';
  const periodLabel = formatGapPeriodLabel(gap.period);
  const hasDate = Boolean(lastWorkingDay || defaultDate);

  const applyResolution = useCallback(
    (action: WorkforceResolution['action']) => {
      const base: WorkforceResolution = {
        gap_id: gap.gap_id,
        employee_id: gap.employee_id,
        action,
      };
      if (action === 'ignore') {
        onResolutionChange({ ...base, ignore_reason: ignoreReason });
        return;
      }
      if (action === 'delete_permanently') {
        onResolutionChange(base);
        setDeleteDialogOpen(false);
        return;
      }
      onResolutionChange({
        ...base,
        exit_type: exitType,
        last_working_day: lastWorkingDay || defaultDate,
        exit_reason:
          action === 'close_departure'
            ? `Réconciliation DSN — ${gapLabel}`
            : undefined,
      });
    },
    [gap, exitType, lastWorkingDay, defaultDate, ignoreReason, onResolutionChange, gapLabel],
  );

  const exitDeepLink = `/employee-exits?create=1&employeeId=${encodeURIComponent(gap.employee_id)}&exitType=${encodeURIComponent(exitType)}&returnTo=dsn-import&batchId=${encodeURIComponent(batchId)}`;

  const resolutionSummary = resolution ? describeResolution(resolution) : null;

  return (
    <div className="rounded-lg border p-4 space-y-4">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium">{gap.employee_name}</p>
          <Badge variant="outline" className="text-xs">
            {gapLabel}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          NIR {gap.nir_masked}
          {gap.period && <> · DSN : {gap.period}</>}
          {defaultDate && (
            <>
              {' '}
              · Dernier jour suggéré : {formatDateFr(defaultDate)}
            </>
          )}
        </p>
        {isAbsentFromDsn ? (
          <p className="text-xs text-muted-foreground">
            Ce salarié est actif en base mais n&apos;apparaît pas dans la DSN de {periodLabel}.
            Indiquez ce qu&apos;il s&apos;est passé avant de valider l&apos;import.
          </p>
        ) : null}
      </div>

      {resolutionSummary ? (
        <div
          className={cn(
            'rounded-md border px-3 py-3 text-sm',
            resolutionSummary.tone === 'destructive' && 'border-destructive/30 bg-destructive/5',
            resolutionSummary.tone === 'muted' && 'border-muted bg-muted/30',
            resolutionSummary.tone === 'default' && 'border-emerald-200 bg-emerald-50/60 dark:border-emerald-900 dark:bg-emerald-950/30',
          )}
        >
          <div className="flex items-start gap-2">
            <CheckCircle2
              className={cn(
                'mt-0.5 h-4 w-4 shrink-0',
                resolutionSummary.tone === 'destructive'
                  ? 'text-destructive'
                  : 'text-emerald-600 dark:text-emerald-400',
              )}
              aria-hidden
            />
            <div className="space-y-1">
              <p
                className={cn(
                  'font-medium',
                  resolutionSummary.tone === 'destructive' && 'text-destructive',
                )}
              >
                {resolutionSummary.title}
              </p>
              <p className="text-muted-foreground">{resolutionSummary.detail}</p>
            </div>
          </div>
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="mt-3"
            onClick={() => onResolutionClear?.(gap.gap_id)}
          >
            Changer de décision
          </Button>
        </div>
      ) : (
        <>
          <div className="rounded-md border bg-muted/20 p-3 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Si le salarié a quitté l&apos;entreprise
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor={`exit-type-${gap.gap_id}`}>Type de sortie</Label>
                <Select value={exitType} onValueChange={(v) => setExitType(v as ExitType)}>
                  <SelectTrigger id={`exit-type-${gap.gap_id}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {EXIT_TYPES.map((t) => (
                      <SelectItem key={t.value} value={t.value}>
                        {t.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor={`lwd-${gap.gap_id}`}>Dernier jour travaillé</Label>
                <Input
                  id={`lwd-${gap.gap_id}`}
                  type="date"
                  value={lastWorkingDay}
                  onChange={(e) => setLastWorkingDay(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Button
                type="button"
                size="sm"
                className="w-full justify-start sm:w-auto"
                onClick={() => applyResolution('close_departure')}
                disabled={!hasDate}
              >
                <UserMinus className="mr-2 h-3.5 w-3.5 shrink-0" />
                Clôturer le départ à la validation
              </Button>
              <ActionHint>
                Crée le départ en base et passe le salarié en « parti » dès que vous validez
                l&apos;import. Idéal si vous connaissez le motif et la date (démission, rupture
                conventionnelle, licenciement…).
              </ActionHint>
            </div>

            <div className="space-y-2 border-t border-border/60 pt-3">
              <Button type="button" size="sm" variant="outline" className="w-full justify-start sm:w-auto" asChild>
                <Link to={exitDeepLink} target="_blank" rel="noopener noreferrer">
                  <ExternalLink className="mr-2 h-3.5 w-3.5 shrink-0" />
                  Ouvrir le parcours Départs complet
                </Link>
              </Button>
              <ActionHint>
                Ouvre le module Départs dans un nouvel onglet (documents, solde, checklist). À
                utiliser si le dossier nécessite un suivi détaillé — l&apos;import peut ensuite être
                validé avec « départ à traiter » ci-dessous.
              </ActionHint>
            </div>

            <div className="space-y-2 border-t border-border/60 pt-3">
              <Button
                type="button"
                size="sm"
                variant="secondary"
                className="w-full justify-start sm:w-auto"
                onClick={() => applyResolution('open_exit')}
                disabled={!hasDate}
              >
                Enregistrer : départ à traiter plus tard
              </Button>
              <ActionHint>
                Mémorise le type et la date sans clôturer la fiche. Le salarié reste actif en
                attendant que vous finalisiez le départ dans le module Départs.
              </ActionHint>
            </div>
          </div>

          <div className="rounded-md border border-dashed p-3 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Si ce n&apos;est pas un départ
            </p>
            <div className="flex flex-wrap items-end gap-2">
              <div className="min-w-[200px] flex-1 space-y-2">
                <Label htmlFor={`ignore-${gap.gap_id}`}>Motif d&apos;écart</Label>
                <Select value={ignoreReason} onValueChange={setIgnoreReason}>
                  <SelectTrigger id={`ignore-${gap.gap_id}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {IGNORE_REASONS.map((r) => (
                      <SelectItem key={r.value} value={r.value}>
                        {r.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button type="button" size="sm" variant="outline" onClick={() => applyResolution('ignore')}>
                Ignorer cet écart
              </Button>
            </div>
            <ActionHint>
              Aucune modification sur la fiche. À choisir si la DSN est incomplète, si le salarié est
              sur un autre établissement, ou si le départ est déjà géré ailleurs.
            </ActionHint>
          </div>

          {isAbsentFromDsn && (
            <div className="border-t pt-2">
              <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <AlertDialogTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-auto px-0 text-xs text-muted-foreground hover:text-destructive"
                  >
                    <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                    Fiche créée par erreur — supprimer définitivement
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Supprimer {gap.employee_name} ?</AlertDialogTitle>
                    <AlertDialogDescription asChild>
                      <div className="space-y-2 text-sm text-muted-foreground">
                        <p>
                          Ce salarié est actif en base mais absent de la DSN de{' '}
                          <strong>{periodLabel}</strong>.
                        </p>
                        <p>
                          La suppression est définitive : fiche, cumuls et données associées seront
                          retirés à la validation de l&apos;import.
                        </p>
                      </div>
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Annuler</AlertDialogCancel>
                    <AlertDialogAction
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      onClick={() => applyResolution('delete_permanently')}
                    >
                      Supprimer définitivement
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function WorkforceGapRow(props: Props) {
  if (props.gap.gap_type === 'new_hire_not_in_dsn') {
    return (
      <WorkforceNewHireGapRow
        gap={props.gap}
        resolution={props.resolution}
        onResolutionChange={props.onResolutionChange}
      />
    );
  }
  return <WorkforceDepartureGapRow {...props} />;
}
