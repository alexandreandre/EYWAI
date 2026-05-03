// src/pages/Exports.tsx
// Onglet RH "Exports" — Paie, déclarations, historique, exports planifiés

import { useState, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, Calculator, Receipt, Users, History, CalendarClock, Play, Trash2 } from "lucide-react";
import { useHasActiveCompanyRhAccess, useCompany } from "@/contexts/CompanyContext";
import { Navigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { useToast } from "@/hooks/use-toast";
import {
  SCHEDULABLE_EXPORT_TYPES,
  SCHEDULED_EXPORT_TYPE_LABELS,
  createScheduledExport,
  deleteScheduledExport,
  getScheduledExportHistory,
  getScheduledExports,
  runScheduledExportNow,
  updateScheduledExport,
  type ExportHistoryEntry,
  type ScheduledExport,
  type ScheduledExportCreate,
  type ScheduledExportFrequency,
} from "@/api/exports";

// Composants des sous-onglets
import { PaieComptabiliteTab } from "@/components/exports/PaieComptabiliteTab";
import { DeclarationsTab } from "@/components/exports/DeclarationsTab";
import { PaiementsTab } from "@/components/exports/PaiementsTab";
import { ExportsRhTab } from "@/components/exports/ExportsRhTab";
import { ExportHistory } from "@/components/exports/ExportHistory";

const WEEKDAYS: { value: number; label: string }[] = [
  { value: 0, label: "Lundi" },
  { value: 1, label: "Mardi" },
  { value: 2, label: "Mercredi" },
  { value: 3, label: "Jeudi" },
  { value: 4, label: "Vendredi" },
  { value: 5, label: "Samedi" },
  { value: 6, label: "Dimanche" },
];

function parseRecipientEmails(raw: string): string[] {
  return raw
    .split(/[\s,;]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function formatUtcDt(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fr-FR", { timeZone: "UTC" }) + " UTC";
  } catch {
    return iso;
  }
}

function ScheduledExportsTab() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? null;
  const qc = useQueryClient();
  const { toast } = useToast();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyForId, setHistoryForId] = useState<string | null>(null);
  const [historyRows, setHistoryRows] = useState<ExportHistoryEntry[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [formName, setFormName] = useState("");
  const [formType, setFormType] = useState<string>(SCHEDULABLE_EXPORT_TYPES[0]);
  const [formFreq, setFormFreq] = useState<ScheduledExportFrequency>("monthly");
  const [formDow, setFormDow] = useState(0);
  const [formDom, setFormDom] = useState(1);
  const [formHour, setFormHour] = useState(6);
  const [formEmails, setFormEmails] = useState("");

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["scheduled-exports", companyId],
    queryFn: () => getScheduledExports(companyId),
    enabled: Boolean(companyId),
  });

  const resetForm = () => {
    setFormName("");
    setFormType(SCHEDULABLE_EXPORT_TYPES[0]);
    setFormFreq("monthly");
    setFormDow(0);
    setFormDom(1);
    setFormHour(6);
    setFormEmails("");
  };

  const openHistory = async (scheduleId: string) => {
    setHistoryForId(scheduleId);
    setHistoryOpen(true);
    setHistoryLoading(true);
    setHistoryRows([]);
    try {
      const res = await getScheduledExportHistory(scheduleId, companyId);
      setHistoryRows(res.exports);
    } catch {
      toast({ title: "Historique", description: "Chargement impossible.", variant: "destructive" });
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!companyId) return;
    const name = formName.trim();
    if (!name) {
      toast({ title: "Nom requis", variant: "destructive" });
      return;
    }
    const body: ScheduledExportCreate = {
      name,
      export_type: formType,
      frequency: formFreq,
      hour_utc: Math.min(23, Math.max(0, formHour)),
      recipients: parseRecipientEmails(formEmails),
    };
    if (formFreq === "weekly") body.day_of_week = formDow;
    if (formFreq === "monthly") body.day_of_month = Math.min(28, Math.max(1, formDom));

    try {
      await createScheduledExport(companyId, body);
      toast({ title: "Planning créé" });
      setDialogOpen(false);
      resetForm();
      void qc.invalidateQueries({ queryKey: ["scheduled-exports", companyId] });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur";
      toast({ title: "Création impossible", description: msg, variant: "destructive" });
    }
  };

  const toggleActive = async (row: ScheduledExport, checked: boolean) => {
    if (!companyId) return;
    setBusyId(row.id);
    try {
      await updateScheduledExport(row.id, companyId, { is_active: checked });
      void refetch();
    } catch {
      toast({ title: "Mise à jour impossible", variant: "destructive" });
    } finally {
      setBusyId(null);
    }
  };

  const handleRunNow = async (id: string) => {
    if (!companyId) return;
    setBusyId(id);
    try {
      const r = await runScheduledExportNow(id, companyId);
      toast({ title: "Export lancé", description: r.message });
      void qc.invalidateQueries({ queryKey: ["scheduled-exports", companyId] });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur";
      toast({ title: "Échec", description: msg, variant: "destructive" });
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    if (!companyId || !deleteId) return;
    setBusyId(deleteId);
    try {
      await deleteScheduledExport(deleteId, companyId);
      toast({ title: "Planning supprimé" });
      setDeleteId(null);
      void refetch();
    } catch {
      toast({ title: "Suppression impossible", variant: "destructive" });
    } finally {
      setBusyId(null);
    }
  };

  if (!companyId) {
    return (
      <p className="text-muted-foreground text-sm">Sélectionnez une entreprise.</p>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-semibold">Exports planifiés</h2>
          <p className="text-muted-foreground text-sm">
            Déclenchements automatiques (UTC). L’envoi par e-mail aux destinataires pourra être branché
            sur un worker ultérieurement.
          </p>
        </div>
        <Button type="button" onClick={() => setDialogOpen(true)}>
          Nouveau planning d&apos;export
        </Button>
      </div>

      {isLoading ? (
        <div className="grid gap-4 md:grid-cols-2">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      ) : !data?.length ? (
        <Card>
          <CardContent className="text-muted-foreground py-10 text-center text-sm">
            Aucun export planifié
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {data.map((row) => (
            <Card key={row.id}>
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base">{row.name}</CardTitle>
                  <div className="flex items-center gap-2">
                    <span className="text-muted-foreground text-xs">Actif</span>
                    <Switch
                      checked={row.is_active}
                      disabled={busyId === row.id || isFetching}
                      onCheckedChange={(v) => void toggleActive(row, v)}
                    />
                  </div>
                </div>
                <CardDescription className="flex flex-wrap gap-2">
                  <Badge variant="secondary">{row.export_type_label}</Badge>
                  <Badge variant="outline">{row.frequency_label}</Badge>
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="text-muted-foreground grid gap-1">
                  <div>
                    Prochain :{" "}
                    <span className="text-foreground font-medium">
                      {formatUtcDt(row.next_run_at)}
                    </span>
                  </div>
                  <div>
                    Dernier :{" "}
                    <span className="text-foreground font-medium">
                      {formatUtcDt(row.last_run_at)}
                    </span>
                  </div>
                  {row.recipients?.length ? (
                    <div className="truncate" title={row.recipients.join(", ")}>
                      Destinataires : {row.recipients.join(", ")}
                    </div>
                  ) : null}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={busyId === row.id}
                    onClick={() => void handleRunNow(row.id)}
                  >
                    <Play className="mr-1 h-3.5 w-3.5" />
                    Lancer maintenant
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => void openHistory(row.id)}
                  >
                    Historique
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="text-destructive hover:text-destructive"
                    onClick={() => setDeleteId(row.id)}
                  >
                    <Trash2 className="mr-1 h-3.5 w-3.5" />
                    Supprimer
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Nouveau planning d&apos;export</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="space-y-2">
              <Label>Nom</Label>
              <Input value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="Ex. Journal paie — fin de mois" />
            </div>
            <div className="space-y-2">
              <Label>Type d&apos;export</Label>
              <Select value={formType} onValueChange={setFormType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SCHEDULABLE_EXPORT_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {SCHEDULED_EXPORT_TYPE_LABELS[t] ?? t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Fréquence</Label>
              <Select
                value={formFreq}
                onValueChange={(v) => setFormFreq(v as ScheduledExportFrequency)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="daily">Quotidien</SelectItem>
                  <SelectItem value="weekly">Hebdomadaire</SelectItem>
                  <SelectItem value="monthly">Mensuel</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {formFreq === "weekly" ? (
              <div className="space-y-2">
                <Label>Jour de la semaine</Label>
                <Select value={String(formDow)} onValueChange={(v) => setFormDow(parseInt(v, 10))}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {WEEKDAYS.map((d) => (
                      <SelectItem key={d.value} value={String(d.value)}>
                        {d.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}
            {formFreq === "monthly" ? (
              <div className="space-y-2">
                <Label>Jour du mois (1–28)</Label>
                <Input
                  type="number"
                  min={1}
                  max={28}
                  value={formDom}
                  onChange={(e) => setFormDom(parseInt(e.target.value || "1", 10))}
                />
              </div>
            ) : null}
            <div className="space-y-2">
              <Label>Heure UTC (0–23)</Label>
              <Input
                type="number"
                min={0}
                max={23}
                value={formHour}
                onChange={(e) => setFormHour(parseInt(e.target.value || "0", 10))}
              />
            </div>
            <div className="space-y-2">
              <Label>Destinataires (e-mails, séparés par virgule ou retour ligne)</Label>
              <Textarea
                value={formEmails}
                onChange={(e) => setFormEmails(e.target.value)}
                rows={3}
                placeholder="rh@entreprise.fr"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
              Annuler
            </Button>
            <Button type="button" onClick={() => void handleCreate()}>
              Confirmer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>10 derniers exports ({historyForId?.slice(0, 8)}…)</DialogTitle>
          </DialogHeader>
          {historyLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : (
            <ul className="text-muted-foreground max-h-64 space-y-2 overflow-auto text-xs">
              {historyRows.length === 0 ? (
                <li>Aucune entrée dans l&apos;historique pour ce type.</li>
              ) : (
                historyRows.map((h) => (
                  <li key={h.id} className="border-b pb-1">
                    <span className="text-foreground font-medium">{h.period}</span> —{" "}
                    {new Date(h.generated_at).toLocaleString("fr-FR")} — {h.status}
                  </li>
                ))
              )}
            </ul>
          )}
        </DialogContent>
      </Dialog>

      <AlertDialog open={Boolean(deleteId)} onOpenChange={(o) => !o && setDeleteId(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce planning ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action est définitive. Les exports déjà générés restent dans l&apos;historique.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => void confirmDelete()}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function Exports() {
  const hasRhAccess = useHasActiveCompanyRhAccess();
  const [activeTab, setActiveTab] = useState("paie-comptabilite");
  const [historyFilter, setHistoryFilter] = useState<string | undefined>(undefined);

  useEffect(() => {
    window.scrollTo(0, 0);
    if (activeTab !== "historique") {
      setHistoryFilter(undefined);
    }
  }, [activeTab]);

  if (!hasRhAccess) {
    return <Navigate to="/" replace />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Exports</h1>
        <p className="text-muted-foreground mt-2">
          Centre de production réglementaire pour transmettre des données à la comptabilité,
          produire des déclarations sociales et extraire des tableaux RH complets et auditables.
        </p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid h-auto w-full grid-cols-2 gap-1 sm:grid-cols-3 lg:grid-cols-6">
          <TabsTrigger value="paie-comptabilite" className="flex items-center gap-2 text-xs sm:text-sm">
            <Calculator className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Paie & Comptabilité</span>
            <span className="sm:hidden">Paie</span>
          </TabsTrigger>
          <TabsTrigger value="declarations" className="flex items-center gap-2 text-xs sm:text-sm">
            <FileText className="h-4 w-4 shrink-0" />
            Déclarations
          </TabsTrigger>
          <TabsTrigger value="paiements" className="flex items-center gap-2 text-xs sm:text-sm">
            <Receipt className="h-4 w-4 shrink-0" />
            Paiements
          </TabsTrigger>
          <TabsTrigger value="exports-rh" className="flex items-center gap-2 text-xs sm:text-sm">
            <Users className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Exports RH</span>
            <span className="sm:hidden">RH</span>
          </TabsTrigger>
          <TabsTrigger value="planifies" className="flex items-center gap-2 text-xs sm:text-sm">
            <CalendarClock className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Planifiés</span>
            <span className="sm:hidden">Planif.</span>
          </TabsTrigger>
          <TabsTrigger value="historique" className="flex items-center gap-2 text-xs sm:text-sm">
            <History className="h-4 w-4 shrink-0" />
            <span className="hidden sm:inline">Historique</span>
            <span className="sm:hidden">Hist.</span>
          </TabsTrigger>
        </TabsList>

        <TabsContent value="paie-comptabilite" className="space-y-6 mt-6">
          <PaieComptabiliteTab />
        </TabsContent>

        <TabsContent value="declarations" className="space-y-6 mt-6">
          <DeclarationsTab />
        </TabsContent>

        <TabsContent value="paiements" className="space-y-6 mt-6">
          <PaiementsTab />
        </TabsContent>

        <TabsContent value="exports-rh" className="space-y-6 mt-6">
          <ExportsRhTab />
        </TabsContent>

        <TabsContent value="planifies" className="space-y-6 mt-6">
          <ScheduledExportsTab />
        </TabsContent>

        <TabsContent value="historique" className="space-y-6 mt-6">
          <ExportHistory exportType={historyFilter} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
