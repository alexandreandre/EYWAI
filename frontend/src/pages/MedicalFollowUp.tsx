// Page RH : Suivi médical des salariés (obligations VIP, SIR, reprise, mi-carrière)

import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import {
  getObligations,
  getKPIs,
  markPlanified,
  markCompleted,
  createOnDemand,
  getOverdueObligations,
  getUpcomingObligations,
  sendMedicalReminders,
  getComplianceReport,
  type ObligationListItem,
  type KPIs,
  type ComplianceReport,
} from "@/api/medicalFollowUp";
import apiClient from "@/api/apiClient";
import { Loader2, PlusCircle, FileDown, Bell, RefreshCw } from "lucide-react";

const VISIT_TYPE_LABELS: Record<string, string> = {
  aptitude_sir_avant_affectation: "Aptitude SIR avant affectation",
  vip_avant_affectation_mineur_nuit: "VIP avant affectation (mineur/nuit)",
  reprise: "Reprise",
  vip: "VIP",
  sir: "SIR",
  mi_carriere_45: "Mi-carrière (45 ans)",
  demande: "À la demande",
};

const STATUS_LABELS: Record<string, string> = {
  a_faire: "À faire",
  planifiee: "Planifiée",
  realisee: "Réalisée",
  annulee: "Annulée",
};

const ALL_FILTER = "__all__";

function formatDate(s: string | null | undefined): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
  } catch {
    return s;
  }
}

function statusBadgeVariant(status: string, dueDate: string): "default" | "secondary" | "destructive" | "outline" {
  if (status === "realisee") return "secondary";
  const today = new Date().toISOString().slice(0, 10);
  if (dueDate < today) return "destructive";
  const d30 = new Date();
  d30.setDate(d30.getDate() + 30);
  if (dueDate <= d30.toISOString().slice(0, 10)) return "outline";
  return "default";
}

function globalComplianceTextClass(rate: number): string {
  if (rate >= 80) return "text-green-600";
  if (rate >= 60) return "text-orange-600";
  return "text-destructive";
}

function globalComplianceBarClass(rate: number): string {
  if (rate >= 80) return "bg-green-600";
  if (rate >= 60) return "bg-orange-500";
  return "bg-destructive";
}

function visitTypeBarClass(rate: number): string {
  if (rate >= 80) return "bg-green-600";
  if (rate >= 60) return "bg-orange-500";
  return "bg-destructive";
}

