// Référentiel compétences, matrice, gaps, export (Pack Talent T9)

import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { ChevronDown, Loader2, Pencil, Plus, RefreshCw } from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

import apiClient from "@/api/apiClient";
import {
  analyzeMobility,
  archiveCompetencyRef,
  createCompetencyRef,
  evaluateEmployee,
  exportMatrixExcel,
  getCompetencyRefs,
  getEvaluations,
  getMatrix,
  updateCompetencyRef,
  type CompetencyMatrix,
  type CompetencyRef,
  type CompetencyRefCreate,
  type EmployeeCompetency,
  type MobilityAnalysis,
} from "@/api/competencies";
import { listCompanyServices, type CompanyService } from "@/api/objectives";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { useViewOptional } from "@/contexts/ViewContext";
import { cn } from "@/lib/utils";
import { isPlatformAdmin } from '@/lib/platformAdmin';

type EmpRow = { id: string; first_name: string; last_name: string; email?: string | null };

const CATEGORIES: { value: string; label: string }[] = [
  { value: "technique", label: "Technique" },
  { value: "manageriale", label: "Managériale" },
  { value: "transversale", label: "Transversale" },
  { value: "reglementaire", label: "Réglementaire" },
  { value: "securite", label: "Sécurité" },
];

function scoreCellClass(score: number, isGap: boolean) {
  const bg =
    score === 0
      ? "bg-neutral-200 text-neutral-700"
      : score === 1
        ? "bg-red-500 text-white"
        : score === 2
          ? "bg-orange-400 text-white"
          : score === 3
            ? "bg-green-200 text-green-900"
            : "bg-green-700 text-white";
  return cn(
    "min-w-[3rem] text-center text-xs font-medium",
    bg,
    isGap && "ring-2 ring-red-600 ring-offset-1",
  );
}

function scoreBadge(score: number) {
  const cls = scoreCellClass(score, false);
  return <Badge className={cn(cls, "border-0")}>{score === 0 ? "—" : String(score)}</Badge>;
}

function potentielBadgeClass(ev: string) {
  const v = ev.toLowerCase();
  if (v.includes("fort")) return "bg-emerald-600 hover:bg-emerald-600";
  if (v.includes("faible")) return "bg-orange-500 hover:bg-orange-500";
  return "bg-blue-600 hover:bg-blue-600";
}

function prioriteBadgeClass(p: string) {
  const v = p.toLowerCase();
  if (v.includes("haute")) return "bg-red-600 hover:bg-red-600";
  if (v.includes("faible")) return "bg-emerald-600 hover:bg-emerald-600";
  return "bg-orange-500 hover:bg-orange-500";
}

export type CompetencesTabProps = {
  referentialOnly?: boolean;
  hideReferential?: boolean;
  defaultSub?: "matrice" | "gaps" | "referentiel";
  collapseMobilityDefault?: boolean;
};

