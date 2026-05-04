import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import apiClient from "@/api/apiClient";
import { getMatrix, type CompetencyMatrix } from "@/api/competencies";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useCompany } from "@/contexts/CompanyContext";

import { useCanQueryRhApis, useManagerTeamMemberIds } from "@/pages/manager/teamScope";

type EmpRow = { id: string; first_name?: string; last_name?: string; email?: string | null };

export default function ManagerCompetences() {
  const { activeCompany } = useCompany();
  const canRh = useCanQueryRhApis(activeCompany);
  const teamQ = useManagerTeamMemberIds();
  const companyId = activeCompany?.company_id ?? "";

  const matrixQ = useQuery({
    queryKey: ["competencies", "matrix", "manager", companyId],
    queryFn: () => getMatrix({}),
    enabled: Boolean(companyId) && canRh,
  });

  const employeesQ = useQuery({
    queryKey: ["employees", "manager-competences", companyId],
    queryFn: async () => {
      const res = await apiClient.get<EmpRow[]>("/api/employees");
      return res.data ?? [];
    },
    enabled: Boolean(companyId) && !canRh,
  });

  const statsByEmp = useMemo(() => {
    const m: CompetencyMatrix | undefined = matrixQ.data;
    const ids = teamQ.data;
    if (!m || !ids || ids.size === 0) return new Map<string, { evalCount: number; gapCount: number; avg: number | null }>();

    const map = new Map<string, { scores: number[]; gapCount: number }>();
    for (const cell of m.cells) {
      if (!ids.has(cell.employee_id)) continue;
      const cur = map.get(cell.employee_id) ?? { scores: [] as number[], gapCount: 0 };
      cur.scores.push(cell.score);
      if (cell.is_gap) cur.gapCount += 1;
      map.set(cell.employee_id, cur);
    }

    const out = new Map<string, { evalCount: number; gapCount: number; avg: number | null }>();
    for (const [eid, v] of map) {
      const evalCount = v.scores.filter((s) => s > 0).length;
      const sum = v.scores.reduce((a, b) => a + b, 0);
      const avg = v.scores.length ? sum / v.scores.length : null;
      out.set(eid, { evalCount, gapCount: v.gapCount, avg });
    }
    return out;
  }, [matrixQ.data, teamQ.data]);

  const simpleRows = useMemo(() => {
    if (canRh) return [];
    const ids = teamQ.data ?? new Set<string>();
    const emps = employeesQ.data ?? [];
    return emps.filter((e) => ids.has(e.id));
  }, [canRh, employeesQ.data, teamQ.data]);

  const loading = teamQ.isLoading || (canRh ? matrixQ.isLoading : employeesQ.isLoading);

  const matrixEmployees = matrixQ.data?.employees ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Compétences de mon équipe</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Visualisez les compétences et gaps de votre équipe.
        </p>
      </div>

      {!canRh && (
        <p className="rounded-md border border-muted bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
          La matrice détaillée nécessite des droits RH. Ci-dessous : accès simplifié aux fiches des
          collaborateurs liés à vos demandes à traiter.
        </p>
      )}

      {loading && (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      )}

      {canRh && matrixQ.isError && (
        <p className="text-sm text-destructive">Impossible de charger la matrice de compétences.</p>
      )}

      {canRh && !loading && !matrixQ.isError && teamQ.data && teamQ.data.size === 0 && (
        <p className="text-sm text-muted-foreground">
          Aucun collaborateur dans votre périmètre (vérifiez l&apos;affectation manager des équipes).
        </p>
      )}

      {canRh && !loading && !matrixQ.isError && (teamQ.data?.size ?? 0) > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Salarié</TableHead>
                <TableHead>Nb compétences évaluées</TableHead>
                <TableHead>Nb gaps</TableHead>
                <TableHead>Score moyen</TableHead>
                <TableHead className="text-right">Détail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {matrixEmployees
                .filter((e) => teamQ.data?.has(e.id))
                .map((e) => {
                  const st = statsByEmp.get(e.id);
                  return (
                    <TableRow key={e.id}>
                      <TableCell className="font-medium">{e.name}</TableCell>
                      <TableCell>{st?.evalCount ?? 0}</TableCell>
                      <TableCell>{st?.gapCount ?? 0}</TableCell>
                      <TableCell>
                        {st?.avg != null ? st.avg.toFixed(1) : "—"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="outline" size="sm" asChild>
                          <Link to={`/employees/${e.id}`}>Voir le détail</Link>
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
            </TableBody>
          </Table>
        </div>
      )}

      {!canRh && !loading && simpleRows.length === 0 && (
        <p className="text-sm text-muted-foreground">
          Aucun collaborateur identifié dans votre périmètre pour le moment.
        </p>
      )}

      {!canRh && simpleRows.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Salarié</TableHead>
                <TableHead>Nb compétences évaluées</TableHead>
                <TableHead>Nb gaps</TableHead>
                <TableHead>Score moyen</TableHead>
                <TableHead className="text-right">Détail</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {simpleRows.map((e) => (
                <TableRow key={e.id}>
                  <TableCell className="font-medium">
                    {e.first_name} {e.last_name}
                  </TableCell>
                  <TableCell>—</TableCell>
                  <TableCell>—</TableCell>
                  <TableCell>—</TableCell>
                  <TableCell className="text-right">
                    <Button variant="outline" size="sm" asChild>
                      <Link to={`/employees/${e.id}`}>Voir le détail</Link>
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
