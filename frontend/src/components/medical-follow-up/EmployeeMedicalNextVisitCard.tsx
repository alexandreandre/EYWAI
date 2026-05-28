import type { ObligationListItem } from '@/api/medicalFollowUp';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  formatMedicalDate,
  formatTriggerType,
  getDueDateRelativeLabel,
  getNextObligation,
  isObligationOverdue,
  STATUS_LABELS,
  statusBadgeVariant,
  VISIT_TYPE_LABELS,
} from '@/lib/medicalFollowUpLabels';
import { cn } from '@/lib/utils';

interface EmployeeMedicalNextVisitCardProps {
  obligations: ObligationListItem[];
}

export function EmployeeMedicalNextVisitCard({ obligations }: EmployeeMedicalNextVisitCardProps) {
  const nextObligation = getNextObligation(obligations);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Prochaine visite</CardTitle>
        <CardDescription>
          Consultez la date limite et le statut de votre prochaine obligation
        </CardDescription>
      </CardHeader>
      <CardContent>
        {!nextObligation ? (
          <p className="text-sm text-muted-foreground rounded-lg border border-dashed p-4">
            Aucune visite à planifier — toutes vos obligations actives sont à jour ou clôturées.
          </p>
        ) : (
          <NextVisitContent obligation={nextObligation} />
        )}
      </CardContent>
    </Card>
  );
}

function NextVisitContent({ obligation }: { obligation: ObligationListItem }) {
  const overdue = isObligationOverdue(obligation);
  const relative = getDueDateRelativeLabel(obligation.due_date, obligation.status);

  return (
    <div
      className={cn(
        'rounded-lg border p-4 space-y-3',
        overdue && 'border-destructive/50 bg-destructive/5'
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="space-y-1">
          <p className="font-medium">
            {VISIT_TYPE_LABELS[obligation.visit_type] ?? obligation.visit_type}
          </p>
          <p className="text-sm text-muted-foreground">
            Déclencheur : {formatTriggerType(obligation.trigger_type)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={statusBadgeVariant(obligation.status, obligation.due_date)}>
            {STATUS_LABELS[obligation.status] ?? obligation.status}
          </Badge>
          {overdue && <Badge variant="destructive">En retard</Badge>}
        </div>
      </div>

      <div className="space-y-1 text-sm">
        <p className="text-muted-foreground">
          Date limite : {formatMedicalDate(obligation.due_date)}
        </p>
        {obligation.planned_date && (
          <p className="text-muted-foreground">
            Date planifiée : {formatMedicalDate(obligation.planned_date)}
          </p>
        )}
        {relative && (
          <p
            className={cn(
              'font-medium',
              overdue ? 'text-destructive' : 'text-muted-foreground'
            )}
          >
            {relative}
          </p>
        )}
      </div>

      {obligation.justification && (
        <p className="text-sm text-muted-foreground">{obligation.justification}</p>
      )}

      <p className="text-xs text-muted-foreground border-t pt-3">
        La planification des visites est gérée par votre employeur et la médecine du travail.
        Contactez les RH pour toute question.
      </p>
    </div>
  );
}
