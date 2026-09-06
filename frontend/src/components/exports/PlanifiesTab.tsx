// Onglet Planifiés — envois compta & banque

import { useEffect, useMemo, useState } from "react";
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
  getAccountingConfig,
  getAccountingTransmissions,
  TRANSMISSION_STATUS_LABELS,
  type AccountingTransmission,
  type TransmissionStatus,
} from "@/api/accountingIntegration";
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
import { ProviderLogo } from "@/components/integrations/ProviderLogo";
import { TransmissionStatusBadge } from "@/features/accounting-integration/components/TransmissionStatusBadge";
import { getProviderMeta } from "@/features/accounting-integration/providers";
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
import { SharkFinLoader } from "@/components/SharkFinLoader";
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
import { DispatchAnomaliesCollapsible } from "@/components/exports/DispatchAnomaliesCollapsible";
import { ExportCardRefreshOverlay } from "@/components/exports/ExportCardRefreshOverlay";
import { ScheduledExportsPanel } from "@/components/exports/ScheduledExportsPanel";
import {
  exportsLiveQueryOptions,
  exportsWizardPreviewQueryOptions,
  refreshExportsPageQueries,
} from "@/lib/exportsQuery";
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

function comptaTransmissionLabel(tx: AccountingTransmission | undefined): string | null {
  if (!tx) return null;
  const provider = getProviderMeta(tx.provider).name;
  if (tx.status === "sent" || tx.status === "acknowledged") {
    return `Transmis via ${provider}`;
  }
  if (tx.status === "queued" || tx.status === "generated") {
    return "En file de transmission";
  }
  if (tx.status === "failed") {
    return `Échec API — réessayer ou télécharger`;
  }
  if (tx.status === "manual") {
    return "Mode manuel — téléchargement disponible";
  }
  return TRANSMISSION_STATUS_LABELS[tx.status] ?? tx.status;
}

interface ChannelCardProps {
  channel: DispatchChannel;
  title: string;
  description: string;
  icon: typeof Calculator;
  status: DispatchChannelStatus | undefined;
  comptaTransmission?: AccountingTransmission;
  isLoading: boolean;
  isRefreshing?: boolean;
  onSend: () => void;
}

