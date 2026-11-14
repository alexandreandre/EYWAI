import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  DEFAULT_MEDAL_TIERS,
  OFFICIAL_MEDAL_YEARS,
  getWorkMedalSettings,
  saveWorkMedalSettings,
  scanWorkMedals,
  type MedalTier,
  type WorkMedalSettings,
  type SeniorityBasis,
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
import { Award, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { accord, pluriel } from '@/lib/pluriel';

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
        description: `${pluriel(result.created, 'dossier')} ${accord(result.created, 'créé')}, ${result.updated} mis à jour.`,
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

  const addTier = () => {
    if (!form) return;
    const used = new Set(form.tiers.map((t) => t.years));
    let years = 10;
    while (used.has(years) && years < 50) years += 5;
    setForm({
      ...form,
      tiers: [
        ...form.tiers,
        { level: `palier_${years}`, years, label: '', amount_mode: 'fixed', amount_value: 0 },
      ],
    });
  };

  const removeTier = (index: number) => {
    if (!form) return;
    setForm({ ...form, tiers: form.tiers.filter((_, i) => i !== index) });
  };

  const duplicateYears = useMemo(() => {
    if (!form) return null;
    const seen = new Set<number>();
    for (const t of form.tiers) {
      if (seen.has(t.years)) return t.years;
      seen.add(t.years);
    }
    return null;
  }, [form]);

  const invalidYears = form?.tiers.some((t) => !Number.isInteger(t.years) || t.years < 1 || t.years > 50);

  const handleSave = () => {
    if (!form || duplicateYears !== null || invalidYears) return;
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
          Primes aux paliers d&apos;ancienneté, années au choix. Alertes RH et versement en
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
              onValueChange={(v: SeniorityBasis) =>
                setForm({ ...form, seniority_basis: v })
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="seniority_reference_date">
                  Date d&apos;ancienneté, reprise incluse
                </SelectItem>
                <SelectItem value="company_only">Depuis la date d&apos;embauche</SelectItem>
                <SelectItem value="total_career">
                  Embauche + reprise saisie en mois
                </SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              La date d&apos;ancienneté de la fiche salarié tient compte des reprises
              d&apos;ancienneté ; à défaut, la date d&apos;embauche est utilisée.
            </p>
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
          <p className="text-xs text-muted-foreground">
            La médaille du travail officielle a quatre échelons : 20, 30, 35 et 40 ans. Un
            autre palier (10 ans par exemple) est une prime d&apos;ancienneté : elle est
            toujours soumise à cotisations. La prime d&apos;une vraie médaille est exonérée en
            2026 jusqu&apos;au salaire de base, puis soumise à partir du 1er janvier 2027.
          </p>
          {form.tiers.map((tier, index) => {
            const official = OFFICIAL_MEDAL_YEARS.includes(tier.years);
            return (
              <div
                key={index}
                className="grid gap-3 rounded-lg border p-3 sm:grid-cols-2 lg:grid-cols-[6rem_1fr_10rem_9rem_auto]"
              >
                <div className="space-y-1">
                  <Label className="text-xs" htmlFor={`medal-years-${index}`}>
                    Années
                  </Label>
                  <Input
                    id={`medal-years-${index}`}
                    type="number"
                    min={1}
                    max={50}
                    step={1}
                    disabled={readOnly}
                    value={tier.years}
                    onChange={(e) => updateTier(index, { years: Number(e.target.value) || 0 })}
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs" htmlFor={`medal-label-${index}`}>
                    Libellé sur le bulletin
                  </Label>
                  <Input
                    id={`medal-label-${index}`}
                    disabled={readOnly}
                    value={tier.label}
                    placeholder={official ? 'Médaille du travail' : `Prime ${tier.years} ans`}
                    onChange={(e) => updateTier(index, { label: e.target.value })}
                  />
                  <p className="text-xs text-muted-foreground">
                    {official
                      ? 'Échelon officiel de la médaille du travail'
                      : 'Prime d’ancienneté, soumise à cotisations'}
                  </p>
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
                <div className="space-y-1">
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
                {canEdit ? (
                  <div className="flex items-end">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label={`Retirer le palier de ${tier.years} ans`}
                      onClick={() => removeTier(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ) : null}
              </div>
            );
          })}
          {duplicateYears !== null ? (
            <p className="text-sm text-destructive">
              Deux paliers à {duplicateYears} ans : gardez-en un seul.
            </p>
          ) : null}
          {invalidYears ? (
            <p className="text-sm text-destructive">
              Chaque palier doit être compris entre 1 et 50 ans.
            </p>
          ) : null}
          {canEdit ? (
            <Button type="button" variant="outline" size="sm" onClick={addTier}>
              <Plus className="mr-2 h-4 w-4" />
              Ajouter un palier
            </Button>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-2">
          {canEdit ? (
            <>
              <Button
                onClick={handleSave}
                disabled={saveMutation.isPending || duplicateYears !== null || Boolean(invalidYears)}
              >
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
