import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getMaintenanceSettings,
  saveMaintenanceSettings,
  type MaintenanceSettings,
  type MaintenanceSettingsUpdate,
} from '@/api/maintenanceSettings';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { useToast } from '@/hooks/use-toast';
import { Wallet } from 'lucide-react';

function toUpdatePayload(form: MaintenanceSettings): MaintenanceSettingsUpdate {
  return {
    apply_legal_maintenance: form.apply_legal_maintenance,
    min_seniority_months: form.min_seniority_months,
    employer_waiting_days: form.employer_waiting_days,
    seniority_extension_enabled: form.seniority_extension_enabled,
    remove_employer_waiting: form.remove_employer_waiting,
    annual_unique_waiting: form.annual_unique_waiting,
    maintain_100_percent: form.maintain_100_percent,
    differentiated_at_illness: form.differentiated_at_illness,
    maintain_by_category: form.maintain_by_category,
    no_seniority_condition: form.no_seniority_condition,
    custom_duration_days: form.custom_duration_days,
    subrogation_mode: form.subrogation_mode,
    provident_relay_days: form.provident_relay_days,
  };
}

export default function MaintenanceSettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const canEdit = useMemo(() => {
    const r = user?.role;
    return r === 'admin' || r === 'rh' || r === 'admin';
  }, [user?.role]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['maintenance-settings', activeCompanyId],
    queryFn: getMaintenanceSettings,
    enabled: Boolean(activeCompanyId),
  });

  const [form, setForm] = useState<MaintenanceSettings | null>(null);

  useEffect(() => {
    if (data) {
      setForm(data);
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: saveMaintenanceSettings,
    onSuccess: (saved) => {
      queryClient.setQueryData(['maintenance-settings', activeCompanyId], saved);
      setForm(saved);
      toast({ title: 'Enregistré', description: 'Paramètres de maintien de salaire mis à jour.' });
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

  const readOnly = !canEdit;

  const handleSave = () => {
    if (!form) return;
    mutation.mutate(toUpdatePayload(form));
  };

  if (!activeCompanyId) {
    return null;
  }

  if (isError) {
    const err = error as { response?: { data?: { detail?: string } } };
    return (
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>Maintien de salaire</CardTitle>
          <CardDescription className="text-destructive">
            {err.response?.data?.detail ?? 'Chargement impossible.'}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (isLoading || !form) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="h-4 w-full max-w-md mt-2" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-10 w-32" />
        </CardContent>
      </Card>
    );
  }

  const setNum = (key: keyof MaintenanceSettings, raw: string, optional = false) => {
    if (raw === '' && optional) {
      setForm((prev) => (prev ? { ...prev, [key]: null } : prev));
      return;
    }
    const n = parseInt(raw, 10);
    if (Number.isNaN(n)) return;
    setForm((prev) => (prev ? { ...prev, [key]: n } : prev));
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Wallet className="h-5 w-5" />
            Maintien de salaire
          </CardTitle>
          <CardDescription>
            Règles légales, conventionnelles et prévoyance pour l’entreprise active.
          </CardDescription>
        </div>
        {readOnly ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex">
                <Button type="button" disabled variant="secondary" size="sm">
                  Enregistrer
                </Button>
              </span>
            </TooltipTrigger>
            <TooltipContent>Modification réservée au RH principal</TooltipContent>
          </Tooltip>
        ) : (
          <Button
            type="button"
            size="sm"
            onClick={handleSave}
            disabled={mutation.isPending}
          >
            {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        )}
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="legal" className="w-full">
          <TabsList className="grid w-full max-w-md grid-cols-1 gap-1 sm:grid-cols-2 lg:grid-cols-3">
            <TabsTrigger value="legal">
              Légal
            </TabsTrigger>
            <TabsTrigger value="convention">Convention</TabsTrigger>
            <TabsTrigger value="prevoyance">Prévoyance</TabsTrigger>
          </TabsList>

          <TabsContent value="legal" className="mt-4 space-y-6">
            <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
              <div>
                <Label htmlFor="apply_legal_maintenance">Appliquer le maintien légal</Label>
                <p className="text-sm text-muted-foreground">Référence aux règles légales de maintien.</p>
              </div>
              <Switch
                id="apply_legal_maintenance"
                checked={form.apply_legal_maintenance}
                onCheckedChange={(v) =>
                  setForm((p) => (p ? { ...p, apply_legal_maintenance: v } : p))
                }
                disabled={readOnly}
              />
            </div>
            <div className="grid gap-2 max-w-xs">
              <Label htmlFor="min_seniority_months">Ancienneté minimale (mois)</Label>
              <Input
                id="min_seniority_months"
                type="number"
                min={0}
                max={120}
                value={form.min_seniority_months}
                onChange={(e) => setNum('min_seniority_months', e.target.value)}
                disabled={readOnly}
              />
            </div>
            <div className="grid gap-2 max-w-xs">
              <Label htmlFor="employer_waiting_days">Délai de carence employeur (jours)</Label>
              <Input
                id="employer_waiting_days"
                type="number"
                min={0}
                max={30}
                value={form.employer_waiting_days}
                onChange={(e) => setNum('employer_waiting_days', e.target.value)}
                disabled={readOnly || form.remove_employer_waiting}
              />
            </div>
            <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
              <div>
                <Label htmlFor="seniority_extension_enabled">Prolongation selon ancienneté</Label>
                <p className="text-sm text-muted-foreground">Allongement des droits lié à l’ancienneté.</p>
              </div>
              <Switch
                id="seniority_extension_enabled"
                checked={form.seniority_extension_enabled}
                onCheckedChange={(v) =>
                  setForm((p) => (p ? { ...p, seniority_extension_enabled: v } : p))
                }
                disabled={readOnly}
              />
            </div>
          </TabsContent>

          <TabsContent value="convention" className="mt-4 space-y-4">
            {[
              ['remove_employer_waiting', 'Supprimer la carence employeur'] as const,
              ['annual_unique_waiting', 'Carence annuelle unique'] as const,
              ['maintain_100_percent', 'Maintien à 100 %'] as const,
              ['differentiated_at_illness', 'Différenciation selon pathologie'] as const,
              ['maintain_by_category', 'Maintien par catégorie'] as const,
              ['no_seniority_condition', 'Sans condition d’ancienneté'] as const,
            ].map(([key, label]) => (
              <div
                key={key}
                className="flex items-center justify-between gap-4 rounded-lg border p-4"
              >
                <Label htmlFor={key} className="cursor-pointer">
                  {label}
                </Label>
                <Switch
                  id={key}
                  checked={Boolean(form[key])}
                onCheckedChange={(v) =>
                  setForm((p) => {
                    if (!p) return p;
                    const next = { ...p, [key]: v } as MaintenanceSettings;
                    if (key === 'remove_employer_waiting' && v) {
                      next.employer_waiting_days = 0;
                    }
                    return next;
                  })
                }
                disabled={readOnly}
              />
              </div>
            ))}
            <div className="grid gap-2 max-w-xs">
              <Label htmlFor="custom_duration_days">Durée personnalisée (jours, optionnel)</Label>
              <Input
                id="custom_duration_days"
                type="number"
                min={0}
                value={form.custom_duration_days ?? ''}
                onChange={(e) => setNum('custom_duration_days', e.target.value, true)}
                disabled={readOnly}
                placeholder="—"
              />
            </div>
          </TabsContent>

          <TabsContent value="prevoyance" className="mt-4 space-y-6">
            <div className="grid gap-2 max-w-md">
              <Label>Mode de subrogation</Label>
              <Select
                value={form.subrogation_mode}
                onValueChange={(v: MaintenanceSettings['subrogation_mode']) =>
                  setForm((p) => (p ? { ...p, subrogation_mode: v } : p))
                }
                disabled={readOnly}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Choisir" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="automatic">Automatique</SelectItem>
                  <SelectItem value="at_mp_only">Uniquement AT/MP</SelectItem>
                  <SelectItem value="per_case">Au cas par cas</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2 max-w-xs">
              <Label htmlFor="provident_relay_days">Relais prévoyance (jours, optionnel)</Label>
              <Input
                id="provident_relay_days"
                type="number"
                min={0}
                value={form.provident_relay_days ?? ''}
                onChange={(e) => setNum('provident_relay_days', e.target.value, true)}
                disabled={readOnly}
                placeholder="—"
              />
            </div>
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
