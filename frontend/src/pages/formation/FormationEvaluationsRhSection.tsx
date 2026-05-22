import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";

import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { getEvaluationsSummary, type EvaluationSummary } from "@/api/training";

export default function FormationEvaluationsRhSection() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";

  const isRhLike =
    Boolean(user?.is_super_admin) ||
    activeCompany?.role === "admin" ||
    activeCompany?.role === "rh" ||
    activeCompany?.role === "collaborateur_rh";

  const q = useQuery({
    queryKey: ["formation-evaluations-summary", companyId],
    queryFn: () => getEvaluationsSummary(companyId),
    enabled: Boolean(companyId) && isRhLike,
  });

  if (!isRhLike) return null;

  const rows = [...(q.data ?? [])].sort((a, b) => b.nb_evaluations - a.nb_evaluations);

  return (
    <Collapsible defaultOpen={false} className="rounded-lg border">
      <CollapsibleTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          className="flex w-full items-center justify-between px-4 py-3 h-auto font-semibold"
        >
          <span>Analyses — évaluations formations</span>
          <ChevronDown className="h-4 w-4 shrink-0 transition-transform [[data-state=open]_&]:rotate-180" />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-3 border-t px-4 pb-4 pt-2">
        <p className="text-sm text-muted-foreground">
          Synthèse des notes laissées par les collaborateurs après leurs formations.
        </p>
        {q.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : q.isError ? (
          <p className="text-sm text-destructive">Impossible de charger les statistiques d&apos;évaluation.</p>
        ) : rows.length === 0 ? (
          <p className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">
            Aucune évaluation enregistrée pour le moment.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-md border w-full">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Formation</TableHead>
                  <TableHead className="text-right">Nb évaluations</TableHead>
                  <TableHead>Note moyenne</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row: EvaluationSummary) => (
                  <TableRow key={row.training_id}>
                    <TableCell className="font-medium">{row.training_title}</TableCell>
                    <TableCell className="text-right tabular-nums">{row.nb_evaluations}</TableCell>
                    <TableCell>
                      <span className="text-sm font-medium tabular-nums">
                        {row.avg_rating.toFixed(1)} / 5
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CollapsibleContent>
    </Collapsible>
  );
}
