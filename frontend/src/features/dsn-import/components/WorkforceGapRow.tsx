import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, Trash2, UserMinus } from 'lucide-react';
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
import type { WorkforceGap, WorkforceResolution } from '@/api/dsnImport';
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

const EXIT_TYPES = [
  { value: 'demission', label: 'Démission' },
  { value: 'licenciement', label: 'Licenciement' },
  { value: 'depart_retraite', label: 'Départ retraite' },
  { value: 'fin_periode_essai', label: "Fin période d'essai" },
] as const;

type Props = {
  gap: WorkforceGap;
  batchId: string;
  resolution?: WorkforceResolution;
  onResolutionChange: (resolution: WorkforceResolution) => void;
  onResolutionClear?: (gapId: string) => void;
};

function resolutionBadge(resolution?: WorkforceResolution) {
  if (!resolution) return null;
  if (resolution.action === 'delete_permanently') {
    return (
      <Badge variant="destructive" className="text-xs">
        Suppression prévue
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="text-xs">
      Décision enregistrée
    </Badge>
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
  const [exitType, setExitType] = useState(resolution?.exit_type ?? 'demission');
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
  const isDeleteResolution = resolution?.action === 'delete_permanently';

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

  const periodLabel = formatGapPeriodLabel(gap.period);

  return (
    <div className="rounded-lg border p-4 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium">{gap.employee_name}</p>
            <Badge variant="outline" className="text-xs">
              {gapLabel}
            </Badge>
            {resolutionBadge(resolution)}
          </div>
          <p className="text-xs text-muted-foreground">
            NIR {gap.nir_masked}
            {gap.period && <> · DSN : {gap.period}</>}
            {defaultDate && !isDeleteResolution && (
              <>
                {' '}
                · Dernier jour suggéré :{' '}
                {new Date(defaultDate).toLocaleDateString('fr-FR')}
              </>
            )}
          </p>
        </div>
      </div>

      {isDeleteResolution ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-3 text-sm">
          <p className="font-medium text-destructive">Suppression définitive prévue</p>
          <p className="mt-1 text-muted-foreground">
            La fiche de <strong>{gap.employee_name}</strong> sera supprimée à la validation de
            l&apos;import (absent de la DSN de {periodLabel}).
          </p>
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
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor={`exit-type-${gap.gap_id}`}>Type de sortie</Label>
              <Select value={exitType} onValueChange={setExitType}>
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

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => applyResolution('close_departure')}
              disabled={!lastWorkingDay && !defaultDate}
            >
              <UserMinus className="mr-2 h-3.5 w-3.5" />
              Clôture rapide
            </Button>
            <Button type="button" size="sm" variant="outline" asChild>
              <Link to={exitDeepLink} target="_blank" rel="noopener noreferrer">
                <ExternalLink className="mr-2 h-3.5 w-3.5" />
                Parcours départ complet
              </Link>
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={() => applyResolution('open_exit')}
              disabled={!lastWorkingDay && !defaultDate}
            >
              Marquer : départ à traiter
            </Button>
          </div>

          <div className="flex flex-wrap items-end gap-2 border-t pt-3">
            <div className="min-w-[200px] flex-1 space-y-2">
              <Label htmlFor={`ignore-${gap.gap_id}`}>Ou ignorer cet écart</Label>
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
              Ignorer
            </Button>
          </div>

          {isAbsentFromDsn && (
            <div className="border-t pt-3">
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
