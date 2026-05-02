import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getAllAnnualReviews, type AnnualReviewListItem } from "@/api/annualReviews";
import { AnnualReviewBadge } from "@/components/AnnualReviewBadge";
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
import { Eye } from "lucide-react";

import { useCanQueryRhApis, useManagerTeamMemberIds } from "@/pages/manager/teamScope";

function formatDate(value: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

export default function ManagerAnnualReviews() {
  const navigate = useNavigate();
  const { activeCompany } = useCompany();
  const canRh = useCanQueryRhApis(activeCompany);
  const teamQ = useManagerTeamMemberIds();
  const companyId = activeCompany?.company_id ?? "";

  const listQ = useQuery({
    queryKey: ["annual-reviews", "manager-view", companyId],
    queryFn: async () => {
      const res = await getAllAnnualReviews({});
      return res.data ?? [];
    },
    enabled: Boolean(companyId) && canRh,
  });

  const filtered: AnnualReviewListItem[] = useMemo(() => {
    const raw = listQ.data ?? [];
    const ids = teamQ.data;
    if (!ids || ids.size === 0) return [];
    return raw.filter((r) => ids.has(r.employee_id));
  }, [listQ.data, teamQ.data]);

  const loading = teamQ.isLoading || (canRh && listQ.isLoading);
  const error = canRh && listQ.isError;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Entretiens de mon équipe</h1>
        <p className="text-sm text-muted-foreground">
          Entretiens des collaborateurs dont vous êtes le manager d&apos;équipe.
        </p>
      </div>

      {!canRh && (
        <p className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          La liste consolidée des entretiens est réservée aux profils avec droits RH sur
          l&apos;entreprise. Avec votre profil actuel, les données d&apos;entretiens
          équipe ne sont pas exposées par l&apos;API.
        </p>
      )}

      {loading && (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      )}

      {error && (
        <p className="text-sm text-destructive">
          Impossible de charger les entretiens. Vérifiez vos droits ou réessayez plus tard.
        </p>
      )}

      {!loading && !error && canRh && filtered.length === 0 && (
        <p className="rounded-md border border-dashed py-10 text-center text-sm text-muted-foreground">
          Aucun entretien pour votre équipe.
        </p>
      )}

      {!loading && !error && canRh && filtered.length > 0 && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Salarié</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead>Date prévue</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((row) => (
                <TableRow key={row.id}>
                  <TableCell className="font-medium">
                    {row.first_name} {row.last_name}
                  </TableCell>
                  <TableCell>Entretien {row.year}</TableCell>
                  <TableCell>
                    <AnnualReviewBadge status={row.status} compact />
                  </TableCell>
                  <TableCell>{formatDate(row.planned_date)}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => navigate(`/annual-reviews/${row.id}`)}
                    >
                      <Eye className="mr-1 h-4 w-4" />
                      Voir
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
