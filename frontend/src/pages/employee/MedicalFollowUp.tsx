// Page Collaborateur : Mon suivi médical (lecture seule)

import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { getMyObligations, type ObligationListItem } from "@/api/medicalFollowUp";
import {
  formatMedicalDate as formatDate,
  getNextObligation,
  STATUS_LABELS,
  statusBadgeVariant,
  VISIT_TYPE_LABELS,
} from "@/lib/medicalFollowUpLabels";
import { Loader2, Stethoscope } from "lucide-react";

export default function EmployeeMedicalFollowUp() {
  const [obligations, setObligations] = useState<ObligationListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getMyObligations()
      .then(setObligations)
      .catch((e: any) => setError(e.response?.data?.detail ?? e.message ?? "Erreur de chargement"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-[200px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Stethoscope className="h-7 w-7 text-teal-600" />
          Mon suivi médical
        </h1>
        <Card className="border-amber-500/50">
          <CardContent className="pt-6">
            <p className="text-muted-foreground">{error}</p>
            <p className="text-sm text-muted-foreground mt-2">Si le module est activé par votre entreprise, cette page affichera vos prochaines visites médicales.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const nextObligation = getNextObligation(obligations);
  const isOverdue =
    nextObligation?.due_date &&
    nextObligation.status !== "realisee" &&
    nextObligation.status !== "annulee" &&
    new Date(nextObligation.due_date) < new Date();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Stethoscope className="h-7 w-7 text-teal-600" />
          Mon suivi médical
        </h1>
        <p className="text-muted-foreground mt-1">
          Vos prochaines visites et l’historique de suivi médical
        </p>
      </div>

      {obligations.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">Aucune visite à ce jour.</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <Card className={isOverdue ? "border-red-500/50 bg-red-500/5" : ""}>
            <CardHeader>
              <CardTitle className="text-lg">Prochaine visite</CardTitle>
              <CardDescription>Prochaine obligation de suivi médical</CardDescription>
            </CardHeader>
            <CardContent>
              {nextObligation ? (
                <div className="flex flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">
                      {VISIT_TYPE_LABELS[nextObligation.visit_type] ?? nextObligation.visit_type}
                    </span>
                    {isOverdue && (
                      <Badge variant="destructive">En retard</Badge>
                    )}
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Date limite : {formatDate(nextObligation.due_date)}
                  </p>
                  <p className="text-sm">
                    Statut : {STATUS_LABELS[nextObligation.status] ?? nextObligation.status}
                  </p>
                  {nextObligation.justification && (
                    <p className="text-sm text-muted-foreground">{nextObligation.justification}</p>
                  )}
                </div>
              ) : (
                <p className="text-muted-foreground">Toutes vos obligations sont à jour.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Liste détaillée</CardTitle>
              <CardDescription>Historique et prochaines échéances</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Date limite</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead>Message</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {obligations.map((o) => (
                    <TableRow key={o.id}>
                      <TableCell>{VISIT_TYPE_LABELS[o.visit_type] ?? o.visit_type}</TableCell>
                      <TableCell>{formatDate(o.due_date)}</TableCell>
                      <TableCell>
                        <Badge variant={statusBadgeVariant(o.status, o.due_date)}>
                          {STATUS_LABELS[o.status] ?? o.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {o.justification ?? (o.status === "realisee" && o.completed_date ? `Réalisée le ${formatDate(o.completed_date)}` : "—")}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
