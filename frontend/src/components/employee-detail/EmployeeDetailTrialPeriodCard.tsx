import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { confirmTrialPeriod, updateEmployee } from "@/api/employees";
import { TrialPeriodBadge, type TrialPeriodData } from "@/components/TrialPeriodBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
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
import { toast } from "@/components/ui/use-toast";
import type { Employee } from "@/features/employee-detail/types";

type PeriodeEssaiForm = {
  enabled: boolean;
  duree_initiale: number;
  unite: "jours" | "semaines" | "mois";
  renouvellement_possible: boolean;
};

function readPeriodeEssai(employee: Employee): PeriodeEssaiForm {
  const pe = employee.periode_essai;
  if (!pe || typeof pe !== "object") {
    return {
      enabled: false,
      duree_initiale: 2,
      unite: "mois",
      renouvellement_possible: true,
    };
  }
  const raw = pe as Record<string, unknown>;
  return {
    enabled: true,
    duree_initiale: Number(raw.duree_initiale ?? raw.duree ?? 2),
    unite: (String(raw.unite ?? "mois").startsWith("jour")
      ? "jours"
      : String(raw.unite ?? "mois").startsWith("sem")
        ? "semaines"
        : "mois") as PeriodeEssaiForm["unite"],
    renouvellement_possible: Boolean(raw.renouvellement_possible ?? true),
  };
}

function formatEndDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso.slice(0, 10)).toLocaleDateString("fr-FR", { dateStyle: "long" });
}

interface EmployeeDetailTrialPeriodCardProps {
  employee: Employee;
  onEmployeeUpdated: (employee: Employee) => void;
}

export function EmployeeDetailTrialPeriodCard({
  employee,
  onEmployeeUpdated,
}: EmployeeDetailTrialPeriodCardProps) {
  const navigate = useNavigate();
  const initial = useMemo(() => readPeriodeEssai(employee), [employee]);
  const [form, setForm] = useState<PeriodeEssaiForm>(initial);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    setForm(readPeriodeEssai(employee));
  }, [employee.id, employee.periode_essai, employee.trial_period_status]);

  const trialData: TrialPeriodData = {
    trial_period_applicable: employee.trial_period_applicable,
    trial_period_status: employee.trial_period_status,
    trial_period_end_date: employee.trial_period_end_date,
    trial_period_days_remaining: employee.trial_period_days_remaining,
    trial_period_renewal_possible: employee.trial_period_renewal_possible,
  };

  const showCard =
    employee.trial_period_applicable ||
    employee.trial_period_status === "to_complete" ||
    form.enabled;

  if (!showCard) return null;

  const dirty =
    form.enabled !== initial.enabled ||
    form.duree_initiale !== initial.duree_initiale ||
    form.unite !== initial.unite ||
    form.renouvellement_possible !== initial.renouvellement_possible;

  const canConfirm =
    employee.trial_period_status !== "confirmed" &&
    (employee.trial_period_status === "ending_soon" ||
      employee.trial_period_status === "ended" ||
      employee.trial_period_status === "in_progress");

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload = form.enabled
        ? {
            periode_essai: {
              duree_initiale: form.duree_initiale,
              unite: form.unite,
              renouvellement_possible: form.renouvellement_possible,
              statut:
                employee.trial_period_status === "confirmed"
                  ? "confirmee"
                  : "en_cours",
            },
          }
        : { periode_essai: null };
      const updated = await updateEmployee(employee.id, payload);
      onEmployeeUpdated(updated);
      toast({ title: "Période d'essai enregistrée" });
    } catch (error: unknown) {
      toast({
        title: "Erreur",
        description:
          (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          "Impossible d'enregistrer la période d'essai.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleConfirm = async () => {
    setConfirming(true);
    try {
      const updated = await confirmTrialPeriod(employee.id);
      onEmployeeUpdated(updated);
      toast({ title: "Embauche confirmée", description: "Le suivi de période d'essai est clos." });
    } catch (error: unknown) {
      toast({
        title: "Erreur",
        description:
          (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          "Impossible de confirmer l'embauche.",
        variant: "destructive",
      });
    } finally {
      setConfirming(false);
    }
  };

  const handleBreak = () => {
    navigate(
      `/employee-exits?create=1&employeeId=${encodeURIComponent(employee.id)}&exitType=fin_periode_essai`,
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0">
        <div>
          <CardTitle>Période d&apos;essai</CardTitle>
          <CardDescription>Suivi contractuel et actions RH.</CardDescription>
        </div>
        <TrialPeriodBadge data={trialData} />
      </CardHeader>
      <CardContent className="space-y-4">
        {employee.trial_period_end_date && employee.trial_period_status !== "to_complete" ? (
          <p className="text-sm text-muted-foreground">
            Fin prévue le {formatEndDate(employee.trial_period_end_date)}
            {employee.trial_period_days_remaining != null &&
            employee.trial_period_status !== "confirmed"
              ? ` · J-${Math.max(0, employee.trial_period_days_remaining)}`
              : null}
          </p>
        ) : null}

        <div className="space-y-4 rounded-md border border-dashed p-4">
          <div className="flex items-center justify-between gap-4">
            <Label htmlFor="trial-enabled">Activer le suivi</Label>
            <Switch
              id="trial-enabled"
              checked={form.enabled}
              onCheckedChange={(checked) => setForm((prev) => ({ ...prev, enabled: checked }))}
            />
          </div>
          {form.enabled && (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="trial-duration">Durée</Label>
                <Input
                  id="trial-duration"
                  type="number"
                  min={1}
                  value={form.duree_initiale}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      duree_initiale: Number(e.target.value) || 1,
                    }))
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Unité</Label>
                <Select
                  value={form.unite}
                  onValueChange={(value) =>
                    setForm((prev) => ({
                      ...prev,
                      unite: value as PeriodeEssaiForm["unite"],
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="jours">Jours</SelectItem>
                    <SelectItem value="semaines">Semaines</SelectItem>
                    <SelectItem value="mois">Mois</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-center gap-2 rounded-md border p-3 sm:mt-6">
                <Checkbox
                  id="trial-renewal"
                  checked={form.renouvellement_possible}
                  onCheckedChange={(checked) =>
                    setForm((prev) => ({
                      ...prev,
                      renouvellement_possible: checked === true,
                    }))
                  }
                />
                <Label htmlFor="trial-renewal" className="text-sm font-normal">
                  Renouvellement possible
                </Label>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="secondary" disabled={!dirty || saving} onClick={() => void handleSave()}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Enregistrer
          </Button>
          {canConfirm && (
            <Button type="button" disabled={confirming} onClick={() => void handleConfirm()}>
              {confirming ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Confirmer l&apos;embauche
            </Button>
          )}
          {employee.trial_period_status !== "confirmed" && form.enabled && (
            <Button type="button" variant="outline" onClick={handleBreak}>
              Rompre la période d&apos;essai
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
