import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink, RefreshCw } from "lucide-react";

import { getAnomaliesPayslips, type AnomaliesReport } from "@/api/analytics";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export type PayrollAnomaliesPanelProps = {
  companyId: string;
  payrollYear: number;
  payrollMonth: number;
  periodLabel: string;
  periodHint?: string | null;
  maxRows?: number;
  sectionId?: string;
};

function summarize(anomalies: AnomaliesReport["anomalies"]) {
  let bloquants = 0;
  let avertissements = 0;
  for (const x of anomalies) {
    if (x.severite === "bloquant") bloquants += 1;
    else avertissements += 1;
  }
  return { bloquants, avertissements };
}

export function PayrollAnomaliesPanel({
  companyId,
  payrollYear,
  payrollMonth,
  periodLabel,
  periodHint,
  maxRows = 10,
  sectionId = "anomalies-paie",
}: PayrollAnomaliesPanelProps) {
  const {
    data: anomaliesData,
    isLoading,
    isFetching,
    error,
  } = useQuery({
    queryKey: ["payslips-anomalies", companyId, payrollYear, payrollMonth],
    queryFn: () => getAnomaliesPayslips(companyId, payrollYear, payrollMonth),
    enabled: Boolean(companyId),
    staleTime: 0,
    placeholderData: (previous) => previous,
  });

  const summary = useMemo(
    () => summarize(anomaliesData?.anomalies ?? []),
    [anomaliesData],
  );

  const visibleRows = anomaliesData?.anomalies.slice(0, maxRows) ?? [];

  return (
    <section id={sectionId} aria-labelledby={`${sectionId}-title`} className="mt-6">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id={`${sectionId}-title`} className="text-lg font-semibold leading-tight tracking-tight">
            Anomalies de paie
          </h2>
          <p className="text-muted-foreground line-clamp-2 text-sm">
            Contrôles automatiques — {periodLabel}
          </p>
        </div>
        {isFetching && !isLoading ? (
          <RefreshCw
            className="text-muted-foreground h-4 w-4 animate-spin"
            aria-label="Mise à jour des anomalies"
          />
        ) : null}
      </div>
      {periodHint ? (
        <p className="text-muted-foreground -mt-2 mb-2 text-xs">{periodHint}</p>
      ) : null}
      <Card
        className={
          isFetching && anomaliesData ? "opacity-80 transition-opacity duration-150" : undefined
        }
      >
        <CardContent className="space-y-3 p-4">
          {error ? (
            <Alert variant="destructive">
              <AlertTitle>Anomalies</AlertTitle>
              <AlertDescription>
                {error instanceof Error ? error.message : "Erreur de chargement."}
              </AlertDescription>
            </Alert>
          ) : null}
          {isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : anomaliesData ? (
            <>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Card>
                  <CardContent className="p-3">
                    <p className="text-2xl font-bold tabular-nums">{anomaliesData.total_bulletins}</p>
                    <p className="text-muted-foreground text-xs">Bulletins analysés</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3">
                    <p className="text-2xl font-bold tabular-nums">
                      {anomaliesData.bulletins_avec_anomalies}
                    </p>
                    <p className="text-muted-foreground text-xs">Avec anomalies</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3">
                    <p className="text-2xl font-bold tabular-nums text-red-600">
                      {summary.bloquants}
                    </p>
                    <p className="text-muted-foreground text-xs">Bloquants</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3">
                    <p className="text-2xl font-bold tabular-nums text-amber-600">
                      {summary.avertissements}
                    </p>
                    <p className="text-muted-foreground text-xs">Avertissements</p>
                  </CardContent>
                </Card>
              </div>
              {anomaliesData.anomalies.length === 0 ? (
                <p className="text-muted-foreground py-4 text-center text-sm">
                  Aucune anomalie détectée pour {periodLabel}.
                </p>
              ) : (
                <div className="w-full overflow-x-auto rounded-md border">
                  <Table className="text-sm [&_td]:px-3 [&_td]:py-2 [&_th]:px-3 [&_th]:py-2">
                    <TableHeader>
                      <TableRow>
                        <TableHead>Salarié</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Sévérité</TableHead>
                        <TableHead>Détail</TableHead>
                        <TableHead className="text-right">Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {visibleRows.map((row, idx) => (
                        <TableRow key={`${row.payslip_id}-${row.type}-${idx}`}>
                          <TableCell className="max-w-[10rem] truncate font-medium">
                            {row.employee_name}
                          </TableCell>
                          <TableCell className="max-w-[6rem] truncate text-muted-foreground text-xs">
                            {row.type}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="secondary"
                              className={
                                row.severite === "bloquant"
                                  ? "bg-red-600 text-white hover:bg-red-600"
                                  : "bg-amber-600 text-white hover:bg-amber-600"
                              }
                            >
                              {row.severite === "bloquant" ? "Bloquant" : "Avertissement"}
                            </Badge>
                          </TableCell>
                          <TableCell className="max-w-[220px] text-xs">
                            <span className="line-clamp-2" title={row.message}>
                              {row.message}
                            </span>
                            {row.valeur_detectee ? (
                              <span className="text-muted-foreground block truncate">
                                {row.valeur_detectee}
                              </span>
                            ) : null}
                          </TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="sm" className="h-8" asChild>
                              <Link to={`/payslips/${row.payslip_id}/edit`} title="Ouvrir le bulletin">
                                <ExternalLink className="mr-1 h-3.5 w-3.5" />
                                Bulletin
                              </Link>
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
              {anomaliesData.anomalies.length > maxRows ? (
                <p className="text-muted-foreground text-center text-xs">
                  {anomaliesData.anomalies.length - maxRows} anomalie(s) supplémentaire(s) non affichée(s).
                </p>
              ) : null}
            </>
          ) : null}
        </CardContent>
      </Card>
    </section>
  );
}

export function usePayrollAnomaliesSummary(
  companyId: string | null,
  payrollYear: number,
  payrollMonth: number,
) {
  const { data } = useQuery({
    queryKey: ["payslips-anomalies", companyId, payrollYear, payrollMonth],
    queryFn: () => getAnomaliesPayslips(companyId, payrollYear, payrollMonth),
    enabled: Boolean(companyId),
    staleTime: 0,
  });
  return useMemo(() => summarize(data?.anomalies ?? []), [data]);
}
