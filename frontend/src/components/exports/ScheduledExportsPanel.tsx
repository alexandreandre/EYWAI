import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Play, Trash2 } from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";
import { useToast } from "@/hooks/use-toast";
import {
  SCHEDULABLE_EXPORT_TYPES,
  SCHEDULED_EXPORT_TYPE_LABELS,
  createScheduledExport,
  deleteScheduledExport,
  getScheduledExports,
  runScheduledExportNow,
  type ExportType,
  type ScheduledExportCreate,
  type ScheduledExportFrequency,
} from "@/api/exports";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";

export function ScheduledExportsPanel() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? null;
  const { toast } = useToast();
  const qc = useQueryClient();

  const [name, setName] = useState("");
  const [exportType, setExportType] = useState<ExportType>("journal_paie");
  const [frequency, setFrequency] = useState<ScheduledExportFrequency>("monthly");
  const [dayOfMonth, setDayOfMonth] = useState(5);
  const [hourUtc, setHourUtc] = useState(6);
  const [recipients, setRecipients] = useState("");

  const { data: schedules, isLoading } = useQuery({
    queryKey: ["scheduled-exports", companyId],
    queryFn: () => getScheduledExports(companyId),
    enabled: Boolean(companyId),
  });

  const invalidate = () => {
    void qc.invalidateQueries({ queryKey: ["scheduled-exports", companyId] });
  };

  const createMutation = useMutation({
    mutationFn: (body: ScheduledExportCreate) => createScheduledExport(companyId, body),
    onSuccess: () => {
      toast({ title: "Export planifié créé" });
      setName("");
      invalidate();
    },
    onError: (e: Error) => {
      toast({ title: "Erreur", description: e.message, variant: "destructive" });
    },
  });

  if (!companyId) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-lg">
          <CalendarClock className="h-5 w-5" />
          Exports planifiés par type
        </CardTitle>
        <CardDescription>
          Planifiez la génération automatique d&apos;exports paie (journal, OD, FEC, DSN…).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-1">
            <Label>Nom</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Journal mensuel" />
          </div>
          <div className="space-y-1">
            <Label>Type d&apos;export</Label>
            <Select value={exportType} onValueChange={(v) => setExportType(v as ExportType)}>
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
          <div className="space-y-1">
            <Label>Fréquence</Label>
            <Select
              value={frequency}
              onValueChange={(v) => setFrequency(v as ScheduledExportFrequency)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="monthly">Mensuel</SelectItem>
                <SelectItem value="weekly">Hebdomadaire</SelectItem>
                <SelectItem value="daily">Quotidien</SelectItem>
              </SelectContent>
            </Select>
          </div>
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
          <div className="space-y-1">
            <Label>Destinataires e-mail</Label>
            <Input
              value={recipients}
              onChange={(e) => setRecipients(e.target.value)}
              placeholder="rh@entreprise.fr"
            />
          </div>
        </div>
        <Button
          type="button"
          disabled={!name.trim() || createMutation.isPending}
          onClick={() =>
            createMutation.mutate({
              name: name.trim(),
              export_type: exportType,
              frequency,
              day_of_month: dayOfMonth,
              hour_utc: hourUtc,
              recipients: recipients
                .split(/[\s,;]+/)
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
        >
          Ajouter une planification
        </Button>

        {isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (schedules ?? []).length === 0 ? (
          <p className="text-muted-foreground text-sm">Aucun export planifié.</p>
        ) : (
          <ul className="space-y-3">
            {(schedules ?? []).map((s) => (
              <li
                key={s.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3"
              >
                <div>
                  <p className="font-medium">{s.name}</p>
                  <p className="text-muted-foreground text-sm">
                    {s.export_type_label} — {s.frequency_label}
                    {s.next_run_at ? ` — prochain : ${new Date(s.next_run_at).toLocaleString("fr-FR")}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Switch checked={s.is_active} disabled aria-readonly />
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    onClick={async () => {
                      try {
                        const r = await runScheduledExportNow(s.id, companyId);
                        toast({ title: "Export lancé", description: r.message });
                        invalidate();
                      } catch (e: unknown) {
                        toast({
                          title: "Échec",
                          description: e instanceof Error ? e.message : "Erreur",
                          variant: "destructive",
                        });
                      }
                    }}
                  >
                    <Play className="mr-1 h-3.5 w-3.5" />
                    Lancer
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={async () => {
                      try {
                        await deleteScheduledExport(s.id, companyId);
                        toast({ title: "Planification supprimée" });
                        invalidate();
                      } catch (e: unknown) {
                        toast({
                          title: "Erreur",
                          description: e instanceof Error ? e.message : "Erreur",
                          variant: "destructive",
                        });
                      }
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
