import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createOnDemand,
  getObligationsForEmployee,
  markCompleted,
  markPlanified,
  type ObligationListItem,
} from "@/api/medicalFollowUp";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/hooks/use-toast";
import {
  countMedicalObligations,
  formatMedicalDate,
  getDueDateRelativeLabel,
  getNextObligation,
  isObligationOverdue,
  obligationMessage,
  sortObligationsForDisplay,
  STATUS_LABELS,
  statusBadgeVariant,
  VISIT_TYPE_LABELS,
} from "@/lib/medicalFollowUpLabels";
import { cn } from "@/lib/utils";
import {
  ChevronDown,
  ExternalLink,
  Loader2,
  PlusCircle,
  RefreshCw,
  Stethoscope,
} from "lucide-react";

const EMPLOYEE_OBLIGATIONS_QUERY_KEY = "employee";

function medicalEmployeeQueryKey(employeeId: string) {
  return ["medical-follow-up", EMPLOYEE_OBLIGATIONS_QUERY_KEY, employeeId] as const;
}

export interface EmployeeDetailMedicalTabProps {
  employeeId: string;
  employeeName?: string;
}

function TableSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  );
}

export function EmployeeDetailMedicalTab({
  employeeId,
  employeeName,
}: EmployeeDetailMedicalTabProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const obligationsQuery = useQuery({
    queryKey: medicalEmployeeQueryKey(employeeId),
    queryFn: () => getObligationsForEmployee(employeeId),
    enabled: !!employeeId,
  });

  const obligations = obligationsQuery.data ?? [];
  const sorted = useMemo(() => sortObligationsForDisplay(obligations), [obligations]);
  const counts = useMemo(() => countMedicalObligations(obligations), [obligations]);
  const nextObligation = useMemo(() => getNextObligation(obligations), [obligations]);

  const [planifiedModal, setPlanifiedModal] = useState<ObligationListItem | null>(null);
  const [planifiedDate, setPlanifiedDate] = useState("");
  const [planifiedComment, setPlanifiedComment] = useState("");
  const [completedModal, setCompletedModal] = useState<ObligationListItem | null>(null);
  const [completedDate, setCompletedDate] = useState("");
  const [completedComment, setCompletedComment] = useState("");
  const [onDemandOpen, setOnDemandOpen] = useState(false);
  const [onDemandMotif, setOnDemandMotif] = useState("");
  const [onDemandDate, setOnDemandDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [showAdvanced, setShowAdvanced] = useState(false);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: medicalEmployeeQueryKey(employeeId) });
    void queryClient.invalidateQueries({ queryKey: ["medical-follow-up", "kpis"] });
    void queryClient.invalidateQueries({ queryKey: ["medical-follow-up", "obligations"] });
  };

  const planifiedMutation = useMutation({
    mutationFn: async () => {
      if (!planifiedModal || !planifiedDate) throw new Error("Date requise");
      await markPlanified(planifiedModal.id, {
        planned_date: planifiedDate,
        justification: planifiedComment || undefined,
      });
    },
    onSuccess: () => {
      toast({ title: "Succès", description: "Obligation marquée comme planifiée." });
      setPlanifiedModal(null);
      setPlanifiedDate("");
      setPlanifiedComment("");
      invalidate();
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === "object" && "response" in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Erreur",
        description: typeof msg === "string" ? msg : "Enregistrement impossible",
        variant: "destructive",
      });
    },
  });

  const completedMutation = useMutation({
    mutationFn: async () => {
      if (!completedModal || !completedDate) throw new Error("Date requise");
      await markCompleted(completedModal.id, {
        completed_date: completedDate,
        justification: completedComment || undefined,
      });
    },
    onSuccess: () => {
      toast({ title: "Succès", description: "Obligation marquée comme réalisée." });
      setCompletedModal(null);
      setCompletedDate("");
      setCompletedComment("");
      invalidate();
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === "object" && "response" in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Erreur",
        description: typeof msg === "string" ? msg : "Enregistrement impossible",
        variant: "destructive",
      });
    },
  });

  const onDemandMutation = useMutation({
    mutationFn: async () => {
      if (!onDemandMotif || !onDemandDate) throw new Error("Champs requis");
      await createOnDemand({
        employee_id: employeeId,
        request_motif: onDemandMotif,
        request_date: onDemandDate,
      });
    },
    onSuccess: () => {
      toast({ title: "Succès", description: "Visite à la demande créée." });
      setOnDemandOpen(false);
      setOnDemandMotif("");
      setOnDemandDate(new Date().toISOString().slice(0, 10));
      invalidate();
    },
    onError: (e: unknown) => {
      const msg =
        e && typeof e === "object" && "response" in e
          ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Erreur",
        description: typeof msg === "string" ? msg : "Création impossible",
        variant: "destructive",
      });
    },
  });

  const openPlanified = (o: ObligationListItem) => {
    setPlanifiedModal(o);
    setPlanifiedDate(o.planned_date || new Date().toISOString().slice(0, 10));
    setPlanifiedComment(o.justification || "");
  };

  const openCompleted = (o: ObligationListItem) => {
    setCompletedModal(o);
    setCompletedDate(o.completed_date || new Date().toISOString().slice(0, 10));
    setCompletedComment(o.justification || "");
  };

  const pilotageHref = `/medical-follow-up?employee=${encodeURIComponent(employeeId)}`;
  const saving =
    planifiedMutation.isPending || completedMutation.isPending || onDemandMutation.isPending;

  return (
    <>
      <Card>
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2">
              <Stethoscope className="h-5 w-5 text-primary" aria-hidden />
              Suivi médical
            </CardTitle>
            <CardDescription>
              {employeeName
                ? `Obligations de visite pour ${employeeName}`
                : "Prochaine obligation et historique des visites médicales"}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => void obligationsQuery.refetch()}
              disabled={obligationsQuery.isFetching}
            >
              {obligationsQuery.isFetching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Actualiser
            </Button>
            <Button type="button" variant="outline" size="sm" className="gap-2" asChild>
              <Link to={pilotageHref}>
                <ExternalLink className="h-4 w-4" />
                Pilotage global
              </Link>
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => setOnDemandOpen(true)}
            >
              <PlusCircle className="h-4 w-4" />
              Visite à la demande
            </Button>
          </div>
        </CardHeader>

        <CardContent className="space-y-6">
          {obligationsQuery.isLoading ? (
            <TableSkeleton />
          ) : obligationsQuery.isError ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
              <p className="font-medium text-destructive">Impossible de charger le suivi médical</p>
              <p className="text-muted-foreground mt-1">
                Vérifiez vos droits RH ou réessayez. Si le problème persiste, contactez le support.
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={() => void obligationsQuery.refetch()}
              >
                Réessayer
              </Button>
            </div>
          ) : obligations.length === 0 ? (
            <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
              <p>Aucune obligation de suivi médical pour le moment.</p>
              <p className="mt-2">
                Les obligations sont calculées à partir du contrat, des visites enregistrées et des
                règles légales applicables.
              </p>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap gap-2 text-sm">
                {counts.overdue > 0 && (
                  <Badge variant="destructive">{counts.overdue} en retard</Badge>
                )}
                {counts.active > 0 && (
                  <Badge variant="outline">{counts.active} à traiter</Badge>
                )}
                {counts.completed > 0 && (
                  <Badge variant="secondary">{counts.completed} réalisée{counts.completed > 1 ? "s" : ""}</Badge>
                )}
              </div>

              <div>
                <h4 className="text-sm font-medium mb-2">Prochaine obligation</h4>
                {!nextObligation ? (
                  <p className="text-sm text-muted-foreground rounded-lg border border-dashed p-4">
                    Aucune visite à planifier — toutes les obligations actives sont à jour ou clôturées.
                  </p>
                ) : (
                  (() => {
                    const overdue = isObligationOverdue(nextObligation);
                    const relative = getDueDateRelativeLabel(
                      nextObligation.due_date,
                      nextObligation.status
                    );
                    return (
                      <div
                        className={cn(
                          "rounded-lg border p-4 space-y-3",
                          overdue && "border-destructive/50 bg-destructive/5"
                        )}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="space-y-1">
                            <p className="font-medium">
                              {VISIT_TYPE_LABELS[nextObligation.visit_type] ??
                                nextObligation.visit_type}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              Date limite : {formatMedicalDate(nextObligation.due_date)}
                            </p>
                            {nextObligation.planned_date && (
                              <p className="text-sm text-muted-foreground">
                                Date planifiée : {formatMedicalDate(nextObligation.planned_date)}
                              </p>
                            )}
                            {relative && (
                              <p
                                className={cn(
                                  "text-sm font-medium",
                                  overdue ? "text-destructive" : "text-muted-foreground"
                                )}
                              >
                                {relative}
                              </p>
                            )}
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <Badge
                              variant={statusBadgeVariant(
                                nextObligation.status,
                                nextObligation.due_date
                              )}
                            >
                              {STATUS_LABELS[nextObligation.status] ?? nextObligation.status}
                            </Badge>
                            {overdue && <Badge variant="destructive">En retard</Badge>}
                          </div>
                        </div>
                        {nextObligation.justification && (
                          <p className="text-sm text-muted-foreground">
                            {nextObligation.justification}
                          </p>
                        )}
                        <div className="flex flex-wrap gap-2 pt-1">
                          <Button type="button" variant="outline" size="sm" onClick={() => openPlanified(nextObligation)}>
                            Planifier
                          </Button>
                          <Button type="button" size="sm" onClick={() => openCompleted(nextObligation)}>
                            Marquer réalisée
                          </Button>
                        </div>
                      </div>
                    );
                  })()
                )}
              </div>

              <div>
                <h4 className="text-sm font-medium mb-2">Historique</h4>
                <div className="w-full overflow-x-auto rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Type</TableHead>
                        <TableHead>Date limite</TableHead>
                        <TableHead>Statut</TableHead>
                        <TableHead>Planifiée</TableHead>
                        <TableHead>Réalisée</TableHead>
                        <TableHead className="min-w-[140px]">Message</TableHead>
                        <TableHead className="text-right w-[180px]">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {sorted.map((o) => {
                        const overdue = isObligationOverdue(o);
                        const cancelled = o.status === "annulee";
                        return (
                          <TableRow
                            key={o.id}
                            className={cn(
                              overdue && "bg-destructive/5",
                              cancelled && "opacity-60"
                            )}
                          >
                            <TableCell className="font-medium">
                              {VISIT_TYPE_LABELS[o.visit_type] ?? o.visit_type}
                            </TableCell>
                            <TableCell>{formatMedicalDate(o.due_date)}</TableCell>
                            <TableCell>
                              <Badge variant={statusBadgeVariant(o.status, o.due_date)}>
                                {STATUS_LABELS[o.status] ?? o.status}
                              </Badge>
                            </TableCell>
                            <TableCell>{formatMedicalDate(o.planned_date)}</TableCell>
                            <TableCell>{formatMedicalDate(o.completed_date)}</TableCell>
                            <TableCell className="text-muted-foreground text-sm max-w-[200px] truncate">
                              {obligationMessage(o)}
                            </TableCell>
                            <TableCell className="text-right">
                              {o.status !== "realisee" && o.status !== "annulee" && (
                                <div className="flex justify-end gap-1">
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => openPlanified(o)}
                                  >
                                    Planifier
                                  </Button>
                                  <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => openCompleted(o)}
                                  >
                                    Réalisée
                                  </Button>
                                </div>
                              )}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              </div>

              <Collapsible open={showAdvanced} onOpenChange={setShowAdvanced}>
                <CollapsibleTrigger asChild>
                  <Button type="button" variant="ghost" size="sm" className="gap-2 px-0">
                    <ChevronDown
                      className={cn("h-4 w-4 transition-transform", showAdvanced && "rotate-180")}
                    />
                    Détails conformité
                  </Button>
                </CollapsibleTrigger>
                <CollapsibleContent className="pt-2">
                  <div className="w-full overflow-x-auto rounded-md border">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Type</TableHead>
                          <TableHead>Déclencheur</TableHead>
                          <TableHead>Priorité</TableHead>
                          <TableHead>Source</TableHead>
                          <TableHead>IDCC</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {sorted.map((o) => (
                          <TableRow key={`adv-${o.id}`} className={o.status === "annulee" ? "opacity-60" : undefined}>
                            <TableCell className="text-sm">
                              {VISIT_TYPE_LABELS[o.visit_type] ?? o.visit_type}
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">{o.trigger_type}</TableCell>
                            <TableCell className="text-sm tabular-nums">{o.priority}</TableCell>
                            <TableCell className="text-sm text-muted-foreground">{o.rule_source}</TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {o.collective_agreement_idcc ?? "—"}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </CollapsibleContent>
              </Collapsible>
            </>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!planifiedModal} onOpenChange={(open) => !open && setPlanifiedModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Marquer comme planifiée</DialogTitle>
            <DialogDescription>Indiquez la date de planification et un commentaire optionnel.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="med-plan-date">Date de planification</Label>
              <Input
                id="med-plan-date"
                type="date"
                value={planifiedDate}
                onChange={(e) => setPlanifiedDate(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="med-plan-comment">Commentaire (optionnel)</Label>
              <Input
                id="med-plan-comment"
                value={planifiedComment}
                onChange={(e) => setPlanifiedComment(e.target.value)}
                placeholder="Commentaire"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setPlanifiedModal(null)}>
              Annuler
            </Button>
            <Button
              type="button"
              onClick={() => planifiedMutation.mutate()}
              disabled={saving || !planifiedDate}
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Enregistrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!completedModal} onOpenChange={(open) => !open && setCompletedModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Marquer comme réalisée</DialogTitle>
            <DialogDescription>Indiquez la date de réalisation et un commentaire optionnel.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="med-done-date">Date réelle</Label>
              <Input
                id="med-done-date"
                type="date"
                value={completedDate}
                onChange={(e) => setCompletedDate(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="med-done-comment">Commentaire (optionnel)</Label>
              <Input
                id="med-done-comment"
                value={completedComment}
                onChange={(e) => setCompletedComment(e.target.value)}
                placeholder="Commentaire"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setCompletedModal(null)}>
              Annuler
            </Button>
            <Button
              type="button"
              onClick={() => completedMutation.mutate()}
              disabled={saving || !completedDate}
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Enregistrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={onDemandOpen} onOpenChange={setOnDemandOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Créer une visite à la demande</DialogTitle>
            <DialogDescription>
              {employeeName
                ? `Pour ${employeeName} — indiquez le motif et la date de demande.`
                : "Indiquez le motif et la date de demande."}
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="med-demand-motif">Motif</Label>
              <Input
                id="med-demand-motif"
                value={onDemandMotif}
                onChange={(e) => setOnDemandMotif(e.target.value)}
                placeholder="Motif de la demande"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="med-demand-date">Date demande</Label>
              <Input
                id="med-demand-date"
                type="date"
                value={onDemandDate}
                onChange={(e) => setOnDemandDate(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setOnDemandOpen(false)}>
              Annuler
            </Button>
            <Button
              type="button"
              onClick={() => onDemandMutation.mutate()}
              disabled={saving || !onDemandMotif || !onDemandDate}
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Créer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** Query key partagée pour badge onglet et invalidation. */
export { medicalEmployeeQueryKey };
