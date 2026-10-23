import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { acquitAlert, getRevueDuMois, type SalarieRevue } from '@/api/payslips';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { libelleNiveau, regleAcquittable } from '@/features/payroll/utils/revueARegarder';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';
import { cn } from '@/lib/utils';

/** Écarts relus sur les bulletins du mois, à côté de la liste. */
export function RevueARegarder({ year, month }: { year: number; month: number }) {
  const companyId = useActiveCompanyId();
  const query = useQuery({
    queryKey: queryKeys.revueDuMois(companyId, year, month),
    queryFn: () => getRevueDuMois(year, month, companyId),
    enabled: Boolean(companyId),
    staleTime: 30_000,
  });

  return (
    <Card data-testid="revue-du-mois">
      <CardHeader className="py-3">
        <CardTitle className="text-base">À regarder</CardTitle>
        <p className="text-xs text-muted-foreground">
          Écarts relus sur les bulletins déjà générés de ce mois.
        </p>
      </CardHeader>
      <CardContent className="pt-0">
        {query.isLoading ? (
          <p className="text-sm text-muted-foreground">Lecture des bulletins…</p>
        ) : query.isError ? (
          <p className="text-sm text-destructive">La revue du mois n'a pas pu être lue.</p>
        ) : (query.data?.salaries.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">Rien à regarder ce mois-ci.</p>
        ) : (
          <ul className="divide-y divide-border/60">
            {query.data?.salaries.map((salarie) => (
              <Salarie key={salarie.identifiant} salarie={salarie} year={year} month={month} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function Salarie({
  salarie,
  year,
  month,
}: {
  salarie: SalarieRevue;
  year: number;
  month: number;
}) {
  const nom = `${salarie.prenom} ${salarie.nom}`.trim();
  const vues = new Set<string>();
  return (
    <li className="py-3 first:pt-0">
      {salarie.bulletin_id ? (
        <Link
          to={`/payslips/${salarie.bulletin_id}/edit`}
          className="text-sm font-medium underline-offset-2 hover:underline"
        >
          {nom}
        </Link>
      ) : (
        <p className="text-sm font-medium">{nom}</p>
      )}
      <ul className="mt-2 space-y-3">
        {salarie.alertes.map((alerte) => {
          const montrerAcquit = regleAcquittable(alerte.rule_id) && !vues.has(alerte.rule_id);
          if (montrerAcquit) vues.add(alerte.rule_id);
          return (
            <li key={`${alerte.rule_id}-${alerte.field}-${alerte.message}`}>
              <p className="text-sm">
                <span
                  className={cn(
                    'mr-2 text-xs font-medium uppercase tracking-wide',
                    alerte.level === 'CRITIQUE' ? 'text-destructive' : 'text-muted-foreground',
                  )}
                >
                  {libelleNiveau(alerte.level)}
                </span>
                {alerte.message}
              </p>
              {montrerAcquit && (
                <Acquitter
                  bulletinId={salarie.bulletin_id}
                  ruleId={alerte.rule_id}
                  year={year}
                  month={month}
                />
              )}
            </li>
          );
        })}
      </ul>
    </li>
  );
}

function Acquitter({
  bulletinId,
  ruleId,
  year,
  month,
}: {
  bulletinId: string;
  ruleId: string;
  year: number;
  month: number;
}) {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();
  const [motif, setMotif] = useState('');
  const mutation = useMutation({
    mutationFn: () => acquitAlert(bulletinId, ruleId, motif.trim()),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.revueDuMois(companyId, year, month),
      });
    },
  });
  if (!bulletinId) return null;
  return (
    <form
      className="mt-2 flex flex-wrap items-center gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (motif.trim().length < 3 || mutation.isPending) return;
        mutation.mutate();
      }}
    >
      <Input
        value={motif}
        onChange={(event) => setMotif(event.target.value)}
        placeholder="Pourquoi c'est juste"
        className="h-8 max-w-xs text-sm"
        aria-label="Motif de l'acquittement"
      />
      <Button type="submit" size="sm" variant="outline" disabled={motif.trim().length < 3 || mutation.isPending}>
        {mutation.isPending ? 'Enregistrement…' : 'Acquitter'}
      </Button>
      {mutation.isError && (
        <p className="text-xs text-destructive">L'acquittement n'a pas été enregistré.</p>
      )}
    </form>
  );
}
