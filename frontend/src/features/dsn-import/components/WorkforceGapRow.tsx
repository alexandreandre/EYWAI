import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { ExternalLink, UserMinus } from 'lucide-react';
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
  missing_from_dsn: 'Départ probable — absent de la DSN',
  contract_end_in_dsn: 'Fin de contrat dans la DSN',
};

const IGNORE_REASONS = [
  { value: 'dsn_incomplete', label: 'DSN incomplète / erreur fichier' },
  { value: 'other_establishment', label: 'Autre établissement' },
  { value: 'already_handled', label: 'Déjà traité ailleurs' },
  { value: 'other', label: 'Autre motif' },
] as const;

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
};

function WorkforceDepartureGapRow({ gap, batchId, resolution, onResolutionChange }: Props) {
  const defaultDate =
    gap.suggested_last_working_day?.slice(0, 10)
    ?? gap.contract_end_date?.slice(0, 10)
    ?? '';
  const [exitType, setExitType] = useState(resolution?.exit_type ?? 'demission');
  const [lastWorkingDay, setLastWorkingDay] = useState(
    resolution?.last_working_day?.slice(0, 10) ?? defaultDate,
  );
  const [ignoreReason, setIgnoreReason] = useState(resolution?.ignore_reason ?? 'dsn_incomplete');

  const gapLabel =
    gap.gap_type === 'missing_from_dsn' || gap.gap_type === 'contract_end_in_dsn'
      ? DEPARTURE_GAP_LABELS[gap.gap_type]
      : 'Écart effectif';

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

  return (
    <div className="rounded-lg border p-4 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium">{gap.employee_name}</p>
            <Badge variant="outline" className="text-xs">
              {gapLabel}
            </Badge>
            {resolution && (
              <Badge variant="secondary" className="text-xs">
                Décision enregistrée
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            NIR {gap.nir_masked}
            {gap.period && <> · DSN : {gap.period}</>}
            {defaultDate && (
              <>
                {' '}
                · Dernier jour suggéré :{' '}
                {new Date(defaultDate).toLocaleDateString('fr-FR')}
              </>
            )}
          </p>
        </div>
      </div>

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
