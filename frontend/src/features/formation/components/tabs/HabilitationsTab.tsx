// Onglet Habilitations (référentiel + collaborateurs) — Pack Talent

import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, ExternalLink, Loader2, Pencil, Plus, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
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
import { getEmployeesLite } from "@/api/employees";
import {
  archiveCertificationRef,
  archiveEmployeeCertification,
  createCertificationRef,
  createEmployeeCertification,
  getCertificationRefs,
  getDashboardCounts,
  getEmployeeCertifications,
  updateCertificationRef,
  updateEmployeeCertification,
  uploadCertificateFile,
  type CertificationRef,
  type ComputedStatus,
  type EmployeeCertification,
} from "@/api/certifications";
import { cn } from "@/lib/utils";
import { isPlatformAdmin } from '@/lib/platformAdmin';

const CATEGORY_OPTIONS = [
  { value: "reglementaire", label: "Réglementaire" },
  { value: "interne", label: "Interne" },
  { value: "securite", label: "Sécurité" },
  { value: "qualite", label: "Qualité" },
  { value: "autre", label: "Autre" },
] as const;

const STATUS_FILTER_OPTIONS: { value: "all" | ComputedStatus; label: string }[] = [
  { value: "all", label: "Tous les statuts" },
  { value: "valid", label: "Valide" },
  { value: "expiring_soon", label: "Expire bientôt" },
  { value: "expired", label: "Expiré" },
  { value: "no_expiry", label: "Sans expiration" },
];

function categoryLabel(v: string) {
  return CATEGORY_OPTIONS.find((c) => c.value === v)?.label ?? v;
}

function StatusBadge({ status }: { status: ComputedStatus }) {
  const cfg: Record<ComputedStatus, { label: string; className: string }> = {
    valid: { label: "Valide", className: "border-0 bg-emerald-600 text-white hover:bg-emerald-600" },
    expiring_soon: {
      label: "Expire bientôt",
      className: "border-0 bg-orange-500 text-white hover:bg-orange-500",
    },
    expired: { label: "Expiré", className: "border-0 bg-red-600 text-white hover:bg-red-600" },
    no_expiry: {
      label: "Sans expiration",
      className: "border-0 bg-muted text-muted-foreground hover:bg-muted",
    },
  };
  const c = cfg[status];
  return <Badge className={c.className}>{c.label}</Badge>;
}

function addMonthsIso(isoDate: string, months: number): string {
  const d = new Date(`${isoDate}T12:00:00`);
  d.setMonth(d.getMonth() + months);
  return d.toISOString().slice(0, 10);
}

export type HabilitationsTabProps = {
  /** Affiche uniquement le référentiel (Paramètres). */
  referentialOnly?: boolean;
  /** Filtre par défaut : expirées + expire bientôt. */
  defaultAlertFilter?: boolean;
  /** Masque l’onglet référentiel (Conformité opérationnelle). */
  hideReferential?: boolean;
};

