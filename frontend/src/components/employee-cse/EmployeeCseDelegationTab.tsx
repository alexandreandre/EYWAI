import type { DelegationHour } from '@/api/cse';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatCseDate } from '@/lib/employeeCseUtils';
import { SharkFinLoader } from '@/components/SharkFinLoader';

interface EmployeeCseDelegationTabProps {
  hours: DelegationHour[];
  isLoading: boolean;
  isError?: boolean;
}

export function EmployeeCseDelegationTab({
  hours,
  isLoading,
  isError,
}: EmployeeCseDelegationTabProps) {
  if (isError) {
    return (
      <Card className="border-destructive/50">
        <CardContent className="pt-6 text-sm text-destructive">
          Impossible de charger vos heures de délégation.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Historique du mois en cours</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <SharkFinLoader label="Chargement des heures de délégation…" />
        ) : hours.length === 0 ? (
          <p className="py-8 text-center text-muted-foreground">
            Aucune heure de délégation saisie ce mois-ci.
          </p>
        ) : (
          <ul className="space-y-2">
            {hours.map((hour) => (
              <li
                key={hour.id}
                className="flex items-center justify-between rounded-md border p-3"
              >
                <div>
                  <p className="font-medium">{formatCseDate(hour.date)}</p>
                  <p className="text-sm text-muted-foreground">{hour.reason}</p>
                  {hour.source && hour.source !== 'propre' && (
                    <p className="text-xs text-muted-foreground capitalize">{hour.source}</p>
                  )}
                </div>
                <p className="font-semibold">{hour.duration_hours} h</p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
