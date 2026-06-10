import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  DEFAULT_MEDAL_TIERS,
  getWorkMedalSettings,
  saveWorkMedalSettings,
  scanWorkMedals,
  type MedalTier,
  type WorkMedalSettings,
  type WorkMedalSettingsUpdate,
} from '@/api/workMedals';
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
import { Award, RefreshCw } from 'lucide-react';

function toUpdatePayload(form: WorkMedalSettings): WorkMedalSettingsUpdate {
  return {
    enabled: form.enabled,
    seniority_basis: form.seniority_basis,
    reminder_months_before: form.reminder_months_before,
    tiers: form.tiers,
    default_is_taxable: form.default_is_taxable,
    default_is_socially_taxed: form.default_is_socially_taxed,
  };
}

function ensureTiers(tiers: MedalTier[] | undefined): MedalTier[] {
  if (tiers && tiers.length > 0) return tiers;
  return DEFAULT_MEDAL_TIERS;
}

export default function WorkMedalSettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh';
  }, [user?.role]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['work-medal-settings', activeCompanyId],
    queryFn: getWorkMedalSettings,
    enabled: Boolean(activeCompanyId),
  });

  const [form, setForm] = useState<WorkMedalSettings | null>(null);

  useEffect(() => {
    if (data) {
      setForm({ ...data, tiers: ensureTiers(data.tiers) });
    }
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: saveWorkMedalSettings,
    onSuccess: (saved) => {
      queryClient.setQueryData(['work-medal-settings', activeCompanyId], saved);
      setForm({ ...saved, tiers: ensureTiers(saved.tiers) });
      queryClient.invalidateQueries({ queryKey: ['work-medals'] });
      queryClient.invalidateQueries({ queryKey: ['work-medal-summary'] });
      toast({ title: 'Enregistré', description: 'Paramètres médailles du travail mis à jour.' });
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Impossible d’enregistrer les paramètres.',
        variant: 'destructive',
      });
    },
  });

  const scanMutation = useMutation({
    mutationFn: scanWorkMedals,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ['work-medals'] });
      queryClient.invalidateQueries({ queryKey: ['work-medal-summary'] });
      toast({
        title: 'Scan terminé',
        description: `${result.created} dossier(s) créé(s), ${result.updated} mis à jour.`,
      });
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Le scan a échoué.',
        variant: 'destructive',
      });
    },
  });

  const readOnly = !canEdit;

  const updateTier = (index: number, patch: Partial<MedalTier>) => {
    if (!form) return;
    const tiers = [...form.tiers];
    tiers[index] = { ...tiers[index], ...patch };
    setForm({ ...form, tiers });
  };

  const handleSave = () => {
    if (!form) return;
    saveMutation.mutate(toUpdatePayload(form));
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
          {(error as Error)?.message ?? 'Impossible de charger les paramètres.'}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center text-base">
          <Award className="mr-2 h-5 w-5 text-amber-600" />
          Médailles du travail
        </CardTitle>
        <CardDescription>
          Primes aux paliers d&apos;ancienneté (20, 30, 35, 40 ans). Alertes RH et versement en
          paie.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-between gap-4">
          <div className="space-y-1">
            <Label htmlFor="work-medal-enabled">Activer les médailles du travail</Label>
            <p className="text-xs text-muted-foreground">
              Détection automatique des paliers et workflow de prime.
            </p>
          </div>
          <Switch
            id="work-medal-enabled"
            checked={form.enabled}
            disabled={readOnly}
            onCheckedChange={(enabled) => setForm({ ...form, enabled })}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Base d&apos;ancienneté</Label>
            <Select
              value={form.seniority_basis}
              disabled={readOnly}
              onValueChange={(v: 'total_career' | 'company_only') =>
                setForm({ ...form, seniority_basis: v })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="total_career">Carrière totale (défaut légal)</SelectItem>
                <SelectItem value="company_only">Entreprise uniquement</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="reminder-months">Rappel avant palier (mois)</Label>
            <Input
              id="reminder-months"
              type="number"
              min={0}
              max={24}
              disabled={readOnly}
              value={form.reminder_months_before}
              onChange={(e) =>
                setForm({
                  ...form,
                  reminder_months_before: Number(e.target.value) || 0,
                })
              }
            />
          </div>
        </div>

        <div className="space-y-3">
          <Label>Barème des primes</Label>
          {form.tiers.map((tier, index) => (
            <div
              key={tier.level}
              className="grid gap-3 rounded-lg border p-3 sm:grid-cols-2 lg:grid-cols-4"
            >
              <div className="space-y-1">
                <p className="text-sm font-medium">{tier.label}</p>
                <p className="text-xs text-muted-foreground">{tier.years} ans</p>
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Mode</Label>
                <Select
                  value={tier.amount_mode}
                  disabled={readOnly}
                  onValueChange={(v: 'fixed' | 'salary_months') =>
                    updateTier(index, { amount_mode: v })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="fixed">Montant fixe (€)</SelectItem>
                    <SelectItem value="salary_months">Mois de salaire</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1 sm:col-span-2">
                <Label className="text-xs">
                  {tier.amount_mode === 'fixed' ? 'Montant (€)' : 'Nombre de mois'}
                </Label>
                <Input
                  type="number"
                  min={0}
                  step={tier.amount_mode === 'fixed' ? 1 : 0.5}
                  disabled={readOnly}
                  value={tier.amount_value}
                  onChange={(e) =>
                    updateTier(index, { amount_value: Number(e.target.value) || 0 })
                  }
                />
              </div>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap gap-2">
          {canEdit ? (
            <>
              <Button onClick={handleSave} disabled={saveMutation.isPending}>
                Enregistrer
              </Button>
              {form.enabled ? (
                <Button
                  variant="outline"
                  onClick={() => scanMutation.mutate()}
                  disabled={scanMutation.isPending}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Lancer le scan
                </Button>
              ) : null}
            </>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
