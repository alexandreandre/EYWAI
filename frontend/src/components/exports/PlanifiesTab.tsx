// Onglet Planifiés — envois compta & banque

import { useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Building2,
  Calculator,
  CalendarClock,
  CheckCircle2,
  Download,
  Eye,
  Play,
  Send,
} from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";
import { useToast } from "@/hooks/use-toast";
import {
  DISPATCH_STATUS_LABELS,
  dispatchBanque,
  dispatchCompta,
  getDispatchHistory,
  getDispatchSchedules,
  getDispatchStatus,
  markDispatchTransmitted,
  previewExport,
  runDispatchScheduleNow,
  upsertDispatchSchedule,
  type DispatchChannel,
  type DispatchChannelStatus,
  type DispatchHistoryEntry,
  type DispatchResultResponse,
  type DispatchSchedule,
  type DispatchStatus,
  type ExportPreviewResponse,
} from "@/api/exports";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type WizardStep = "preview" | "generating" | "result";

function currentMonthValue(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function monthOptions(): { value: string; label: string }[] {
  const options: { value: string; label: string }[] = [];
  const now = new Date();
  for (let i = -12; i <= 2; i++) {
    const date = new Date(now.getFullYear(), now.getMonth() + i, 1);
    const value = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
    const label = date.toLocaleDateString("fr-FR", { month: "long", year: "numeric" });
    options.push({ value, label: label.charAt(0).toUpperCase() + label.slice(1) });
  }
  return options;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

function formatMoney(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(value);
}

function statusBadgeVariant(status: DispatchStatus): "default" | "secondary" | "outline" | "destructive" {
  if (status === "transmitted") return "default";
  if (status === "generated") return "secondary";
  if (status === "failed") return "destructive";
  return "outline";
}

function DispatchStatusBadge({ status }: { status: DispatchStatus }) {
  return (
    <Badge variant={statusBadgeVariant(status)}>
      {DISPATCH_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

function parseEmails(raw: string): string[] {
  return raw
    .split(/[\s,;]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

interface ChannelCardProps {
  channel: DispatchChannel;
  title: string;
  description: string;
  icon: typeof Calculator;
  status: DispatchChannelStatus | undefined;
  isLoading: boolean;
  onSend: () => void;
}

function DispatchChannelCard({
  channel,
  title,
  description,
  icon: Icon,
  status,
  isLoading,
  onSend,
}: ChannelCardProps) {
  const blocked = status && !status.can_generate && status.blocking_anomalies_count > 0;
  const totalLabel =
    channel === "compta"
      ? formatMoney(status?.totals?.total_brut)
      : formatMoney(status?.totals?.total_net_a_payer);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2">
              <Icon className="h-5 w-5 text-primary" />
            </div>
            <div>
              <CardTitle className="text-lg">{title}</CardTitle>
              <CardDescription className="mt-1">{description}</CardDescription>
            </div>
          </div>
          {status ? <DispatchStatusBadge status={status.status} /> : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <Skeleton className="h-16 w-full" />
        ) : (
          <div className="text-muted-foreground grid gap-1 text-sm">
            <div>
              Salariés :{" "}
              <span className="text-foreground font-medium">
                {status?.totals?.employees_count ?? "—"}
              </span>
            </div>
            <div>
              {channel === "compta" ? "Total brut" : "Total net à payer"} :{" "}
              <span className="text-foreground font-medium">{totalLabel}</span>
            </div>
            <div>
              Dernier envoi :{" "}
              <span className="text-foreground font-medium">
                {formatDate(status?.generated_at)}
              </span>
            </div>
            {status?.status === "transmitted" ? (
              <div>
                Transmis le :{" "}
                <span className="text-foreground font-medium">
                  {formatDate(status.transmitted_at)}
                </span>
              </div>
            ) : null}
            {blocked ? (
              <p className="text-destructive text-xs">
                {status?.blocking_anomalies_count} anomalie(s) bloquante(s) — corrigez avant envoi.
              </p>
            ) : null}
          </div>
        )}

        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-block w-full">
                <Button
                  type="button"
                  className="w-full"
                  disabled={isLoading || blocked}
                  onClick={onSend}
                >
                  <Send className="mr-2 h-4 w-4" />
                  {channel === "compta" ? "Envoyer vers compta" : "Envoyer vers banque"}
                </Button>
              </span>
            </TooltipTrigger>
            {blocked ? (
              <TooltipContent>Anomalies bloquantes sur cette période</TooltipContent>
            ) : null}
          </Tooltip>
        </TooltipProvider>
      </CardContent>
    </Card>
  );
}

interface ScheduleBlockProps {
  schedule: DispatchSchedule;
  period: string;
  companyId: string;
  onSaved: () => void;
}

function DispatchScheduleBlock({ schedule, period, companyId, onSaved }: ScheduleBlockProps) {
  const { toast } = useToast();
  const [isActive, setIsActive] = useState(schedule.is_active);
  const [dayOfMonth, setDayOfMonth] = useState(schedule.day_of_month);
  const [hourUtc, setHourUtc] = useState(schedule.hour_utc);
  const [emails, setEmails] = useState(schedule.recipients.join(", "));
  const [busy, setBusy] = useState(false);

  const label = schedule.channel === "compta" ? "Comptabilité" : "Banque";

  const handleSave = async () => {
    setBusy(true);
    try {
      await upsertDispatchSchedule(companyId, schedule.channel, {
        is_active: isActive,
        day_of_month: dayOfMonth,
        hour_utc: hourUtc,
        recipients: parseEmails(emails),
      });
      toast({ title: `Planification ${label} enregistrée` });
      onSaved();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur";
      toast({ title: "Enregistrement impossible", description: msg, variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  const handleRunNow = async () => {
    setBusy(true);
    try {
      const r = await runDispatchScheduleNow(companyId, schedule.channel, period);
      toast({ title: "Export lancé", description: r.message });
      onSaved();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur";
      toast({ title: "Échec", description: msg, variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Planification auto — {label}</CardTitle>
        <CardDescription className="text-xs">
          Exécution mensuelle (UTC). Les plannings actifs sont traités automatiquement
          toutes les heures (GitHub Actions en production). Vous pouvez aussi lancer
          manuellement ci-dessous.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between">
          <Label htmlFor={`active-${schedule.channel}`}>Actif</Label>
          <Switch
            id={`active-${schedule.channel}`}
            checked={isActive}
            onCheckedChange={setIsActive}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label>Jour du mois</Label>
            <Input
              type="number"
              min={1}
              max={28}
              value={dayOfMonth}
              onChange={(e) => setDayOfMonth(parseInt(e.target.value || "5", 10))}
            />
          </div>
          <div className="space-y-1">
            <Label>Heure UTC</Label>
            <Input
              type="number"
              min={0}
              max={23}
              value={hourUtc}
              onChange={(e) => setHourUtc(parseInt(e.target.value || "6", 10))}
            />
          </div>
        </div>
        <div className="space-y-1">
          <Label>Destinataires e-mail</Label>
          <Input
            value={emails}
            onChange={(e) => setEmails(e.target.value)}
            placeholder="compta@entreprise.fr"
          />
        </div>
        {schedule.next_run_at ? (
          <p className="text-muted-foreground text-xs">
            Prochain run : {formatDate(schedule.next_run_at)} UTC
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" disabled={busy} onClick={() => void handleSave()}>
            Enregistrer
          </Button>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={busy}
            onClick={() => void handleRunNow()}
          >
            <Play className="mr-1 h-3.5 w-3.5" />
            Lancer maintenant
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

interface WizardProps {
  open: boolean;
  channel: DispatchChannel | null;
  period: string;
  companyId: string;
  onClose: () => void;
  onDone: () => void;
}

function DispatchWizardDialog({ open, channel, period, companyId, onClose, onDone }: WizardProps) {
  const { toast } = useToast();
  const [step, setStep] = useState<WizardStep>("preview");
  const [preview, setPreview] = useState<ExportPreviewResponse | null>(null);
  const [result, setResult] = useState<DispatchResultResponse | null>(null);
  const [executionDate, setExecutionDate] = useState("");
  const [paymentLabel, setPaymentLabel] = useState("");
  const [transmissionNote, setTransmissionNote] = useState("");
  const [loading, setLoading] = useState(false);

  const previewType = channel === "compta" ? "od_globale" : "virement_salaires";
  const title = channel === "compta" ? "Envoi vers compta" : "Envoi vers banque";

  const resetAndClose = () => {
    setStep("preview");
    setPreview(null);
    setResult(null);
    setTransmissionNote("");
    onClose();
  };

  const loadPreview = async () => {
    if (!channel) return;
    setLoading(true);
    try {
      const data = await previewExport({
        export_type: previewType,
        period,
        company_id: companyId,
      });
      setPreview(data);
      setStep("preview");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur";
      toast({ title: "Prévisualisation impossible", description: msg, variant: "destructive" });
      resetAndClose();
    } finally {
      setLoading(false);
    }
  };

  const handleOpenChange = (isOpen: boolean) => {
    if (isOpen && channel) {
      void loadPreview();
    } else if (!isOpen) {
      resetAndClose();
    }
  };

  const handleGenerate = async () => {
    if (!channel) return;
    setStep("generating");
    setLoading(true);
    try {
      const res =
        channel === "compta"
          ? await dispatchCompta(companyId, period)
          : await dispatchBanque(companyId, {
              period,
              execution_date: executionDate || undefined,
              payment_label: paymentLabel || undefined,
            });
      setResult(res);
      setStep("result");
      onDone();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur";
      toast({ title: "Génération impossible", description: msg, variant: "destructive" });
      setStep("preview");
    } finally {
      setLoading(false);
    }
  };

  const handleMarkTransmitted = async () => {
    if (!result?.dispatch_id) return;
    setLoading(true);
    try {
      await markDispatchTransmitted(companyId, result.dispatch_id, transmissionNote || undefined);
      toast({ title: "Envoi marqué comme transmis" });
      onDone();
      resetAndClose();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur";
      toast({ title: "Mise à jour impossible", description: msg, variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>Période {period}</DialogDescription>
        </DialogHeader>

        {loading && step !== "result" ? (
          <Skeleton className="h-32 w-full" />
        ) : null}

        {!loading && step === "preview" && preview ? (
          <div className="space-y-4">
            {channel === "banque" ? (
              <Alert className="border-orange-200 bg-orange-50 dark:bg-orange-950">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Transmission manuelle</AlertTitle>
                <AlertDescription>
                  Ce fichier ne déclenche aucun paiement automatiquement. Il doit être transmis
                  manuellement à votre banque après validation.
                </AlertDescription>
              </Alert>
            ) : (
              <p className="text-muted-foreground text-sm">
                Génération de l&apos;OD globale et du journal de paie pour la comptabilité.
              </p>
            )}

            <div className="grid gap-2 text-sm">
              <div>Salariés : {preview.employees_count}</div>
              {channel === "compta" ? (
                <div>Total brut : {formatMoney(preview.totals.total_brut)}</div>
              ) : (
                <div>Total net à payer : {formatMoney(preview.totals.total_net_a_payer)}</div>
              )}
              {preview.anomalies.length > 0 ? (
                <div className="text-destructive">
                  {preview.anomalies.length} anomalie(s) détectée(s)
                </div>
              ) : null}
            </div>

            {channel === "banque" ? (
              <div className="grid gap-3">
                <div className="space-y-1">
                  <Label>Date d&apos;exécution</Label>
                  <Input
                    type="date"
                    value={executionDate}
                    onChange={(e) => setExecutionDate(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label>Libellé de virement</Label>
                  <Input
                    value={paymentLabel}
                    onChange={(e) => setPaymentLabel(e.target.value)}
                    placeholder="Salaires juin 2026"
                  />
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {step === "generating" ? (
          <p className="text-muted-foreground py-6 text-center text-sm">Génération en cours…</p>
        ) : null}

        {step === "result" && result ? (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-400">
              <CheckCircle2 className="h-4 w-4" />
              {result.message}
            </div>
            <ul className="space-y-2">
              {result.downloads.map((d) => (
                <li key={d.export_id}>
                  <a
                    href={d.download_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary inline-flex items-center gap-1 text-sm hover:underline"
                  >
                    <Download className="h-3.5 w-3.5" />
                    {d.filename}
                  </a>
                </li>
              ))}
            </ul>
            <div className="space-y-1">
              <Label>Note de transmission (optionnel)</Label>
              <Textarea
                value={transmissionNote}
                onChange={(e) => setTransmissionNote(e.target.value)}
                rows={2}
                placeholder="Ex. déposé sur le portail comptable le 05/06"
              />
            </div>
          </div>
        ) : null}

        <DialogFooter className="gap-2 sm:gap-0">
          {step === "preview" ? (
            <>
              <Button type="button" variant="outline" onClick={resetAndClose}>
                Annuler
              </Button>
              <Button
                type="button"
                disabled={!preview?.can_generate || loading}
                onClick={() => void handleGenerate()}
              >
                <Eye className="mr-1 h-4 w-4" />
                Générer les fichiers
              </Button>
            </>
          ) : null}
          {step === "result" ? (
            <>
              <Button type="button" variant="outline" onClick={resetAndClose}>
                Fermer
              </Button>
              <Button type="button" disabled={loading} onClick={() => void handleMarkTransmitted()}>
                <Send className="mr-1 h-4 w-4" />
                Marquer comme transmis
              </Button>
            </>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DispatchHistoryTable({
  rows,
  isLoading,
}: {
  rows: DispatchHistoryEntry[];
  isLoading: boolean;
}) {
  const handleDownload = async (exportId: string) => {
    try {
      const { downloadExport } = await import("@/api/exports");
      const { download_url } = await downloadExport(exportId);
      window.open(download_url, "_blank");
    } catch {
      // ignore
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarClock className="h-5 w-5 text-muted-foreground" />
          Historique des envois
        </CardTitle>
        <CardDescription>10 derniers envois compta et banque</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : rows.length === 0 ? (
          <p className="text-muted-foreground py-6 text-center text-sm">Aucun envoi enregistré.</p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Canal</TableHead>
                  <TableHead>Période</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead>Généré le</TableHead>
                  <TableHead>Transmis le</TableHead>
                  <TableHead>Par</TableHead>
                  <TableHead className="text-right">Fichiers</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-medium capitalize">{row.channel}</TableCell>
                    <TableCell>{row.period}</TableCell>
                    <TableCell>
                      <DispatchStatusBadge status={row.status} />
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {formatDate(row.generated_at)}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {formatDate(row.transmitted_at)}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-sm">
                      {row.created_by_name ?? "—"}
                    </TableCell>
                    <TableCell className="text-right">
                      {row.export_ids[0] ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => void handleDownload(row.export_ids[0])}
                        >
                          <Download className="h-3.5 w-3.5" />
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
  );
}

export function PlanifiesTab() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? null;
  const qc = useQueryClient();
  const [period, setPeriod] = useState(currentMonthValue);
  const [wizardChannel, setWizardChannel] = useState<DispatchChannel | null>(null);

  const months = useMemo(() => monthOptions(), []);

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["dispatch-status", companyId, period] });
    void qc.invalidateQueries({ queryKey: ["dispatch-history", companyId] });
    void qc.invalidateQueries({ queryKey: ["dispatch-schedules", companyId] });
  };

  const { data: statusData, isLoading: statusLoading } = useQuery({
    queryKey: ["dispatch-status", companyId, period],
    queryFn: () => getDispatchStatus(companyId, period),
    enabled: Boolean(companyId),
  });

  const { data: historyData, isLoading: historyLoading } = useQuery({
    queryKey: ["dispatch-history", companyId],
    queryFn: () => getDispatchHistory(companyId, undefined, 10),
    enabled: Boolean(companyId),
  });

  const { data: schedulesData } = useQuery({
    queryKey: ["dispatch-schedules", companyId],
    queryFn: () => getDispatchSchedules(companyId),
    enabled: Boolean(companyId),
  });

  if (!companyId) {
    return <p className="text-muted-foreground text-sm">Sélectionnez une entreprise.</p>;
  }

  const schedules = schedulesData?.schedules ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Envois planifiés</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          Clôture paie : générez et suivez les envois vers la comptabilité et la banque. La
          transmission reste manuelle tant qu&apos;aucune intégration API n&apos;est configurée.
        </p>
      </div>

      <div className="max-w-xs space-y-2">
        <Label>Période de paie</Label>
        <Select value={period} onValueChange={setPeriod}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {months.map((m) => (
              <SelectItem key={m.value} value={m.value}>
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <DispatchChannelCard
          channel="compta"
          title="Comptabilité"
          description="OD globale + journal de paie"
          icon={Calculator}
          status={statusData?.compta}
          isLoading={statusLoading}
          onSend={() => setWizardChannel("compta")}
        />
        <DispatchChannelCard
          channel="banque"
          title="Banque"
          description="Fichier virement des salaires"
          icon={Building2}
          status={statusData?.banque}
          isLoading={statusLoading}
          onSend={() => setWizardChannel("banque")}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {schedules.map((s) => (
          <DispatchScheduleBlock
            key={s.channel}
            schedule={s}
            period={period}
            companyId={companyId}
            onSaved={invalidate}
          />
        ))}
      </div>

      <DispatchHistoryTable
        rows={historyData?.dispatches ?? []}
        isLoading={historyLoading}
      />

      <DispatchWizardDialog
        open={wizardChannel !== null}
        channel={wizardChannel}
        period={period}
        companyId={companyId}
        onClose={() => setWizardChannel(null)}
        onDone={invalidate}
      />
    </div>
  );
}