export default function HabilitationsTab({
  referentialOnly = false,
  defaultAlertFilter = false,
  hideReferential = false,
}: HabilitationsTabProps = {}) {
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

  const showReferentialTab = Boolean(
    isRh && !(viewOpt?.isCollaborateurRh && viewOpt.viewMode === "collaborateur"),
  );

  const [mainTab, setMainTab] = useState<"collaborateurs" | "referentiel">(
    referentialOnly ? "referentiel" : "collaborateurs",
  );

  useEffect(() => {
    if (referentialOnly) {
      setMainTab("referentiel");
      return;
    }
    if (!showReferentialTab && mainTab === "referentiel") {
      setMainTab("collaborateurs");
    }
  }, [showReferentialTab, mainTab, referentialOnly]);

  const [filterEmployeeId, setFilterEmployeeId] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<"all" | ComputedStatus>("all");
  const [alertsOnly, setAlertsOnly] = useState(defaultAlertFilter);
  const [includeArchived, setIncludeArchived] = useState(false);

  const [empSheetOpen, setEmpSheetOpen] = useState(false);
  const [empSheetMode, setEmpSheetMode] = useState<"create" | "edit" | "renew">("create");
  const [editingEmpCert, setEditingEmpCert] = useState<EmployeeCertification | null>(null);
  const [renewFromId, setRenewFromId] = useState<string | null>(null);
  const [formEmployeeId, setFormEmployeeId] = useState("");
  const [formCertificationId, setFormCertificationId] = useState("");
  const [formObtained, setFormObtained] = useState("");
  const [formExpiry, setFormExpiry] = useState("");
  const [formBody, setFormBody] = useState("");
  const [formNumber, setFormNumber] = useState("");
  const [formNotes, setFormNotes] = useState("");
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  const [refSheetOpen, setRefSheetOpen] = useState(false);
  const [refEditing, setRefEditing] = useState<CertificationRef | null>(null);
  const [refName, setRefName] = useState("");
  const [refCode, setRefCode] = useState("");
  const [refCategory, setRefCategory] = useState<string>("reglementaire");
  const [refValidityMonths, setRefValidityMonths] = useState<string>("");
  const [refAlertDays, setRefAlertDays] = useState("60");
  const [refBody, setRefBody] = useState("");
  const [refDesc, setRefDesc] = useState("");
  const [refLegal, setRefLegal] = useState("");

  const [archiveEmpTarget, setArchiveEmpTarget] = useState<EmployeeCertification | null>(null);
  const [archiveRefTarget, setArchiveRefTarget] = useState<CertificationRef | null>(null);

  const refsQuery = useQuery({
    queryKey: ["certifications", "refs"],
    queryFn: getCertificationRefs,
    enabled: isRh,
  });

  const dashboardQuery = useQuery({
    queryKey: ["certifications", "dashboard"],
    queryFn: getDashboardCounts,
    enabled: showReferentialTab,
  });

  const employeesQuery = useQuery({
    queryKey: ["certifications", "employees-lite"],
    queryFn: getEmployeesLite,
    enabled: isRh,
  });

  const employeeCertsQuery = useQuery({
    queryKey: ["certifications", "employee-certs", filterEmployeeId, includeArchived, isRh],
    queryFn: () =>
      getEmployeeCertifications({
        employee_id:
          isRh && filterEmployeeId !== "all" ? filterEmployeeId : undefined,
        include_archived: includeArchived,
      }),
  });

  const activeRefs = useMemo(
    () => (refsQuery.data ?? []).filter((r) => r.status === "active"),
    [refsQuery.data],
  );

  const filteredEmployeeCerts = useMemo(() => {
    let rows = employeeCertsQuery.data ?? [];
    if (alertsOnly) {
      rows = rows.filter(
        (r) => r.computed_status === "expired" || r.computed_status === "expiring_soon",
      );
    } else if (filterStatus !== "all") {
      rows = rows.filter((r) => r.computed_status === filterStatus);
    }
    return rows;
  }, [employeeCertsQuery.data, filterStatus, alertsOnly]);

  const openCreateEmployee = () => {
    setEmpSheetMode("create");
    setEditingEmpCert(null);
    setRenewFromId(null);
    setFormEmployeeId("");
    setFormCertificationId("");
    setFormObtained("");
    setFormExpiry("");
    setFormBody("");
    setFormNumber("");
    setFormNotes("");
    setPendingFile(null);
    setEmpSheetOpen(true);
  };

  const openEditEmployee = (row: EmployeeCertification) => {
    setEmpSheetMode("edit");
    setEditingEmpCert(row);
    setRenewFromId(null);
    setFormEmployeeId(row.employee_id);
    setFormCertificationId(row.certification_id);
    setFormObtained(row.obtained_date?.slice(0, 10) ?? "");
    setFormExpiry(row.expiry_date?.slice(0, 10) ?? "");
    setFormBody(row.certifying_body ?? "");
    setFormNumber(row.certificate_number ?? "");
    setFormNotes(row.notes ?? "");
    setPendingFile(null);
    setEmpSheetOpen(true);
  };

  const openRenewEmployee = (row: EmployeeCertification) => {
    setEmpSheetMode("renew");
    setEditingEmpCert(null);
    setRenewFromId(row.id);
    setFormEmployeeId(row.employee_id);
    setFormCertificationId(row.certification_id);
    setFormObtained("");
    setFormExpiry("");
    setFormBody(row.certifying_body ?? "");
    setFormNumber("");
    setFormNotes("");
    setPendingFile(null);
    setEmpSheetOpen(true);
  };

  useEffect(() => {
    if (!formCertificationId || !formObtained || empSheetMode === "edit") return;
    const ref = activeRefs.find((r) => r.id === formCertificationId);
    if (!ref?.validity_months) return;
    setFormExpiry(addMonthsIso(formObtained, Number(ref.validity_months)));
  }, [formCertificationId, formObtained, activeRefs, empSheetMode]);

  const invalidateAll = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ["certifications"] });
  }, [qc]);

  const saveEmployeeMutation = useMutation({
    mutationFn: async () => {
      if (!formEmployeeId || !formCertificationId || !formObtained) {
        throw new Error("Champs obligatoires manquants.");
      }
      const base = {
        employee_id: formEmployeeId,
        certification_id: formCertificationId,
        obtained_date: formObtained,
        expiry_date: formExpiry || null,
        certifying_body: formBody || null,
        certificate_number: formNumber || null,
        notes: formNotes || null,
      };
      if (empSheetMode === "edit" && editingEmpCert) {
        const updated = await updateEmployeeCertification(editingEmpCert.id, {
          certification_id: formCertificationId,
          obtained_date: formObtained,
          expiry_date: formExpiry || null,
          certifying_body: formBody || null,
          certificate_number: formNumber || null,
          notes: formNotes || null,
        });
        if (pendingFile) {
          await uploadCertificateFile(updated.id, pendingFile);
        }
        return updated;
      }
      const created = await createEmployeeCertification(base);
      if (pendingFile) {
        await uploadCertificateFile(created.id, pendingFile);
      }
      if (empSheetMode === "renew" && renewFromId) {
        await archiveEmployeeCertification(renewFromId);
      }
      return created;
    },
    onSuccess: () => {
      toast({ title: "Enregistré", description: "L’habilitation a été sauvegardée." });
      setEmpSheetOpen(false);
      invalidateAll();
    },
    onError: (e: Error) => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: e.message || "Impossible d’enregistrer.",
      });
    },
  });

  const archiveEmpMutation = useMutation({
    mutationFn: (id: string) => archiveEmployeeCertification(id),
    onSuccess: () => {
      toast({ title: "Archivé", description: "L’habilitation a été archivée." });
      setArchiveEmpTarget(null);
      invalidateAll();
    },
    onError: () => {
      toast({ variant: "destructive", title: "Erreur", description: "Archivage impossible." });
    },
  });

  const saveRefMutation = useMutation({
    mutationFn: async () => {
      if (!refName.trim()) throw new Error("L’intitulé est obligatoire.");
      const vm = refValidityMonths.trim() ? Number(refValidityMonths) : null;
      const alertDays = refAlertDays.trim() ? Number(refAlertDays) : 60;
      if (refEditing) {
        return updateCertificationRef(refEditing.id, {
          name: refName.trim(),
          code: refCode.trim() || null,
          category: refCategory,
          validity_months: vm,
          alert_days: alertDays,
          certifying_body: refBody.trim() || null,
          description: refDesc.trim() || null,
          legal_link: refLegal.trim() || null,
        });
      }
      return createCertificationRef({
        name: refName.trim(),
        code: refCode.trim() || null,
        category: refCategory,
        validity_months: vm,
        alert_days: alertDays,
        certifying_body: refBody.trim() || null,
        description: refDesc.trim() || null,
        legal_link: refLegal.trim() || null,
      });
    },
    onSuccess: () => {
      toast({ title: "Référentiel", description: "Enregistrement effectué." });
      setRefSheetOpen(false);
      invalidateAll();
    },
    onError: (e: Error) => {
      toast({
        variant: "destructive",
        title: "Erreur",
        description: e.message || "Impossible d’enregistrer.",
      });
    },
  });

  const archiveRefMutation = useMutation({
    mutationFn: (id: string) => archiveCertificationRef(id),
    onSuccess: () => {
      toast({ title: "Archivé", description: "Le référentiel a été archivé." });
      setArchiveRefTarget(null);
      invalidateAll();
    },
    onError: (e: unknown) => {
      const msg =
        typeof e === "object" && e && "response" in e
          ? String((e as { response?: { data?: { detail?: string } } }).response?.data?.detail)
          : "";
      toast({
        variant: "destructive",
        title: "Erreur",
        description: msg || "Archivage impossible.",
      });
    },
  });

  const openRefCreate = () => {
    setRefEditing(null);
    setRefName("");
    setRefCode("");
    setRefCategory("reglementaire");
    setRefValidityMonths("");
    setRefAlertDays("60");
    setRefBody("");
    setRefDesc("");
    setRefLegal("");
    setRefSheetOpen(true);
  };

  const openRefEdit = (r: CertificationRef) => {
    setRefEditing(r);
    setRefName(r.name);
    setRefCode(r.code ?? "");
    setRefCategory(r.category);
    setRefValidityMonths(r.validity_months != null ? String(r.validity_months) : "");
    setRefAlertDays(String(r.alert_days ?? 60));
    setRefBody(r.certifying_body ?? "");
    setRefDesc(r.description ?? "");
    setRefLegal(r.legal_link ?? "");
    setRefSheetOpen(true);
  };

  const onPickFile = (f: File | null) => {
    if (!f) {
      setPendingFile(null);
      return;
    }
    const allowed = ["application/pdf", "image/jpeg", "image/png"];
    if (!allowed.includes(f.type)) {
      toast({ variant: "destructive", title: "Format", description: "PDF, JPG ou PNG uniquement." });
      return;
    }
    if (f.size > 5 * 1024 * 1024) {
      toast({ variant: "destructive", title: "Taille", description: "Maximum 5 Mo." });
      return;
    }
    setPendingFile(f);
  };

  const loadingRefs = showReferentialTab && refsQuery.isLoading;
  const errorRefs = showReferentialTab && refsQuery.isError;
  const loadingCerts = employeeCertsQuery.isLoading;
  const errorCerts = employeeCertsQuery.isError;

  if (referentialOnly && !showReferentialTab) {
    return (
      <p className="text-sm text-muted-foreground">
        Le référentiel habilitations est réservé aux équipes RH.
      </p>
    );
  }

  const showRefTab = showReferentialTab && (!hideReferential || referentialOnly);
  const showCollaborateursPanel = !referentialOnly;
  const showTabBar = showCollaborateursPanel && showRefTab && !hideReferential;
  const tabsValue = referentialOnly ? "referentiel" : mainTab;

  const collaborateursPanel = showCollaborateursPanel ? (
        <div className="space-y-4 pt-2">
          {showReferentialTab && dashboardQuery.data ? (
            <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
              <span>
                Expirent bientôt :{" "}
                <strong className="text-orange-600">{dashboardQuery.data.expiring}</strong>
              </span>
              <span>
                Expirées : <strong className="text-red-600">{dashboardQuery.data.expired}</strong>
              </span>
            </div>
          ) : null}

          <div className="flex flex-col gap-3 md:flex-row md:flex-wrap md:items-end">
            {isRh ? (
              <div className="grid gap-2 min-w-0">
                <Label>Collaborateur</Label>
                <Select value={filterEmployeeId} onValueChange={setFilterEmployeeId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Tous" />
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
            ) : null}
            {alertsOnly ? (
              <Button type="button" variant="outline" onClick={() => setAlertsOnly(false)}>
                Voir tout
              </Button>
            ) : (
              <div className="grid gap-2 min-w-0">
                <Label>Statut</Label>
                <Select
                  value={filterStatus}
                  onValueChange={(v) => setFilterStatus(v as typeof filterStatus)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUS_FILTER_OPTIONS.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {defaultAlertFilter && !alertsOnly ? (
              <Button type="button" variant="secondary" onClick={() => setAlertsOnly(true)}>
                Alertes uniquement
              </Button>
            ) : null}
            <div className="flex items-center gap-2 pb-2">
              <Switch
                id="arch"
                checked={includeArchived}
                onCheckedChange={(c) => setIncludeArchived(Boolean(c))}
              />
              <Label htmlFor="arch">Inclure archivées</Label>
            </div>
            {isRh ? (
              <Button className="md:ml-auto" onClick={openCreateEmployee}>
                <Plus className="mr-2 h-4 w-4" />
                Enregistrer une habilitation
              </Button>
            ) : null}
          </div>

          {loadingCerts ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : errorCerts ? (
            <p className="text-sm text-destructive">Impossible de charger les habilitations.</p>
          ) : filteredEmployeeCerts.length === 0 ? (
            <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
              Aucune habilitation pour ces critères.
            </div>
          ) : (
            <div className="rounded-md border overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Collaborateur</TableHead>
                    <TableHead>Habilitation</TableHead>
                    <TableHead>Obtention</TableHead>
                    <TableHead>Expiration</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead>Certificat</TableHead>
                    {isRh ? <TableHead className="text-right">Actions</TableHead> : null}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredEmployeeCerts.map((row) => {
                    const label = row.certification_ref?.name ?? "—";
                    return (
                      <TableRow key={row.id}>
                        <TableCell>{row.employee_name ?? "—"}</TableCell>
                        <TableCell className="font-medium">{label}</TableCell>
                        <TableCell>{row.obtained_date?.slice(0, 10) ?? "—"}</TableCell>
                        <TableCell>{row.expiry_date?.slice(0, 10) ?? "—"}</TableCell>
                        <TableCell>
                          <StatusBadge status={row.computed_status} />
                        </TableCell>
                        <TableCell>
                          {row.certificate_url ? (
                            <Button variant="link" className="h-auto p-0" asChild>
                              <a href={row.certificate_url} target="_blank" rel="noreferrer">
                                Voir
                              </a>
                            </Button>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        {isRh ? (
                          <TableCell className="text-right space-x-1 whitespace-nowrap">
                            <Button size="sm" variant="outline" onClick={() => openEditEmployee(row)}>
                              <Pencil className="h-3.5 w-3.5 mr-1" />
                              Modifier
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => openRenewEmployee(row)}>
                              <RefreshCw className="h-3.5 w-3.5 mr-1" />
                              Renouveler
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => setArchiveEmpTarget(row)}>
                              <Archive className="h-3.5 w-3.5 mr-1" />
                              Archiver
                            </Button>
                          </TableCell>
                        ) : null}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
  ) : null;

  const referentielPanel = showRefTab ? (
          <div className="space-y-4 pt-2">
            <div className="flex justify-end">
              <Button onClick={openRefCreate}>
                <Plus className="mr-2 h-4 w-4" />
                Ajouter une habilitation
              </Button>
            </div>
            {loadingRefs ? (
              <div className="space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : errorRefs ? (
              <p className="text-sm text-destructive">Impossible de charger le référentiel.</p>
            ) : (refsQuery.data ?? []).length === 0 ? (
              <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                Aucune entrée dans le référentiel.
              </div>
            ) : (
              <div className="rounded-md border overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Intitulé</TableHead>
                      <TableHead>Code</TableHead>
                      <TableHead>Catégorie</TableHead>
                      <TableHead>Durée (mois)</TableHead>
                      <TableHead>Alerte (j)</TableHead>
                      <TableHead>Statut</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(refsQuery.data ?? []).map((r) => (
                      <TableRow key={r.id}>
                        <TableCell className="font-medium">{r.name}</TableCell>
                        <TableCell>{r.code ?? "—"}</TableCell>
                        <TableCell>{categoryLabel(r.category)}</TableCell>
                        <TableCell>{r.validity_months ?? "—"}</TableCell>
                        <TableCell>{r.alert_days}</TableCell>
                        <TableCell>
                          <Badge variant={r.status === "active" ? "default" : "secondary"}>
                            {r.status === "active" ? "Actif" : "Archivé"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right space-x-1">
                          <Button size="sm" variant="outline" onClick={() => openRefEdit(r)}>
                            <Pencil className="h-3.5 w-3.5 mr-1" />
                            Modifier
                          </Button>
                          {r.status === "active" ? (
                            <Button size="sm" variant="outline" onClick={() => setArchiveRefTarget(r)}>
                              <Archive className="h-3.5 w-3.5 mr-1" />
                              Archiver
                            </Button>
                          ) : null}
                          {r.legal_link ? (
                            <Button size="sm" variant="ghost" asChild>
                              <a href={r.legal_link} target="_blank" rel="noreferrer">
                                <ExternalLink className="h-3.5 w-3.5" />
                              </a>
                            </Button>
                          ) : null}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
  ) : null;

  return (
    <div className="space-y-4">
      {showTabBar ? (
        <Tabs
          value={tabsValue}
          onValueChange={(v) => setMainTab(v as "collaborateurs" | "referentiel")}
        >
          <TabsList className="grid h-11 w-full grid-cols-2 gap-1">
            <TabsTrigger value="collaborateurs" className="w-full">
              Habilitations collaborateurs
            </TabsTrigger>
            <TabsTrigger value="referentiel" className="w-full">
              Référentiel
            </TabsTrigger>
          </TabsList>
          <TabsContent value="collaborateurs">{collaborateursPanel}</TabsContent>
          <TabsContent value="referentiel">{referentielPanel}</TabsContent>
        </Tabs>
      ) : referentialOnly ? (
        referentielPanel
      ) : (
        collaborateursPanel
      )}

      <Sheet open={empSheetOpen} onOpenChange={setEmpSheetOpen}>
        <SheetContent className="sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>
              {empSheetMode === "edit"
                ? "Modifier l’habilitation"
                : empSheetMode === "renew"
                  ? "Renouveler l’habilitation"
                  : "Nouvelle habilitation"}
            </SheetTitle>
          </SheetHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Employé</Label>
              <Select
                value={formEmployeeId}
                onValueChange={setFormEmployeeId}
                disabled={empSheetMode === "edit"}
              >
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
              <Label>Habilitation (référentiel)</Label>
              <Select value={formCertificationId} onValueChange={setFormCertificationId}>
                <SelectTrigger>
                  <SelectValue placeholder="Choisir…" />
                </SelectTrigger>
                <SelectContent>
                  {activeRefs.map((r) => (
                    <SelectItem key={r.id} value={r.id}>
                      {r.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Date d’obtention</Label>
              <Input type="date" value={formObtained} onChange={(e) => setFormObtained(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Date d’expiration</Label>
              <Input type="date" value={formExpiry} onChange={(e) => setFormExpiry(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Organisme certificateur</Label>
              <Input value={formBody} onChange={(e) => setFormBody(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Numéro de certificat</Label>
              <Input value={formNumber} onChange={(e) => setFormNumber(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Notes</Label>
              <Input value={formNotes} onChange={(e) => setFormNotes(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Certificat (PDF, JPG, PNG — max 5 Mo)</Label>
              <Input type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => onPickFile(e.target.files?.[0] ?? null)} />
              {pendingFile ? (
                <p className="text-xs text-muted-foreground">{pendingFile.name}</p>
              ) : null}
            </div>
          </div>
          <SheetFooter>
            <Button
              disabled={saveEmployeeMutation.isPending}
              onClick={() => saveEmployeeMutation.mutate()}
            >
              {saveEmployeeMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                "Enregistrer"
              )}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <Sheet open={refSheetOpen} onOpenChange={setRefSheetOpen}>
        <SheetContent className="sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle>{refEditing ? "Modifier le référentiel" : "Nouvelle habilitation référentielle"}</SheetTitle>
          </SheetHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label>Intitulé</Label>
              <Input value={refName} onChange={(e) => setRefName(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Code interne</Label>
              <Input value={refCode} onChange={(e) => setRefCode(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Catégorie</Label>
              <Select value={refCategory} onValueChange={setRefCategory}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORY_OPTIONS.map((c) => (
                    <SelectItem key={c.value} value={c.value}>
                      {c.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Durée de validité (mois)</Label>
              <Input
                type="number"
                min={0}
                value={refValidityMonths}
                onChange={(e) => setRefValidityMonths(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label>Seuil d’alerte (jours)</Label>
              <Input type="number" min={0} value={refAlertDays} onChange={(e) => setRefAlertDays(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Organisme certificateur</Label>
              <Input value={refBody} onChange={(e) => setRefBody(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label>Description</Label>
              <Textarea value={refDesc} onChange={(e) => setRefDesc(e.target.value)} rows={3} />
            </div>
            <div className="grid gap-2">
              <Label>Lien réglementaire (URL)</Label>
              <Input value={refLegal} onChange={(e) => setRefLegal(e.target.value)} />
            </div>
          </div>
          <SheetFooter>
            <Button disabled={saveRefMutation.isPending} onClick={() => saveRefMutation.mutate()}>
              {saveRefMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Enregistrer"}
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      <AlertDialog open={!!archiveEmpTarget} onOpenChange={() => setArchiveEmpTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archiver cette habilitation ?</AlertDialogTitle>
            <AlertDialogDescription>
              Elle restera consultable si vous activez « Inclure archivées ».
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => archiveEmpTarget && archiveEmpMutation.mutate(archiveEmpTarget.id)}
            >
              Archiver
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!archiveRefTarget} onOpenChange={() => setArchiveRefTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archiver ce référentiel ?</AlertDialogTitle>
            <AlertDialogDescription>
              Impossible s’il existe des habilitations actives liées.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => archiveRefTarget && archiveRefMutation.mutate(archiveRefTarget.id)}
            >
              Archiver
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
