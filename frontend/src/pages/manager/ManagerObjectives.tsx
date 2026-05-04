import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { getObjectives, type EmployeeObjective } from "@/api/objectives";
import { Badge } from "@/components/ui/badge";
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

function objectiveStatusBadge(status: string) {
  const cfg: Record<string, { label: string; className: string }> = {
    draft: { label: "Brouillon", className: "bg-muted text-muted-foreground" },
    active: { label: "Actif", className: "bg-blue-600 text-white hover:bg-blue-600" },
    achieved: { label: "Atteint", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    partially_achieved: {
      label: "Partiellement atteint",
      className: "bg-orange-500 text-white hover:bg-orange-500",
    },
    not_achieved: { label: "Non atteint", className: "bg-red-600 text-white hover:bg-red-600" },
    cancelled: { label: "Annulé", className: "bg-muted text-muted-foreground" },
  };
  const x = cfg[status] ?? { label: status, className: "bg-muted text-muted-foreground" };
  return <Badge className={x.className}>{x.label}</Badge>;
}

function progressLabel(obj: EmployeeObjective): string {
  if (obj.type === "quantitative" && obj.milestones?.length) {
    const last = [...obj.milestones].sort(
      (a, b) => new Date(a.milestone_date).getTime() - new Date(b.milestone_date).getTime(),
    );
    const m = last[last.length - 1];
    if (m?.actual_value != null && obj.kpi_target_value != null) {
      return `${m.actual_value} / ${obj.kpi_target_value}${obj.kpi_unit ? ` ${obj.kpi_unit}` : ""}`;
    }
  }
  if (obj.final_achievement_rate != null) return `${obj.final_achievement_rate}%`;
  return "—";
}

function fmtDate(s?: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("fr-FR");
}

export default function ManagerObjectives() {
  const { activeCompany } = useCompany();
  const canRh = useCanQueryRhApis(activeCompany);
  const teamQ = useManagerTeamMemberIds();
  const companyId = activeCompany?.company_id ?? "";
  const year = new Date().getFullYear();

  const objQ = useQuery({
    queryKey: ["objectives", "manager-team", companyId, year],
    queryFn: () =>
      getObjectives({
        period_year: year,
        include_inactive: true,
      }),
    enabled: Boolean(companyId) && canRh,
  });

  const rows = useMemo(() => {
    const list = objQ.data ?? [];
    const ids = teamQ.data;
    if (!ids || ids.size === 0) return [];
    return list.filter((o) => o.employee_id && ids.has(o.employee_id));
  }, [objQ.data, teamQ.data]);

  const loading = teamQ.isLoading || (canRh && objQ.isLoading);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Objectifs de mon équipe</h1>
        <p className="text-sm text-muted-foreground">
          Objectifs {year} pour les membres de votre périmètre manager.
        </p>
      </div>

      {!canRh && (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          La consultation des objectifs par équipe nécessite des droits RH sur l&apos;entreprise.
        </p>
      )}

      {loading && (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      )}

      {canRh && objQ.isError && (
        <p className="text-sm text-destructive">Impossible de charger les objectifs.</p>
      )}

      {!loading && canRh && rows.length === 0 && (
        <p className="rounded-md border border-dashed py-10 text-center text-sm text-muted-foreground">
          Aucun objectif pour votre équipe sur cette période.
        </p>
      )}

      {!loading && canRh && rows.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Salarié</TableHead>
                <TableHead>Objectif</TableHead>
                <TableHead>Progression</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead>Échéance</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((o) => (
                <TableRow key={o.id}>
                  <TableCell className="font-medium">{o.employee_name ?? "—"}</TableCell>
                  <TableCell>{o.title}</TableCell>
                  <TableCell className="text-sm">{progressLabel(o)}</TableCell>
                  <TableCell>{objectiveStatusBadge(String(o.status))}</TableCell>
                  <TableCell>{fmtDate(o.due_date)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}
