import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { getARegarder, marquerPointVu, type PointARegarder } from '@/api/relectureIa';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { libelleGravite } from '@/features/payroll/utils/relectureIa';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { showErrorToast } from '@/lib/errorMessages';
import { queryKeys } from '@/lib/queryKeys';

/** Points relevés par la relecture IA pour la société active. */
export function RelectureIaARegarder({ year, month }: { year: number; month: number }) {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();
  const cle = queryKeys.relectureIaARegarder(companyId, year, month);
  const query = useQuery({
    queryKey: cle,
    queryFn: () => getARegarder(year, month, companyId),
    enabled: Boolean(companyId),
    staleTime: 30_000,
  });
  const vu = useMutation({
    mutationFn: (point: PointARegarder) =>
      marquerPointVu(point.bulletin_relu_id, point.ligne, companyId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: cle });
    },
    onError: (error) => {
      showErrorToast(error, {
        title: 'Point non enregistré',
        fallback: 'Ce point n’a pas pu être marqué. Réessayez.',
      });
    },
  });

  const donnees = query.data;

  return (
    <Card data-testid="relecture-ia-a-regarder">
      <CardHeader className="py-3">
        <CardTitle className="text-base">À regarder : relecture par l’IA</CardTitle>
        <p className="text-xs text-muted-foreground">
          Ce que l’IA a relevé sur les bulletins de ce mois. Elle ne modifie aucun bulletin.
        </p>
      </CardHeader>
      <CardContent className="space-y-2 pt-0">
        {query.isLoading ? (
          <p className="text-sm text-muted-foreground">Lecture de la relecture…</p>
        ) : query.isError ? (
          <p className="text-sm text-destructive">
            Les points relevés par l’IA n’ont pas pu être lus. Rechargez la page.
          </p>
        ) : !donnees?.relecture_faite ? (
          <p className="text-sm text-muted-foreground">
            La paie de ce mois n’a pas encore été relue par l’IA.
          </p>
        ) : donnees.points.length === 0 && donnees.autres_points === 0 ? (
          <p className="text-sm text-muted-foreground">Rien à regarder : l’IA n’a relevé aucun point.</p>
        ) : (
          <ul className="divide-y divide-border/60">
            {donnees.points.map((point) => (
              <li
                key={`${point.bulletin_relu_id}-${point.ligne}`}
                className="flex flex-wrap items-start justify-between gap-2 py-2"
                data-testid="relecture-ia-point"
              >
                <div className="min-w-0 flex-1 space-y-0.5">
                  <p className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="font-medium">{point.nom}</span>
                    <Badge variant={point.gravite === 'important' ? 'destructive' : 'secondary'}>
                      {libelleGravite(point.gravite)}
                    </Badge>
                  </p>
                  <p className="text-sm">{point.ligne}</p>
                  <p className="text-xs text-muted-foreground">{point.raison}</p>
                  {point.bulletin_modifie_depuis ? (
                    <p className="text-xs text-amber-700">Ce bulletin a changé depuis la relecture.</p>
                  ) : null}
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Link
                    to={`/payslips/${point.payslip_id}/edit`}
                    className="text-xs font-medium text-primary hover:underline"
                  >
                    Ouvrir le bulletin
                  </Link>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={vu.isPending}
                    onClick={() => vu.mutate(point)}
                    data-testid="relecture-ia-vu"
                  >
                    Vu, c’est normal
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
        {donnees && donnees.autres_points > 0 ? (
          <p className="text-xs text-muted-foreground" data-testid="relecture-ia-autres">
            {donnees.autres_points === 1
              ? '1 autre point moins important'
              : `${donnees.autres_points} autres points moins importants`}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