function DispatchChannelCard({
  channel,
  title,
  description,
  icon: Icon,
  status,
  comptaTransmission,
  isLoading,
  isRefreshing = false,
  onSend,
}: ChannelCardProps) {
  const blocked = Boolean(status && !status.can_generate);
  const totalLabel =
    channel === "compta"
      ? formatMoney(status?.totals?.total_brut)
      : formatMoney(status?.totals?.total_net_a_payer);

  return (
    <Card className="relative">
      <ExportCardRefreshOverlay
        visible={isRefreshing && !isLoading}
        label="Actualisation du statut…"
      />
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
          <SharkFinLoader
            variant="compact"
            className="min-h-[88px]"
            label="Chargement du statut…"
          />
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
            {channel === "compta" && comptaTransmission ? (
              <div className="flex flex-wrap items-center gap-2">
                <ProviderLogo providerKey={comptaTransmission.provider} size="sm" />
                <TransmissionStatusBadge status={comptaTransmission.status} />
                <span className="text-foreground text-xs">
                  {comptaTransmissionLabel(comptaTransmission)}
                </span>
              </div>
            ) : null}
            {status?.status === "transmitted" ? (
              <div>
                Transmis le :{" "}
                <span className="text-foreground font-medium">
                  {formatDate(status.transmitted_at)}
                </span>
              </div>
            ) : null}
            {blocked && status ? (
              <DispatchAnomaliesCollapsible
                channel={channel}
                anomalies={status.blocking_anomalies ?? []}
                anomaliesCount={status.blocking_anomalies_count}
                canGenerate={status.can_generate}
              />
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
              <TooltipContent>
                {status?.blocking_anomalies_count
                  ? "Anomalies bloquantes sur cette période"
                  : "Données insuffisantes pour générer l'export"}
              </TooltipContent>
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
  isRefreshing?: boolean;
  onSaved: () => void;
}

function DispatchScheduleBlock({
  schedule,
  period,
  companyId,
  isRefreshing = false,
  onSaved,
}: ScheduleBlockProps) {
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
    <Card className="relative">
      <ExportCardRefreshOverlay
        visible={isRefreshing && !busy}
        label="Actualisation de la planification…"
      />
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Planification auto — {label}</CardTitle>
        <CardDescription className="text-xs">
          Exécution mensuelle (UTC). Les plannings actifs sont traités automatiquement
          toutes les heures via l&apos;exécution automatique planifiée. Vous pouvez aussi
          lancer manuellement ci-dessous.
        </CardDescription>
      </CardHeader>
      <CardContent className="relative space-y-3">
        {busy ? (
          <div className="bg-background/80 absolute inset-0 z-10 flex items-center justify-center rounded-md backdrop-blur-[1px]">
            <SharkFinLoader variant="compact" label="Traitement en cours…" />
          </div>
        ) : null}
        <div className="flex items-center justify-between">
          <Label htmlFor={`active-${schedule.channel}`}>Actif</Label>
          <Switch
            id={`active-${schedule.channel}`}
            checked={isActive}
            onCheckedChange={setIsActive}
            disabled={busy}
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
              disabled={busy}
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
              disabled={busy}
            />
          </div>
        </div>
        <div className="space-y-1">
          <Label>Destinataires e-mail</Label>
          <Input
            value={emails}
            onChange={(e) => setEmails(e.target.value)}
            placeholder="compta@entreprise.fr"
            disabled={busy}
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
  const [result, setResult] = useState<DispatchResultResponse | null>(null);
  const [executionDate, setExecutionDate] = useState("");
  const [paymentLabel, setPaymentLabel] = useState("");
  const [transmissionNote, setTransmissionNote] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [previewErrorNotified, setPreviewErrorNotified] = useState(false);

  const previewType = channel === "compta" ? "od_globale" : "virement_salaires";
  const title = channel === "compta" ? "Envoi vers compta" : "Envoi vers banque";

  const {
    data: preview,
    isLoading: previewLoading,
    isFetching: previewFetching,
    error: previewQueryError,
  } = useQuery({
    queryKey: ["dispatch-preview", companyId, period, previewType],
    queryFn: () =>
      previewExport({
        export_type: previewType,
        period,
        company_id: companyId,
      }),
    enabled: open && Boolean(channel) && Boolean(companyId),
    ...exportsWizardPreviewQueryOptions,
  });

  const previewError =
    previewQueryError instanceof Error
      ? previewQueryError.message
      : previewQueryError
        ? "Erreur"
        : null;

  const resetAndClose = () => {
    setStep("preview");
    setResult(null);
    setTransmissionNote("");
    setPreviewErrorNotified(false);
    setActionLoading(false);
    onClose();
  };

  useEffect(() => {
    if (!open || !channel) return;
    setStep("preview");
    setResult(null);
    setPreviewErrorNotified(false);
  }, [open, channel, period, companyId, previewType]);

  useEffect(() => {
    if (!previewError || previewErrorNotified || !open) return;
    setPreviewErrorNotified(true);
    toast({
      title: "Prévisualisation impossible",
      description: previewError,
      variant: "destructive",
    });
  }, [previewError, previewErrorNotified, open, toast]);

  const handleOpenChange = (isOpen: boolean) => {
    if (!isOpen) resetAndClose();
  };

  const { data: accountingConfig } = useQuery({
    queryKey: ["accounting-integration-config", companyId],
    queryFn: () => getAccountingConfig(companyId),
    enabled: open && channel === "compta" && Boolean(companyId),
    ...exportsLiveQueryOptions,
  });

  const apiMayTransmit =
    channel === "compta" &&
    accountingConfig?.enabled &&
    accountingConfig.connection_state === "connected" &&
    !accountingConfig.force_manual &&
    accountingConfig.provider !== "manual";

  const runGenerate = async (forceManual = false) => {
    if (!channel) return;
    setStep("generating");
    setActionLoading(true);
    try {
      const res =
        channel === "compta"
          ? await dispatchCompta(companyId, period, "csv", { force_manual: forceManual })
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
      setActionLoading(false);
    }
  };

  const handleGenerate = () => void runGenerate(false);
  const handleGenerateManualOnly = () => void runGenerate(true);

  const handleMarkTransmitted = async () => {
    if (!result?.dispatch_id) return;
    setActionLoading(true);
    try {
      await markDispatchTransmitted(companyId, result.dispatch_id, transmissionNote || undefined);
      toast({ title: "Envoi marqué comme transmis" });
      onDone();
      resetAndClose();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur";
      toast({ title: "Mise à jour impossible", description: msg, variant: "destructive" });
    } finally {
      setActionLoading(false);
    }
  };

  const showPreviewLoader =
    step === "preview" &&
    (previewLoading ||
      previewFetching ||
      (open && preview === undefined && !previewError));

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>Période {period}</DialogDescription>
        </DialogHeader>

        {showPreviewLoader ? (
          <SharkFinLoader
            className="min-h-[180px]"
            label={
              channel === "compta"
                ? "Analyse comptabilité (OD, journal, FEC)…"
                : "Analyse du fichier virement…"
            }
          />
        ) : null}

        {!showPreviewLoader && step === "preview" && previewError && !preview ? (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Prévisualisation impossible</AlertTitle>
            <AlertDescription>{previewError}</AlertDescription>
          </Alert>
        ) : null}

        {!showPreviewLoader && step === "preview" && preview ? (
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
              <div className="space-y-2">
                <p className="text-muted-foreground text-sm">
                  Génération de l&apos;OD globale, du journal de paie et du FEC pour la comptabilité.
                </p>
                {apiMayTransmit ? (
                  <Alert className="border-blue-200 bg-blue-50 dark:bg-blue-950">
                    <AlertTitle>Intégration API active</AlertTitle>
                    <AlertDescription>
                      Les fichiers seront transmis automatiquement via{" "}
                      {getProviderMeta(accountingConfig?.provider ?? "manual").name}. Vous pouvez
                      forcer un envoi manuel ci-dessous.
                    </AlertDescription>
                  </Alert>
                ) : null}
              </div>
            )}

            {preview.employees_count === 0 ? (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Aucune donnée pour cette période</AlertTitle>
                <AlertDescription>
                  {channel === "compta"
                    ? "Aucun bulletin de paie validé n'a été trouvé pour cette période. Générez la paie avant de transmettre à la comptabilité."
                    : "Aucun virement à générer pour cette période. Vérifiez que la paie est générée et que les salariés ont un IBAN valide."}
                </AlertDescription>
              </Alert>
            ) : null}

            <div className="grid gap-2 text-sm">
              <div>Salariés : {preview.employees_count}</div>
              {channel === "compta" ? (
                <div>Total brut : {formatMoney(preview.totals.total_brut)}</div>
              ) : (
                <div>Total net à payer : {formatMoney(preview.totals.total_net_a_payer)}</div>
              )}
            </div>

            {preview.anomalies.length > 0 ? (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>
                  {preview.anomalies.length} anomalie(s) à corriger avant l&apos;envoi
                </AlertTitle>
                <AlertDescription>
                  <ul className="mt-1 list-disc space-y-1 pl-4">
                    {preview.anomalies.slice(0, 8).map((a, i) => (
                      <li key={`${a.employee_id ?? "x"}-${i}`}>
                        {a.employee_name ? `${a.employee_name} — ` : ""}
                        {a.message}
                      </li>
                    ))}
                    {preview.anomalies.length > 8 ? (
                      <li>… et {preview.anomalies.length - 8} autre(s)</li>
                    ) : null}
                  </ul>
                </AlertDescription>
              </Alert>
            ) : null}

            {preview.warnings.length > 0 ? (
              <Alert className="border-orange-200 bg-orange-50 dark:bg-orange-950">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Points de vigilance</AlertTitle>
                <AlertDescription>
                  <ul className="mt-1 list-disc space-y-1 pl-4">
                    {preview.warnings.slice(0, 5).map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </AlertDescription>
              </Alert>
            ) : null}

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
          <SharkFinLoader
            className="min-h-[160px]"
            label="Génération des fichiers…"
          />
        ) : null}

        {step === "result" && result ? (
          <div className="relative space-y-4">
            {actionLoading ? (
              <div className="bg-background/80 absolute inset-0 z-10 flex items-center justify-center rounded-md backdrop-blur-[1px]">
                <SharkFinLoader variant="compact" label="Enregistrement de la transmission…" />
              </div>
            ) : null}
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm text-green-700 dark:text-green-400">
                <CheckCircle2 className="h-4 w-4" />
                {result.message}
              </div>
              {channel === "compta" && result.transmission_status ? (
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  {result.transmission_provider ? (
                    <ProviderLogo providerKey={result.transmission_provider} size="sm" />
                  ) : null}
                  <TransmissionStatusBadge
                    status={result.transmission_status as TransmissionStatus}
                  />
                  {result.transmission_manual_fallback ? (
                    <span className="text-muted-foreground text-xs">
                      Repli manuel — téléchargez les fichiers ci-dessous.
                    </span>
                  ) : null}
                </div>
              ) : null}
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
          {showPreviewLoader ? (
            <Button type="button" variant="outline" onClick={resetAndClose}>
              Annuler
            </Button>
          ) : null}
          {step === "preview" && !showPreviewLoader && previewError && !preview ? (
            <Button type="button" variant="outline" onClick={resetAndClose}>
              Fermer
            </Button>
          ) : null}
          {step === "preview" && !showPreviewLoader && preview ? (
            <>
              <Button type="button" variant="outline" onClick={resetAndClose}>
                Annuler
              </Button>
              {channel === "compta" && apiMayTransmit ? (
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!preview.can_generate || actionLoading}
                  onClick={handleGenerateManualOnly}
                >
                  <Download className="mr-1 h-4 w-4" />
                  Télécharger sans transmettre
                </Button>
              ) : null}
              <Button
                type="button"
                disabled={!preview.can_generate || actionLoading}
                onClick={handleGenerate}
              >
                <Eye className="mr-1 h-4 w-4" />
                {channel === "compta" && apiMayTransmit
                  ? "Générer et transmettre"
                  : "Générer les fichiers"}
              </Button>
            </>
          ) : null}
          {step === "result" ? (
            <>
              <Button type="button" variant="outline" onClick={resetAndClose} disabled={actionLoading}>
                Fermer
              </Button>
              <Button
                type="button"
                disabled={actionLoading}
                onClick={() => void handleMarkTransmitted()}
              >
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
  isRefreshing = false,
}: {
  rows: DispatchHistoryEntry[];
  isLoading: boolean;
  isRefreshing?: boolean;
}) {
  const { toast } = useToast();

  const handleDownload = async (exportId: string) => {
    try {
      const { listExportDownloadFiles } = await import("@/api/exports");
      const files = await listExportDownloadFiles(exportId);
      if (files.length === 0) {
        throw new Error("Aucun fichier disponible");
      }
      for (const file of files) {
        window.open(file.download_url, "_blank");
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Erreur";
      toast({ title: "Téléchargement impossible", description: msg, variant: "destructive" });
    }
  };

  return (
    <Card className="relative">
      <ExportCardRefreshOverlay
        visible={isRefreshing && !isLoading}
        label="Actualisation de l'historique…"
      />
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <CalendarClock className="h-5 w-5 text-muted-foreground" />
          Historique des envois
        </CardTitle>
        <CardDescription>10 derniers envois compta et banque</CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <SharkFinLoader
            className="min-h-[180px]"
            label="Chargement de l'historique des envois…"
          />
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
                    <TableCell className="font-medium">
                      {row.channel === "compta" ? "Comptabilité" : "Banque"}
                    </TableCell>
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
                      <div className="flex justify-end gap-1">
                        {row.export_ids.map((exportId) => (
                          <Button
                            key={exportId}
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() => void handleDownload(exportId)}
                            title="Télécharger un fichier de l'envoi"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </Button>
                        ))}
                      </div>
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
    refreshExportsPageQueries(qc, companyId);
  };

  const {
    data: statusData,
    isLoading: statusLoading,
    isFetching: statusFetching,
  } = useQuery({
    queryKey: ["dispatch-status", companyId, period],
    queryFn: () => getDispatchStatus(companyId, period),
    enabled: Boolean(companyId),
    ...exportsLiveQueryOptions,
  });

  const {
    data: historyData,
    isLoading: historyLoading,
    isFetching: historyFetching,
  } = useQuery({
    queryKey: ["dispatch-history", companyId],
    queryFn: () => getDispatchHistory(companyId, undefined, 10),
    enabled: Boolean(companyId),
    ...exportsLiveQueryOptions,
  });

  const {
    data: schedulesData,
    isLoading: schedulesLoading,
    isFetching: schedulesFetching,
  } = useQuery({
    queryKey: ["dispatch-schedules", companyId],
    queryFn: () => getDispatchSchedules(companyId),
    enabled: Boolean(companyId),
    ...exportsLiveQueryOptions,
  });

  const { data: comptaTransmissions } = useQuery({
    queryKey: ["accounting-integration-transmissions", companyId, period],
    queryFn: () => getAccountingTransmissions(companyId, { period, limit: 1 }),
    enabled: Boolean(companyId),
    ...exportsLiveQueryOptions,
  });

  const comptaTransmission = comptaTransmissions?.transmissions?.[0];

  if (!companyId) {
    return <p className="text-muted-foreground text-sm">Sélectionnez une entreprise.</p>;
  }

  const schedules = schedulesData?.schedules ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Envois planifiés</h2>
        <p className="text-muted-foreground mt-1 text-sm">
          Clôture paie : générez et suivez les envois vers la comptabilité et la banque. Le mode
          manuel reste disponible à tout moment, même avec une intégration API active.
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

      <Alert>
        <AlertTitle>Quel export pour quel besoin ?</AlertTitle>
        <AlertDescription>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            <li>Clôture mensuelle paie → Comptabilité (OD + journal + FEC)</li>
            <li>Import Quadra / Sage → onglet Paie &amp; Comptabilité, formats comptables</li>
            <li>Contrôle fiscal → FEC seul</li>
            <li>Paiement salaires → Banque ou Paiements → Virement</li>
          </ul>
        </AlertDescription>
      </Alert>

      <h3 className="text-lg font-semibold">Envoi immédiat</h3>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <DispatchChannelCard
          channel="compta"
          title="Comptabilité"
          description="OD globale + journal de paie + FEC"
          icon={Calculator}
          status={statusData?.compta}
          comptaTransmission={comptaTransmission}
          isLoading={statusLoading && !statusData}
          isRefreshing={statusFetching && Boolean(statusData)}
          onSend={() => setWizardChannel("compta")}
        />
        <DispatchChannelCard
          channel="banque"
          title="Banque"
          description="Fichier virement des salaires"
          icon={Building2}
          status={statusData?.banque}
          isLoading={statusLoading && !statusData}
          isRefreshing={statusFetching && Boolean(statusData)}
          onSend={() => setWizardChannel("banque")}
        />
      </div>

      <h3 className="text-lg font-semibold">Planification automatique</h3>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {schedulesLoading ? (
          <>
            <Card>
              <CardContent className="pt-6">
                <SharkFinLoader
                  className="min-h-[200px]"
                  label="Chargement de la planification comptabilité…"
                />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <SharkFinLoader
                  className="min-h-[200px]"
                  label="Chargement de la planification banque…"
                />
              </CardContent>
            </Card>
          </>
        ) : (
          schedules.map((s) => (
            <DispatchScheduleBlock
              key={s.channel}
              schedule={s}
              period={period}
              companyId={companyId}
              isRefreshing={schedulesFetching}
              onSaved={invalidate}
            />
          ))
        )}
      </div>

      <h3 className="text-lg font-semibold">Exports planifiés par type</h3>
      <ScheduledExportsPanel />

      <h3 className="text-lg font-semibold">Historique</h3>
      <DispatchHistoryTable
        rows={historyData?.dispatches ?? []}
        isLoading={historyLoading && !historyData}
        isRefreshing={historyFetching && Boolean(historyData)}
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
