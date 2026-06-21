import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ChevronDown, Clock } from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  applyModulationPreset,
  getModulationSettings,
  updateModulationSettings,
  type HsRoutingPolicy,
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

const HS_POLICY_LABELS: Record<HsRoutingPolicy, string> = {
  pay_all: 'Tout payer au bulletin',
  account_all: 'Tout mettre au compteur',
  franchise: 'Franchise (plafond par période)',
  manual: 'Validation RH mensuelle',
};

const PRESETS = [
  { id: 'standard', label: 'Standard (HS payées)' },
  { id: 'metallurgie_hour_account', label: 'Métallurgie annualisée' },
  { id: 'hour_account_only', label: 'Compte HS sans modulation' },
] as const;

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
  const [annualOpen, setAnnualOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(true);
  const [policyOpen, setPolicyOpen] = useState(true);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: (payload: ModulationSettingsUpdate) => updateModulationSettings(payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.modulationSettings(activeCompanyId), saved);
      setForm(saved);
      toast({ title: 'Enregistré', description: 'Paramètres temps de travail mis à jour.' });
    },
    onError: (err: Error) => {
      toast({
        title: 'Erreur',
        description: err.message || 'Enregistrement impossible.',
        variant: 'destructive',
      });
    },
  });

  const applyPresetMutation = useMutation({
    mutationFn: (preset: string) => applyModulationPreset(preset),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.modulationSettings(activeCompanyId), saved);
      setForm(saved);
      toast({ title: 'Preset appliqué', description: 'Configuration mise à jour.' });
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
    hs_routing_policy: form!.hs_routing_policy,
  });

  const needsHourAccount =
    form?.hs_routing_policy === 'account_all' ||
    form?.hs_routing_policy === 'franchise' ||
    form?.hs_routing_policy === 'manual';

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
          Temps de travail et heures supplémentaires
        </CardTitle>
        <CardDescription>
          L&apos;accord de modulation, le compte d&apos;heures et la politique HS sont indépendants.
          Configurez chaque axe selon votre entreprise.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Collapsible open={policyOpen} onOpenChange={setPolicyOpen}>
          <CollapsibleTrigger className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-sm font-medium">
            Politique de routage des HS
            <ChevronDown className={`h-4 w-4 transition-transform ${policyOpen ? 'rotate-180' : ''}`} />
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-4">
            <div className="space-y-2">
              <Label>Traitement des heures supplémentaires</Label>
              <Select
                disabled={!canEdit}
                value={form.hs_routing_policy}
                onValueChange={(v: HsRoutingPolicy) => {
                  const next = { ...form, hs_routing_policy: v };
                  if (v !== 'pay_all' && !next.hour_account_enabled) {
                    next.hour_account_enabled = true;
                  }
                  setForm(next);
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(HS_POLICY_LABELS) as HsRoutingPolicy[]).map((key) => (
                    <SelectItem key={key} value={key}>
                      {HS_POLICY_LABELS[key]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {needsHourAccount && !form.hour_account_enabled && (
              <p className="text-xs text-amber-700 dark:text-amber-400">
                Cette politique nécessite le compte d&apos;heures (activé automatiquement à l&apos;enregistrement).
              </p>
            )}
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
                  disabled={!canEdit || !form.hour_account_enabled || form.hs_routing_policy !== 'franchise'}
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
                <Label>Plafond solde compte (h)</Label>
                <Input
                  type="number"
                  step={0.5}
                  min={0}
                  disabled={!canEdit || !form.hour_account_enabled || form.hs_routing_policy === 'account_all'}
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

        <Collapsible open={annualOpen} onOpenChange={setAnnualOpen}>
          <CollapsibleTrigger className="flex w-full items-center justify-between rounded-md border px-3 py-2 text-sm font-medium">
            Annualisation (accord de modulation)
            <ChevronDown className={`h-4 w-4 transition-transform ${annualOpen ? 'rotate-180' : ''}`} />
          </CollapsibleTrigger>
          <CollapsibleContent className="space-y-4 pt-4">
            <div className="flex items-center gap-2">
              <Switch
                checked={form.enabled}
                disabled={!canEdit}
                onCheckedChange={(v) => setForm({ ...form, enabled: v })}
              />
              <Label>Activer l&apos;annualisation (accord d&apos;entreprise)</Label>
            </div>
            <div className={`grid gap-4 sm:grid-cols-2 ${!form.enabled ? 'opacity-50' : ''}`}>
              <div className="space-y-2">
                <Label>Semaine haute (h)</Label>
                <Input
                  type="number"
                  step={0.5}
                  disabled={!canEdit || !form.enabled}
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
                  disabled={!canEdit || !form.enabled}
                  value={form.weekly_low_hours}
                  onChange={(e) =>
                    setForm({ ...form, weekly_low_hours: Number(e.target.value) || 32 })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Moyenne hebdo (h)</Label>
                <Input
                  type="number"
                  step={0.5}
                  disabled={!canEdit || !form.enabled}
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
                  disabled={!canEdit || !form.enabled}
                  value={form.weekly_cap_hours}
                  onChange={(e) =>
                    setForm({ ...form, weekly_cap_hours: Number(e.target.value) || 44 })
                  }
                />
              </div>
            </div>
            <div className={`flex items-center gap-2 ${!form.enabled ? 'opacity-50' : ''}`}>
              <Switch
                checked={form.pay_smoothed}
                disabled={!canEdit || !form.enabled}
                onCheckedChange={(v) => setForm({ ...form, pay_smoothed: v })}
              />
              <Label>Lisser la rémunération sur l&apos;année</Label>
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
          {canEdit &&
            PRESETS.map((p) => (
              <Button
                key={p.id}
                type="button"
                variant="secondary"
                size="sm"
                disabled={applyPresetMutation.isPending}
                onClick={() => applyPresetMutation.mutate(p.id)}
              >
                {p.label}
              </Button>
            ))}
          <Button variant="outline" size="sm" asChild>
            <Link to="/suivi-modulation">Suivi compteurs</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