export default function CompetencesTab({
  referentialOnly = false,
  hideReferential = false,
  defaultSub = "matrice",
  collapseMobilityDefault = false,
}: CompetencesTabProps = {}) {
  const { toast } = useToast();
  const qc = useQueryClient();
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const viewOpt = useViewOptional();

  const isRh =
    isPlatformAdmin(user) ||
    activeCompany?.role === "admin" ||
    activeCompany?.role === "rh" ||
    activeCompany?.role === "collaborateur_rh";

  const showRhActions = Boolean(
    isRh && !(viewOpt?.isCollaborateurRh && viewOpt.viewMode === "collaborateur"),
  );

  const companyKey = activeCompany?.company_id ?? "none";
  const [sub, setSub] = useState<"matrice" | "gaps" | "referentiel">(
    referentialOnly ? "referentiel" : defaultSub,
  );
  const [mobilityOpen, setMobilityOpen] = useState(!collapseMobilityDefault);
  const [svc, setSvc] = useState<string>("all");
  const [cat, setCat] = useState<string>("all");
  const [mobilityEmpId, setMobilityEmpId] = useState<string>("");
  const [mobilityResult, setMobilityResult] = useState<MobilityAnalysis | null>(null);

  const servicesQuery = useQuery({
    queryKey: ["objectives", "services", companyKey],
    queryFn: () => listCompanyServices(),
    enabled: showRhActions && Boolean(activeCompany),
  });

  const matrixQuery = useQuery({
    queryKey: ["competencies", "matrix", companyKey, svc, cat],
    queryFn: () =>
      getMatrix({
        service_id: svc === "all" ? undefined : svc,
        category: cat === "all" ? undefined : cat,
      }),
    enabled: showRhActions && Boolean(activeCompany),
  });

  const refsQuery = useQuery({
    queryKey: ["competencies", "refs", companyKey],
    queryFn: () => getCompetencyRefs(true),
    enabled: showRhActions && Boolean(activeCompany),
  });

  const activeRefs = useMemo(
    () => (refsQuery.data ?? []).filter((r) => r.status !== "archived"),
    [refsQuery.data],
  );

  const employeesQuery = useQuery({
    queryKey: ["employees", "competencies", companyKey],
    queryFn: async () => {
      const res = await apiClient.get<EmpRow[]>("/api/employees");
      return res.data ?? [];
    },
    enabled: Boolean(activeCompany),
  });

  const myEmployeeId = useMemo(() => {
    if (!user?.email || !employeesQuery.data?.length) return null;
    const em = user.email.toLowerCase();
    return employeesQuery.data.find((e) => (e.email || "").toLowerCase() === em)?.id ?? null;
  }, [employeesQuery.data, user?.email]);

  const myEvalsQuery = useQuery({
    queryKey: ["competencies", "evals", "mine", companyKey, myEmployeeId],
    queryFn: () => getEvaluations(myEmployeeId!),
    enabled: !showRhActions && Boolean(activeCompany) && Boolean(myEmployeeId),
  });

  const [evalSheet, setEvalSheet] = useState(false);
  const [evEmp, setEvEmp] = useState("");
  const [evDate, setEvDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [evScores, setEvScores] = useState<Record<string, number>>({});
  const [evComments, setEvComments] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!evEmp || !activeRefs.length) return;
    const init: Record<string, number> = {};
    activeRefs.forEach((r) => {
      init[r.id] = 0;
    });
    setEvScores(init);
  }, [evEmp, activeRefs, evalSheet]);

  const evalMut = useMutation({
    mutationFn: async () => {
      if (!evEmp) throw new Error("Collaborateur requis.");
      for (const c of activeRefs) {
        const score = evScores[c.id] ?? 0;
        const comment = (evComments[c.id] || "").trim() || null;
        await evaluateEmployee({
          employee_id: evEmp,
          competency_id: c.id,
          score,
          evaluation_date: evDate,
          comment,
        });
      }
    },
    onSuccess: () => {
      toast({ title: "Évaluations enregistrées" });
      void qc.invalidateQueries({ queryKey: ["competencies"] });
      setEvalSheet(false);
    },
    onError: (e: unknown) => {
      toast({
        title: "Erreur",
        description: e instanceof Error ? e.message : "Échec",
        variant: "destructive",
      });
    },
  });

  const [refSheet, setRefSheet] = useState(false);
  const [editRef, setEditRef] = useState<CompetencyRef | null>(null);
  const [rfName, setRfName] = useState("");
  const [rfCat, setRfCat] = useState<string>("technique");
  const [rfDesc, setRfDesc] = useState("");
  const [rfLvl, setRfLvl] = useState<string>("none");

  function openRefCreate() {
    setEditRef(null);
    setRfName("");
    setRfCat("technique");
    setRfDesc("");
    setRfLvl("none");
    setRefSheet(true);
  }

  function openRefEdit(r: CompetencyRef) {
    setEditRef(r);
    setRfName(r.name);
    setRfCat(r.category);
    setRfDesc(r.description || "");
    setRfLvl(r.required_level == null ? "none" : String(r.required_level));
    setRefSheet(true);
  }

  const saveRefMut = useMutation({
    mutationFn: async () => {
      const rl = rfLvl === "none" ? null : parseInt(rfLvl, 10);
      const body: CompetencyRefCreate = {
        name: rfName.trim(),
        category: rfCat as CompetencyRefCreate["category"],
        description: rfDesc.trim() || null,
        required_level: rl,
      };
      if (editRef) {
        return updateCompetencyRef(editRef.id, body);
      }
      return createCompetencyRef(body);
    },
    onSuccess: () => {
      toast({ title: editRef ? "Compétence mise à jour" : "Compétence créée" });
      void qc.invalidateQueries({ queryKey: ["competencies"] });
      setRefSheet(false);
    },
    onError: () => toast({ title: "Erreur", variant: "destructive" }),
  });

  const archMut = useMutation({
    mutationFn: (id: string) => archiveCompetencyRef(id),
    onSuccess: () => {
      toast({ title: "Compétence archivée" });
      void qc.invalidateQueries({ queryKey: ["competencies"] });
    },
    onError: () => toast({ title: "Erreur", variant: "destructive" }),
  });

  const trainingByComp = useMemo(() => {
    const m: CompetencyMatrix | undefined = matrixQuery.data;
    const map: Record<string, { training_id: string; training_title: string }> = {};
    (m?.gap_trainings ?? []).forEach((x) => {
      map[x.competency_id] = { training_id: x.training_id, training_title: x.training_title };
    });
    return map;
  }, [matrixQuery.data]);

  useEffect(() => {
    setMobilityResult(null);
  }, [mobilityEmpId]);

  const mobilityMut = useMutation({
    mutationFn: async () => {
      if (!mobilityEmpId) throw new Error("Sélectionnez un collaborateur.");
      return analyzeMobility(mobilityEmpId, activeCompany?.company_id);
    },
    onMutate: () => {
      toast({ title: "Analyse en cours..." });
    },
    onSuccess: (data) => {
      setMobilityResult(data);
      toast({ title: "Analyse terminée" });
    },
    onError: (e: unknown) => {
      if (isAxiosError(e) && e.response?.status === 503) {
        toast({
          title: "Clé API non configurée",
          variant: "destructive",
        });
        return;
      }
      const msg =
        isAxiosError(e) && e.response?.data && typeof e.response.data === "object"
          ? String((e.response.data as { detail?: string }).detail ?? "")
          : e instanceof Error
            ? e.message
            : "Échec de l’analyse";
      toast({
        title: "Erreur",
        description: msg || "Échec de l’analyse",
        variant: "destructive",
      });
    },
  });

  const matrix = matrixQuery.data;
  const compById = useMemo(() => {
    const m: Record<
      string,
      { id: string; name: string; category: string; required_level?: number | null }
    > = {};
    (matrix?.competencies ?? []).forEach((c) => {
      m[c.id] = c;
    });
    return m;
  }, [matrix]);

  if (!activeCompany) {
    return (
      <p className="text-sm text-muted-foreground">Sélectionnez une entreprise pour continuer.</p>
    );
  }

  if (!showRhActions) {
    if (employeesQuery.isLoading || myEvalsQuery.isLoading) {
      return (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      );
    }
    if (!myEmployeeId) {
      return (
        <p className="text-sm text-muted-foreground">
          Impossible de résoudre votre fiche collaborateur pour cette entreprise.
        </p>
      );
    }
    const rows = myEvalsQuery.data ?? [];
    return (
      <div className="space-y-3">
        <h3 className="text-lg font-semibold">Mes compétences évaluées</h3>
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune évaluation enregistrée.</p>
        ) : (
          <div className="space-y-2">
            {rows.map((e: EmployeeCompetency) => {
              const delta =
                e.required_level != null ? e.score - e.required_level : null;
              return (
                <div
                  key={e.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3"
                >
                  <div>
                    <p className="font-medium">{e.competency_name ?? e.competency_id}</p>
                    <p className="text-xs text-muted-foreground">{e.competency_category}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {scoreBadge(e.score)}
                    {delta != null && e.required_level != null && (
                      <span className="text-xs text-muted-foreground">
                        Requis {e.required_level}
                        {delta < 0 ? (
                          <span className="text-red-600"> ({delta})</span>
                        ) : (
                          <span className="text-emerald-600">
                            {" "}
                            ({delta > 0 ? `+${delta}` : String(delta)})
                          </span>
                        )}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  const showRefSub = !hideReferential || referentialOnly;
  const tabsValue = referentialOnly ? "referentiel" : sub;

  return (
    <div className="space-y-4">
      <Tabs
        value={tabsValue}
        onValueChange={(v) => {
          if (!referentialOnly) setSub(v as typeof sub);
        }}
      >
        {!referentialOnly ? (
          <TabsList
            className={cn(
              "grid h-11 w-full gap-1",
              showRefSub && !hideReferential ? "grid-cols-3" : "grid-cols-2",
            )}
          >
            <TabsTrigger value="gaps" className="w-full">
              Écarts
            </TabsTrigger>
            <TabsTrigger value="matrice" className="w-full">
              Matrice
            </TabsTrigger>
            {showRefSub && !hideReferential ? (
              <TabsTrigger value="referentiel" className="w-full">
                Référentiel
              </TabsTrigger>
            ) : null}
          </TabsList>
        ) : null}

        {!referentialOnly ? (
        <TabsContent value="matrice" className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label>Service</Label>
              <Select value={svc} onValueChange={setSvc}>
                <SelectTrigger className="w-[200px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tous</SelectItem>
                  {(servicesQuery.data ?? []).map((s: CompanyService) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>Catégorie</Label>
              <Select value={cat} onValueChange={setCat}>
                <SelectTrigger className="w-[200px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Toutes</SelectItem>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button
              type="button"
              variant="secondary"
              onClick={() =>
                exportMatrixExcel({
                  service_id: svc === "all" ? undefined : svc,
                  category: cat === "all" ? undefined : cat,
                })
              }
            >
              Exporter Excel
            </Button>
            <Button type="button" onClick={() => setEvalSheet(true)}>
              Évaluer un collaborateur
            </Button>
          </div>

          {matrixQuery.isLoading && <Skeleton className="h-64 w-full" />}
          {matrixQuery.isError && (
            <p className="text-sm text-destructive">Impossible de charger la matrice.</p>
          )}
          {matrix && !matrixQuery.isLoading && (
            <div className="w-full max-w-full overflow-x-auto rounded-md border">
              <table className="w-max min-w-full border-collapse text-sm">
                <thead>
                  <tr>
                    <th className="sticky left-0 z-10 bg-background px-2 py-2 text-left font-medium">
                      Collaborateur
                    </th>
                    {matrix.competencies.map((c) => (
                      <th
                        key={c.id}
                        className="min-w-[4.5rem] px-1 py-2 text-center text-xs font-medium"
                        title={c.name}
                      >
                        <span className="line-clamp-3">{c.name}</span>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrix.employees.map((emp) => (
                    <tr key={emp.id}>
                      <td className="sticky left-0 z-10 bg-background px-2 py-1 font-medium">
                        {emp.name}
                      </td>
                      {matrix.competencies.map((c) => {
                        const cell = matrix.cells.find(
                          (x) => x.employee_id === emp.id && x.competency_id === c.id,
                        );
                        const score = cell?.score ?? 0;
                        const g = cell?.is_gap ?? false;
                        return (
                          <td key={c.id} className="p-0.5">
                            <div
                              className={cn(
                                "rounded px-1 py-2",
                                scoreCellClass(score, g),
                              )}
                            >
                              {score === 0 ? "—" : score}
                            </div>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {matrix && !matrixQuery.isLoading && (
            <Collapsible open={mobilityOpen} onOpenChange={setMobilityOpen} className="border-t pt-6">
              <CollapsibleTrigger asChild>
                <Button
                  type="button"
                  variant="ghost"
                  className="flex w-full items-center justify-between px-0 py-2 h-auto font-semibold"
                >
                  <span>Analyse de mobilité interne</span>
                  <ChevronDown className="h-4 w-4 shrink-0 transition-transform [[data-state=open]_&]:rotate-180" />
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="space-y-4 pt-2">
              <div className="flex flex-wrap items-end gap-3">
                <div className="space-y-1">
                  <Label>Collaborateur</Label>
                  <Select value={mobilityEmpId} onValueChange={setMobilityEmpId}>
                    <SelectTrigger className="w-[280px]">
                      <SelectValue placeholder="Choisir un collaborateur…" />
                    </SelectTrigger>
                    <SelectContent>
                      {matrix.employees.map((e) => (
                        <SelectItem key={e.id} value={e.id}>
                          {e.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  type="button"
                  disabled={!mobilityEmpId || mobilityMut.isPending}
                  onClick={() => mobilityMut.mutate()}
                >
                  {mobilityMut.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  Analyser le potentiel de mobilité
                </Button>
              </div>

              {mobilityResult && mobilityResult.employee_id === mobilityEmpId && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                    <Card>
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Score de mobilité</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-3">
                        <div className="flex items-center gap-4">
                          <div
                            className="flex h-24 w-24 shrink-0 items-center justify-center rounded-full border-4 border-primary bg-muted/40 text-2xl font-bold"
                            aria-label={`Score ${mobilityResult.mobilite_score} sur 100`}
                          >
                            {mobilityResult.mobilite_score}
                          </div>
                          <div className="min-w-0 flex-1 space-y-2">
                            <Badge
                              className={cn("text-white", potentielBadgeClass(mobilityResult.potentiel_evolution))}
                            >
                              Potentiel : {mobilityResult.potentiel_evolution}
                            </Badge>
                            <Progress value={mobilityResult.mobilite_score} className="h-2" />
                          </div>
                        </div>
                        <p className="text-sm italic text-muted-foreground">{mobilityResult.synthese}</p>
                        <p className="text-xs text-muted-foreground">
                          Analyse du{" "}
                          {new Date(mobilityResult.analyzed_at).toLocaleString("fr-FR", {
                            dateStyle: "short",
                            timeStyle: "short",
                          })}
                        </p>
                      </CardContent>
                    </Card>

                    <Card className="lg:col-span-2">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-base">Postes recommandés</CardTitle>
                      </CardHeader>
                      <CardContent className="space-y-4">
                        {mobilityResult.postes_recommandes.length === 0 ? (
                          <p className="text-sm text-muted-foreground">Aucun poste suggéré.</p>
                        ) : (
                          mobilityResult.postes_recommandes.map((p, i) => (
                            <div key={`${p.poste}-${i}`} className="rounded-md border p-3 space-y-2">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="font-medium">{p.poste}</p>
                                <span className="text-sm text-muted-foreground">{p.compatibilite}%</span>
                              </div>
                              <Progress value={p.compatibilite} className="h-2" />
                              {p.points_forts.length > 0 && (
                                <ul className="list-inside list-disc text-sm text-emerald-700">
                                  {p.points_forts.map((x) => (
                                    <li key={x}>{x}</li>
                                  ))}
                                </ul>
                              )}
                              {p.competences_a_developper.length > 0 && (
                                <ul className="list-inside list-disc text-sm text-orange-700">
                                  {p.competences_a_developper.map((x) => (
                                    <li key={x}>{x}</li>
                                  ))}
                                </ul>
                              )}
                            </div>
                          ))
                        )}
                      </CardContent>
                    </Card>
                  </div>

                  <Card>
                    <CardHeader className="pb-2">
                      <CardTitle className="text-base">Formations recommandées</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {mobilityResult.formations_recommandees.length === 0 ? (
                        <p className="text-sm text-muted-foreground">Aucune formation suggérée.</p>
                      ) : (
                        mobilityResult.formations_recommandees.map((f, i) => (
                          <div
                            key={`${f.titre}-${i}`}
                            className="flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-start sm:justify-between"
                          >
                            <div className="space-y-1 min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="font-medium">{f.titre}</p>
                                <Badge
                                  className={cn("text-white", prioriteBadgeClass(f.priorite))}
                                >
                                  {f.priorite}
                                </Badge>
                              </div>
                              <p className="text-xs text-muted-foreground">
                                Compétence : {f.competence_ciblee}
                              </p>
                              <p className="text-sm">{f.impact_estime}</p>
                            </div>
                            {f.training_id ? (
                              <Button variant="outline" size="sm" asChild className="shrink-0">
                                <Link
                                  to={{
                                    pathname: "/formation",
                                    hash: "formations",
                                    search: `?sub=inscriptions&enrollTraining=${encodeURIComponent(f.training_id)}`,
                                  }}
                                >
                                  Voir dans le catalogue
                                </Link>
                              </Button>
                            ) : null}
                          </div>
                        ))
                      )}
                    </CardContent>
                  </Card>

                  <div>
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={!mobilityEmpId || mobilityMut.isPending}
                      onClick={() => mobilityMut.mutate()}
                    >
                      {mobilityMut.isPending ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="mr-2 h-4 w-4" />
                      )}
                      Relancer l&apos;analyse
                    </Button>
                  </div>
                </div>
              )}
              </CollapsibleContent>
            </Collapsible>
          )}
        </TabsContent>
        ) : null}

        {!referentialOnly ? (
        <TabsContent value="gaps" className="space-y-4">
          {matrixQuery.isLoading && <Skeleton className="h-48 w-full" />}
          {matrixQuery.isError && (
            <p className="text-sm text-destructive">Impossible de charger les gaps.</p>
          )}
          {matrix && (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Collaborateur</TableHead>
                    <TableHead>Compétence</TableHead>
                    <TableHead>Score</TableHead>
                    <TableHead>Niveau requis</TableHead>
                    <TableHead>Écart</TableHead>
                    <TableHead>Formation recommandée</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {matrix.gaps.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center text-muted-foreground">
                        Aucun gap sur les filtres courants.
                      </TableCell>
                    </TableRow>
                  ) : (
                    matrix.gaps.map((g, idx) => {
                      const req = g.required_level ?? compById[g.competency_id]?.required_level;
                      const gap = req != null ? g.score - req : null;
                      const tr = trainingByComp[g.competency_id];
                      return (
                        <TableRow key={`${g.employee_id}-${g.competency_id}-${idx}`}>
                          <TableCell>{g.employee_name}</TableCell>
                          <TableCell>{g.competency_name}</TableCell>
                          <TableCell>{g.score}</TableCell>
                          <TableCell>{req ?? "—"}</TableCell>
                          <TableCell>{gap ?? "—"}</TableCell>
                          <TableCell>
                            {tr ? (
                              <div className="flex flex-col gap-1 sm:flex-row sm:items-center">
                                <span className="text-sm">{tr.training_title}</span>
                                <Button variant="outline" size="sm" asChild>
                                  <Link
                                    to={{
                                      pathname: "/formation",
                                    hash: "formations",
                                    search: `?sub=inscriptions&enrollTraining=${encodeURIComponent(tr.training_id)}`,
                                    }}
                                  >
                                    Inscrire
                                  </Link>
                                </Button>
                              </div>
                            ) : (
                              "—"
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
        </TabsContent>
        ) : null}

        {showRefSub ? (
        <TabsContent value="referentiel" className="space-y-4">
          <Button type="button" onClick={openRefCreate}>
            <Plus className="mr-2 h-4 w-4" />
            Ajouter une compétence
          </Button>
          {refsQuery.isLoading && <Skeleton className="h-40 w-full" />}
          {refsQuery.data && (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Nom</TableHead>
                    <TableHead>Catégorie</TableHead>
                    <TableHead>Niveau requis</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {refsQuery.data.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="font-medium">{r.name}</TableCell>
                      <TableCell>{r.category}</TableCell>
                      <TableCell>{r.required_level ?? "—"}</TableCell>
                      <TableCell>
                        <Badge variant={r.status === "archived" ? "secondary" : "default"}>
                          {r.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right space-x-2">
                        <Button type="button" variant="outline" size="sm" onClick={() => openRefEdit(r)}>
                          <Pencil className="h-3 w-3" />
                        </Button>
                        {r.status !== "archived" && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => archMut.mutate(r.id)}
                          >
                            Archiver
                          </Button>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </TabsContent>
        ) : null}
      </Tabs>

      <Sheet open={evalSheet} onOpenChange={setEvalSheet}>
        <SheetContent className="overflow-y-auto sm:max-w-lg">
          <SheetHeader>
            <SheetTitle>Évaluation collaborateurs</SheetTitle>
          </SheetHeader>
          <div className="mt-4 space-y-4">
            <div className="space-y-2">
              <Label>Collaborateur</Label>
              <Select value={evEmp} onValueChange={setEvEmp}>
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
            <div className="space-y-2">
              <Label>Date d&apos;évaluation</Label>
              <Input type="date" value={evDate} onChange={(ev) => setEvDate(ev.target.value)} />
            </div>
            <div className="max-h-[50vh] space-y-3 overflow-y-auto pr-1">
              {activeRefs.map((c) => (
                <div key={c.id} className="rounded-md border p-3 space-y-2">
                  <p className="text-sm font-medium">{c.name}</p>
                  <div className="flex gap-2">
                    <Select
                      value={String(evScores[c.id] ?? 0)}
                      onValueChange={(v) =>
                        setEvScores((s) => ({ ...s, [c.id]: parseInt(v, 10) }))
                      }
                    >
                      <SelectTrigger className="w-[100px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {[0, 1, 2, 3, 4].map((n) => (
                          <SelectItem key={n} value={String(n)}>
                            {n}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <Textarea
                    placeholder="Commentaire (optionnel)"
                    value={evComments[c.id] ?? ""}
                    onChange={(ev) =>
                      setEvComments((s) => ({ ...s, [c.id]: ev.target.value }))
                    }
                    rows={2}
                  />
                </div>
              ))}
            </div>
          </div>
          <SheetFooter className="mt-6">
            <Button
              type="button"
              disabled={!evEmp || evalMut.isPending}
              onClick={() => evalMut.mutate()}
            >
              {evalMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enregistrer
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Sheet open={refSheet} onOpenChange={setRefSheet}>
        <SheetContent>
          <SheetHeader>
            <SheetTitle>{editRef ? "Modifier la compétence" : "Nouvelle compétence"}</SheetTitle>
          </SheetHeader>
          <div className="mt-4 space-y-4">
            <div className="space-y-2">
              <Label>Nom</Label>
              <Input value={rfName} onChange={(e) => setRfName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Catégorie</Label>
              <Select value={rfCat} onValueChange={setRfCat}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea value={rfDesc} onChange={(e) => setRfDesc(e.target.value)} rows={3} />
            </div>
            <div className="space-y-2">
              <Label>Niveau requis</Label>
              <Select value={rfLvl} onValueChange={setRfLvl}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">Non défini</SelectItem>
                  <SelectItem value="1">1</SelectItem>
                  <SelectItem value="2">2</SelectItem>
                  <SelectItem value="3">3</SelectItem>
                  <SelectItem value="4">4</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <SheetFooter className="mt-6">
            <Button
              type="button"
              disabled={!rfName.trim() || saveRefMut.isPending}
              onClick={() => saveRefMut.mutate()}
            >
              Enregistrer
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>
    </div>
  );
}
