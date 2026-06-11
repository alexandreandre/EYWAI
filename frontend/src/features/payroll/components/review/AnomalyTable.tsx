import { Fragment, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
import type { PreflightAnomaly, PreflightAnomalyType } from '@/api/payrollPreflight';
import {
  PREFLIGHT_ANOMALY_TYPE_LABELS,
  PREFLIGHT_STATUS_LABELS,
  correctionPathForType,
  formatEcartValue,
} from '@/features/payroll/components/review/preflightLabels';

interface AnomalyTableProps {
  anomalies: PreflightAnomaly[];
  teamNames: Record<string, string>;
  activeType: PreflightAnomalyType | 'all';
  selectedIds: Set<string>;
  onSelectedIdsChange: (ids: Set<string>) => void;
  onJustify: (anomalies: PreflightAnomaly[]) => void;
  onRemoveJustification: (anomaly: PreflightAnomaly) => void;
}

function severityBadge(severity: PreflightAnomaly['severity']) {
  if (severity === 'bloquant') {
    return (
      <Badge variant="destructive" className="font-normal">
        Bloquant
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-100">
      À vérifier
    </Badge>
  );
}

function statusBadge(status: PreflightAnomaly['status']) {
  if (status === 'a_traiter') {
    return (
      <Badge variant="outline" className="border-amber-300 text-amber-800 dark:text-amber-200">
        {PREFLIGHT_STATUS_LABELS[status]}
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="border-success/40 text-success">
      {PREFLIGHT_STATUS_LABELS[status]}
    </Badge>
  );
}

export function AnomalyTable({
  anomalies,
  teamNames,
  activeType,
  selectedIds,
  onSelectedIdsChange,
  onJustify,
  onRemoveJustification,
}: AnomalyTableProps) {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    if (activeType === 'all') return anomalies;
    return anomalies.filter((a) => a.type === activeType);
  }, [anomalies, activeType]);

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleSelected = (id: string, checked: boolean) => {
    const next = new Set(selectedIds);
    if (checked) next.add(id);
    else next.delete(id);
    onSelectedIdsChange(next);
  };

  const selectableOpen = filtered.filter((a) => a.status === 'a_traiter');
  const allSelected =
    selectableOpen.length > 0 && selectableOpen.every((a) => selectedIds.has(a.id));

  const toggleSelectAll = () => {
    if (allSelected) {
      onSelectedIdsChange(new Set());
      return;
    }
    onSelectedIdsChange(new Set(selectableOpen.map((a) => a.id)));
  };

  if (filtered.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border px-6 py-10 text-center text-sm text-muted-foreground">
        Aucune anomalie dans cette catégorie pour le mois sélectionné.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-10">
              <Checkbox
                checked={allSelected}
                onCheckedChange={toggleSelectAll}
                aria-label="Tout sélectionner"
              />
            </TableHead>
            <TableHead>Salarié</TableHead>
            <TableHead>Type</TableHead>
            <TableHead className="text-right">Prévu</TableHead>
            <TableHead className="text-right">Réel</TableHead>
            <TableHead className="text-right">Écart</TableHead>
            <TableHead>Statut</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filtered.map((anomaly) => {
            const expanded = expandedIds.has(anomaly.id);
            const hasDetails =
              anomaly.detail_jours.length > 0 ||
              anomaly.conflict_days.length > 0 ||
              (anomaly.days_with_pointage_anomalies ?? 0) > 0;
            const unit = anomaly.is_forfait_jour ? ' j' : ' h';
            const teamLabel = anomaly.team_id ? teamNames[anomaly.team_id] : null;

            return (
              <Fragment key={anomaly.id}>
                <TableRow className={anomaly.status !== 'a_traiter' ? 'opacity-80' : undefined}>
                  <TableCell>
                    <Checkbox
                      checked={selectedIds.has(anomaly.id)}
                      disabled={anomaly.status !== 'a_traiter'}
                      onCheckedChange={(checked) =>
                        toggleSelected(anomaly.id, checked === true)
                      }
                      aria-label={`Sélectionner ${anomaly.employee_name}`}
                    />
                  </TableCell>
                  <TableCell>
                    <div className="flex items-start gap-1">
                      {hasDetails ? (
                        <button
                          type="button"
                          className="mt-0.5 text-muted-foreground"
                          onClick={() => toggleExpanded(anomaly.id)}
                          aria-expanded={expanded}
                        >
                          {expanded ? (
                            <ChevronDown className="h-4 w-4" aria-hidden />
                          ) : (
                            <ChevronRight className="h-4 w-4" aria-hidden />
                          )}
                        </button>
                      ) : (
                        <span className="w-4" />
                      )}
                      <div>
                        <p className="font-medium leading-tight">{anomaly.employee_name}</p>
                        {teamLabel && (
                          <p className="text-xs text-muted-foreground">{teamLabel}</p>
                        )}
                        {anomaly.message && (
                          <p className="mt-0.5 text-xs text-muted-foreground">{anomaly.message}</p>
                        )}
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <span className="text-sm">{PREFLIGHT_ANOMALY_TYPE_LABELS[anomaly.type]}</span>
                      {severityBadge(anomaly.severity)}
                    </div>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {anomaly.heures_prevues != null
                      ? `${anomaly.heures_prevues.toFixed(1)}${unit}`
                      : '—'}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {anomaly.heures_faites != null
                      ? `${anomaly.heures_faites.toFixed(1)}${unit}`
                      : '—'}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    <span
                      className={cn(
                        'font-medium',
                        anomaly.ecart != null && Math.abs(anomaly.ecart) > 0
                          ? 'text-amber-700 dark:text-amber-300'
                          : undefined,
                      )}
                    >
                      {formatEcartValue(anomaly)}
                    </span>
                  </TableCell>
                  <TableCell>{statusBadge(anomaly.status)}</TableCell>
                  <TableCell className="text-right">
                    <div className="flex flex-wrap justify-end gap-1">
                      {anomaly.status === 'a_traiter' ? (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => onJustify([anomaly])}
                          >
                            Justifier
                          </Button>
                          <Button size="sm" variant="ghost" asChild>
                            <Link to={correctionPathForType(anomaly.type)}>Corriger</Link>
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => onRemoveJustification(anomaly)}
                        >
                          Annuler
                        </Button>
                      )}
                    </div>
                  </TableCell>
                </TableRow>

                {expanded && hasDetails && (
                  <TableRow className="bg-muted/20 hover:bg-muted/20">
                    <TableCell colSpan={8} className="py-3">
                      {anomaly.detail_jours.length > 0 && (
                        <div className="mb-2">
                          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                            Détail jour par jour
                          </p>
                          <div className="flex flex-wrap gap-2">
                            {anomaly.detail_jours.map((day) => (
                              <span
                                key={day.jour}
                                className="rounded-md border bg-background px-2 py-1 text-xs tabular-nums"
                              >
                                J{day.jour} : {day.heures_prevues.toFixed(1)} →{' '}
                                {day.heures_faites.toFixed(1)} ({day.ecart >= 0 ? '+' : ''}
                                {day.ecart.toFixed(1)}
                                {unit})
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {anomaly.conflict_days.length > 0 && (
                        <p className="text-xs text-muted-foreground">
                          Jours en conflit : {anomaly.conflict_days.join(', ')}
                        </p>
                      )}
                      {(anomaly.days_with_pointage_anomalies ?? 0) > 0 && (
                        <p className="text-xs text-muted-foreground">
                          {anomaly.days_with_pointage_anomalies} jour(s) de pointage incohérent
                        </p>
                      )}
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
