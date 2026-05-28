import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { Link } from "react-router-dom";

import { getEmployeeStatus } from "@/api/legalObligations";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { sixYearCriteriaMetCount } from "@/lib/employeeFormationUtils";

import { CriterionReadOnly, fmtDate, profBadge, sixBadge } from "./employeeFormationFormatters";

export function FormationLegalPanel({ employeeId }: { employeeId: string }) {
  const q = useQuery({
    queryKey: ["formation-legal", employeeId],
    queryFn: () => getEmployeeStatus(employeeId),
  });

  if (q.isLoading) {
    return (
      <div className="flex items-center gap-2 py-8 text-muted-foreground">
        <Loader2 className="h-5 w-5 animate-spin" />
        Chargement…
      </div>
    );
  }
  if (q.isError || !q.data) {
    return <p className="text-sm text-destructive">Impossible de charger vos obligations légales.</p>;
  }
  const s = q.data;
  const criteriaCount = sixYearCriteriaMetCount(s);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Entretien professionnel (2 ans)</CardTitle>
          <CardDescription>Suivi réglementaire en lecture seule.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div>{profBadge(s.professional_interview_status)}</div>
          <p>
            {s.last_professional_interview_date ? (
              <>
                <span className="text-muted-foreground">Dernier entretien : </span>
                {fmtDate(s.last_professional_interview_date)}
              </>
            ) : (
              <span className="text-muted-foreground">Aucun entretien enregistré</span>
            )}
          </p>
          <p>
            <span className="text-muted-foreground">Prochain entretien avant : </span>
            {fmtDate(s.professional_interview_next_due)}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Bilan de compétences (6 ans)</CardTitle>
          <CardDescription>Critères cumulés sur la période.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div>{sixBadge(s.six_year_review_status)}</div>
          <p>
            <span className="text-muted-foreground">Échéance : </span>
            {fmtDate(s.six_year_next_due)}
          </p>
          {s.last_six_year_review_date && (
            <p>
              <span className="text-muted-foreground">Dernier bilan : </span>
              {fmtDate(s.last_six_year_review_date)}
            </p>
          )}
          <p className="font-medium">
            {criteriaCount} critère{criteriaCount > 1 ? "s" : ""} sur 3 rempli{criteriaCount > 1 ? "s" : ""}
            {s.six_year_criteria_met ? " — bilan validé" : ""}
          </p>
          <div className="space-y-2 border-t pt-3">
            <CriterionReadOnly ok={s.criteria_training_completed} label="Formation non obligatoire suivie" />
            <CriterionReadOnly ok={s.criteria_certification_obtained} label="Certification obtenue" />
            <CriterionReadOnly ok={s.criteria_career_evolution} label="Évolution salariale ou professionnelle" />
          </div>
          <p className="border-t pt-3 text-xs text-muted-foreground">
            Consultez vos{" "}
            <Link to="/employee/formation#formations" className="text-primary underline-offset-4 hover:underline">
              formations
            </Link>{" "}
            et vos{" "}
            <Link to="/employee/formation#habilitations" className="text-primary underline-offset-4 hover:underline">
              habilitations
            </Link>{" "}
            pour le détail de chaque critère.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
