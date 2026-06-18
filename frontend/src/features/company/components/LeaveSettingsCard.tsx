import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getLeaveSettings,
  updateLeaveSettings,
  type LeaveSettings,
  type LeaveSettingsUpdate,
} from '@/api/leaveSettings';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';
import { CalendarRange } from 'lucide-react';

type RttMode = 'default' | 'fixed' | 'calendar' | 'forfait';

function deriveRttMode(form: LeaveSettings): RttMode {
  if (form.rtt_annual_days != null) return 'fixed';
  if (form.rtt_use_forfait_jours_formula) return 'forfait';
  if (form.rtt_use_calendar_formula) return 'calendar';
  return 'default';
}

function applyRttMode(form: LeaveSettings, mode: RttMode): LeaveSettings {
  switch (mode) {
    case 'fixed':
      return {
        ...form,
        rtt_annual_days: form.rtt_annual_days ?? form.rtt_annual_days_computed,
        rtt_use_calendar_formula: false,
        rtt_use_forfait_jours_formula: false,
      };
    case 'calendar':
      return {
        ...form,
        rtt_annual_days: null,
        rtt_use_calendar_formula: true,
        rtt_use_forfait_jours_formula: false,
      };
    case 'forfait':
      return {
        ...form,
        rtt_annual_days: null,
        rtt_use_calendar_formula: false,
        rtt_use_forfait_jours_formula: true,
      };
    default:
      return {
        ...form,
        rtt_annual_days: null,
        rtt_use_calendar_formula: false,
        rtt_use_forfait_jours_formula: false,
      };
  }
}

function buildRttPayload(form: LeaveSettings): Pick<
  LeaveSettingsUpdate,
  | 'rtt_annual_days'
  | 'rtt_use_calendar_formula'
  | 'rtt_use_forfait_jours_formula'
  | 'rtt_forfait_annual_days'
  | 'rtt_forfait_cp_ouvres_deduction'
  | 'rtt_forfait_cadres_only'
> {
  const mode = deriveRttMode(form);
  return {
    rtt_annual_days: mode === 'fixed' ? form.rtt_annual_days : null,
    rtt_use_calendar_formula: mode === 'calendar',
    rtt_use_forfait_jours_formula: mode === 'forfait',
    rtt_forfait_annual_days: form.rtt_forfait_annual_days,
    rtt_forfait_cp_ouvres_deduction: form.rtt_forfait_cp_ouvres_deduction,
    rtt_forfait_cadres_only: form.rtt_forfait_cadres_only ?? true,
  };
}

