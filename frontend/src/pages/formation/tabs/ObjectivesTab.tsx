// Onglet RH / collaborateur : objectifs & KPI (Pack Talent)

import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  BarChart3,
  Eye,
  Loader2,
  Pencil,
  Plus,
  Target,
  Trash2,
  Users,
} from "lucide-react";

import apiClient from "@/api/apiClient";
import {
  addCheckin,
  cancelObjective,
  createCompanyService,
  createObjective,
  declineObjectiveToTeam,
  evaluateObjective,
  getAchievementRate,
  getObjective,
  getObjectives,
  listCompanyServices,
  updateObjective,
  type CheckinCreate,
  type EmployeeObjective,
  type MilestoneCreate,
  type ObjectiveCreate,
  type ObjectiveEvaluate,
  type ObjectiveStatus,
  type ObjectiveType,
} from "@/api/objectives";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Dialog,
  DialogContent,
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
import { useToast } from "@/components/ui/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { useViewOptional } from "@/contexts/ViewContext";
import { cn } from "@/lib/utils";

type EmployeeRow = {
  id: string;
  first_name: string;
  last_name: string;
  service_id?: string | null;
};

function statusBadge(status: string) {
  const cfg: Record<string, { label: string; className: string }> = {
    draft: { label: "Brouillon", className: "bg-muted text-muted-foreground" },
    active: { label: "Actif", className: "bg-blue-600 text-white hover:bg-blue-600" },
    achieved: { label: "Atteint", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    partially_achieved: {
      label: "Partiellement atteint",
      className: "bg-orange-500 text-white hover:bg-orange-500",
    },
    not_achieved: { label: "Non atteint", className: "bg-red-600 text-white hover:bg-red-600" },
    cancelled: {
      label: "Annulé",
      className: "bg-muted text-muted-foreground line-through decoration-foreground/50",
    },
  };
  const c = cfg[status] ?? { label: status, className: "bg-muted" };
  return <Badge className={cn("border-0", c.className)}>{c.label}</Badge>;
}

function currentKpiValue(o: EmployeeObjective): string {
  if (o.type !== "quantitative") return "—";
  const ms = [...(o.milestones || [])].sort((a, b) =>
    a.milestone_date.localeCompare(b.milestone_date),
  );
  const last = ms.filter((m) => m.actual_value != null).pop();
  if (last?.actual_value != null) return String(last.actual_value);
  if (o.kpi_initial_value != null) return String(o.kpi_initial_value);
  return "—";
}

function rateCellClass(rate: number | null | undefined): string {
  if (rate == null || Number.isNaN(rate)) return "bg-muted text-muted-foreground";
  if (rate >= 80) return "bg-emerald-600/90 text-white";
  if (rate >= 50) return "bg-orange-500/90 text-white";
  return "bg-red-600/90 text-white";
}

export default function ObjectivesTab() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const viewOpt = useViewOptional();

  const isRh =
    Boolean(user?.is_super_admin) ||
    activeCompany?.role === "admin" ||
    activeCompany?.role === "rh" ||
    activeCompany?.role === "collaborateur_rh";

  const showRhActions = Boolean(
    isRh && !(viewOpt?.isCollaborateurRh && viewOpt.viewMode === "collaborateur"),
  );

  const defaultYear = new Date().getFullYear();
  const [filterEmployee, setFilterEmployee] = useState<string>("all");
  const [filterService, setFilterService] = useState<string>("all");
  const [filterYear, setFilterYear] = useState<number>(defaultYear);
  const [filterType, setFilterType] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [includeInactive, setIncludeInactive] = useState(false);
  const [reportingMode, setReportingMode] = useState(false);

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);

  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [editing, setEditing] = useState<EmployeeObjective | null>(null);

  const [evalOpen, setEvalOpen] = useState(false);
  const [evalTarget, setEvalTarget] = useState<EmployeeObjective | null>(null);
  const [evalRate, setEvalRate] = useState("");
  const [evalStatus, setEvalStatus] = useState<ObjectiveStatus>("achieved");
  const [evalComment, setEvalComment] = useState("");
  const [evalDate, setEvalDate] = useState(new Date().toISOString().slice(0, 10));

  const [cancelTarget, setCancelTarget] = useState<EmployeeObjective | null>(null);

  const [newServiceName, setNewServiceName] = useState("");

  const [scopeIndividual, setScopeIndividual] = useState(true);
  const [formEmployee, setFormEmployee] = useState("");
  const [formService, setFormService] = useState("");
  const [formTitle, setFormTitle] = useState("");
  const [formType, setFormType] = useState<ObjectiveType>("qualitative");
  const [formDesc, setFormDesc] = useState("");
  const [formKpiLabel, setFormKpiLabel] = useState("");
  const [formKpiUnit, setFormKpiUnit] = useState("");
  const [formKpiTarget, setFormKpiTarget] = useState("");
  const [formKpiInitial, setFormKpiInitial] = useState("");
  const [formDue, setFormDue] = useState("");
  const [formWeight, setFormWeight] = useState("");
  const [formNotes, setFormNotes] = useState("");
  const [formMilestones, setFormMilestones] = useState<MilestoneCreate[]>([]);
  const [declineAfterCreate, setDeclineAfterCreate] = useState(false);

  const employeesQuery = useQuery({
    queryKey: ["objectives", "employees"],
    queryFn: async () => {
      const res = await apiClient.get<EmployeeRow[]>("/api/employees");
      return res.data ?? [];
    },
    enabled: showRhActions,
  });

  const servicesQuery = useQuery({
    queryKey: ["objectives", "services"],
    queryFn: listCompanyServices,
    enabled: showRhActions,
  });

  const objectivesQuery = useQuery({
    queryKey: [
      "objectives",
      "list",
      filterEmployee,
      filterService,
      filterYear,
      filterType,
      filterStatus,
      includeInactive,
    ],
    queryFn: () =>
      getObjectives({
        employee_id: filterEmployee === "all" ? undefined : filterEmployee,
        service_id: filterService === "all" ? undefined : filterService,
        period_year: filterYear,
        status: filterStatus === "all" ? undefined : filterStatus,
        include_inactive: includeInactive,
      }),
  });

  const achievementQuery = useQuery({
    queryKey: ["objectives", "achievement", filterYear],
    queryFn: () => getAchievementRate(filterYear),
    enabled: showRhActions && !reportingMode,
  });

  const detailQuery = useQuery({
    queryKey: ["objectives", "detail", detailId],
    queryFn: () => getObjective(detailId as string),
    enabled: Boolean(detailId && detailOpen),
  });

  const filteredRows = useMemo(() => {
    let rows = objectivesQuery.data ?? [];
    if (filterType !== "all") {
      rows = rows.filter((r) => r.type === filterType);
    }
    return rows;
  }, [objectivesQuery.data, filterType]);

  const matrix = useMemo(() => {
    const rows = (filteredRows ?? []).filter((o) => o.employee_id && o.period_year === filterYear);
    const empIds = [...new Set(rows.map((r) => r.employee_id as string))];
    const objIds = [...new Set(rows.map((r) => r.id))];
    const byEmpObj = new Map<string, EmployeeObjective>();
    rows.forEach((o) => {
      if (o.employee_id) byEmpObj.set(`${o.employee_id}::${o.id}`, o);
    });
    const empName = (id: string) => {
      const e = employeesQuery.data?.find((x) => x.id === id);
      return e ? `${e.first_name} ${e.last_name}` : id;
    };
    return { empIds, objIds, byEmpObj, empName, rows };
  }, [filteredRows, filterYear, employeesQuery.data]);

  const invalidate = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ["objectives"] });
  }, [qc]);

  const createMutation = useMutation({
    mutationFn: async () => {
      const weight = formWeight.trim() ? Number(formWeight) : undefined;
      const body: ObjectiveCreate = {
        title: formTitle.trim(),
        type: formType,
        period_year: filterYear,
        description: formDesc.trim() || null,
        kpi_label: formKpiLabel.trim() || null,
        kpi_unit: formKpiUnit.trim() || null,
        kpi_target_value: formKpiTarget.trim() ? Number(formKpiTarget) : null,
        kpi_initial_value: formKpiInitial.trim() ? Number(formKpiInitial) : null,
        due_date: formDue || null,
        weight: weight != null && !Number.isNaN(weight) ? weight : null,
        notes: formNotes.trim() || null,
        milestones: formType === "quantitative" ? formMilestones : [],
        employee_id: scopeIndividual ? formEmployee || null : null,
        service_id: scopeIndividual ? null : formService || null,
      };
      const created = await createObjective(body);
      if (!scopeIndividual && declineAfterCreate && created.id) {
        await declineObjectiveToTeam(created.id);
      }
      return created;
    },
    onSuccess: () => {
      toast({ title: "Objectif créé" });
      setCreateOpen(false);
      resetCreateForm();
      invalidate();
    },
    onError: (e: unknown) => {
      const msg =
        typeof e === "object" && e && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail)
          : "";
      toast({ variant: "destructive", title: "Erreur", description: msg || "Création impossible." });
    },
  });

  const updateMutation = useMutation({
    mutationFn: async () => {
      if (!editing) return;
      return updateObjective(editing.id, {
        title: formTitle.trim(),
        type: formType,
        description: formDesc.trim() || null,
        kpi_label: formKpiLabel.trim() || null,
        kpi_unit: formKpiUnit.trim() || null,
        kpi_target_value: formKpiTarget.trim() ? Number(formKpiTarget) : null,
        kpi_initial_value: formKpiInitial.trim() ? Number(formKpiInitial) : null,
        due_date: formDue || null,
        weight: formWeight.trim() ? Number(formWeight) : null,
        notes: formNotes.trim() || null,
      });
    },
    onSuccess: () => {
      toast({ title: "Mis à jour" });
      setEditOpen(false);
      setEditing(null);
      invalidate();
    },
    onError: (e: unknown) => {
      const msg =
        typeof e === "object" && e && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail)
          : "";
      toast({ variant: "destructive", title: "Erreur", description: msg || "Échec." });
    },
  });

  const evaluateMutation = useMutation({
    mutationFn: async () => {
      if (!evalTarget) return;
      const rateNum = Number(evalRate);
      if (Number.isNaN(rateNum)) {
        throw new Error("Taux d’atteinte invalide.");
      }
      const body: ObjectiveEvaluate = {
        final_achievement_rate: rateNum,
        status: evalStatus,
        evaluation_comment: evalComment.trim() || null,
        evaluation_date: evalDate,
      };
      return evaluateObjective(evalTarget.id, body);
    },
    onSuccess: () => {
      toast({ title: "Évaluation enregistrée" });
      setEvalOpen(false);
      setEvalTarget(null);
      invalidate();
    },
    onError: (e: unknown) => {
      if (e instanceof Error && e.message) {
        toast({ variant: "destructive", title: "Erreur", description: e.message });
        return;
      }
      const msg =
        typeof e === "object" && e && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail)
          : "";
      toast({ variant: "destructive", title: "Erreur", description: msg || "Échec." });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (id: string) => cancelObjective(id),
    onSuccess: () => {
      toast({ title: "Objectif annulé" });
      setCancelTarget(null);
      invalidate();
    },
    onError: () => {
      toast({ variant: "destructive", title: "Erreur", description: "Annulation impossible." });
    },
  });

  const createServiceMutation = useMutation({
    mutationFn: () => createCompanyService(newServiceName.trim()),
    onSuccess: () => {
      toast({ title: "Service créé" });
      setNewServiceName("");
      void qc.invalidateQueries({ queryKey: ["objectives", "services"] });
    },
    onError: () => {
      toast({ variant: "destructive", title: "Erreur", description: "Création service impossible." });
    },
  });

  const checkinMutation = useMutation({
    mutationFn: async ({ id, note }: { id: string; note: string }) => {
      const body: CheckinCreate = {
        checkin_date: new Date().toISOString().slice(0, 10),
        progress_note: note,
      };
      return addCheckin(id, body);
    },
    onSuccess: () => {
      toast({ title: "Point de suivi ajouté" });
      invalidate();
    },
  });

  function resetCreateForm() {
    setScopeIndividual(true);
    setFormEmployee("");
    setFormService("");
    setFormTitle("");
    setFormType("qualitative");
    setFormDesc("");
    setFormKpiLabel("");
    setFormKpiUnit("");
    setFormKpiTarget("");
    setFormKpiInitial("");
    setFormDue("");
    setFormWeight("");
    setFormNotes("");
    setFormMilestones([]);
    setDeclineAfterCreate(false);
  }

  function openCreate() {
    resetCreateForm();
    setCreateOpen(true);
  }

  function openEdit(o: EmployeeObjective) {
    setEditing(o);
    setFormTitle(o.title);
    setFormType((o.type as ObjectiveType) || "qualitative");
    setFormDesc(o.description ?? "");
    setFormKpiLabel(o.kpi_label ?? "");
    setFormKpiUnit(o.kpi_unit ?? "");
    setFormKpiTarget(o.kpi_target_value != null ? String(o.kpi_target_value) : "");
    setFormKpiInitial(o.kpi_initial_value != null ? String(o.kpi_initial_value) : "");
    setFormDue(o.due_date?.slice(0, 10) ?? "");
    setFormWeight(o.weight != null ? String(o.weight) : "");
    setFormNotes(o.notes ?? "");
    setEditOpen(true);
  }

  function openEvaluate(o: EmployeeObjective) {
    setEvalTarget(o);
    setEvalRate(o.final_achievement_rate != null ? String(o.final_achievement_rate) : "");
    setEvalStatus("achieved");
    setEvalComment("");
    setEvalDate(new Date().toISOString().slice(0, 10));
    setEvalOpen(true);
  }

  function addMilestoneRow() {
    setFormMilestones((prev) => [
      ...prev,
      { milestone_date: new Date().toISOString().slice(0, 10), expected_value: 0 },
    ]);
  }

  const chartData = useMemo(() => {
    const o = detailQuery.data;
    if (!o || o.type !== "quantitative") return [];
    return [...(o.milestones || [])]
      .sort((a, b) => a.milestone_date.localeCompare(b.milestone_date))
      .map((m) => ({
        date: m.milestone_date.slice(0, 10),
        expected: m.expected_value,
        actual: m.actual_value,
      }));
  }, [detailQuery.data]);

  const loading = objectivesQuery.isLoading;
  const err = objectivesQuery.isError;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {showRhActions && achievementQuery.data?.rate != null ? (
          <p className="text-sm text-muted-foreground">
            Taux d&apos;atteinte moyen pondéré ({filterYear}) :{" "}
            <strong>{achievementQuery.data.rate.toFixed(1)} %</strong>
          </p>
        ) : (
          <span />
        )}
        <div className="flex flex-wrap gap-2">
          {showRhActions ? (
            <Button variant={reportingMode ? "secondary" : "outline"} onClick={() => setReportingMode(!reportingMode)}>
              <BarChart3 className="mr-2 h-4 w-4" />
              {reportingMode ? "Vue liste" : "Vue reporting"}
            </Button>
          ) : null}
          {showRhActions ? (
            <Button onClick={openCreate}>
              <Plus className="mr-2 h-4 w-4" />
              Définir des objectifs
            </Button>
          ) : null}
        </div>
      </div>

      {showRhActions ? (
        <div className="flex flex-wrap gap-3 md:items-end">
          <div className="grid gap-1.5 min-w-[160px]">
            <Label>Collaborateur</Label>
            <Select value={filterEmployee} onValueChange={setFilterEmployee}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous</SelectItem>
                {(employeesQuery.data ?? []).map((e) => (
                  <SelectItem key={e.id} value={e.id}>
                    {e.first_name} {e.last_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5 min-w-[160px]">
            <Label>Service</Label>
            <Select value={filterService} onValueChange={setFilterService}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous</SelectItem>
                {(servicesQuery.data ?? []).map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    {s.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5 w-[100px]">
            <Label>Année</Label>
            <Input
              type="number"
              value={filterYear}
              onChange={(e) => setFilterYear(Number(e.target.value) || defaultYear)}
            />
          </div>
          <div className="grid gap-1.5 min-w-[140px]">
            <Label>Type</Label>
            <Select value={filterType} onValueChange={setFilterType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous</SelectItem>
                <SelectItem value="quantitative">Quantitatif</SelectItem>
                <SelectItem value="qualitative">Qualitatif</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1.5 min-w-[160px]">
            <Label>Statut</Label>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous</SelectItem>
                <SelectItem value="draft">Brouillon</SelectItem>
                <SelectItem value="active">Actif</SelectItem>
                <SelectItem value="achieved">Atteint</SelectItem>
                <SelectItem value="partially_achieved">Partiellement atteint</SelectItem>
                <SelectItem value="not_achieved">Non atteint</SelectItem>
                <SelectItem value="cancelled">Annulé</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-center gap-2 pb-1">
            <Switch checked={includeInactive} onCheckedChange={(c) => setIncludeInactive(Boolean(c))} id="inc" />
            <Label htmlFor="inc">Inclure inactifs</Label>
          </div>
        </div>
      ) : null}

      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : err ? (
        <p className="text-sm text-destructive">Impossible de charger les objectifs.</p>
      ) : reportingMode && showRhActions ? (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="sticky left-0 z-10 bg-background min-w-[160px]">Collaborateur</TableHead>
                {matrix.objIds.map((oid) => {
                  const o = matrix.rows.find((r) => r.id === oid);
                  return (
                    <TableHead key={oid} className="min-w-[120px] max-w-[180px] whitespace-normal text-xs">
                      {o?.title ?? oid.slice(0, 8)}
                    </TableHead>
                  );
                })}
              </TableRow>
            </TableHeader>
            <TableBody>
              {matrix.empIds.map((eid) => (
                <TableRow key={eid}>
                  <TableCell className="sticky left-0 z-10 bg-background font-medium">
                    {matrix.empName(eid)}
                  </TableCell>
                  {matrix.objIds.map((oid) => {
                    const cell = matrix.byEmpObj.get(`${eid}::${oid}`);
                    const rate = cell?.final_achievement_rate;
                    return (
                      <TableCell key={oid} className="p-0">
                        <div
                          className={cn(
                            "m-0.5 flex min-h-[40px] items-center justify-center rounded px-1 text-xs font-semibold",
                            rateCellClass(rate ?? null),
                          )}
                        >
                          {rate != null ? `${rate.toFixed(0)}%` : "—"}
                        </div>
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {matrix.empIds.length === 0 ? (
            <p className="p-4 text-center text-sm text-muted-foreground">Aucune donnée pour cette matrice.</p>
          ) : null}
        </div>
      ) : filteredRows.length === 0 ? (
        <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
          Aucun objectif pour ces critères.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Collaborateur</TableHead>
                <TableHead>Service</TableHead>
                <TableHead>Intitulé</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Valeur cible</TableHead>
                <TableHead>Valeur actuelle</TableHead>
                <TableHead>Taux</TableHead>
                <TableHead>Échéance</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredRows.map((o) => (
                <TableRow key={o.id}>
                  <TableCell>{o.employee_name ?? "—"}</TableCell>
                  <TableCell>{o.service_name ?? "—"}</TableCell>
                  <TableCell className="max-w-[200px] font-medium">{o.title}</TableCell>
                  <TableCell>{o.type === "quantitative" ? "Quantitatif" : "Qualitatif"}</TableCell>
                  <TableCell>
                    {o.kpi_target_value != null ? `${o.kpi_target_value}${o.kpi_unit ? ` ${o.kpi_unit}` : ""}` : "—"}
                  </TableCell>
                  <TableCell>{currentKpiValue(o)}</TableCell>
                  <TableCell>
                    {o.final_achievement_rate != null ? `${o.final_achievement_rate.toFixed(0)}%` : "—"}
                  </TableCell>
                  <TableCell>{o.due_date?.slice(0, 10) ?? "—"}</TableCell>
                  <TableCell>{statusBadge(String(o.status))}</TableCell>
                  <TableCell className="text-right space-x-1 whitespace-nowrap">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setDetailId(o.id);
                        setDetailOpen(true);
                      }}
                    >
                      <Eye className="mr-1 h-3.5 w-3.5" />
                      Détail
                    </Button>
                    {showRhActions ? (
                      <>
                        <Button size="sm" variant="outline" onClick={() => openEdit(o)}>
                          <Pencil className="mr-1 h-3.5 w-3.5" />
                          Modifier
                        </Button>
                        {(o.status === "active" || o.status === "partially_achieved") && (
                          <Button size="sm" variant="outline" onClick={() => openEvaluate(o)}>
                            <Target className="mr-1 h-3.5 w-3.5" />
                            Évaluer
                          </Button>
                        )}
                        <Button size="sm" variant="outline" onClick={() => setCancelTarget(o)}>
                          <Trash2 className="mr-1 h-3.5 w-3.5" />
                          Annuler
                        </Button>
                      </>
                    ) : null}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <Sheet open={detailOpen} onOpenChange={setDetailOpen}>
        <SheetContent className="w-full sm:max-w-xl overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{detailQuery.data?.title ?? "Détail objectif"}</SheetTitle>
          </SheetHeader>
          {detailQuery.isLoading ? (
            <Loader2 className="my-8 h-8 w-8 animate-spin text-muted-foreground" />
          ) : detailQuery.data ? (
            <div className="space-y-4 py-4 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <span className="text-muted-foreground">Statut</span>
                <span>{statusBadge(String(detailQuery.data.status))}</span>
                <span className="text-muted-foreground">Collaborateur</span>
                <span>{detailQuery.data.employee_name ?? "—"}</span>
                <span className="text-muted-foreground">Service</span>
                <span>{detailQuery.data.service_name ?? "—"}</span>
                <span className="text-muted-foreground">Pondération</span>
                <span>{detailQuery.data.weight ?? "—"}</span>
              </div>
              {detailQuery.data.type === "quantitative" && chartData.length > 0 ? (
                <div className="h-64 w-full pt-2">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                      <YAxis tick={{ fontSize: 11 }} />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="expected"
                        name="Attendu"
                        stroke="#94a3b8"
                        strokeDasharray="5 5"
                        dot={false}
                      />
                      <Line
                        type="monotone"
                        dataKey="actual"
                        name="Réel"
                        stroke="#2563eb"
                        connectNulls
                        dot={(props: { cx?: number; cy?: number; payload?: { expected?: number; actual?: number } }) => {
                          const { cx = 0, cy = 0, payload } = props;
                          const a = payload?.actual;
                          const e = payload?.expected;
                          if (a != null && e != null && a < e) {
                            return <circle cx={cx} cy={cy} r={5} fill="#f97316" />;
                          }
                          return <circle cx={cx} cy={cy} r={3} fill="#2563eb" />;
                        }}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              ) : null}
              {detailQuery.data.type === "qualitative" ? (
                <div>
                  <p className="font-medium mb-2">Points de suivi</p>
                  <ul className="space-y-2 border rounded-md p-3 max-h-60 overflow-y-auto">
                    {[...(detailQuery.data.checkins || [])]
                      .sort((a, b) => b.checkin_date.localeCompare(a.checkin_date))
                      .map((c) => (
                        <li key={c.id} className="border-b pb-2 last:border-0">
                          <span className="text-xs text-muted-foreground">{c.checkin_date}</span>
                          <p>{c.progress_note}</p>
                        </li>
                      ))}
                  </ul>
                  {showRhActions ? (
                    <AddCheckinForm
                      onAdd={(note) => checkinMutation.mutate({ id: detailQuery.data.id, note })}
                      busy={checkinMutation.isPending}
                    />
                  ) : null}
                </div>
              ) : null}
              <div>
                <p className="font-medium mb-2">Jalons</p>
                <ul className="space-y-1 text-xs">
                  {[...(detailQuery.data.milestones || [])]
                    .sort((a, b) => a.milestone_date.localeCompare(b.milestone_date))
                    .map((m) => (
                      <li key={m.id}>
                        {m.milestone_date} — attendu {m.expected_value}, réel {m.actual_value ?? "—"}
                      </li>
                    ))}
                </ul>
              </div>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>

      <Sheet open={createOpen} onOpenChange={setCreateOpen}>
        <SheetContent className="sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Nouvel objectif</SheetTitle>
          </SheetHeader>
          <div className="grid gap-3 py-4">
            <div className="flex items-center justify-between rounded-md border p-3">
              <span className="text-sm">Individuel / Équipe</span>
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-muted-foreground" />
                <Switch checked={!scopeIndividual} onCheckedChange={(c) => setScopeIndividual(!c)} />
              </div>
            </div>
            {scopeIndividual ? (
              <div className="grid gap-2">
                <Label>Employé</Label>
                <Select value={formEmployee} onValueChange={setFormEmployee}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choisir…" />
                  </SelectTrigger>
                  <SelectContent>
                    {(employeesQuery.data ?? []).map((e) => (
                      <SelectItem key={e.id} value={e.id}>
                        {e.first_name} {e.last_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : (
              <>
                <div className="grid gap-2">
                  <Label>Service</Label>
                  <Select value={formService} onValueChange={setFormService}>
                    <SelectTrigger>
                      <SelectValue placeholder="Choisir…" />
                    </SelectTrigger>
                    <SelectContent>
                      {(servicesQuery.data ?? []).map((s) => (
                        <SelectItem key={s.id} value={s.id}>
                          {s.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="Nouveau service"
                    value={newServiceName}
                    onChange={(e) => setNewServiceName(e.target.value)}
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={!newServiceName.trim() || createServiceMutation.isPending}
                    onClick={() => createServiceMutation.mutate()}
                  >
                    Créer
                  </Button>
                </div>
                <div className="flex items-center gap-2">
                  <Switch checked={declineAfterCreate} onCheckedChange={(c) => setDeclineAfterCreate(Boolean(c))} id="dec" />
                  <Label htmlFor="dec">Décliner sur toute l&apos;équipe après création</Label>
                </div>
              </>
            )}
            <div className="grid gap-2">
              <Label>Intitulé</Label>
              <Input value={formTitle} onChange={(e) => setFormTitle(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Type</Label>
              <Select value={formType} onValueChange={(v) => setFormType(v as ObjectiveType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="qualitative">Qualitatif</SelectItem>
                  <SelectItem value="quantitative">Quantitatif</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {formType === "quantitative" ? (
              <>
                <div className="grid gap-2">
                  <Label>Libellé KPI</Label>
                  <Input value={formKpiLabel} onChange={(e) => setFormKpiLabel(e.target.value)} />
                </div>
                <div className="grid gap-2">
                  <Label>Unité</Label>
                  <Input value={formKpiUnit} onChange={(e) => setFormKpiUnit(e.target.value)} />
                </div>
                <div className="grid gap-2">
                  <Label>Valeur cible</Label>
                  <Input type="number" value={formKpiTarget} onChange={(e) => setFormKpiTarget(e.target.value)} />
                </div>
                <div className="grid gap-2">
                  <Label>Valeur initiale</Label>
                  <Input type="number" value={formKpiInitial} onChange={(e) => setFormKpiInitial(e.target.value)} />
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label>Jalons</Label>
                    <Button type="button" size="sm" variant="outline" onClick={addMilestoneRow}>
                      Ajouter un jalon
                    </Button>
                  </div>
                  {formMilestones.map((m, idx) => (
                    <div key={idx} className="flex gap-2 items-end">
                      <div className="flex-1 grid gap-1">
                        <Label className="text-xs">Date</Label>
                        <Input
                          type="date"
                          value={m.milestone_date}
                          onChange={(e) => {
                            const next = [...formMilestones];
                            next[idx] = { ...next[idx], milestone_date: e.target.value };
                            setFormMilestones(next);
                          }}
                        />
                      </div>
                      <div className="w-28 grid gap-1">
                        <Label className="text-xs">Attendu</Label>
                        <Input
                          type="number"
                          value={String(m.expected_value)}
                          onChange={(e) => {
                            const next = [...formMilestones];
                            next[idx] = { ...next[idx], expected_value: Number(e.target.value) || 0 };
                            setFormMilestones(next);
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="grid gap-2">
                <Label>Description</Label>
                <Textarea value={formDesc} onChange={(e) => setFormDesc(e.target.value)} rows={3} />
              </div>
            )}
            <div className="grid gap-2">
              <Label>Échéance</Label>
              <Input type="date" value={formDue} onChange={(e) => setFormDue(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Pondération (0–100)</Label>
              <Input type="number" value={formWeight} onChange={(e) => setFormWeight(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Notes</Label>
              <Textarea value={formNotes} onChange={(e) => setFormNotes(e.target.value)} rows={2} />
            </div>
          </div>
          <SheetFooter>
            <Button disabled={createMutation.isPending} onClick={() => createMutation.mutate()}>
              {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Enregistrer"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Sheet open={editOpen} onOpenChange={setEditOpen}>
        <SheetContent className="sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Modifier l&apos;objectif</SheetTitle>
          </SheetHeader>
          <div className="grid gap-3 py-4">
            <div className="grid gap-2">
              <Label>Intitulé</Label>
              <Input value={formTitle} onChange={(e) => setFormTitle(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Type</Label>
              <Select value={formType} onValueChange={(v) => setFormType(v as ObjectiveType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="qualitative">Qualitatif</SelectItem>
                  <SelectItem value="quantitative">Quantitatif</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {formType === "qualitative" ? (
              <div className="grid gap-2">
                <Label>Description</Label>
                <Textarea value={formDesc} onChange={(e) => setFormDesc(e.target.value)} rows={3} />
              </div>
            ) : (
              <>
                <div className="grid gap-2">
                  <Label>Libellé KPI</Label>
                  <Input value={formKpiLabel} onChange={(e) => setFormKpiLabel(e.target.value)} />
                </div>
                <div className="grid gap-2">
                  <Label>Unité</Label>
                  <Input value={formKpiUnit} onChange={(e) => setFormKpiUnit(e.target.value)} />
                </div>
                <div className="grid gap-2">
                  <Label>Valeur cible</Label>
                  <Input type="number" value={formKpiTarget} onChange={(e) => setFormKpiTarget(e.target.value)} />
                </div>
                <div className="grid gap-2">
                  <Label>Valeur initiale</Label>
                  <Input type="number" value={formKpiInitial} onChange={(e) => setFormKpiInitial(e.target.value)} />
                </div>
              </>
            )}
            <div className="grid gap-2">
              <Label>Échéance</Label>
              <Input type="date" value={formDue} onChange={(e) => setFormDue(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Pondération</Label>
              <Input type="number" value={formWeight} onChange={(e) => setFormWeight(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Notes</Label>
              <Textarea value={formNotes} onChange={(e) => setFormNotes(e.target.value)} rows={2} />
            </div>
          </div>
          <SheetFooter>
            <Button disabled={updateMutation.isPending} onClick={() => updateMutation.mutate()}>
              {updateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Enregistrer"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Dialog open={evalOpen} onOpenChange={setEvalOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Évaluer l&apos;objectif</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>Taux d&apos;atteinte (%)</Label>
              <Input value={evalRate} onChange={(e) => setEvalRate(e.target.value)} type="number" />
            </div>
            <div className="grid gap-2">
              <Label>Statut après évaluation</Label>
              <Select value={evalStatus} onValueChange={(v) => setEvalStatus(v as ObjectiveStatus)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="achieved">Atteint</SelectItem>
                  <SelectItem value="partially_achieved">Partiellement atteint</SelectItem>
                  <SelectItem value="not_achieved">Non atteint</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Date d&apos;évaluation</Label>
              <Input type="date" value={evalDate} onChange={(e) => setEvalDate(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Commentaire</Label>
              <Textarea value={evalComment} onChange={(e) => setEvalComment(e.target.value)} rows={3} />
            </div>
          </div>
          <DialogFooter>
            <Button disabled={evaluateMutation.isPending} onClick={() => evaluateMutation.mutate()}>
              {evaluateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Valider"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!cancelTarget} onOpenChange={() => setCancelTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Annuler cet objectif ?</AlertDialogTitle>
            <AlertDialogDescription>Le statut passera à « Annulé ».</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Retour</AlertDialogCancel>
            <AlertDialogAction onClick={() => cancelTarget && cancelMutation.mutate(cancelTarget.id)}>
              Confirmer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function AddCheckinForm({
  onAdd,
  busy,
}: {
  onAdd: (note: string) => void;
  busy: boolean;
}) {
  const [note, setNote] = useState("");
  return (
    <div className="mt-3 flex gap-2">
      <Textarea
        placeholder="Nouveau point de suivi…"
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        className="flex-1"
      />
      <Button
        type="button"
        disabled={busy || !note.trim()}
        onClick={() => {
          onAdd(note.trim());
          setNote("");
        }}
      >
        Ajouter
      </Button>
    </div>
  );
}
