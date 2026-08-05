import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { getEmployee } from "@/api/employees";
import {
  confirmTrialPeriod,
  createTrialPeriod,
  renewTrialPeriod,
  updateTrialPeriod,
  type TrialPeriodUnit,
} from "@/api/trialPeriods";
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
import {
  formatHireDateLong,
  formatTrialPeriodEndPreview,
} from "@/lib/trialPeriodUtils";

type TrialForm = {
  enabled: boolean;
  duree_initiale: number;
  unite: TrialPeriodUnit;
  renouvellement_possible: boolean;
};

function readTrialForm(employee: Employee): TrialForm {
  const tp = employee.trial_period;
  if (!tp) {
    return {
      enabled: false,
      duree_initiale: 2,
      unite: "mois",
      renouvellement_possible: true,
    };
  }
  return {
    enabled: tp.status !== "rompue",
    duree_initiale: tp.duration_value,
    unite: tp.duration_unit,
    renouvellement_possible: tp.renewal_allowed,
  };
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso.slice(0, 10)).toLocaleDateString("fr-FR", { dateStyle: "long" });
}

function errorMessage(error: unknown, fallback: string): string {
  return (
    (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || fallback
  );
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
  const initial = useMemo(() => readTrialForm(employee), [employee]);
  const [form, setForm] = useState<TrialForm>(initial);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [renewing, setRenewing] = useState(false);
  const [renewalDate, setRenewalDate] = useState<string>("");
  const [renewalValue, setRenewalValue] = useState<number>(2);
  const [renewalUnit, setRenewalUnit] = useState<TrialPeriodUnit>("mois");

  // `initial` est mémoïsé sur `employee` : le formulaire se recale dès que la
  // fiche est rechargée après une écriture.
  useEffect(() => {
    setForm(initial);
  }, [initial]);

  const trial = employee.trial_period ?? null;

  const trialData: TrialPeriodData = {
    trial_period_applicable: employee.trial_period_applicable,
    trial_period_status: employee.trial_period_status,
    trial_period_end_date: employee.trial_period_end_date,
    trial_period_days_remaining: employee.trial_period_days_remaining,
    trial_period_renewal_possible: employee.trial_period_renewal_possible,
  };

  // La carte reste visible pour tout salarié suivi : c'est le point d'entrée
  // permettant d'activer le suivi après la création, quelle que soit son
  // ancienneté. La condition précédente la masquait passé 90 jours, soit pour
  // 239 salariés sur 241.
  const trackable =
    employee.employment_status === "actif" || employee.employment_status === "en_onboarding";

  if (!trackable) return null;

  const dirty =
    form.enabled !== initial.enabled ||
    form.duree_initiale !== initial.duree_initiale ||
    form.unite !== initial.unite ||
    form.renouvellement_possible !== initial.renouvellement_possible;

  const canConfirm = trial != null && trial.status === "en_cours";
  const canRenew =
    trial != null && trial.status === "en_cours" && trial.renewal_allowed && !trial.renewed_at;

  const endPreview =
    form.enabled && employee.hire_date
      ? formatTrialPeriodEndPreview(employee.hire_date, form.duree_initiale, form.unite)
      : null;

  const reloadEmployee = async () => {
    const fresh = await getEmployee(employee.id);
    onEmployeeUpdated(fresh);
  };

  const handleSave = async () => {
    if (form.enabled && !employee.hire_date) {
      toast({
        title: "Date d'entrée requise",
        description:
          "Renseignez d'abord la date d'entrée sur la fiche contrat pour calculer la fin de période d'essai.",
        variant: "destructive",
      });
      return;
    }

    setSaving(true);
    try {
      if (!form.enabled) {
        toast({
          title: "Suivi non désactivable",
          description:
            "Une période d'essai enregistrée se clôt en confirmant l'embauche ou en enregistrant une rupture, jamais en l'effaçant.",
          variant: "destructive",
        });
        return;
      }
      if (trial) {
        await updateTrialPeriod(trial.id, {
          duration_value: form.duree_initiale,
          duration_unit: form.unite,
          renewal_allowed: form.renouvellement_possible,
        });
      } else {
        await createTrialPeriod({
          employee_id: employee.id,
          start_date: employee.hire_date!.slice(0, 10),
          duration_value: form.duree_initiale,
          duration_unit: form.unite,
          renewal_allowed: form.renouvellement_possible,
        });
      }
      await reloadEmployee();
      toast({ title: "Période d'essai enregistrée" });
    } catch (error: unknown) {
      toast({
        title: "Erreur",
        description: errorMessage(error, "Impossible d'enregistrer la période d'essai."),
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleConfirm = async () => {
    if (!trial) return;
    setConfirming(true);
    try {
      await confirmTrialPeriod(trial.id);
      await reloadEmployee();
      toast({ title: "Embauche confirmée", description: "Le suivi de période d'essai est clos." });
    } catch (error: unknown) {
      toast({
        title: "Erreur",
        description: errorMessage(error, "Impossible de confirmer l'embauche."),
        variant: "destructive",
      });
    } finally {
      setConfirming(false);
    }
  };

  const handleRenew = async () => {
    if (!trial || !renewalDate) return;
    setRenewing(true);
    try {
      await renewTrialPeriod(trial.id, {
        renewed_at: renewalDate,
        duration_value: renewalValue,
        duration_unit: renewalUnit,
      });
      await reloadEmployee();
      toast({ title: "Renouvellement enregistré" });
    } catch (error: unknown) {
      // Le backend refuse un renouvellement notifié après le terme : son
      // message explique le refus, on le montre tel quel.
      toast({
        title: "Renouvellement refusé",
        description: errorMessage(error, "Impossible d'enregistrer le renouvellement."),
        variant: "destructive",
      });
    } finally {
      setRenewing(false);
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
        {employee.hire_date ? (
          <p className="text-sm text-muted-foreground">
            Date d&apos;entrée : {formatHireDateLong(employee.hire_date)}
          </p>
        ) : (
          <p className="text-sm text-amber-700">
            Renseignez d&apos;abord la date d&apos;entrée sur la fiche contrat pour calculer la fin
            de période d&apos;essai.
          </p>
        )}

        {trial ? (
          <p className="text-sm text-muted-foreground">
            Fin prévue le {formatDate(trial.end_date)}
            {employee.trial_period_days_remaining != null && trial.status === "en_cours"
              ? ` · J-${Math.max(0, employee.trial_period_days_remaining)}`
              : null}
          </p>
        ) : null}

        {trial?.renewed_at ? (
          <p className="text-sm text-muted-foreground">
            Renouvelée le {formatDate(trial.renewed_at)} pour {trial.renewal_duration_value}{" "}
            {trial.renewal_duration_unit} — fin repoussée au {formatDate(trial.end_date)}
          </p>
        ) : null}

        {trial?.confirmed_at ? (
          <p className="text-sm text-muted-foreground">
            Embauche confirmée le {formatDate(trial.confirmed_at)}
          </p>
        ) : null}

        <div className="space-y-4 rounded-md border border-dashed p-4">
          <div className="flex items-center justify-between gap-4">
            <Label htmlFor="trial-enabled">Activer le suivi</Label>
            <Switch
              id="trial-enabled"
              checked={form.enabled}
              disabled={trial != null}
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
                    setForm((prev) => ({ ...prev, unite: value as TrialPeriodUnit }))
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
          {endPreview ? <p className="text-sm text-muted-foreground">{endPreview}</p> : null}
        </div>

        {canRenew && (
          <div className="space-y-4 rounded-md border p-4">
            <div>
              <Label className="text-sm font-medium">Enregistrer un renouvellement</Label>
              <p className="text-xs text-muted-foreground">
                Il doit être notifié au salarié avant le terme, soit au plus tard le{" "}
                {formatDate(trial.end_date)}.
              </p>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="renewal-date">Date de décision</Label>
                <Input
                  id="renewal-date"
                  type="date"
                  value={renewalDate}
                  onChange={(e) => setRenewalDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="renewal-duration">Durée</Label>
                <Input
                  id="renewal-duration"
                  type="number"
                  min={1}
                  value={renewalValue}
                  onChange={(e) => setRenewalValue(Number(e.target.value) || 1)}
                />
              </div>
              <div className="space-y-2">
                <Label>Unité</Label>
                <Select
                  value={renewalUnit}
                  onValueChange={(value) => setRenewalUnit(value as TrialPeriodUnit)}
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
            </div>
            <Button
              type="button"
              variant="secondary"
              disabled={!renewalDate || renewing}
              onClick={() => void handleRenew()}
            >
              {renewing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Enregistrer le renouvellement
            </Button>
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="secondary"
            disabled={!dirty || saving}
            onClick={() => void handleSave()}
          >
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Enregistrer
          </Button>
          {canConfirm && (
            <Button type="button" disabled={confirming} onClick={() => void handleConfirm()}>
              {confirming ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Confirmer l&apos;embauche
            </Button>
          )}
          {trial?.status === "en_cours" && (
            <Button type="button" variant="outline" onClick={handleBreak}>
              Rompre la période d&apos;essai
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
