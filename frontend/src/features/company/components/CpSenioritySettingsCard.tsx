import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Award, Plus, Trash2 } from 'lucide-react';
import {
  applyCpSeniorityPreset,
  getCpSeniorityPreview,
  getCpSenioritySettings,
  updateCpSenioritySettings,
  type CpSenioritySettings,
  type CpSenioritySettingsUpdate,
  type CpSeniorityTier,
} from '@/api/cpSeniority';
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';

const CATEGORY_LABELS: Record<string, string> = {
  all: 'Tous',
  ouvrier_etam: 'Ouvriers / ETAM',
  cadre: 'Cadres',
  forfait: 'Forfait jour',
};

function emptyTier(): CpSeniorityTier {
  return { category: 'all', min_years: 2, days: 1 };
}

export default function CpSenioritySettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const grantYear = new Date().getFullYear();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'collaborateur_rh';
  }, [user?.role]);

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.cpSenioritySettings(activeCompanyId),
    queryFn: getCpSenioritySettings,
    enabled: Boolean(activeCompanyId),
  });

  const previewQuery = useQuery({
    queryKey: queryKeys.cpSeniorityPreview(activeCompanyId, grantYear),
    queryFn: () => getCpSeniorityPreview(grantYear),
    enabled: Boolean(activeCompanyId) && Boolean(data?.enabled),
  });

  const [form, setForm] = useState<CpSenioritySettings | null>(null);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const saveSettings = useMutation({
    mutationFn: (payload: CpSenioritySettingsUpdate) =>
      updateCpSenioritySettings(payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.cpSenioritySettings(activeCompanyId), saved);
      setForm(saved);
      toast({ title: 'Enregistré', description: 'Paramètres CP ancienneté mis à jour.' });
    },
  });

  const applyPreset = useMutation({
    mutationFn: (preset: string) => applyCpSeniorityPreset(preset),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.cpSenioritySettings(activeCompanyId), saved);
      setForm(saved);
      toast({ title: 'Preset appliqué' });
    },
  });

  const updateTier = (index: number, patch: Partial<CpSeniorityTier>) => {
    if (!form) return;
    const tiers = [...(form.rules.tiers || [])];
    tiers[index] = { ...tiers[index], ...patch };
    setForm({
      ...form,
      preset: 'custom',
      rules: { ...form.rules, mode: 'cumulative_rules', tiers },
    });
  };

  const addTier = () => {
    if (!form) return;
    setForm({
      ...form,
      preset: 'custom',
      rules: {
        mode: 'cumulative_rules',
        tiers: [...(form.rules.tiers || []), emptyTier()],
      },
    });
  };

  const removeTier = (index: number) => {
    if (!form) return;
    const tiers = form.rules.tiers.filter((_, i) => i !== index);
    setForm({
      ...form,
      preset: 'custom',
      rules: { ...form.rules, mode: 'cumulative_rules', tiers },
    });
  };

  if (isLoading || !form) {
    return (
      <Card>
        <CardHeader><Skeleton className="h-6 w-64" /></CardHeader>
        <CardContent><Skeleton className="h-24 w-full" /></CardContent>
      </Card>
    );
  }

  if (isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Award className="h-5 w-5" />
            CP ancienneté
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-destructive">
          Impossible de charger les paramètres CP ancienneté.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Award className="h-5 w-5" />
          CP ancienneté (congés supplémentaires)
        </CardTitle>
        <CardDescription>
          Jours conventionnels en plus du CP légal. Éditeur de règles générique avec presets
          (plasturgie, accord LEWIS).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <Switch
            id="cp-seniority-enabled"
            checked={form.enabled}
            disabled={!canEdit || form.company_agreement_overrides}
            onCheckedChange={(checked) => setForm({ ...form, enabled: checked })}
          />
          <Label htmlFor="cp-seniority-enabled">Activer les CP ancienneté</Label>
          {canEdit && (
            <>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={applyPreset.isPending}
                onClick={() => applyPreset.mutate('plasturgie_idcc_0292')}
              >
                Preset plasturgie
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={applyPreset.isPending}
                onClick={() => applyPreset.mutate('lewis_agreement')}
              >
                Preset LEWIS
              </Button>
            </>
          )}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Base ancienneté</Label>
            <Select
              value={form.seniority_basis}
              disabled={!canEdit}
              onValueChange={(v) =>
                setForm({
                  ...form,
                  seniority_basis: v as CpSenioritySettings['seniority_basis'],
                })
              }
            >
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="company_only">Date d&apos;entrée</SelectItem>
                <SelectItem value="include_prior_service">Reprise d&apos;ancienneté</SelectItem>
                <SelectItem value="seniority_reference_date">Date ancienneté (fiche)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="forfait-days">Forfait annuel de base (j)</Label>
            <Input
              id="forfait-days"
              type="number"
              min={1}
              disabled={!canEdit}
              value={form.forfait_annual_days_default}
              onChange={(e) =>
                setForm({
                  ...form,
                  forfait_annual_days_default: Number(e.target.value) || 216,
                })
              }
            />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Règles cumulatives</Label>
            {canEdit && (
              <Button type="button" variant="outline" size="sm" onClick={addTier}>
                <Plus className="mr-1 h-4 w-4" />
                Ajouter
              </Button>
            )}
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Catégorie</TableHead>
                <TableHead>Ancienneté min.</TableHead>
                <TableHead>Âge min.</TableHead>
                <TableHead>Jours</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {(form.rules.tiers || []).map((tier, idx) => (
                <TableRow key={idx}>
                  <TableCell>
                    <Select
                      value={tier.category}
                      disabled={!canEdit}
                      onValueChange={(v) =>
                        updateTier(idx, {
                          category: v as CpSeniorityTier['category'],
                        })
                      }
                    >
                      <SelectTrigger className="h-8"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {Object.entries(CATEGORY_LABELS).map(([k, label]) => (
                          <SelectItem key={k} value={k}>{label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      className="h-8 w-20"
                      disabled={!canEdit}
                      value={tier.min_years}
                      onChange={(e) =>
                        updateTier(idx, { min_years: Number(e.target.value) || 0 })
                      }
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      className="h-8 w-20"
                      disabled={!canEdit}
                      value={tier.min_age ?? ''}
                      placeholder="—"
                      onChange={(e) =>
                        updateTier(idx, {
                          min_age: e.target.value ? Number(e.target.value) : undefined,
                        })
                      }
                    />
                  </TableCell>
                  <TableCell>
                    <Input
                      type="number"
                      className="h-8 w-16"
                      disabled={!canEdit}
                      value={tier.days}
                      onChange={(e) =>
                        updateTier(idx, { days: Number(e.target.value) || 0 })
                      }
                    />
                  </TableCell>
                  <TableCell>
                    {canEdit && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() => removeTier(idx)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {canEdit && (
          <Button
            type="button"
            disabled={saveSettings.isPending}
            onClick={() =>
              saveSettings.mutate({
                enabled: form.enabled,
                preset: form.preset,
                seniority_basis: form.seniority_basis,
                rules: form.rules,
                forfait_annual_days_default: form.forfait_annual_days_default,
                forfait_reduction_enabled: form.forfait_reduction_enabled,
                company_agreement_overrides: form.company_agreement_overrides,
              })
            }
          >
            Enregistrer
          </Button>
        )}

        {form.enabled && previewQuery.data && previewQuery.data.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium">
              Aperçu — référence 31/05/{grantYear}
            </h4>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Catégorie</TableHead>
                  <TableHead>Ancienneté</TableHead>
                  <TableHead>Jours CP+</TableHead>
                  <TableHead>Forfait adj.</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewQuery.data.map((row) => (
                  <TableRow key={row.employee_id}>
                    <TableCell>{row.first_name} {row.last_name}</TableCell>
                    <TableCell>{row.category ?? '—'}</TableCell>
                    <TableCell>{row.seniority_years_at_ref.toFixed(1)} ans</TableCell>
                    <TableCell>{row.days_granted}</TableCell>
                    <TableCell>
                      {row.forfait_annual_days_adjusted != null
                        ? `${row.forfait_annual_days_adjusted} j`
                        : '—'}
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