export default function LeaveSettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const currentYear = new Date().getFullYear();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.leaveSettings(activeCompanyId),
    queryFn: getLeaveSettings,
    enabled: Boolean(activeCompanyId),
  });

  const [form, setForm] = useState<LeaveSettings | null>(null);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const rttMode = form ? deriveRttMode(form) : 'default';

  const mutation = useMutation({
    mutationFn: (payload: LeaveSettingsUpdate) => updateLeaveSettings(payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.leaveSettings(activeCompanyId), saved);
      setForm(saved);
      toast({
        title: 'Enregistré',
        description: 'Paramètres congés et RTT mis à jour.',
      });
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Impossible d’enregistrer.',
        variant: 'destructive',
      });
    },
  });

  const handleSave = () => {
    if (!form) return;
    mutation.mutate({
      cp_acquisition_days_per_month: form.cp_acquisition_days_per_month,
      cp_counting_unit: form.cp_counting_unit,
      cp_carryover_enabled: form.cp_carryover_enabled,
      cp_carryover_max_days: form.cp_carryover_max_days,
      ...buildRttPayload(form),
      rtt_year_end_reminder_enabled: form.rtt_year_end_reminder_enabled,
      rtt_year_end_reminder_days_before: form.rtt_year_end_reminder_days_before,
    });
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !form) {
    return (
      <Card>
        <CardContent className="py-6 text-sm text-destructive">
          Impossible de charger les paramètres congés / RTT.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card id="conges-rtt">
      <CardHeader>
        <CardTitle className="flex items-center text-base">
          <CalendarRange className="mr-2 h-5 w-5 text-primary" />
          Congés &amp; RTT
        </CardTitle>
        <CardDescription>
          Règles d&apos;acquisition, report des CP et clôture RTT en fin d&apos;année.
          {!form.configured ? (
            <span className="mt-1 block text-amber-700">
              Valeurs par défaut (légal) — enregistrez pour activer des règles spécifiques.
            </span>
          ) : null}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>Unité d&apos;affichage CP</Label>
            <Select
              value={form.cp_counting_unit}
              disabled={!canEdit}
              onValueChange={(v) =>
                setForm((f) =>
                  f ? { ...f, cp_counting_unit: v as LeaveSettings['cp_counting_unit'] } : f,
                )
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ouvrable">Jours ouvrables (2,5 / mois)</SelectItem>
                <SelectItem value="ouvre">Jours ouvrés (25 / an ≈ 2,08 / mois)</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Affichage : {form.cp_acquisition_rate_display} j/mois —{' '}
              {form.cp_annual_days_display} j/an
            </p>
          </div>

          <div className="flex items-center justify-between gap-4 rounded-lg border p-3">
            <div>
              <Label>Report des CP (N-1 utilisable)</Label>
              <p className="text-xs text-muted-foreground">
                Les soldes N-1 sont consommés avant la période en cours.
              </p>
            </div>
            <Switch
              checked={form.cp_carryover_enabled}
              disabled={!canEdit}
              onCheckedChange={(v) =>
                setForm((f) => (f ? { ...f, cp_carryover_enabled: v } : f))
              }
            />
          </div>

          {form.cp_carryover_enabled ? (
            <div className="space-y-2">
              <Label>Plafond report CP (optionnel)</Label>
              <Input
                type="number"
                min={0}
                step={0.5}
                disabled={!canEdit}
                value={form.cp_carryover_max_days ?? ''}
                onChange={(e) =>
                  setForm((f) =>
                    f
                      ? {
                          ...f,
                          cp_carryover_max_days: e.target.value
                            ? parseFloat(e.target.value)
                            : null,
                        }
                      : f,
                  )
                }
              />
            </div>
          ) : null}
        </div>

        <div className="space-y-4 rounded-lg border p-4">
          <div className="space-y-2">
            <Label>Mode RTT annuel</Label>
            <Select
              value={rttMode}
              disabled={!canEdit}
              onValueChange={(v) =>
                setForm((f) => (f ? applyRttMode(f, v as RttMode) : f))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="default">Défaut (10 j/an)</SelectItem>
                <SelectItem value="fixed">Nombre fixe</SelectItem>
                <SelectItem value="calendar">Calendrier simple (10 ou 11 j)</SelectItem>
                <SelectItem value="forfait">Forfait jours cadres</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              Base calculée pour {currentYear} :{' '}
              <span className="font-medium tabular-nums">
                {form.rtt_annual_days_computed} j
              </span>
            </p>
          </div>

          {rttMode === 'fixed' ? (
            <div className="space-y-2">
              <Label>RTT annuels (fixe)</Label>
              <Input
                type="number"
                min={0}
                step={0.5}
                disabled={!canEdit}
                value={form.rtt_annual_days ?? ''}
                onChange={(e) =>
                  setForm((f) =>
                    f
                      ? {
                          ...f,
                          rtt_annual_days: e.target.value
                            ? parseFloat(e.target.value)
                            : null,
                        }
                      : f,
                  )
                }
              />
            </div>
          ) : null}

          {rttMode === 'forfait' ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Forfait annuel (jours)</Label>
                <Input
                  type="number"
                  min={180}
                  max={250}
                  disabled={!canEdit}
                  value={form.rtt_forfait_annual_days}
                  onChange={(e) =>
                    setForm((f) =>
                      f
                        ? {
                            ...f,
                            rtt_forfait_annual_days: parseInt(e.target.value, 10) || 214,
                          }
                        : f,
                    )
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>CP ouvrés déduits</Label>
                <Input
                  type="number"
                  min={0}
                  max={30}
                  step={0.5}
                  disabled={!canEdit}
                  value={form.rtt_forfait_cp_ouvres_deduction}
                  onChange={(e) =>
                    setForm((f) =>
                      f
                        ? {
                            ...f,
                            rtt_forfait_cp_ouvres_deduction:
                              parseFloat(e.target.value) || 25,
                          }
                        : f,
                    )
                  }
                />
              </div>
              <p className="text-xs text-muted-foreground sm:col-span-2">
                Jours ouvrés travaillables − forfait. Utilise les jours fériés observés
                de l&apos;entreprise (paramètre Jours fériés). Réservé aux forfait-jours
                si l&apos;option ci-dessous est active.
              </p>
              <div className="flex items-center gap-2 sm:col-span-2">
                <Switch
                  id="rtt-forfait-cadres-only"
                  checked={form.rtt_forfait_cadres_only ?? true}
                  disabled={!canEdit}
                  onCheckedChange={(v) =>
                    setForm((f) => (f ? { ...f, rtt_forfait_cadres_only: v } : f))
                  }
                />
                <Label htmlFor="rtt-forfait-cadres-only">
                  RTT uniquement pour les forfait-jours
                </Label>
              </div>
            </div>
          ) : null}

          <div className="flex items-center justify-between gap-4 border-t pt-4">
            <div>
              <Label>Rappel clôture RTT au 31/12</Label>
              <p className="text-xs text-muted-foreground">
                Alerte RH en décembre pour solder les RTT non posés.
              </p>
            </div>
            <Switch
              checked={form.rtt_year_end_reminder_enabled}
              disabled={!canEdit}
              onCheckedChange={(v) =>
                setForm((f) => (f ? { ...f, rtt_year_end_reminder_enabled: v } : f))
              }
            />
          </div>
        </div>

        {canEdit ? (
          <Button onClick={handleSave} disabled={mutation.isPending}>
            {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}
