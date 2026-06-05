import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { SharkFinLoader } from '@/components/SharkFinLoader';

import { getEvaluations, type EmployeeCompetency } from "@/api/competencies";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { competencyLevelLabel } from "@/lib/employeeFormationUtils";

import { categoryLabelFr, competencyScoreBadge, fmtDate } from "./employeeFormationFormatters";

export function FormationCompetenciesPanel({ employeeId }: { employeeId: string }) {
  const [gapsOnly, setGapsOnly] = useState(false);

  const q = useQuery({
    queryKey: ["formation-competencies", employeeId],
    queryFn: () => getEvaluations(employeeId),
  });

  const rows = useMemo(() => {
    const all = q.data ?? [];
    if (!gapsOnly) return all;
    return all.filter((e) => e.is_gap);
  }, [q.data, gapsOnly]);

  if (q.isLoading) {
    return <SharkFinLoader label="Chargement des compétences…" />;
  }
  if (q.isError) {
    return <p className="text-sm text-destructive">Impossible de charger vos compétences.</p>;
  }
  const allRows = q.data ?? [];
  if (allRows.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        Vos compétences n&apos;ont pas encore été évaluées.
      </p>
    );
  }

  const gapCount = allRows.filter((e) => e.is_gap).length;

  return (
    <div className="space-y-4">
      {gapCount > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant={gapsOnly ? "default" : "outline"}
            onClick={() => setGapsOnly((v) => !v)}
          >
            {gapsOnly ? "Voir toutes les compétences" : `Écarts uniquement (${gapCount})`}
          </Button>
        </div>
      )}

      {rows.length === 0 ? (
        <p className="text-center text-sm text-muted-foreground">Aucun écart par rapport au niveau requis.</p>
      ) : (
        rows.map((e: EmployeeCompetency) => (
          <Card key={e.id}>
            <CardHeader className="pb-2">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <CardTitle className="text-base">{e.competency_name ?? "Compétence"}</CardTitle>
                  <CardDescription>{categoryLabelFr(e.competency_category)}</CardDescription>
                </div>
                {competencyScoreBadge(e.score)}
              </div>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {e.required_level != null && (
                <p>
                  <span className="text-muted-foreground">Niveau requis : </span>
                  {competencyLevelLabel(e.required_level)}
                </p>
              )}
              {e.is_gap && (
                <Badge variant="destructive" className="border-0">
                  En dessous du niveau requis
                </Badge>
              )}
              {e.comment?.trim() ? (
                <p>
                  <span className="text-muted-foreground">Commentaire : </span>
                  {e.comment}
                </p>
              ) : null}
              <p className="text-muted-foreground">Évaluation : {fmtDate(e.evaluation_date)}</p>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}
