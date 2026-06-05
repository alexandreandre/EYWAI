/**
 * Rappel dashboard RH — nouveaux salariés dont la fiche paie reste à compléter.
 *
 * Une embauche issue du recrutement crée une fiche minimale (état civil + contrat).
 * Ce widget liste les collaborateurs récents auxquels il manque des informations
 * indispensables à la paie et propose un accès direct à la fiche.
 */

import { Link } from 'react-router-dom';
import { ArrowRight, CheckCircle2, Loader2, UserRoundPlus } from 'lucide-react';

import type { OnboardingHubItem } from '@/api/onboarding';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { formatDateFR } from '@/lib/onboardingUtils';

interface IncompleteEmployeesCardProps {
  items: OnboardingHubItem[];
  loading: boolean;
}

const MAX_VISIBLE = 4;

export function IncompleteEmployeesCard({ items, loading }: IncompleteEmployeesCardProps) {
  const incomplete = items.filter((item) => !item.profile_complete);
  const visible = incomplete.slice(0, MAX_VISIBLE);
  const remaining = incomplete.length - visible.length;

  return (
    <Card className={incomplete.length > 0 ? 'border-l-4 border-l-amber-500' : undefined}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <UserRoundPlus className="h-5 w-5 text-amber-600" />
          Nouveaux salariés à compléter
          {incomplete.length > 0 && (
            <Badge variant="secondary" className="ml-1 tabular-nums">
              {incomplete.length}
            </Badge>
          )}
        </CardTitle>
        <p className="mt-1 text-xs text-muted-foreground">
          Finalisez la fiche paie des collaborateurs récemment embauchés.
        </p>
      </CardHeader>
      <CardContent className="space-y-2">
        {loading ? (
          <div className="flex justify-center py-6">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : incomplete.length === 0 ? (
          <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
            Toutes les fiches des nouveaux arrivants sont complètes.
          </div>
        ) : (
          <>
            {visible.map((item) => {
              const fullName = `${item.first_name} ${item.last_name}`.trim();
              return (
                <div
                  key={item.employee_id}
                  className="rounded-lg border border-amber-200 bg-amber-50/40 p-3"
                >
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-foreground">{fullName}</span>
                        <span className="text-xs text-muted-foreground">
                          {item.job_title ?? '—'}
                          {item.days_since_hire != null ? ` · J+${item.days_since_hire}` : ''}
                          {item.hire_date ? ` · ${formatDateFR(item.hire_date)}` : ''}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {item.missing_fields.map((field) => (
                          <Badge
                            key={field}
                            variant="outline"
                            className="border-amber-300 bg-white text-[11px] font-normal text-amber-700"
                          >
                            {field}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <Button asChild size="sm" variant="outline" className="shrink-0">
                      <Link to={`/employees/${item.employee_id}`}>Compléter la fiche</Link>
                    </Button>
                  </div>
                </div>
              );
            })}
            {remaining > 0 && (
              <Button asChild variant="link" className="h-auto p-0 text-sm">
                <Link to="/onboarding">
                  Voir {remaining} autre{remaining > 1 ? 's' : ''} collaborateur
                  {remaining > 1 ? 's' : ''}
                  <ArrowRight className="ml-1 h-3.5 w-3.5" />
                </Link>
              </Button>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
