import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ExternalLink, PiggyBank } from 'lucide-react';
import {
  getCetSettings,
  updateCetSettings,
  type CetSettings,
  type CetSettingsUpdate,
} from '@/api/cet';
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

export default function CetSettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.cetSettings(activeCompanyId),
    queryFn: getCetSettings,
    enabled: Boolean(activeCompanyId),
  });

  const [form, setForm] = useState<CetSettings | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    if (data) {
      setForm(data);
      setShowAdvanced(data.cet_enabled);
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: (payload: CetSettingsUpdate) => updateCetSettings(payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.cetSettings(activeCompanyId), saved);
      setForm(saved);
      toast({
        title: 'Enregistré',
        description: 'Paramètres CET mis à jour.',
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
      cet_enabled: form.cet_enabled,
      agreement_reference: form.agreement_reference,
      hours_per_rest_day: form.hours_per_rest_day,
      request_deadline_day_of_month: form.request_deadline_day_of_month,
      validation_mode: form.validation_mode,
      allow_deposit_hs: form.allow_deposit_hs,
      allow_deposit_cp: form.allow_deposit_cp,
      max_cp_days_per_year: form.max_cp_days_per_year,
      max_account_balance_days: form.max_account_balance_days,
      cp_unit: form.cp_unit,
      ouvres_to_ouvrables_ratio: form.ouvres_to_ouvrables_ratio,
      cp_debit_timing: form.cp_debit_timing,
      hs_debit_timing: form.hs_debit_timing,
    });
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (isError || !form) {
    return (
      <Card>
        <CardContent className="py-6 text-destructive text-sm">
          Impossible de charger les paramètres CET.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <PiggyBank className="h-4 w-4" />
          Compte épargne-temps (CET)
        </CardTitle>
        <CardDescription>
          Paramétrez l&apos;accord d&apos;entreprise : alimentations HS et CP, plafonds et
          règles de débit.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between gap-4">
          <Label htmlFor="cet-enabled">Accord CET en vigueur</Label>
          <Switch
            id="cet-enabled"
            disabled={!canEdit}
            checked={form.cet_enabled}
            onCheckedChange={(checked) => {
              setForm({ ...form, cet_enabled: checked });
              setShowAdvanced(checked);
            }}
          />
        </div>

        {showAdvanced && form.cet_enabled ? (
          <div className="space-y-4 border-t pt-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="cet-ref">Référence accord (optionnel)</Label>
                <Input
                  id="cet-ref"
                  disabled={!canEdit}
                  value={form.agreement_reference ?? ''}
                  onChange={(e) =>
                    setForm({ ...form, agreement_reference: e.target.value || null })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cet-hours-day">Heures par jour de repos</Label>
                <Input
                  id="cet-hours-day"
                  type="number"
                  min={0.5}
                  step="0.5"
                  disabled={!canEdit}
                  value={form.hours_per_rest_day}
                  onChange={(e) =>
                    setForm({ ...form, hours_per_rest_day: Number(e.target.value) })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cet-deadline">Jour limite de demande (mois)</Label>
                <Input
                  id="cet-deadline"
                  type="number"
                  min={1}
                  max={28}
                  disabled={!canEdit}
                  value={form.request_deadline_day_of_month ?? ''}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      request_deadline_day_of_month:
                        e.target.value === '' ? null : Number(e.target.value),
                    })
                  }
                />
              </div>
              <div className="space-y-2">
                <Label>Validation des demandes</Label>
                <Select
                  disabled={!canEdit}
                  value={form.validation_mode}
                  onValueChange={(v: CetSettings['validation_mode']) =>
                    setForm({ ...form, validation_mode: v })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="manager">Directeur / manager d&apos;équipe</SelectItem>
                    <SelectItem value="manager_then_rh">Manager puis RH</SelectItem>
                    <SelectItem value="rh">Validation RH</SelectItem>
                    <SelectItem value="auto">Automatique</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="cet-max-balance">Plafond solde compte (jours)</Label>
                <Input
                  id="cet-max-balance"
                  type="number"
                  min={0}
                  step="0.5"
                  disabled={!canEdit}
                  placeholder="Non limité"
                  value={form.max_account_balance_days ?? ''}
                  onChange={(e) =>
                    setForm({
                      ...form,
                      max_account_balance_days:
                        e.target.value === '' ? null : Number(e.target.value),
                    })
                  }
                />
              </div>
            </div>

            <div className="rounded-lg border bg-muted/20 p-4 space-y-4">
              <p className="text-sm font-medium">Alimentations</p>
              <p className="text-xs text-muted-foreground">
                Reprenez les valeurs de l&apos;accord d&apos;entreprise (ex. MBC : HS
                uniquement ; Cartol : HS + CP avec plafond).
              </p>

              <div className="flex items-center justify-between gap-4">
                <Label htmlFor="cet-allow-hs">Heures supplémentaires → CET</Label>
                <Switch
                  id="cet-allow-hs"
                  disabled={!canEdit}
                  checked={form.allow_deposit_hs}
                  onCheckedChange={(checked) =>
                    setForm({ ...form, allow_deposit_hs: checked })
                  }
                />
              </div>

              <div className="flex items-center justify-between gap-4">
                <Label htmlFor="cet-allow-cp">Congés payés → CET</Label>
                <Switch
                  id="cet-allow-cp"
                  disabled={!canEdit}
                  checked={form.allow_deposit_cp}
                  onCheckedChange={(checked) =>
                    setForm({ ...form, allow_deposit_cp: checked })
                  }
                />
              </div>

              {form.allow_deposit_cp ? (
                <div className="grid gap-4 sm:grid-cols-2 pl-0 sm:pl-2 border-l-2 border-primary/20">
                  <div className="space-y-2">
                    <Label htmlFor="cet-cp-max">Plafond CP / an (jours)</Label>
                    <Input
                      id="cet-cp-max"
                      type="number"
                      min={0}
                      step="0.5"
                      disabled={!canEdit}
                      placeholder="Non limité"
                      value={form.max_cp_days_per_year ?? ''}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          max_cp_days_per_year:
                            e.target.value === '' ? null : Number(e.target.value),
                        })
                      }
                    />
                    {form.max_cp_days_per_year == null ? (
                      <p className="text-xs text-amber-700">
                        Champ vide = pas de plafond annuel (à utiliser avec précaution).
                      </p>
                    ) : null}
                  </div>
                  <div className="space-y-2">
                    <Label>Unité CP</Label>
                    <Select
                      disabled={!canEdit}
                      value={form.cp_unit}
                      onValueChange={(v: 'ouvres' | 'ouvrables') =>
                        setForm({ ...form, cp_unit: v })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="ouvres">Ouvrés</SelectItem>
                        <SelectItem value="ouvrables">Ouvrables</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Ratio ouvrés → ouvrables</Label>
                    <Input
                      type="number"
                      min={0.1}
                      step="0.1"
                      disabled={!canEdit}
                      value={form.ouvres_to_ouvrables_ratio}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          ouvres_to_ouvrables_ratio: Number(e.target.value),
                        })
                      }
                    />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label>Débit HS épargnées</Label>
                    <Select
                      disabled={!canEdit}
                      value={form.hs_debit_timing}
                      onValueChange={(v: 'on_validation' | 'on_payroll') =>
                        setForm({ ...form, hs_debit_timing: v })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="on_validation">À la validation</SelectItem>
                        <SelectItem value="on_payroll">À la paie du mois</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <Label>Débit du solde CP</Label>
                    <Select
                      disabled={!canEdit}
                      value={form.cp_debit_timing}
                      onValueChange={(v: 'on_validation' | 'on_payroll') =>
                        setForm({ ...form, cp_debit_timing: v })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="on_validation">À la validation RH</SelectItem>
                        <SelectItem value="on_payroll">À la paie du mois</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        ) : null}

        {canEdit ? (
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              onClick={handleSave}
              disabled={mutation.isPending}
            >
              {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
            </Button>
            {form.cet_enabled ? (
              <Button type="button" variant="outline" asChild>
                <Link to="/suivi-cet">
                  <ExternalLink className="h-4 w-4 mr-2" />
                  Ouvrir le suivi CET
                </Link>
              </Button>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
