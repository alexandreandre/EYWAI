import { useMemo, useState, type ReactNode } from 'react';
import type { ObligationListItem } from '@/api/medicalFollowUp';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  filterMedicalObligations,
  type MedicalObligationFilter,
} from '@/lib/employeeMedicalFollowUp';
import {
  formatMedicalDate,
  formatTriggerType,
  isObligationOverdue,
  obligationMessage,
  sortObligationsForDisplay,
  STATUS_LABELS,
  statusBadgeVariant,
  VISIT_TYPE_LABELS,
} from '@/lib/medicalFollowUpLabels';
import { cn } from '@/lib/utils';

const FILTER_OPTIONS: { value: MedicalObligationFilter; label: string }[] = [
  { value: 'all', label: 'Toutes' },
  { value: 'upcoming', label: 'À venir' },
  { value: 'completed', label: 'Réalisées' },
];

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Button type="button" size="sm" variant={active ? 'default' : 'outline'} onClick={onClick}>
      {children}
    </Button>
  );
}

function ObligationMobileCard({ obligation }: { obligation: ObligationListItem }) {
  const overdue = isObligationOverdue(obligation);
  const cancelled = obligation.status === 'annulee';

  return (
    <div
      className={cn(
        'rounded-lg border bg-card p-4 space-y-2 md:hidden',
        overdue && 'border-destructive/40 bg-destructive/5',
        cancelled && 'opacity-60'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium">
            {VISIT_TYPE_LABELS[obligation.visit_type] ?? obligation.visit_type}
          </p>
          <p className="text-xs text-muted-foreground">
            {formatTriggerType(obligation.trigger_type)}
          </p>
        </div>
        <Badge variant={statusBadgeVariant(obligation.status, obligation.due_date)}>
          {STATUS_LABELS[obligation.status] ?? obligation.status}
        </Badge>
      </div>
      <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
        <dt className="text-muted-foreground">Date limite</dt>
        <dd>{formatMedicalDate(obligation.due_date)}</dd>
        <dt className="text-muted-foreground">Planifiée</dt>
        <dd>{formatMedicalDate(obligation.planned_date)}</dd>
        <dt className="text-muted-foreground">Réalisée</dt>
        <dd>{formatMedicalDate(obligation.completed_date)}</dd>
      </dl>
      <p className="text-sm text-muted-foreground">{obligationMessage(obligation)}</p>
    </div>
  );
}

interface EmployeeMedicalObligationsListProps {
  obligations: ObligationListItem[];
}

export function EmployeeMedicalObligationsList({ obligations }: EmployeeMedicalObligationsListProps) {
  const [filter, setFilter] = useState<MedicalObligationFilter>('all');

  const sorted = useMemo(() => sortObligationsForDisplay(obligations), [obligations]);
  const displayed = useMemo(
    () => filterMedicalObligations(sorted, filter),
    [sorted, filter]
  );

  return (
    <Card>
      <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle className="text-lg">Liste détaillée</CardTitle>
          <CardDescription>Historique et prochaines échéances</CardDescription>
        </div>
        <div className="flex flex-wrap gap-2">
          {FILTER_OPTIONS.map((opt) => (
            <FilterButton
              key={opt.value}
              active={filter === opt.value}
              onClick={() => setFilter(opt.value)}
            >
              {opt.label}
            </FilterButton>
          ))}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {displayed.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center border border-dashed rounded-lg">
            Aucune obligation pour ce filtre.
          </p>
        ) : (
          <>
            {displayed.map((o) => (
              <ObligationMobileCard key={o.id} obligation={o} />
            ))}
            <div className="hidden md:block w-full overflow-x-auto rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Date limite</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead>Planifiée</TableHead>
                    <TableHead>Réalisée</TableHead>
                    <TableHead className="min-w-[140px]">Message</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {displayed.map((o) => {
                    const overdue = isObligationOverdue(o);
                    const cancelled = o.status === 'annulee';
                    return (
                      <TableRow
                        key={o.id}
                        className={cn(
                          overdue && 'bg-destructive/5',
                          cancelled && 'opacity-60'
                        )}
                      >
                        <TableCell>
                          <p className="font-medium">
                            {VISIT_TYPE_LABELS[o.visit_type] ?? o.visit_type}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {formatTriggerType(o.trigger_type)}
                          </p>
                        </TableCell>
                        <TableCell>{formatMedicalDate(o.due_date)}</TableCell>
                        <TableCell>
                          <Badge variant={statusBadgeVariant(o.status, o.due_date)}>
                            {STATUS_LABELS[o.status] ?? o.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{formatMedicalDate(o.planned_date)}</TableCell>
                        <TableCell>{formatMedicalDate(o.completed_date)}</TableCell>
                        <TableCell className="text-muted-foreground text-sm max-w-[220px]">
                          {obligationMessage(o)}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
