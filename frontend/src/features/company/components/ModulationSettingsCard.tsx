import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Clock } from 'lucide-react';
import {
  applyModulationPreset,
  getModulationSettings,
  updateModulationSettings,
  type ModulationSettings,
  type ModulationSettingsUpdate,
} from '@/api/modulation';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';
import { Link } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';

export default function ModulationSettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const { data, isLoading } = useQuery({
    queryKey: queryKeys.modulationSettings(activeCompanyId),
    queryFn: getModulationSettings,
    enabled: Boolean(activeCompanyId),
  });

  const [form, setForm] = useState<ModulationSettings | null>(null);
  const [annualOpen, setAnnualOpen] = useState(true);
  const [accountOpen, setAccountOpen] = useState(true);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: (payload: ModulationSettingsUpdate) => updateModulationSettings(payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.modulationSettings(activeCompanyId), saved);
      setForm(saved);
      toast({ title: 'Enregistré', description: 'Paramètres modulation mis à jour.' });
    },
  });

  const applyPresetMutation = useMutation({
    mutationFn: () => applyModulationPreset('metallurgie_hour_account'),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.modulationSettings(activeCompanyId), saved);
      setForm(saved);
      toast({
        title: 'Preset appliqué',
        description: 'Annualisation 37/32 h et compte d\'heures (franchise 14 h HS/mois).',
      });
    },
    onError: () => {
      toast({
        title: 'Erreur',
        description: 'Impossible d\'appliquer le preset.',
        variant: 'destructive',
      });
    },
  });

  const buildPayload = (): ModulationSettingsUpdate => ({
    enabled: form!.enabled,
    weekly_high_hours: form!.weekly_high_hours,
    weekly_low_hours: form!.weekly_low_hours,
    high_weeks_per_cycle: form!.high_weeks_per_cycle,
    low_weeks_per_cycle: form!.low_weeks_per_cycle,
    average_weekly_hours: form!.average_weekly_hours,
    weekly_cap_hours: form!.weekly_cap_hours,
    pay_smoothed: form!.pay_smoothed,
    reference_period_months: form!.reference_period_months,
    hour_account_enabled: form!.hour_account_enabled,
    hs_franchise_hours_per_period: form!.hs_franchise_hours_per_period,
    hs_franchise_period: form!.hs_franchise_period,
    max_account_balance_hours: form!.max_account_balance_hours,
    recovery_absence_enabled: form!.recovery_absence_enabled,
    recovery_debit_timing: form!.recovery_debit_timing,
  });

  if (isLoading || !form) {
    return (
      <Card>
        <CardHeader><Skeleton className="h-6 w-48" /></CardHeader>
        <CardContent><Skeleton className="h-24 w-full" /></CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="h-5 w-5" />
          Modulation du temps de travail
        </CardTitle>
        <CardDescription>
          Annualisation (semaines hautes / basses) et compte d&apos;heures pour les HS différées.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Collapsible open={annualOpen} onOpenChange={setAnnualOpen}>
          <CollapsibleTrigger className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-sm font-medium">
            Annualisation du temps de travail
            <ChevronDown className={`h-4 w-4 transition-transform ${annualOpen ? 'rotate-180' : ''}`} />
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-4">
            <div className="flex items-center gap-2">
              <Switch
                checked={form.enabled}
                disabled={!canEdit}
                onCheckedChange={(v) => setForm({ ...form, enabled: v })}
              />
              <Label>Activer l&apos;annualisation</Label>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Semaine haute (h)</Label>
                <Input
                  type="number"
                  step={0.5}
                  disabled={!canEdit}
                  value={form.weekly_high_hours}
                  onChange={(e) =>
                    setForm({ ...form, weekly_high_hours: Number(e.target.value) || 37 })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Semaine basse (h)</Label>
                <Input
                  type="number"
                  step={0.5}
                  disabled={!canEdit}
                  value={form.weekly_low_hours}
                  onChange={(e) =>
                    setForm({ ...form, weekly_low_hours: Number(e.target.value) || 32 })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Semaines hautes / cycle</Label>
                <Input
                  type="number"
                  min={0}
                  disabled={!canEdit}
                  value={form.high_weeks_per_cycle}
                  onChange={(e) =>
                    setForm({ ...form, high_weeks_per_cycle: Number(e.target.value) || 1 })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Semaines basses / cycle</Label>
                <Input
                  type="number"
                  min={0}
                  disabled={!canEdit}
                  value={form.low_weeks_per_cycle}
                  onChange={(e) =>
                    setForm({ ...form, low_weeks_per_cycle: Number(e.target.value) || 1 })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Moyenne hebdo (h)</Label>
                <Input
                  type="number"
                  step={0.5}
                  disabled={!canEdit}
                  value={form.average_weekly_hours}
                  onChange={(e) =>
                    setForm({ ...form, average_weekly_hours: Number(e.target.value) || 35 })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Plafond hebdo (h)</Label>
                <Input
                  type="number"
                  step={0.5}
                  disabled={!canEdit}
                  value={form.weekly_cap_hours}
                  onChange={(e) =>
                    setForm({ ...form, weekly_cap_hours: Number(e.target.value) || 44 })
                  }
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={form.pay_smoothed}
                disabled={!canEdit}
                onCheckedChange={(v) => setForm({ ...form, pay_smoothed: v })}
              />
              <Label>Lisser la rémunération sur l&apos;année</Label>
            </div>
          </CollapsibleContent>
        </Collapsible>

        <Collapsible open={accountOpen} onOpenChange={setAccountOpen}>
          <CollapsibleTrigger className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-sm font-medium">
            Compte d&apos;heures (HS différées)
            <ChevronDown className={`h-4 w-4 transition-transform ${accountOpen ? 'rotate-180' : ''}`} />
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-4">
            <div className="flex items-center gap-2">
              <Switch
                checked={form.hour_account_enabled}
                disabled={!canEdit}
                onCheckedChange={(v) => setForm({ ...form, hour_account_enabled: v })}
              />
              <Label>Activer le compte d&apos;heures</Label>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Franchise HS / période (h)</Label>
                <Input
                  type="number"
                  step={0.5}
                  min={0}
                  disabled={!canEdit || !form.hour_account_enabled}
                  value={form.hs_franchise_hours_per_period ?? ''}
                  placeholder="ex. 14"
                  onChange={(e) =>
                    setForm({
                      ...form,
                      hs_franchise_hours_per_period:
                        e.target.value === '' ? null : Number(e.target.value),
                    })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Période de franchise</Label>
                <Select
                  disabled={!canEdit || !form.hour_account_enabled}
                  value={form.hs_franchise_period}
                  onValueChange={(v: 'month' | 'pay_period') =>
                    setForm({ ...form, hs_franchise_period: v })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="month">Mois civil</SelectItem>
                    <SelectItem value="pay_period">Période de paie</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Plafond solde compte (h)</Label>
                <Input
                  type="number"
                  step={0.5}
                  min={0}
                  disabled={!canEdit || !form.hour_account_enabled}
                  value={form.max_account_balance_hours ?? ''}
                  placeholder="Illimité"
                  onChange={(e) =>
                    setForm({
                      ...form,
                      max_account_balance_hours:
                        e.target.value === '' ? null : Number(e.target.value),
                    })
                  }
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={form.recovery_absence_enabled}
                disabled={!canEdit || !form.hour_account_enabled}
                onCheckedChange={(v) => setForm({ ...form, recovery_absence_enabled: v })}
              />
              <Label>Autoriser la récupération sur solde (absences)</Label>
            </div>
          </CollapsibleContent>
        </Collapsible>

        <div className="flex flex-wrap gap-2">
          {canEdit && (
            <Button
              disabled={saveMutation.isPending}
              onClick={() => saveMutation.mutate(buildPayload())}
            >
              Enregistrer
            </Button>
          )}
          {canEdit && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              disabled={applyPresetMutation.isPending}
              onClick={() => applyPresetMutation.mutate()}
            >
              Preset métallurgie (37/32 + compte 14 h)
            </Button>
          )}
          <Button variant="outline" size="sm" asChild>
            <Link to="/suivi-modulation">Suivi modulation</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
