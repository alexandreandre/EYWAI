// Page RH : Suivi médical des salariés (obligations VIP, SIR, reprise, mi-carrière)

import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/hooks/use-toast";
import {
  getObligations,
  getKPIs,
  markPlanified,
  markCompleted,
  createOnDemand,
  type ObligationListItem,
  type KPIs,
} from "@/api/medicalFollowUp";
import apiClient from "@/api/apiClient";
import { Loader2, Stethoscope, Calendar, CheckCircle, PlusCircle, FileDown } from "lucide-react";

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

export default function MedicalFollowUp() {
  const { toast } = useToast();
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
  }, [filterEmployee, filterVisitType, filterStatus, toast]);

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
