// Catalogue formations & inscriptions (Pack Talent)

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Archive,
  BookOpen,
  ExternalLink,
  FileText,
  Loader2,
  Pencil,
  Plus,
  UserPlus,
} from "lucide-react";

import apiClient from "@/api/apiClient";
import { createEmployeeCertification, getCertificationRefs } from "@/api/certifications";
import {
  archiveTraining,
  cancelEnrollment,
  createEnrollment,
  createTraining,
  getEnrollments,
  getTotalConsumed,
  getTrainings,
  updateEnrollment,
  updateTraining,
  type TrainingCatalog,
  type TrainingCatalogCreate,
  type TrainingEnrollment,
  type TrainingType,
} from "@/api/training";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useToast } from "@/components/ui/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { useViewOptional } from "@/contexts/ViewContext";
import { cn } from "@/lib/utils";

type EmployeeRow = { id: string; first_name: string; last_name: string };

const TYPE_LABELS: Record<string, string> = {
  presentiel: "Présentiel",
  distanciel: "Distanciel",
  elearning: "E-learning",
  blended: "Blended",
  habilitation: "Habilitation",
};

const CATEGORY_OPTIONS = [
  "Management",
  "Technique",
  "Réglementaire",
  "Sécurité",
  "Informatique",
  "Langue",
  "Autre",
] as const;

function typeBadgeClass(t: string) {
  switch (t) {
    case "presentiel":
      return "bg-slate-600 text-white";
    case "distanciel":
      return "bg-sky-600 text-white";
    case "elearning":
      return "bg-violet-600 text-white";
    case "blended":
      return "bg-indigo-600 text-white";
    case "habilitation":
      return "bg-amber-600 text-white";
    default:
      return "bg-muted";
  }
}

/** Clés API d'inscription — couleurs basées sur la valeur renvoyée par l'API, pas sur le libellé affiché. */
type EnrollmentApiStatus = "planned" | "in_progress" | "completed" | "cancelled";

function canonicalEnrollmentStatus(raw: string | undefined | null): EnrollmentApiStatus | null {
  const s = (raw ?? "").trim().toLowerCase();
  if (s === "planned" || s === "in_progress" || s === "completed" || s === "cancelled") return s;
  return null;
}

function enrollmentStatusBadgeClass(key: EnrollmentApiStatus | null): string {
  if (!key) return "border-0 bg-muted text-muted-foreground hover:bg-muted";
  switch (key) {
    case "planned":
      return "border-0 bg-blue-600 text-white hover:bg-blue-600";
    case "in_progress":
      return "border-0 bg-orange-500 text-white hover:bg-orange-500";
    case "completed":
      return "border-0 bg-emerald-600 text-white hover:bg-emerald-600";
    case "cancelled":
      return "border-0 bg-muted text-muted-foreground hover:bg-muted";
    default:
      return "border-0 bg-muted text-muted-foreground hover:bg-muted";
  }
}

const ENROLLMENT_STATUS_LABEL: Record<EnrollmentApiStatus, string> = {
  planned: "Planifié",
  in_progress: "En cours",
  completed: "Terminé",
  cancelled: "Annulé",
};

type CertSuggestion = {
  employeeId: string;
  certificationId: string;
  trainingTitle: string;
};

