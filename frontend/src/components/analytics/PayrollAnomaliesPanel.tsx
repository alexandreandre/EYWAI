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

const ANOMALY_TYPE_LABELS: Record<string, string> = {
  DONNEES_BULLETIN_INVALIDES: "Bulletin illisible",
  BRUT_NEGATIF: "Brut négatif",
  BRUT_NUL: "Brut nul",
  NET_SUPERIEUR_BRUT: "Net supérieur au brut",
  TAUX_HORAIRE_INCOHERENT: "Taux horaire inhabituel",
  PRIMES_EXCESSIVES: "Primes élevées",
  COTISATIONS_PAT_NEGATIVES: "Cotisations patronales négatives",
  DELAI_VALIDATION: "Bulletin non validé",
  ALERTE_CC_SALAIRE_SOUS_MINIMUM: "Salaire sous le minimum conventionnel",
  ALERTE_CC_CLASSIFICATION_MANQUANTE: "Classification à renseigner",
  ALERTE_CC_REGLES_ABSENTES: "Convention à mettre à jour",
  ALERTE_CC_GRILLE_VIDE: "Grille conventionnelle à mettre à jour",
  ALERTE_CC_COEFFICIENT_HORS_GRILLE: "Classification hors grille",
  ALERTE_VM_BAREME_ABSENT: "Taux de versement mobilité à renseigner",
  ALERTE_MAINTIEN_SALAIRE: "Maintien de salaire",
  ALERTE_TRANSPORT_PLAFOND_ANNUEL_DEPASSE: "Plafond transport dépassé",
};

/** Libellé RH : jamais le code technique brut dans le tableau. */
function anomalyTypeLabel(type: string): string {
  const known = ANOMALY_TYPE_LABELS[type];
  if (known) return known;
  const words = type.replace(/^ALERTE_/, "").toLowerCase().replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

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
                    <p className="text-2xl font-bold tabular-nums">{summary.bloquants}</p>
                    <p className="text-muted-foreground text-xs">À corriger</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="p-3">
                    <p className="text-2xl font-bold tabular-nums">
                      {summary.avertissements}
                    </p>
                    <p className="text-muted-foreground text-xs">À vérifier</p>
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
                          <TableCell className="max-w-[10rem] truncate text-muted-foreground text-xs">
                            <span title={row.type}>{anomalyTypeLabel(row.type)}</span>
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              className={
                                row.severite === "bloquant"
                                  ? "border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
                                  : "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300"
                              }
                            >
                              {row.severite === "bloquant" ? "À corriger" : "À vérifier"}
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
