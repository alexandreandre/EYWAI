// Page RH : Suivi médical des salariés (obligations VIP, SIR, reprise, mi-carrière)

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import {
  Loader2,
  PlusCircle,
  FileDown,
  Bell,
  RefreshCw,
  MoreHorizontal,
  ArrowUpDown,
  Search,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import {
  formatMedicalDate as formatDate,
  STATUS_LABELS,
  statusBadgeVariant,
  VISIT_TYPE_LABELS,
  formatTriggerType,
  formatPriorityLabel,
  getDueDateRelativeLabel,
  isObligationOverdue,
  isDueWithinDays,
  sortObligationsForDisplay,
  countMedicalObligations,
  obligationMessage,
} from "@/lib/medicalFollowUpLabels";

const ALL_FILTER = "__all__";

type MedTab = "pilotage" | "conformite";
type ClientKpiFilter = "overdue" | "upcoming30" | null;
type SortColumn = "due_date" | "employee" | "status";
type SortDir = "asc" | "desc";

function globalComplianceTextClass(rate: number): string {
  if (rate >= 80) return "text-foreground";
  if (rate >= 60) return "text-muted-foreground";
  return "text-destructive";
}

function globalComplianceBarClass(rate: number): string {
  if (rate >= 80) return "bg-primary";
  if (rate >= 60) return "bg-muted-foreground/60";
  return "bg-destructive";
}

function visitTypeBarClass(rate: number): string {
  if (rate >= 80) return "bg-primary/80";
  if (rate >= 60) return "bg-muted-foreground/50";
  return "bg-destructive";
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

function formatLastAction(o: ObligationListItem): string {
  if (o.status === "realisee" && o.completed_date) {
    return `Réal. le ${formatDate(o.completed_date)}`;
  }
  if (o.planned_date) {
    return `Plan. le ${formatDate(o.planned_date)}`;
  }
  return "—";
}

const STATUS_SORT: Record<string, number> = {
  a_faire: 0,
  planifiee: 1,
  realisee: 2,
  annulee: 3,
};

function sortObligationsByColumn(
  list: ObligationListItem[],
  column: SortColumn,
  dir: SortDir
): ObligationListItem[] {
  const sorted = [...list];
  const mul = dir === "asc" ? 1 : -1;
  sorted.sort((a, b) => {
    if (column === "due_date") {
      return mul * (a.due_date ?? "").localeCompare(b.due_date ?? "");
    }
    if (column === "employee") {
      const na = `${a.employee_last_name ?? ""} ${a.employee_first_name ?? ""}`.trim();
      const nb = `${b.employee_last_name ?? ""} ${b.employee_first_name ?? ""}`.trim();
      return mul * na.localeCompare(nb, "fr");
    }
    const sa = STATUS_SORT[a.status] ?? 9;
    const sb = STATUS_SORT[b.status] ?? 9;
    return mul * (sa - sb);
  });
  return sorted;
}

function exportComplianceReportToCsv(r: ComplianceReport): void {
  const esc = (c: string) => `"${String(c).replace(/"/g, '""')}"`;
  const lines: string[] = [];
  const fileDate = new Date().toISOString().slice(0, 10);

  lines.push(esc("Section 1 — RAPPORT DE CONFORMITÉ MÉDICAL"));
  lines.push(esc(`Généré le : ${formatComplianceGeneratedAtFrench(r.generated_at)}`));
  lines.push([esc("Entreprise :"), esc("")].join(";"));
  lines.push("");

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

  lines.push(esc("Section 4 — SALARIÉS EN RETARD"));
  lines.push(
    ["Salarié", "Nb obligations en retard", "Date la plus urgente", "Types de visites"].map(esc).join(";")
  );
  for (const e of r.employees_overdue) {
    const typesFr = e.visit_types.map((vt) => VISIT_TYPE_LABELS[vt] ?? vt).join(", ");
    lines.push(
      [e.employee_name, String(e.obligations_overdue), formatDate(e.most_urgent_due_date), typesFr]
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

function exportObligationsToCsv(rows: ObligationListItem[]): void {
  const headers = [
    "Salarié",
    "Type de visite",
    "Déclencheur",
    "Date limite",
    "Priorité",
    "Statut",
    "Justification",
    "Date planifiée",
    "Date réalisée",
  ];
  const csvRows = rows.map((o) => [
    `${o.employee_first_name ?? ""} ${o.employee_last_name ?? ""}`.trim(),
    VISIT_TYPE_LABELS[o.visit_type] ?? o.visit_type,
    formatTriggerType(o.trigger_type),
    o.due_date,
    formatPriorityLabel(o.priority),
    STATUS_LABELS[o.status] ?? o.status,
    o.justification ?? "",
    o.planned_date ?? "",
    o.completed_date ?? "",
  ]);
  const csv = [
    headers.join(";"),
    ...csvRows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(";")),
  ].join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `suivi-medical-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

interface MedicalCompliancePanelsProps {
  cr: ComplianceReport;
  onVisitTypeClick?: (visitType: string) => void;
  onEmployeeProfileClick?: (employeeId: string) => void;
  onViewEmployeeObligations?: (employeeId: string) => void;
}

function MedicalCompliancePanels({
  cr,
  onVisitTypeClick,
  onEmployeeProfileClick,
  onViewEmployeeObligations,
}: MedicalCompliancePanelsProps) {
  const rate = cr.compliance_rate;

  const topOverdueVisitType = useMemo(() => {
    if (!cr.by_visit_type.length) return null;
    return [...cr.by_visit_type].sort((a, b) => b.overdue - a.overdue || a.compliance_rate - b.compliance_rate)[0];
  }, [cr.by_visit_type]);

  const visitTypesSorted = useMemo(
    () => [...cr.by_visit_type].sort((a, b) => a.compliance_rate - b.compliance_rate),
    [cr.by_visit_type]
  );

  return (
    <>
      <div>
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">Synthèse</h3>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Taux de conformité
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <p className={cn("text-3xl font-semibold tabular-nums", globalComplianceTextClass(rate))}>
                {rate.toFixed(1)} %
              </p>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={cn("h-full rounded-full transition-all", globalComplianceBarClass(rate))}
                  style={{ width: `${Math.min(100, Math.max(0, rate))}%` }}
                />
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">Couverture</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-semibold tabular-nums">
                {cr.compliant}
                <span className="text-base font-normal text-muted-foreground">
                  {" "}
                  / {cr.total_obligations}
                </span>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {cr.total_employees} salarié{cr.total_employees > 1 ? "s" : ""} concerné
                {cr.total_employees > 1 ? "s" : ""}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Type le plus en retard
              </CardTitle>
            </CardHeader>
            <CardContent>
              {topOverdueVisitType && topOverdueVisitType.overdue > 0 ? (
                <>
                  <p className="text-sm font-medium leading-snug">{topOverdueVisitType.label}</p>
                  <p className="mt-1 text-2xl font-semibold tabular-nums text-destructive">
                    {topOverdueVisitType.overdue}
                    <span className="text-sm font-normal text-muted-foreground"> en retard</span>
                  </p>
                </>
              ) : (
                <p className="text-sm text-muted-foreground">Aucun retard par type.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">Par type de visite</h3>
        <Card>
          <CardContent className="pt-4">
            <div className="w-full overflow-x-auto">
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
                  {visitTypesSorted.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={5} className="py-8 text-center text-muted-foreground">
                        Aucune obligation par type.
                      </TableCell>
                    </TableRow>
                  ) : (
                    visitTypesSorted.map((v) => (
                      <TableRow
                        key={v.visit_type}
                        className={onVisitTypeClick ? "cursor-pointer hover:bg-muted/50" : undefined}
                        onClick={() => onVisitTypeClick?.(v.visit_type)}
                      >
                        <TableCell className="font-medium">{v.label}</TableCell>
                        <TableCell className="text-right tabular-nums">{v.total}</TableCell>
                        <TableCell className="text-right tabular-nums">{v.compliant}</TableCell>
                        <TableCell className="text-right tabular-nums">{v.overdue}</TableCell>
                        <TableCell>
                          <div className="flex min-w-0 items-center gap-2">
                            <span className="w-12 text-sm tabular-nums">
                              {v.compliance_rate.toFixed(0)}%
                            </span>
                            <div className="h-2 max-w-[120px] flex-1 overflow-hidden rounded-full bg-muted">
                              <div
                                className={cn("h-full rounded-full", visitTypeBarClass(v.compliance_rate))}
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
            </div>
          </CardContent>
        </Card>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-medium text-muted-foreground">Salariés en retard</h3>
        <Card>
          <CardContent className="pt-4">
            {cr.employees_overdue.length === 0 ? (
              <p className="py-10 text-center text-sm text-muted-foreground">
                Aucun salarié en retard.
              </p>
            ) : (
              <div className="w-full overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Salarié</TableHead>
                      <TableHead className="text-right">En retard</TableHead>
                      <TableHead>Plus urgent</TableHead>
                      <TableHead>Types de visites</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {cr.employees_overdue.map((e) => (
                      <TableRow key={e.employee_id}>
                        <TableCell className="font-medium">
                          {onEmployeeProfileClick ? (
                            <Link
                              to={`/employees/${e.employee_id}?tab=suivi_medical`}
                              className="text-primary hover:underline"
                              onClick={(ev) => ev.stopPropagation()}
                            >
                              {e.employee_name}
                            </Link>
                          ) : (
                            e.employee_name
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <Badge variant="destructive" className="tabular-nums">
                            {e.obligations_overdue}
                          </Badge>
                        </TableCell>
                        <TableCell className="font-medium tabular-nums text-destructive">
                          {formatDate(e.most_urgent_due_date)}
                        </TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {e.visit_types.map((vt) => VISIT_TYPE_LABELS[vt] ?? vt).join(", ")}
                        </TableCell>
                        <TableCell className="text-right">
                          {onViewEmployeeObligations ? (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-8 text-xs"
                              onClick={() => onViewEmployeeObligations(e.employee_id)}
                            >
                              Voir les obligations
                            </Button>
                          ) : null}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

function SortableHead({
  label,
  column,
  activeColumn,
  dir,
  onSort,
  className,
}: {
  label: string;
  column: SortColumn;
  activeColumn: SortColumn;
  dir: SortDir;
  onSort: (col: SortColumn) => void;
  className?: string;
}) {
  const active = activeColumn === column;
  return (
    <TableHead className={className}>
      <button
        type="button"
        className="inline-flex items-center gap-1 font-medium hover:text-foreground"
        onClick={() => onSort(column)}
      >
        {label}
        <ArrowUpDown className={cn("h-3.5 w-3.5", active ? "opacity-100" : "opacity-40")} />
        {active ? (
          <span className="sr-only">{dir === "asc" ? "croissant" : "décroissant"}</span>
        ) : null}
      </button>
    </TableHead>
  );
}

export default function MedicalFollowUp() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const employeeFromUrl = searchParams.get("employee");
  const visitTypeFromUrl = searchParams.get("visit_type");
  const statusFromUrl = searchParams.get("status");
  const tabFromUrl = searchParams.get("tab");

  const [obligations, setObligations] = useState<ObligationListItem[]>([]);
  const [kpis, setKpis] = useState<KPIs | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterEmployee, setFilterEmployee] = useState<string>(
    employeeFromUrl && employeeFromUrl.length > 0 ? employeeFromUrl : ALL_FILTER
  );
  const [filterVisitType, setFilterVisitType] = useState<string>(
    visitTypeFromUrl && visitTypeFromUrl.length > 0 ? visitTypeFromUrl : ALL_FILTER
  );
  const [filterStatus, setFilterStatus] = useState<string>(
    statusFromUrl && statusFromUrl.length > 0 ? statusFromUrl : ALL_FILTER
  );
  const [employees, setEmployees] = useState<{ id: string; first_name: string; last_name: string }[]>([]);
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [clientKpiFilter, setClientKpiFilter] = useState<ClientKpiFilter>(null);
  const [sortColumn, setSortColumn] = useState<SortColumn>("due_date");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [userSorted, setUserSorted] = useState(false);

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
  const [medTab, setMedTab] = useState<MedTab>(
    tabFromUrl === "conformite" ? "conformite" : "pilotage"
  );

  const syncUrlParams = useCallback(
    (patch: {
      employee?: string;
      visit_type?: string;
      status?: string;
      tab?: MedTab;
    }) => {
      const next = new URLSearchParams(searchParams);
      const emp = patch.employee ?? filterEmployee;
      const vt = patch.visit_type ?? filterVisitType;
      const st = patch.status ?? filterStatus;
      const tab = patch.tab ?? medTab;

      if (emp && emp !== ALL_FILTER) next.set("employee", emp);
      else next.delete("employee");
      if (vt && vt !== ALL_FILTER) next.set("visit_type", vt);
      else next.delete("visit_type");
      if (st && st !== ALL_FILTER) next.set("status", st);
      else next.delete("status");
      if (tab === "conformite") next.set("tab", "conformite");
      else next.delete("tab");

      setSearchParams(next, { replace: true });
    },
    [searchParams, filterEmployee, filterVisitType, filterStatus, medTab, setSearchParams]
  );

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
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: unknown } }; message?: string };
      const raw = err.response?.data?.detail;
      const msg =
        typeof raw === "string"
          ? raw
          : Array.isArray(raw) && raw[0] && typeof raw[0] === "object" && "msg" in raw[0]
            ? String((raw[0] as { msg: string }).msg)
            : err.message ?? "Erreur chargement";
      toast({ title: "Erreur", description: String(msg), variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [filterEmployee, filterVisitType, filterStatus, toast, queryClient]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (employeeFromUrl && employeeFromUrl.length > 0) {
      setFilterEmployee(employeeFromUrl);
    }
  }, [employeeFromUrl]);

  useEffect(() => {
    if (visitTypeFromUrl && visitTypeFromUrl.length > 0) {
      setFilterVisitType(visitTypeFromUrl);
    }
  }, [visitTypeFromUrl]);

  useEffect(() => {
    if (statusFromUrl && statusFromUrl.length > 0) {
      setFilterStatus(statusFromUrl);
    }
  }, [statusFromUrl]);

  useEffect(() => {
    const t = window.setTimeout(() => setSearchQuery(searchInput.trim().toLowerCase()), 200);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    apiClient
      .get("/api/employees")
      .then((r) => {
        const list = (r.data as { id: string; first_name: string; last_name: string }[]) ?? [];
        setEmployees(
          list.map((e) => ({ id: e.id, first_name: e.first_name, last_name: e.last_name }))
        );
      })
      .catch(() => {});
  }, []);

  const complianceQuery = useQuery({
    queryKey: ["medical-follow-up", "compliance-report"],
    queryFn: getComplianceReport,
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

  const upcoming7Count = useMemo(() => {
    if (complianceQuery.data?.upcoming_7 != null) {
      return complianceQuery.data.upcoming_7;
    }
    return (upcoming30Query.data ?? []).filter((o) => isDueWithinDays(o.due_date, 7)).length;
  }, [complianceQuery.data?.upcoming_7, upcoming30Query.data]);

  const obligationCounts = useMemo(() => countMedicalObligations(obligations), [obligations]);

  const displayedObligations = useMemo(() => {
    let list = [...obligations];

    if (searchQuery) {
      list = list.filter((o) => {
        const name = `${o.employee_first_name ?? ""} ${o.employee_last_name ?? ""}`
          .trim()
          .toLowerCase();
        return name.includes(searchQuery);
      });
    }

    if (clientKpiFilter === "overdue") {
      list = list.filter((o) => isObligationOverdue(o));
    } else if (clientKpiFilter === "upcoming30") {
      list = list.filter(
        (o) =>
          o.status !== "realisee" &&
          o.status !== "annulee" &&
          !isObligationOverdue(o) &&
          isDueWithinDays(o.due_date, 30)
      );
    }

    if (userSorted) {
      return sortObligationsByColumn(list, sortColumn, sortDir);
    }
    return sortObligationsForDisplay(list);
  }, [obligations, searchQuery, clientKpiFilter, userSorted, sortColumn, sortDir]);

  const hasActiveFilters =
    filterEmployee !== ALL_FILTER ||
    filterVisitType !== ALL_FILTER ||
    filterStatus !== ALL_FILTER ||
    searchQuery.length > 0 ||
    clientKpiFilter !== null;

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
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      toast({
        title: "Erreur",
        description: err.response?.data?.detail ?? err.message ?? "Envoi impossible",
        variant: "destructive",
      });
    },
  });

  const resetFilters = () => {
    setFilterEmployee(ALL_FILTER);
    setFilterVisitType(ALL_FILTER);
    setFilterStatus(ALL_FILTER);
    setSearchInput("");
    setSearchQuery("");
    setClientKpiFilter(null);
    syncUrlParams({ employee: ALL_FILTER, visit_type: ALL_FILTER, status: ALL_FILTER });
  };

  const applyFilterEmployee = (id: string) => {
    setFilterEmployee(id);
    syncUrlParams({ employee: id });
  };

  const applyFilterVisitType = (vt: string) => {
    setFilterVisitType(vt);
    syncUrlParams({ visit_type: vt });
  };

  const applyFilterStatus = (st: string) => {
    setFilterStatus(st);
    syncUrlParams({ status: st });
  };

  const goToPilotageWithVisitType = (visitType: string) => {
    setMedTab("pilotage");
    setClientKpiFilter(null);
    applyFilterVisitType(visitType);
    syncUrlParams({ tab: "pilotage", visit_type: visitType });
  };

  const goToPilotageWithEmployee = (employeeId: string) => {
    setMedTab("pilotage");
    setClientKpiFilter(null);
    applyFilterEmployee(employeeId);
    syncUrlParams({ tab: "pilotage", employee: employeeId });
  };

  const handleKpiOverdueClick = () => {
    setClientKpiFilter("overdue");
    setFilterStatus(ALL_FILTER);
    syncUrlParams({ status: ALL_FILTER });
  };

  const handleKpiUpcomingClick = () => {
    setClientKpiFilter("upcoming30");
    setFilterStatus(ALL_FILTER);
    syncUrlParams({ status: ALL_FILTER });
  };

  const handleKpiCompletedClick = () => {
    setClientKpiFilter(null);
    applyFilterStatus("realisee");
  };

  const handleSort = (col: SortColumn) => {
    setUserSorted(true);
    if (sortColumn === col) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(col);
      setSortDir("asc");
    }
  };

  const openOnDemandDialog = () => {
    if (filterEmployee !== ALL_FILTER) {
      setOnDemandEmployee(filterEmployee);
    }
    setOnDemandOpen(true);
  };

  const handleMarkPlanified = async () => {
    if (!planifiedModal) return;
    setSaving(true);
    try {
      await markPlanified(planifiedModal.id, {
        planned_date: planifiedDate,
        justification: planifiedComment || undefined,
      });
      toast({ title: "Succès", description: "Obligation marquée comme planifiée." });
      setPlanifiedModal(null);
      setPlanifiedDate("");
      setPlanifiedComment("");
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      toast({
        title: "Erreur",
        description: err.response?.data?.detail ?? err.message,
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleMarkCompleted = async () => {
    if (!completedModal) return;
    setSaving(true);
    try {
      await markCompleted(completedModal.id, {
        completed_date: completedDate,
        justification: completedComment || undefined,
      });
      toast({ title: "Succès", description: "Obligation marquée comme réalisée." });
      setCompletedModal(null);
      setCompletedDate("");
      setCompletedComment("");
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      toast({
        title: "Erreur",
        description: err.response?.data?.detail ?? err.message,
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleCreateOnDemand = async () => {
    if (!onDemandEmployee || !onDemandMotif || !onDemandDate) {
      toast({
        title: "Champs requis",
        description: "Salarié, motif et date sont obligatoires.",
        variant: "destructive",
      });
      return;
    }
    setSaving(true);
    try {
      await createOnDemand({
        employee_id: onDemandEmployee,
        request_motif: onDemandMotif,
        request_date: onDemandDate,
      });
      toast({ title: "Succès", description: "Visite à la demande créée." });
      setOnDemandOpen(false);
      setOnDemandEmployee("");
      setOnDemandMotif("");
      setOnDemandDate(new Date().toISOString().slice(0, 10));
      load();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      toast({
        title: "Erreur",
        description: err.response?.data?.detail ?? err.message,
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const planifiedBeyondDue =
    planifiedModal &&
    planifiedDate &&
    planifiedModal.due_date &&
    planifiedDate > planifiedModal.due_date;

  const overduePct =
    kpis && kpis.active_total > 0
      ? Math.round((kpis.overdue_count / kpis.active_total) * 100)
      : 0;

  return (
    <TooltipProvider>
      <div className="space-y-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Suivi médical</h1>
            <p className="mt-0.5 text-sm text-muted-foreground">
              Pilotage des obligations légales de suivi médical
            </p>
            {complianceQuery.data?.generated_at ? (
              <p className="mt-1 text-xs text-muted-foreground">
                Mis à jour le {formatComplianceGeneratedAtFrench(complianceQuery.data.generated_at)}
              </p>
            ) : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" className="gap-1.5" onClick={openOnDemandDialog}>
              <PlusCircle className="h-4 w-4" />
              Visite à la demande
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-1.5"
              onClick={() => setRemindersConfirmOpen(true)}
              disabled={sendRemindersMutation.isPending}
            >
              {sendRemindersMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Bell className="h-4 w-4" />
              )}
              Rappels
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button type="button" variant="outline" size="sm" className="gap-1.5">
                  <FileDown className="h-4 w-4" />
                  Exporter
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => exportObligationsToCsv(displayedObligations)}>
                  CSV obligations (filtre actuel)
                </DropdownMenuItem>
                <DropdownMenuItem
                  disabled={!complianceQuery.data}
                  onClick={() => {
                    if (complianceQuery.data) exportComplianceReportToCsv(complianceQuery.data);
                  }}
                >
                  CSV rapport de conformité
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <Tabs
          value={medTab}
          onValueChange={(v) => {
            const tab = v as MedTab;
            setMedTab(tab);
            syncUrlParams({ tab });
          }}
          className="w-full"
        >
          <TabsList>
            <TabsTrigger value="pilotage" className="gap-2">
              Pilotage
              {kpis && kpis.overdue_count > 0 ? (
                <Badge variant="destructive" className="h-5 px-1.5 text-xs tabular-nums">
                  {kpis.overdue_count}
                </Badge>
              ) : null}
            </TabsTrigger>
            <TabsTrigger value="conformite" className="gap-2">
              Conformité
              {complianceQuery.data ? (
                <Badge variant="secondary" className="h-5 px-1.5 text-xs tabular-nums">
                  {complianceQuery.data.compliance_rate.toFixed(0)} %
                </Badge>
              ) : complianceQuery.isLoading ? (
                <Loader2 className="h-3 w-3 animate-spin opacity-50" />
              ) : null}
            </TabsTrigger>
          </TabsList>

          <TabsContent value="pilotage" className="mt-4 space-y-4">
            {kpis ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <button
                  type="button"
                  onClick={handleKpiOverdueClick}
                  className={cn(
                    "rounded-lg border bg-card p-4 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    clientKpiFilter === "overdue" && "ring-2 ring-ring"
                  )}
                >
                  <p className="text-sm font-medium text-muted-foreground">En retard</p>
                  <p
                    className={cn(
                      "mt-1 text-2xl font-semibold tabular-nums",
                      kpis.overdue_count > 0 ? "text-destructive" : "text-foreground"
                    )}
                  >
                    {kpis.overdue_count}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {overduePct} % du total actif ({kpis.active_total})
                  </p>
                </button>
                <button
                  type="button"
                  onClick={handleKpiUpcomingClick}
                  className={cn(
                    "rounded-lg border bg-card p-4 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    clientKpiFilter === "upcoming30" && "ring-2 ring-ring"
                  )}
                >
                  <p className="text-sm font-medium text-muted-foreground">À venir 30 j.</p>
                  <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
                    {kpis.due_within_30_count}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Dont {upcoming7Count} sous 7 jours
                  </p>
                </button>
                <button
                  type="button"
                  onClick={handleKpiCompletedClick}
                  className={cn(
                    "rounded-lg border bg-card p-4 text-left transition-colors hover:bg-muted/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                    filterStatus === "realisee" && clientKpiFilter === null && "ring-2 ring-ring"
                  )}
                >
                  <p className="text-sm font-medium text-muted-foreground">Réalisées ce mois</p>
                  <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">
                    {kpis.completed_this_month}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">Cliquer pour filtrer la liste</p>
                </button>
              </div>
            ) : null}

            <div className="space-y-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h2 className="text-base font-semibold tracking-tight">Obligations</h2>
                  <p className="text-xs text-muted-foreground">
                    {displayedObligations.length} résultat{displayedObligations.length !== 1 ? "s" : ""}{" "}
                    — {obligationCounts.active} active{obligationCounts.active !== 1 ? "s" : ""},{" "}
                    {obligationCounts.overdue} en retard
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <div className="relative min-w-[200px] flex-1 sm:max-w-xs">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    className="h-9 pl-8"
                    placeholder="Rechercher un salarié…"
                    value={searchInput}
                    onChange={(e) => setSearchInput(e.target.value)}
                  />
                </div>
                <Select
                  value={filterEmployee}
                  onValueChange={(v) => {
                    applyFilterEmployee(v);
                    setClientKpiFilter(null);
                  }}
                >
                  <SelectTrigger className="h-9 w-[160px]">
                    <SelectValue placeholder="Salarié" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_FILTER}>Tous les salariés</SelectItem>
                    {employees.map((e) => (
                      <SelectItem key={e.id} value={e.id}>
                        {e.first_name} {e.last_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={filterVisitType}
                  onValueChange={(v) => {
                    applyFilterVisitType(v);
                    setClientKpiFilter(null);
                  }}
                >
                  <SelectTrigger className="h-9 w-[180px]">
                    <SelectValue placeholder="Type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_FILTER}>Tous types</SelectItem>
                    {Object.entries(VISIT_TYPE_LABELS).map(([k, v]) => (
                      <SelectItem key={k} value={k}>
                        {v}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={filterStatus}
                  onValueChange={(v) => {
                    applyFilterStatus(v);
                    setClientKpiFilter(null);
                  }}
                >
                  <SelectTrigger className="h-9 w-[130px]">
                    <SelectValue placeholder="Statut" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_FILTER}>Tous</SelectItem>
                    {Object.entries(STATUS_LABELS).map(([k, v]) => (
                      <SelectItem key={k} value={k}>
                        {v}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {hasActiveFilters ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-9 gap-1 text-muted-foreground"
                    onClick={resetFilters}
                  >
                    <X className="h-3.5 w-3.5" />
                    Réinitialiser
                  </Button>
                ) : null}
              </div>

              <Card>
                <CardContent className="p-0">
                  {loading ? (
                    <div className="flex justify-center py-10">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                  ) : (
                    <div className="w-full overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <SortableHead
                              label="Salarié"
                              column="employee"
                              activeColumn={sortColumn}
                              dir={sortDir}
                              onSort={handleSort}
                            />
                            <TableHead>Type de visite</TableHead>
                            <SortableHead
                              label="Échéance"
                              column="due_date"
                              activeColumn={sortColumn}
                              dir={sortDir}
                              onSort={handleSort}
                            />
                            <SortableHead
                              label="Statut"
                              column="status"
                              activeColumn={sortColumn}
                              dir={sortDir}
                              onSort={handleSort}
                            />
                            <TableHead>Dernière action</TableHead>
                            <TableHead className="w-12 text-right">Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {displayedObligations.length === 0 ? (
                            <TableRow>
                              <TableCell
                                colSpan={6}
                                className="py-10 text-center text-sm text-muted-foreground"
                              >
                                Aucune obligation pour les filtres sélectionnés.
                              </TableCell>
                            </TableRow>
                          ) : (
                            displayedObligations.map((o) => {
                              const relative = getDueDateRelativeLabel(o.due_date, o.status);
                              const overdue = isObligationOverdue(o);
                              const secondary = [
                                formatTriggerType(o.trigger_type),
                                formatPriorityLabel(o.priority),
                              ];
                              const msg = obligationMessage(o);
                              if (msg && msg !== "—") secondary.push(msg);

                              return (
                                <TableRow key={o.id} className="text-sm">
                                  <TableCell>
                                    <div className="font-medium">
                                      {o.employee_first_name} {o.employee_last_name}
                                    </div>
                                    <p className="mt-0.5 max-w-[220px] truncate text-xs text-muted-foreground">
                                      {secondary.join(" · ")}
                                    </p>
                                  </TableCell>
                                  <TableCell className="max-w-[180px]">
                                    <span className="line-clamp-2">
                                      {VISIT_TYPE_LABELS[o.visit_type] ?? o.visit_type}
                                    </span>
                                  </TableCell>
                                  <TableCell>
                                    <div className="tabular-nums">{formatDate(o.due_date)}</div>
                                    {relative ? (
                                      <p
                                        className={cn(
                                          "text-xs",
                                          overdue ? "text-destructive" : "text-muted-foreground"
                                        )}
                                      >
                                        {relative}
                                      </p>
                                    ) : null}
                                  </TableCell>
                                  <TableCell>
                                    <Badge variant={statusBadgeVariant(o.status, o.due_date)}>
                                      {STATUS_LABELS[o.status] ?? o.status}
                                    </Badge>
                                  </TableCell>
                                  <TableCell className="text-muted-foreground tabular-nums">
                                    {formatLastAction(o)}
                                  </TableCell>
                                  <TableCell className="text-right">
                                    {o.status !== "realisee" && o.status !== "annulee" ? (
                                      <DropdownMenu>
                                        <DropdownMenuTrigger asChild>
                                          <Button
                                            type="button"
                                            variant="ghost"
                                            size="icon"
                                            className="h-8 w-8"
                                            aria-label="Mettre à jour"
                                          >
                                            <MoreHorizontal className="h-4 w-4" />
                                          </Button>
                                        </DropdownMenuTrigger>
                                        <DropdownMenuContent align="end">
                                          <DropdownMenuItem
                                            onClick={() => {
                                              setPlanifiedModal(o);
                                              setPlanifiedDate(
                                                o.planned_date || new Date().toISOString().slice(0, 10)
                                              );
                                              setPlanifiedComment(o.justification || "");
                                            }}
                                          >
                                            Marquer planifiée
                                          </DropdownMenuItem>
                                          <DropdownMenuItem
                                            onClick={() => {
                                              setCompletedModal(o);
                                              setCompletedDate(
                                                o.completed_date ||
                                                  new Date().toISOString().slice(0, 10)
                                              );
                                              setCompletedComment(o.justification || "");
                                            }}
                                          >
                                            Marquer réalisée
                                          </DropdownMenuItem>
                                        </DropdownMenuContent>
                                      </DropdownMenu>
                                    ) : (
                                      <span className="text-xs text-muted-foreground">—</span>
                                    )}
                                  </TableCell>
                                </TableRow>
                              );
                            })
                          )}
                        </TableBody>
                      </Table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="conformite" className="mt-4 space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              {complianceQuery.data ? (
                <p className="max-w-2xl text-sm text-muted-foreground">
                  Photo de la conformité au{" "}
                  <span className="text-foreground">
                    {formatComplianceGeneratedAtFrench(complianceQuery.data.generated_at)}
                  </span>
                  . {complianceQuery.data.total_employees} salarié
                  {complianceQuery.data.total_employees > 1 ? "s" : ""} concerné
                  {complianceQuery.data.total_employees > 1 ? "s" : ""},{" "}
                  {complianceQuery.data.total_obligations} obligations suivies.
                </p>
              ) : (
                <p className="text-sm text-muted-foreground">Chargement du rapport…</p>
              )}
              <div className="flex gap-2">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => void complianceQuery.refetch()}
                      disabled={complianceQuery.isFetching}
                    >
                      {complianceQuery.isFetching ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4" />
                      )}
                      <span className="sr-only">Actualiser</span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Actualiser</TooltipContent>
                </Tooltip>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="h-8 w-8"
                      disabled={!complianceQuery.data}
                      onClick={() => {
                        if (complianceQuery.data) exportComplianceReportToCsv(complianceQuery.data);
                      }}
                    >
                      <FileDown className="h-4 w-4" />
                      <span className="sr-only">Exporter le rapport</span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Exporter le rapport</TooltipContent>
                </Tooltip>
              </div>
            </div>

            {complianceQuery.isLoading ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  {[0, 1, 2].map((i) => (
                    <Skeleton key={i} className="h-24 w-full" />
                  ))}
                </div>
                <Skeleton className="h-40 w-full" />
                <Skeleton className="h-40 w-full" />
              </div>
            ) : complianceQuery.isError ? (
              <p className="text-sm text-destructive">
                Impossible de charger le rapport de conformité.
              </p>
            ) : complianceQuery.data ? (
              <MedicalCompliancePanels
                cr={complianceQuery.data}
                onVisitTypeClick={goToPilotageWithVisitType}
                onViewEmployeeObligations={goToPilotageWithEmployee}
              />
            ) : null}
          </TabsContent>
        </Tabs>

        <AlertDialog open={remindersConfirmOpen} onOpenChange={setRemindersConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Envoyer les rappels ?</AlertDialogTitle>
              <AlertDialogDescription>
                Envoyer des notifications à {salarieConcerneCount} salarié(s) concerné(s) ? Les
                rappels portent sur les obligations actives dont l&apos;échéance est passée ou dans
                les 30 prochains jours.
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

        <Dialog open={!!planifiedModal} onOpenChange={(open) => !open && setPlanifiedModal(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Marquer comme planifiée</DialogTitle>
              <DialogDescription>
                Indiquez la date de planification et un commentaire optionnel.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label>Date de planification</Label>
                <Input
                  type="date"
                  value={planifiedDate}
                  onChange={(e) => setPlanifiedDate(e.target.value)}
                />
                {planifiedBeyondDue ? (
                  <p className="text-xs text-orange-600 dark:text-orange-400">
                    Date au-delà de l&apos;échéance — risque de non-conformité
                  </p>
                ) : null}
              </div>
              <div className="grid gap-2">
                <Label>Commentaire (optionnel)</Label>
                <Textarea
                  rows={3}
                  value={planifiedComment}
                  onChange={(e) => setPlanifiedComment(e.target.value)}
                  placeholder="Commentaire"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setPlanifiedModal(null)}>
                Annuler
              </Button>
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
              <DialogDescription>
                Indiquez la date de réalisation et un commentaire optionnel.
              </DialogDescription>
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
                <Textarea
                  rows={3}
                  value={completedComment}
                  onChange={(e) => setCompletedComment(e.target.value)}
                  placeholder="Commentaire"
                />
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCompletedModal(null)}>
                Annuler
              </Button>
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
              <DialogDescription>
                Sélectionnez le salarié, le motif et la date de demande.
              </DialogDescription>
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
                      <SelectItem key={e.id} value={e.id}>
                        {e.first_name} {e.last_name}
                      </SelectItem>
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
              <Button variant="outline" onClick={() => setOnDemandOpen(false)}>
                Annuler
              </Button>
              <Button
                onClick={handleCreateOnDemand}
                disabled={saving || !onDemandEmployee || !onDemandMotif || !onDemandDate}
              >
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "Créer"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </TooltipProvider>
  );
}