export default function CatalogueTab() {
  const navigate = useNavigate();
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
  const [mainTab, setMainTab] = useState<"catalogue" | "inscriptions">("catalogue");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tid = params.get("enrollTraining");
    if (!tid) return;
    setEnTrainId(tid);
    setEnrollOpen(true);
    setMainTab("inscriptions");
    params.delete("enrollTraining");
    const qs = params.toString();
    navigate({ pathname: "/formation", hash: "catalogue", search: qs ? `?${qs}` : "" }, { replace: true });
  }, [navigate]);

  const [catType, setCatType] = useState<string>("all");
  const [catStatus, setCatStatus] = useState<string>("active");
  const [catSearch, setCatSearch] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);

  const [enTrain, setEnTrain] = useState<string>("all");
  const [enEmp, setEnEmp] = useState<string>("all");
  const [enStatus, setEnStatus] = useState<string>("all");

  const [sheetOpen, setSheetOpen] = useState(false);
  const [editing, setEditing] = useState<TrainingCatalog | null>(null);
  const [formTitle, setFormTitle] = useState("");
  const [formType, setFormType] = useState<TrainingType>("presentiel");
  const [formProvider, setFormProvider] = useState("");
  const [formDuration, setFormDuration] = useState("");
  const [formCost, setFormCost] = useState("");
  const [formObjective, setFormObjective] = useState("");
  const [formCats, setFormCats] = useState<string[]>([]);
  const [formCertId, setFormCertId] = useState<string>("");
  const [formProgramUrl, setFormProgramUrl] = useState("");
  const [formExternal, setFormExternal] = useState("");

  const [enrollOpen, setEnrollOpen] = useState(false);
  const [enTrainId, setEnTrainId] = useState("");
  const [enEmpId, setEnEmpId] = useState("");
  const [enPlanned, setEnPlanned] = useState("");
  const [enNotes, setEnNotes] = useState("");

  const [archiveTarget, setArchiveTarget] = useState<TrainingCatalog | null>(null);

  const [certSuggestion, setCertSuggestion] = useState<CertSuggestion | null>(null);
  const [habSheetOpen, setHabSheetOpen] = useState(false);
  const [habObtained, setHabObtained] = useState(new Date().toISOString().slice(0, 10));
  const [habExpiry, setHabExpiry] = useState("");
  const [habNotes, setHabNotes] = useState("");

  const employeesQuery = useQuery({
    queryKey: ["training", "employees"],
    queryFn: async () => {
      const res = await apiClient.get<EmployeeRow[]>("/api/employees");
      return res.data ?? [];
    },
    enabled: showRhActions,
  });

  const refsQuery = useQuery({
    queryKey: ["training", "cert-refs"],
    queryFn: getCertificationRefs,
    enabled: showRhActions,
  });

  const fetchArchived =
    includeArchived || catStatus === "archived" || catStatus === "all";

  const trainingsQuery = useQuery({
    queryKey: ["training", "catalog", fetchArchived],
    queryFn: () => getTrainings(fetchArchived),
  });

  const consumedQuery = useQuery({
    queryKey: ["training", "consumed", defaultYear],
    queryFn: () => getTotalConsumed(defaultYear),
    enabled: showRhActions && mainTab === "catalogue",
  });

  const enrollmentsQuery = useQuery({
    queryKey: ["training", "enrollments", enTrain, enEmp, enStatus],
    queryFn: () =>
      getEnrollments({
        training_id: enTrain === "all" ? undefined : enTrain,
        employee_id: enEmp === "all" ? undefined : enEmp,
        status: enStatus === "all" ? undefined : enStatus,
      }),
    enabled: showRhActions && mainTab === "inscriptions",
  });

  const filteredCatalog = useMemo(() => {
    let rows = trainingsQuery.data ?? [];
    if (catType !== "all") rows = rows.filter((r) => r.training_type === catType);
    if (catStatus === "active") rows = rows.filter((r) => r.status === "active");
    if (catStatus === "archived") rows = rows.filter((r) => r.status === "archived");
    if (catSearch.trim()) {
      const q = catSearch.trim().toLowerCase();
      rows = rows.filter((r) => r.title.toLowerCase().includes(q));
    }
    return rows;
  }, [trainingsQuery.data, catType, catStatus, catSearch]);

  const activeTrainings = useMemo(
    () => (trainingsQuery.data ?? []).filter((t) => t.status === "active"),
    [trainingsQuery.data],
  );

  const activeRefs = useMemo(
    () => (refsQuery.data ?? []).filter((r) => r.status === "active"),
    [refsQuery.data],
  );

  const invalidate = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ["training"] });
  }, [qc]);

  const saveTrainingMutation = useMutation({
    mutationFn: async () => {
      const body: TrainingCatalogCreate = {
        title: formTitle.trim(),
        training_type: formType,
        provider: formProvider.trim() || null,
        duration_hours: formDuration.trim() ? Number(formDuration) : null,
        unit_cost_ht: formCost.trim() ? Number(formCost) : null,
        pedagogical_objective: formObjective.trim() || null,
        categories: formCats,
        certification_id: formCertId && formCertId !== "__none__" ? formCertId : null,
        program_url: formProgramUrl.trim() || null,
        external_link: formExternal.trim() || null,
      };
      if (editing) {
        return updateTraining(editing.id, body);
      }
      return createTraining(body);
    },
    onSuccess: () => {
      toast({ title: editing ? "Formation mise à jour" : "Formation créée" });
      setSheetOpen(false);
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

  const archiveMutation = useMutation({
    mutationFn: (id: string) => archiveTraining(id),
    onSuccess: () => {
      toast({ title: "Formation archivée" });
      setArchiveTarget(null);
      invalidate();
    },
    onError: (e: unknown) => {
      const msg =
        typeof e === "object" && e && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail)
          : "";
      toast({ variant: "destructive", title: "Erreur", description: msg || "Archivage impossible." });
    },
  });

  const enrollMutation = useMutation({
    mutationFn: () =>
      createEnrollment({
        training_id: enTrainId,
        employee_id: enEmpId,
        planned_date: enPlanned || null,
        notes: enNotes.trim() || null,
      }),
    onSuccess: (data) => {
      toast({ title: "Inscription créée" });
      setEnrollOpen(false);
      setEnTrainId("");
      setEnEmpId("");
      setEnPlanned("");
      setEnNotes("");
      invalidate();
      if (data.suggest_certification_creation && data.suggested_certification_id) {
        setCertSuggestion({
          employeeId: data.employee_id,
          certificationId: data.suggested_certification_id,
          trainingTitle: data.training_title ?? "",
        });
        toast({
          title: "Habilitation",
          description: "Cette formation est liée à un référentiel : vous pouvez créer l’habilitation.",
        });
      }
    },
    onError: (e: unknown) => {
      const msg =
        typeof e === "object" && e && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail)
          : "";
      toast({ variant: "destructive", title: "Erreur", description: msg || "Échec." });
    },
  });

  const updateEnrollMutation = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Parameters<typeof updateEnrollment>[1] }) =>
      updateEnrollment(id, body),
    onSuccess: (data) => {
      invalidate();
      if (data.suggest_certification_creation && data.suggested_certification_id) {
        setCertSuggestion({
          employeeId: data.employee_id,
          certificationId: data.suggested_certification_id,
          trainingTitle: data.training_title ?? "",
        });
        toast({
          title: "Créer l’habilitation ?",
          description: "La formation terminée est liée à un référentiel d’habilitation.",
        });
      }
    },
    onError: () => {
      toast({ variant: "destructive", title: "Erreur", description: "Mise à jour impossible." });
    },
  });

  const cancelEnrollMutation = useMutation({
    mutationFn: (id: string) => cancelEnrollment(id),
    onSuccess: () => {
      toast({ title: "Inscription annulée" });
      invalidate();
    },
  });

  const createHabMutation = useMutation({
    mutationFn: async () => {
      if (!certSuggestion) return;
      await createEmployeeCertification({
        employee_id: certSuggestion.employeeId,
        certification_id: certSuggestion.certificationId,
        obtained_date: habObtained,
        expiry_date: habExpiry || null,
        notes: habNotes.trim() || null,
      });
    },
    onSuccess: () => {
      toast({ title: "Habilitation créée" });
      setHabSheetOpen(false);
      setCertSuggestion(null);
      void qc.invalidateQueries({ queryKey: ["certifications"] });
    },
    onError: (e: unknown) => {
      const msg =
        typeof e === "object" && e && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail)
          : "";
      toast({ variant: "destructive", title: "Erreur", description: msg || "Échec." });
    },
  });

  function openCreateSheet() {
    setEditing(null);
    setFormTitle("");
    setFormType("presentiel");
    setFormProvider("");
    setFormDuration("");
    setFormCost("");
    setFormObjective("");
    setFormCats([]);
    setFormCertId("__none__");
    setFormProgramUrl("");
    setFormExternal("");
    setSheetOpen(true);
  }

  function openEditSheet(t: TrainingCatalog) {
    setEditing(t);
    setFormTitle(t.title);
    setFormType((t.training_type as TrainingType) || "presentiel");
    setFormProvider(t.provider ?? "");
    setFormDuration(t.duration_hours != null ? String(t.duration_hours) : "");
    setFormCost(t.unit_cost_ht != null ? String(t.unit_cost_ht) : "");
    setFormObjective(t.pedagogical_objective ?? "");
    setFormCats([...(t.categories ?? [])]);
    setFormCertId(t.certification_id ?? "__none__");
    setFormProgramUrl(t.program_url ?? "");
    setFormExternal(t.external_link ?? "");
    setSheetOpen(true);
  }

  function toggleCat(c: string) {
    setFormCats((prev) => (prev.includes(c) ? prev.filter((x) => x !== c) : [...prev, c]));
  }

  const loadingCat = trainingsQuery.isLoading;
  const errCat = trainingsQuery.isError;

  return (
    <div className="space-y-4">
      {certSuggestion ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-500/50 bg-amber-500/10 px-4 py-3 text-sm">
          <span>
            Formation terminée liée à une habilitation ({certSuggestion.trainingTitle || "—"}). Créer la fiche
            habilitation ?
          </span>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => {
                setHabObtained(new Date().toISOString().slice(0, 10));
                setHabExpiry("");
                setHabNotes("");
                setHabSheetOpen(true);
              }}
            >
              Créer l&apos;habilitation
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setCertSuggestion(null)}>
              Fermer
            </Button>
          </div>
        </div>
      ) : null}

      {showRhActions && consumedQuery.data ? (
        <p className="text-sm text-muted-foreground">
          Budget consommé (inscriptions planifiées / terminées, {defaultYear}) :{" "}
          <strong>{consumedQuery.data.total_ht.toFixed(2)} € HT</strong>
        </p>
      ) : null}

      <Tabs value={mainTab} onValueChange={(v) => setMainTab(v as "catalogue" | "inscriptions")}>
        <TabsList>
          <TabsTrigger value="catalogue">Catalogue</TabsTrigger>
          {showRhActions ? <TabsTrigger value="inscriptions">Inscriptions</TabsTrigger> : null}
        </TabsList>

        <TabsContent value="catalogue" className="space-y-4 pt-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="grid gap-1.5 min-w-0">
              <Label>Type</Label>
              <Select value={catType} onValueChange={setCatType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tous</SelectItem>
                  <SelectItem value="presentiel">Présentiel</SelectItem>
                  <SelectItem value="distanciel">Distanciel</SelectItem>
                  <SelectItem value="elearning">E-learning</SelectItem>
                  <SelectItem value="blended">Blended</SelectItem>
                  <SelectItem value="habilitation">Habilitation</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5 min-w-0">
              <Label>Statut catalogue</Label>
              <Select value={catStatus} onValueChange={setCatStatus}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Actif</SelectItem>
                  <SelectItem value="archived">Archivé</SelectItem>
                  <SelectItem value="all">Tous</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5 min-w-0 flex-1">
              <Label>Recherche</Label>
              <Input placeholder="Titre…" value={catSearch} onChange={(e) => setCatSearch(e.target.value)} />
            </div>
            {showRhActions ? (
              <div className="flex items-center gap-2 pb-2">
                <Checkbox
                  id="arch"
                  checked={includeArchived}
                  onCheckedChange={(c) => setIncludeArchived(Boolean(c))}
                />
                <Label htmlFor="arch">Inclure archivées (API)</Label>
              </div>
            ) : null}
            {showRhActions ? (
              <Button className="ml-auto" onClick={openCreateSheet}>
                <Plus className="mr-2 h-4 w-4" />
                Ajouter une formation
              </Button>
            ) : null}
          </div>

          {loadingCat ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Skeleton className="h-48" />
              <Skeleton className="h-48" />
              <Skeleton className="h-48" />
            </div>
          ) : errCat ? (
            <p className="text-sm text-destructive">Impossible de charger le catalogue.</p>
          ) : filteredCatalog.length === 0 ? (
            <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              Aucune formation.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {filteredCatalog.map((t) => (
                <Card key={t.id} className={cn(t.status === "archived" && "opacity-80")}>
                  <CardHeader className="space-y-2">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <CardTitle className="text-lg leading-tight">{t.title}</CardTitle>
                      {t.status === "archived" ? (
                        <Badge variant="secondary" className="line-through">
                          Archivée
                        </Badge>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap gap-1">
                      <Badge className={cn("border-0", typeBadgeClass(t.training_type))}>
                        {TYPE_LABELS[t.training_type] ?? t.training_type}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm text-muted-foreground">
                    <p>
                      <span className="font-medium text-foreground">Organisme : </span>
                      {t.provider ?? "—"}
                    </p>
                    <p>
                      <span className="font-medium text-foreground">Durée : </span>
                      {t.duration_hours != null ? `${t.duration_hours} h` : "—"}
                    </p>
                    <p>
                      <span className="font-medium text-foreground">Coût HT : </span>
                      {t.unit_cost_ht != null ? `${t.unit_cost_ht} €` : "—"}
                    </p>
                    <p>
                      <span className="font-medium text-foreground">Inscrits : </span>
                      {t.enrolled_count}
                    </p>
                    <div className="flex flex-wrap gap-2 pt-1">
                      {t.program_url ? (
                        <Button variant="link" className="h-auto p-0" asChild>
                          <a href={t.program_url} target="_blank" rel="noreferrer">
                            <FileText className="mr-1 h-3.5 w-3.5" />
                            Programme
                          </a>
                        </Button>
                      ) : null}
                      {t.external_link ? (
                        <Button variant="link" className="h-auto p-0" asChild>
                          <a href={t.external_link} target="_blank" rel="noreferrer">
                            <ExternalLink className="mr-1 h-3.5 w-3.5" />
                            Lien externe
                          </a>
                        </Button>
                      ) : null}
                    </div>
                  </CardContent>
                  {showRhActions ? (
                    <CardFooter className="flex flex-wrap gap-2 border-t pt-4">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={t.status !== "active"}
                        onClick={() => {
                          setEnTrainId(t.id);
                          setEnrollOpen(true);
                        }}
                      >
                        <UserPlus className="mr-1 h-3.5 w-3.5" />
                        Inscrire
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => openEditSheet(t)}>
                        <Pencil className="mr-1 h-3.5 w-3.5" />
                        Modifier
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={t.status === "archived"}
                        onClick={() => setArchiveTarget(t)}
                      >
                        <Archive className="mr-1 h-3.5 w-3.5" />
                        Archiver
                      </Button>
                    </CardFooter>
                  ) : null}
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {showRhActions ? (
          <TabsContent value="inscriptions" className="space-y-4 pt-4">
            <div className="flex flex-wrap items-end gap-3">
              <div className="grid gap-1.5 min-w-0">
                <Label>Formation</Label>
                <Select value={enTrain} onValueChange={setEnTrain}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Toutes</SelectItem>
                    {activeTrainings.map((t) => (
                      <SelectItem key={t.id} value={t.id}>
                        {t.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-1.5 min-w-0">
                <Label>Collaborateur</Label>
                <Select value={enEmp} onValueChange={setEnEmp}>
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
              <div className="grid gap-1.5 min-w-0">
                <Label>Statut</Label>
                <Select value={enStatus} onValueChange={setEnStatus}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Tous</SelectItem>
                    <SelectItem value="planned">Planifié</SelectItem>
                    <SelectItem value="in_progress">En cours</SelectItem>
                    <SelectItem value="completed">Terminé</SelectItem>
                    <SelectItem value="cancelled">Annulé</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <Button className="ml-auto" onClick={() => setEnrollOpen(true)}>
                <UserPlus className="mr-2 h-4 w-4" />
                Inscrire un collaborateur
              </Button>
            </div>

            {enrollmentsQuery.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : enrollmentsQuery.isError ? (
              <p className="text-sm text-destructive">Impossible de charger les inscriptions.</p>
            ) : (enrollmentsQuery.data ?? []).length === 0 ? (
              <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                Aucune inscription.
              </div>
            ) : (
              <div className="overflow-x-auto rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Collaborateur</TableHead>
                      <TableHead>Formation</TableHead>
                      <TableHead>Date planifiée</TableHead>
                      <TableHead>Statut</TableHead>
                      <TableHead>Coût</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(enrollmentsQuery.data ?? []).map((row) => {
                      const statusKey = canonicalEnrollmentStatus(row.status);
                      const selectValue = statusKey ?? row.status;
                      return (
                      <TableRow key={row.id}>
                        <TableCell>{row.employee_name ?? "—"}</TableCell>
                        <TableCell>{row.training_title ?? "—"}</TableCell>
                        <TableCell>{row.planned_date?.slice(0, 10) ?? "—"}</TableCell>
                        <TableCell>
                          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-2">
                            <Badge className={cn("w-fit shrink-0", enrollmentStatusBadgeClass(statusKey))}>
                              {statusKey
                                ? ENROLLMENT_STATUS_LABEL[statusKey]
                                : (row.status || "—")}
                            </Badge>
                          <Select
                            value={selectValue}
                            onValueChange={(v) =>
                              updateEnrollMutation.mutate({
                                id: row.id,
                                body: {
                                  status: v as "planned" | "in_progress" | "completed" | "cancelled",
                                  ...(v === "completed"
                                    ? { completion_date: new Date().toISOString().slice(0, 10) }
                                    : {}),
                                },
                              })
                            }
                          >
                            <SelectTrigger className="h-8 w-[140px]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="planned">Planifié</SelectItem>
                              <SelectItem value="in_progress">En cours</SelectItem>
                              <SelectItem value="completed">Terminé</SelectItem>
                              <SelectItem value="cancelled">Annulé</SelectItem>
                            </SelectContent>
                          </Select>
                          </div>
                        </TableCell>
                        <TableCell>
                          {row.unit_cost_ht != null ? `${row.unit_cost_ht} €` : "—"}
                        </TableCell>
                        <TableCell className="text-right">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={canonicalEnrollmentStatus(row.status) === "cancelled"}
                            onClick={() => cancelEnrollMutation.mutate(row.id)}
                          >
                            Annuler
                          </Button>
                        </TableCell>
                      </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            )}
          </TabsContent>
        ) : null}
      </Tabs>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent className="sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{editing ? "Modifier la formation" : "Nouvelle formation"}</SheetTitle>
          </SheetHeader>
          <div className="grid gap-3 py-4">
            <div className="grid gap-2">
              <Label>Titre</Label>
              <Input value={formTitle} onChange={(e) => setFormTitle(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Type</Label>
              <Select value={formType} onValueChange={(v) => setFormType(v as TrainingType)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="presentiel">Présentiel</SelectItem>
                  <SelectItem value="distanciel">Distanciel</SelectItem>
                  <SelectItem value="elearning">E-learning</SelectItem>
                  <SelectItem value="blended">Blended</SelectItem>
                  <SelectItem value="habilitation">Habilitation</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Organisme</Label>
              <Input value={formProvider} onChange={(e) => setFormProvider(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Durée (heures)</Label>
              <Input type="number" value={formDuration} onChange={(e) => setFormDuration(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Coût unitaire HT (€)</Label>
              <Input type="number" value={formCost} onChange={(e) => setFormCost(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Objectif pédagogique</Label>
              <Textarea value={formObjective} onChange={(e) => setFormObjective(e.target.value)} rows={3} />
            </div>
            <div className="grid gap-2">
              <Label>Catégories</Label>
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" type="button" className="justify-start font-normal">
                    <BookOpen className="mr-2 h-4 w-4" />
                    {formCats.length ? formCats.join(", ") : "Choisir…"}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-64 space-y-2" align="start">
                  {CATEGORY_OPTIONS.map((c) => (
                    <label key={c} className="flex items-center gap-2 text-sm">
                      <Checkbox checked={formCats.includes(c)} onCheckedChange={() => toggleCat(c)} />
                      {c}
                    </label>
                  ))}
                </PopoverContent>
              </Popover>
            </div>
            <div className="grid gap-2">
              <Label>Habilitation associée</Label>
              <Select value={formCertId} onValueChange={setFormCertId}>
                <SelectTrigger>
                  <SelectValue placeholder="Aucune" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Aucune</SelectItem>
                  {activeRefs.map((r) => (
                    <SelectItem key={r.id} value={r.id}>
                      {r.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>URL programme (PDF)</Label>
              <Input value={formProgramUrl} onChange={(e) => setFormProgramUrl(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Lien externe</Label>
              <Input value={formExternal} onChange={(e) => setFormExternal(e.target.value)} />
            </div>
          </div>
          <SheetFooter>
            <Button
              disabled={!formTitle.trim() || saveTrainingMutation.isPending}
              onClick={() => saveTrainingMutation.mutate()}
            >
              {saveTrainingMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Enregistrer"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Dialog open={enrollOpen} onOpenChange={setEnrollOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Inscrire un collaborateur</DialogTitle>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <div className="grid gap-2">
              <Label>Formation</Label>
              <Select value={enTrainId} onValueChange={setEnTrainId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent>
                  {activeTrainings.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Collaborateur</Label>
              <Select value={enEmpId} onValueChange={setEnEmpId}>
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
            <div className="grid gap-2">
              <Label>Date planifiée</Label>
              <Input type="date" value={enPlanned} onChange={(e) => setEnPlanned(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Notes</Label>
              <Textarea value={enNotes} onChange={(e) => setEnNotes(e.target.value)} rows={2} />
            </div>
          </div>
          <DialogFooter>
            <Button
              disabled={!enTrainId || !enEmpId || enrollMutation.isPending}
              onClick={() => enrollMutation.mutate()}
            >
              {enrollMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Valider"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Sheet open={habSheetOpen} onOpenChange={setHabSheetOpen}>
        <SheetContent className="sm:max-w-md">
          <SheetHeader>
            <SheetTitle>Créer l&apos;habilitation</SheetTitle>
          </SheetHeader>
          <div className="grid gap-3 py-4 text-sm">
            <p className="text-muted-foreground">
              Référentiel sélectionné automatiquement. Ajustez les dates si besoin.
            </p>
            <div className="grid gap-2">
              <Label>Date d&apos;obtention</Label>
              <Input type="date" value={habObtained} onChange={(e) => setHabObtained(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Date d&apos;expiration (optionnel)</Label>
              <Input type="date" value={habExpiry} onChange={(e) => setHabExpiry(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Notes</Label>
              <Textarea value={habNotes} onChange={(e) => setHabNotes(e.target.value)} rows={2} />
            </div>
          </div>
          <SheetFooter>
            <Button
              disabled={!certSuggestion || createHabMutation.isPending}
              onClick={() => createHabMutation.mutate()}
            >
              {createHabMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Créer"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <AlertDialog open={!!archiveTarget} onOpenChange={() => setArchiveTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archiver cette formation ?</AlertDialogTitle>
            <AlertDialogDescription>
              Impossible s&apos;il reste des inscriptions planifiées ou en cours.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Retour</AlertDialogCancel>
            <AlertDialogAction onClick={() => archiveTarget && archiveMutation.mutate(archiveTarget.id)}>
              Archiver
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