function MedicalCompliancePanels({ cr }: { cr: ComplianceReport }) {
  const rate = cr.compliance_rate;
  return (
    <>
      <div>
        <h3 className="text-sm font-medium text-muted-foreground mb-3">Score global</h3>
        <div className="grid gap-4 md:grid-cols-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Taux de conformité global
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className={`text-4xl font-bold tabular-nums ${globalComplianceTextClass(rate)}`}>
                {rate.toFixed(1)} %
              </p>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={`h-full rounded-full transition-all ${globalComplianceBarClass(rate)}`}
                  style={{ width: `${Math.min(100, Math.max(0, rate))}%` }}
                />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Visites conformes</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold tabular-nums">
                {cr.compliant}
                <span className="text-muted-foreground text-base font-normal">
                  {" "}
                  / {cr.total_obligations}
                </span>
              </p>
            </CardContent>
          </Card>
          <Card className={cr.overdue > 0 ? "border-destructive/40" : ""}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">En retard</CardTitle>
            </CardHeader>
            <CardContent>
              <p
                className={`text-2xl font-bold tabular-nums ${
                  cr.overdue > 0 ? "text-destructive" : "text-muted-foreground"
                }`}
              >
                {cr.overdue}
              </p>
            </CardContent>
          </Card>
          <Card className="border-orange-500/30">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">À venir 30 j.</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold tabular-nums text-orange-600">{cr.upcoming_30}</p>
              <p className="text-xs text-muted-foreground mt-1">Dont {cr.upcoming_7} sous 7 jours</p>
            </CardContent>
          </Card>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-medium text-muted-foreground mb-3">Par type de visite</h3>
        <Card>
          <CardContent className="pt-6">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type de visite</TableHead>
                  <TableHead className="text-right">Total</TableHead>
                  <TableHead className="text-right">Conformes</TableHead>
                  <TableHead className="text-right">En retard</TableHead>
                  <TableHead>Taux de conformité</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {cr.by_visit_type.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center text-muted-foreground py-8">
                      Aucune obligation par type.
                    </TableCell>
                  </TableRow>
                ) : (
                  cr.by_visit_type.map((v) => (
                    <TableRow key={v.visit_type}>
                      <TableCell className="font-medium">{v.label}</TableCell>
                      <TableCell className="text-right tabular-nums">{v.total}</TableCell>
                      <TableCell className="text-right tabular-nums">{v.compliant}</TableCell>
                      <TableCell className="text-right tabular-nums">{v.overdue}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2 min-w-[140px]">
                          <span className="text-sm tabular-nums w-12">{v.compliance_rate.toFixed(0)}%</span>
                          <div className="h-2 flex-1 max-w-[120px] overflow-hidden rounded-full bg-muted">
                            <div
                              className={`h-full rounded-full ${visitTypeBarClass(v.compliance_rate)}`}
                              style={{ width: `${Math.min(100, Math.max(0, v.compliance_rate))}%` }}
                            />
                          </div>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>

      <div>
        <h3 className="text-sm font-medium text-muted-foreground mb-3">Salariés en retard</h3>
        <Card>
          <CardContent className="pt-6">
            {cr.employees_overdue.length === 0 ? (
              <p className="text-center text-sm text-muted-foreground py-10">
                ✅ Tous les salariés sont à jour.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Salarié</TableHead>
                    <TableHead className="text-right">Nb obligations en retard</TableHead>
                    <TableHead>Plus urgent</TableHead>
                    <TableHead>Types de visites</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {cr.employees_overdue.map((e) => (
                    <TableRow key={e.employee_id}>
                      <TableCell className="font-medium">{e.employee_name}</TableCell>
                      <TableCell className="text-right">
                        <Badge variant="destructive" className="tabular-nums">
                          {e.obligations_overdue}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-destructive font-medium tabular-nums">
                        {formatDate(e.most_urgent_due_date)}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {e.visit_types.map((vt) => VISIT_TYPE_LABELS[vt] ?? vt).join(", ")}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function formatComplianceGeneratedAtFrench(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString("fr-FR", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function exportComplianceReportToCsv(r: ComplianceReport): void {
  const esc = (c: string) => `"${String(c).replace(/"/g, '""')}"`;
  const lines: string[] = [];
  const fileDate = new Date().toISOString().slice(0, 10);

  // Section 1 — RAPPORT DE CONFORMITÉ MÉDICAL
  lines.push(esc("Section 1 — RAPPORT DE CONFORMITÉ MÉDICAL"));
  lines.push(esc(`Généré le : ${formatComplianceGeneratedAtFrench(r.generated_at)}`));
  lines.push([esc("Entreprise :"), esc("")].join(";"));
  lines.push("");

  // Section 2 — INDICATEURS GLOBAUX
  lines.push(esc("Section 2 — INDICATEURS GLOBAUX"));
  lines.push(["Libellé", "Valeur"].map(esc).join(";"));
  lines.push([esc("Total salariés concernés"), esc(String(r.total_employees))].join(";"));
  lines.push([esc("Total obligations"), esc(String(r.total_obligations))].join(";"));
  lines.push([esc("Obligations conformes"), esc(String(r.compliant))].join(";"));
  lines.push([esc("Obligations en retard"), esc(String(r.overdue))].join(";"));
  lines.push([esc("Échéances dans 30 jours"), esc(String(r.upcoming_30))].join(";"));
  lines.push([esc("Échéances dans 7 jours"), esc(String(r.upcoming_7))].join(";"));
  lines.push([esc("Taux de conformité"), esc(`${Number(r.compliance_rate).toFixed(2)} %`)].join(";"));
  lines.push("");

  // Section 3 — PAR TYPE DE VISITE
  lines.push(esc("Section 3 — PAR TYPE DE VISITE"));
  lines.push(
    ["Type de visite", "Total", "Conformes", "En retard", "Taux de conformité"].map(esc).join(";")
  );
  for (const v of r.by_visit_type) {
    lines.push(
      [
        v.label,
        String(v.total),
        String(v.compliant),
        String(v.overdue),
        `${Number(v.compliance_rate).toFixed(2)} %`,
      ]
        .map(esc)
        .join(";")
    );
  }
  lines.push("");

  // Section 4 — SALARIÉS EN RETARD
  lines.push(esc("Section 4 — SALARIÉS EN RETARD"));
  lines.push(
    ["Salarié", "Nb obligations en retard", "Date la plus urgente", "Types de visites"].map(esc).join(";")
  );
  for (const e of r.employees_overdue) {
    const typesFr = e.visit_types.map((vt) => VISIT_TYPE_LABELS[vt] ?? vt).join(", ");
    lines.push(
      [
        e.employee_name,
        String(e.obligations_overdue),
        formatDate(e.most_urgent_due_date),
        typesFr,
      ]
        .map(esc)
        .join(";")
    );
  }

  const csv = lines.join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `rapport_conformite_medicale_${fileDate}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function MedicalFollowUp() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [obligations, setObligations] = useState<ObligationListItem[]>([]);
  const [kpis, setKpis] = useState<KPIs | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterEmployee, setFilterEmployee] = useState<string>(ALL_FILTER);
  const [filterVisitType, setFilterVisitType] = useState<string>(ALL_FILTER);
  const [filterStatus, setFilterStatus] = useState<string>(ALL_FILTER);
  const [employees, setEmployees] = useState<{ id: string; first_name: string; last_name: string }[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [oblsRes, kpisRes] = await Promise.all([
        getObligations({
          employee_id: filterEmployee && filterEmployee !== ALL_FILTER ? filterEmployee : undefined,
          visit_type: filterVisitType && filterVisitType !== ALL_FILTER ? filterVisitType : undefined,
          status: filterStatus && filterStatus !== ALL_FILTER ? filterStatus : undefined,
        }),
        getKPIs(),
      ]);
      setObligations(Array.isArray(oblsRes) ? oblsRes : []);
      const validKpis =
        kpisRes &&
        typeof kpisRes === "object" &&
        "overdue_count" in kpisRes &&
        "active_total" in kpisRes;
      setKpis(validKpis ? (kpisRes as KPIs) : null);
      void queryClient.invalidateQueries({ queryKey: ["medical-follow-up", "compliance-report"] });
    } catch (e: any) {
      const raw = e.response?.data?.detail;
      const msg =
        typeof raw === "string"
          ? raw
          : Array.isArray(raw) && raw[0]?.msg
            ? raw[0].msg
            : e.message ?? "Erreur chargement";
      toast({ title: "Erreur", description: String(msg), variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [filterEmployee, filterVisitType, filterStatus, toast, queryClient]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    apiClient.get("/api/employees").then((r) => {
      const list = (r.data as any[]) ?? [];
      setEmployees(list.map((e: any) => ({ id: e.id, first_name: e.first_name, last_name: e.last_name })));
    }).catch(() => {});
  }, []);

  const [planifiedModal, setPlanifiedModal] = useState<ObligationListItem | null>(null);
  const [planifiedDate, setPlanifiedDate] = useState("");
  const [planifiedComment, setPlanifiedComment] = useState("");
  const [completedModal, setCompletedModal] = useState<ObligationListItem | null>(null);
  const [completedDate, setCompletedDate] = useState("");
  const [completedComment, setCompletedComment] = useState("");
  const [onDemandOpen, setOnDemandOpen] = useState(false);
  const [onDemandEmployee, setOnDemandEmployee] = useState("");
  const [onDemandMotif, setOnDemandMotif] = useState("");
  const [onDemandDate, setOnDemandDate] = useState(new Date().toISOString().slice(0, 10));
  const [saving, setSaving] = useState(false);
  const [remindersConfirmOpen, setRemindersConfirmOpen] = useState(false);
  const [medTab, setMedTab] = useState<"pilotage" | "conformite">("pilotage");

  const complianceQuery = useQuery({
    queryKey: ["medical-follow-up", "compliance-report"],
    queryFn: getComplianceReport,
    enabled: medTab === "conformite",
  });

  const overdueQuery = useQuery({
    queryKey: ["medical-follow-up", "obligations", "overdue"],
    queryFn: getOverdueObligations,
  });

  const upcoming30Query = useQuery({
    queryKey: ["medical-follow-up", "obligations", "upcoming", 30],
    queryFn: () => getUpcomingObligations(30),
  });

  const salarieConcerneCount = useMemo(() => {
    const ids = new Set<string>();
    for (const o of overdueQuery.data ?? []) ids.add(o.employee_id);
    for (const o of upcoming30Query.data ?? []) ids.add(o.employee_id);
    return ids.size;
  }, [overdueQuery.data, upcoming30Query.data]);

  const sendRemindersMutation = useMutation({
    mutationFn: sendMedicalReminders,
    onSuccess: (data) => {
      toast({
        title: "Rappels",
        description: data.message ?? `${data.sent} rappel(s) envoyé(s)`,
      });
      void queryClient.invalidateQueries({ queryKey: ["medical-follow-up", "obligations", "overdue"] });
      void queryClient.invalidateQueries({ queryKey: ["medical-follow-up", "obligations", "upcoming", 30] });
      setRemindersConfirmOpen(false);
      void load();
    },
    onError: (e: any) => {
      toast({
        title: "Erreur",
        description: e.response?.data?.detail ?? e.message ?? "Envoi impossible",
        variant: "destructive",
      });
    },
  });

  const exportCSV = () => {
    const headers = ["Salarié", "Type de visite", "Déclencheur", "Date limite", "Priorité", "Statut", "Justification", "Date planifiée", "Date réalisée"];
    const rows = (Array.isArray(obligations) ? obligations : []).map((o) => [
      `${o.employee_first_name ?? ""} ${o.employee_last_name ?? ""}`.trim(),
      VISIT_TYPE_LABELS[o.visit_type] ?? o.visit_type,
      o.trigger_type,
      o.due_date,
      String(o.priority),
      STATUS_LABELS[o.status] ?? o.status,
      o.justification ?? "",
      o.planned_date ?? "",
      o.completed_date ?? "",
    ]);
    const csv = [headers.join(";"), ...rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(";"))].join("\n");
    const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `suivi-medical-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleMarkPlanified = async () => {
    if (!planifiedModal) return;
    setSaving(true);
    try {
      await markPlanified(planifiedModal.id, { planned_date: planifiedDate, justification: planifiedComment || undefined });
      toast({ title: "Succès", description: "Obligation marquée comme planifiée." });
      setPlanifiedModal(null);
      setPlanifiedDate("");
      setPlanifiedComment("");
      load();
    } catch (e: any) {
      toast({ title: "Erreur", description: e.response?.data?.detail ?? e.message, variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleMarkCompleted = async () => {
    if (!completedModal) return;
    setSaving(true);
    try {
      await markCompleted(completedModal.id, { completed_date: completedDate, justification: completedComment || undefined });
      toast({ title: "Succès", description: "Obligation marquée comme réalisée." });
      setCompletedModal(null);
      setCompletedDate("");
      setCompletedComment("");
      load();
    } catch (e: any) {
      toast({ title: "Erreur", description: e.response?.data?.detail ?? e.message, variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleCreateOnDemand = async () => {
    if (!onDemandEmployee || !onDemandMotif || !onDemandDate) {
      toast({ title: "Champs requis", description: "Salarié, motif et date sont obligatoires.", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      await createOnDemand({ employee_id: onDemandEmployee, request_motif: onDemandMotif, request_date: onDemandDate });
      toast({ title: "Succès", description: "Visite à la demande créée." });
      setOnDemandOpen(false);
      setOnDemandEmployee("");
      setOnDemandMotif("");
      setOnDemandDate(new Date().toISOString().slice(0, 10));
      load();
    } catch (e: any) {
      toast({ title: "Erreur", description: e.response?.data?.detail ?? e.message, variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Suivi médical</h1>
        <p className="text-muted-foreground mt-1">
          Pilotage des obligations légales de suivi médical
        </p>
      </div>

      <Tabs value={medTab} onValueChange={(v) => setMedTab(v as "pilotage" | "conformite")} className="w-full">
        <TabsList className="grid w-full max-w-lg grid-cols-2">
          <TabsTrigger value="pilotage">Pilotage</TabsTrigger>
          <TabsTrigger value="conformite">Tableau de conformité</TabsTrigger>
        </TabsList>

        <TabsContent value="pilotage" className="mt-4 space-y-6">
      <div className="space-y-3">
        <h2 className="text-lg font-semibold tracking-tight">Rappels et alertes</h2>
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="border-destructive/30">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Visites en retard</CardTitle>
              <CardDescription>Échéance dépassée, obligations non réalisées</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {overdueQuery.isLoading ? (
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              ) : (
                <>
                  <p className="text-3xl font-bold text-destructive tabular-nums">
                    {overdueQuery.data?.length ?? 0}
                  </p>
                  <ul className="space-y-2 text-sm border-t pt-3">
                    {(overdueQuery.data ?? []).slice(0, 5).map((o) => (
                      <li key={o.id} className="flex flex-col gap-0.5">
                        <span className="font-medium">
                          {o.employee_first_name} {o.employee_last_name}
                        </span>
                        <span className="text-muted-foreground">
                          {VISIT_TYPE_LABELS[o.visit_type] ?? o.visit_type} — échéance {formatDate(o.due_date)}
                        </span>
                      </li>
                    ))}
                    {(overdueQuery.data?.length ?? 0) === 0 ? (
                      <li className="text-muted-foreground">Aucune visite en retard.</li>
                    ) : null}
                  </ul>
                </>
              )}
            </CardContent>
          </Card>
          <Card className="border-orange-500/40">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Visites dans les 30 jours</CardTitle>
              <CardDescription>À venir (hors retards)</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {upcoming30Query.isLoading ? (
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              ) : (
                <>
                  <p className="text-3xl font-bold text-orange-600 tabular-nums">
                    {upcoming30Query.data?.length ?? 0}
                  </p>
                  <ul className="space-y-2 text-sm border-t pt-3">
                    {(upcoming30Query.data ?? []).slice(0, 5).map((o) => (
                      <li key={o.id} className="flex flex-col gap-0.5">
                        <span className="font-medium">
                          {o.employee_first_name} {o.employee_last_name}
                        </span>
                        <span className="text-muted-foreground">
                          {VISIT_TYPE_LABELS[o.visit_type] ?? o.visit_type} — échéance {formatDate(o.due_date)}
                        </span>
                      </li>
                    ))}
                    {(upcoming30Query.data?.length ?? 0) === 0 ? (
                      <li className="text-muted-foreground">Aucune échéance dans les 30 prochains jours.</li>
                    ) : null}
                  </ul>
                </>
              )}
            </CardContent>
          </Card>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            type="button"
            variant="default"
            size="sm"
            className="gap-2"
            onClick={() => setRemindersConfirmOpen(true)}
            disabled={sendRemindersMutation.isPending}
          >
            {sendRemindersMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Bell className="h-4 w-4" />
            )}
            Envoyer les rappels aux salariés
          </Button>
        </div>
      </div>

      <AlertDialog open={remindersConfirmOpen} onOpenChange={setRemindersConfirmOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Envoyer les rappels ?</AlertDialogTitle>
            <AlertDialogDescription>
              Envoyer des notifications à {salarieConcerneCount} salarié(s) concerné(s) ? Les rappels
              portent sur les obligations actives dont l&apos;échéance est passée ou dans les 30 prochains
              jours.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => sendRemindersMutation.mutate()}
              disabled={sendRemindersMutation.isPending}
            >
              Confirmer l&apos;envoi
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {kpis && (
        <div className="grid gap-4 md:grid-cols-4">
          <Card className="border-l-4 border-l-red-500">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">En retard</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{kpis.overdue_count}</div>
            </CardContent>
          </Card>
          <Card className="border-l-4 border-l-orange-500">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Échéance &lt; 30 jours</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-orange-600">{kpis.due_within_30_count}</div>
            </CardContent>
          </Card>
          <Card className="border-l-4 border-l-blue-500">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Total actives</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-600">{kpis.active_total}</div>
            </CardContent>
          </Card>
          <Card className="border-l-4 border-l-green-500">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Réalisées ce mois</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{kpis.completed_this_month}</div>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle>Obligations</CardTitle>
          <div className="flex items-center gap-2">
            <Select value={filterEmployee} onValueChange={setFilterEmployee}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Tous les salariés" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_FILTER}>Tous les salariés</SelectItem>
                {Array.isArray(employees) &&
                  employees.map((e) => (
                    <SelectItem key={e.id} value={e.id}>{e.first_name} {e.last_name}</SelectItem>
                  ))}
              </SelectContent>
            </Select>
            <Select value={filterVisitType} onValueChange={setFilterVisitType}>
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="Type de visite" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_FILTER}>Tous types</SelectItem>
                {Object.entries(VISIT_TYPE_LABELS).map(([k, v]) => (
                  <SelectItem key={k} value={k}>{v}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="w-[140px]">
                <SelectValue placeholder="Statut" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_FILTER}>Tous</SelectItem>
                {Object.entries(STATUS_LABELS).map(([k, v]) => (
                  <SelectItem key={k} value={k}>{v}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button onClick={() => setOnDemandOpen(true)} variant="outline" size="sm">
              <PlusCircle className="h-4 w-4 mr-1" /> Créer visite à la demande
            </Button>
            <Button onClick={exportCSV} variant="outline" size="sm">
              <FileDown className="h-4 w-4 mr-1" /> Export CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Type de visite</TableHead>
                  <TableHead>Déclencheur</TableHead>
                  <TableHead>Date limite</TableHead>
                  <TableHead>Priorité</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Justification</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(!Array.isArray(obligations) || obligations.length === 0) ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center text-muted-foreground py-8">
                      Aucune obligation pour les filtres sélectionnés.
                    </TableCell>
                  </TableRow>
                ) : (
                  obligations.map((o) => (
                    <TableRow key={o.id}>
                      <TableCell>
                        {o.employee_first_name} {o.employee_last_name}
                      </TableCell>
                      <TableCell>{VISIT_TYPE_LABELS[o.visit_type] ?? o.visit_type}</TableCell>
                      <TableCell>{o.trigger_type}</TableCell>
                      <TableCell>{formatDate(o.due_date)}</TableCell>
                      <TableCell>{o.priority}</TableCell>
                      <TableCell>
                        <Badge variant={statusBadgeVariant(o.status, o.due_date)}>
                          {STATUS_LABELS[o.status] ?? o.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate">{o.justification ?? "—"}</TableCell>
                      <TableCell className="text-right">
                        {o.status !== "realisee" && (
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="mr-1"
                              onClick={() => {
                                setPlanifiedModal(o);
                                setPlanifiedDate(o.planned_date || new Date().toISOString().slice(0, 10));
                                setPlanifiedComment(o.justification || "");
                              }}
                            >
                              Planifiée
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                setCompletedModal(o);
                                setCompletedDate(o.completed_date || new Date().toISOString().slice(0, 10));
                                setCompletedComment(o.justification || "");
                              }}
                            >
                              Réalisée
                            </Button>
                          </>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
        </TabsContent>

        <TabsContent value="conformite" className="mt-4 space-y-8">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-semibold tracking-tight">Tableau de conformité</h2>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={() => void complianceQuery.refetch()}
                disabled={complianceQuery.isFetching}
              >
                {complianceQuery.isFetching ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                Actualiser
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="gap-2"
                disabled={!complianceQuery.data}
                onClick={() => {
                  if (complianceQuery.data) exportComplianceReportToCsv(complianceQuery.data);
                }}
              >
                <FileDown className="h-4 w-4" />
                Exporter le rapport
              </Button>
            </div>
          </div>

          {complianceQuery.isLoading ? (
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-4">
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-28 w-full" />
                ))}
              </div>
              <Skeleton className="h-48 w-full" />
              <Skeleton className="h-48 w-full" />
            </div>
          ) : complianceQuery.isError ? (
            <p className="text-sm text-destructive">Impossible de charger le rapport de conformité.</p>
          ) : complianceQuery.data ? (
            <MedicalCompliancePanels cr={complianceQuery.data} />
          ) : null}
        </TabsContent>
      </Tabs>

      <Dialog open={!!planifiedModal} onOpenChange={(open) => !open && setPlanifiedModal(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Marquer comme planifiée</DialogTitle>
            <DialogDescription>Indiquez la date de planification et un commentaire optionnel.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Date de planification</Label>
              <Input
                type="date"
                value={planifiedDate}
                onChange={(e) => setPlanifiedDate(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label>Commentaire (optionnel)</Label>
              <Input
                value={planifiedComment}
                onChange={(e) => setPlanifiedComment(e.target.value)}
                placeholder="Commentaire"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPlanifiedModal(null)}>Annuler</Button>
            <Button onClick={handleMarkPlanified} disabled={saving || !planifiedDate}>
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
              <Label>Date réelle</Label>
              <Input
                type="date"
                value={completedDate}
                onChange={(e) => setCompletedDate(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label>Commentaire (optionnel)</Label>
              <Input
                value={completedComment}
                onChange={(e) => setCompletedComment(e.target.value)}
                placeholder="Commentaire"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCompletedModal(null)}>Annuler</Button>
            <Button onClick={handleMarkCompleted} disabled={saving || !completedDate}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Enregistrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={onDemandOpen} onOpenChange={setOnDemandOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Créer une visite à la demande</DialogTitle>
            <DialogDescription>Sélectionnez le salarié, le motif et la date de demande.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Salarié</Label>
              <Select value={onDemandEmployee} onValueChange={setOnDemandEmployee}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir un salarié" />
                </SelectTrigger>
                <SelectContent>
                  {employees.map((e) => (
                    <SelectItem key={e.id} value={e.id}>{e.first_name} {e.last_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Motif</Label>
              <Input
                value={onDemandMotif}
                onChange={(e) => setOnDemandMotif(e.target.value)}
                placeholder="Motif de la demande"
              />
            </div>
            <div className="grid gap-2">
              <Label>Date demande</Label>
              <Input
                type="date"
                value={onDemandDate}
                onChange={(e) => setOnDemandDate(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOnDemandOpen(false)}>Annuler</Button>
            <Button onClick={handleCreateOnDemand} disabled={saving || !onDemandEmployee || !onDemandMotif || !onDemandDate}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Créer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
