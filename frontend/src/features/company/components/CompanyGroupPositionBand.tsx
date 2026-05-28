import { useQuery } from "@tanstack/react-query";
import apiClient from "@/api/apiClient";
import { useCompany } from "@/contexts/CompanyContext";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface CompanyStats {
  company_id: string;
  company_name: string;
  gross_salary: number;
  employer_charges: number;
  total_employee_count: number;
}

interface ConsolidatedStats {
  by_company: CompanyStats[];
}

export function CompanyGroupPositionBand(): JSX.Element | null {
  const { activeCompany } = useCompany();
  const groupId = activeCompany?.group_id;

  const { data, isLoading } = useQuery({
    queryKey: ["group-position", groupId],
    queryFn: async () => {
      const now = new Date();
      const year = now.getFullYear();
      const month = now.getMonth();
      const m = month === 0 ? 12 : month;
      const y = month === 0 ? year - 1 : year;
      const { data: stats } = await apiClient.get<ConsolidatedStats>(
        `/api/company-groups/${groupId}/consolidated-stats?year=${y}&month=${m}`,
      );
      return stats;
    },
    enabled: Boolean(groupId),
  });

  if (!groupId) return null;

  if (isLoading) {
    return <Skeleton className="h-24 w-full rounded-lg" />;
  }

  const companies = data?.by_company ?? [];
  const mine = companies.find((c) => c.company_id === activeCompany?.company_id);
  if (!mine || companies.length < 2) return null;

  const chargeRates = companies
    .filter((c) => c.gross_salary > 0)
    .map((c) => ({
      id: c.company_id,
      name: c.company_name,
      rate: (c.employer_charges / c.gross_salary) * 100,
    }))
    .sort((a, b) => a.rate - b.rate);

  const myRate =
    mine.gross_salary > 0 ? (mine.employer_charges / mine.gross_salary) * 100 : 0;
  const rank =
    chargeRates.findIndex((c) => c.id === mine.company_id) + 1 || chargeRates.length;

  return (
    <Card className="border-dashed">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Votre position dans le groupe</CardTitle>
        <CardDescription>
          {activeCompany?.group_name ?? "Groupe"} · {companies.length} entités · période M-1
        </CardDescription>
      </CardHeader>
      <CardContent className="text-sm">
        <p>
          Taux de charges patronales :{" "}
          <span className="font-semibold tabular-nums">{myRate.toFixed(1)} %</span>
          {rank > 0 ? (
            <>
              {" "}
              — <span className="text-muted-foreground">rang {rank} / {chargeRates.length}</span>
            </>
          ) : null}
        </p>
      </CardContent>
    </Card>
  );
}
