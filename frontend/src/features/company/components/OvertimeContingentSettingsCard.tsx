import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getContingentSettings,
  updateContingentSettings,
  type ContingentSettings,
  type ContingentSettingsUpdate,
} from '@/api/overtimeContingent';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';
import { Clock } from 'lucide-react';

export default function OvertimeContingentSettingsCard() {
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
    queryKey: queryKeys.overtimeContingentSettings(activeCompanyId),
    queryFn: getContingentSettings,
    enabled: Boolean(activeCompanyId),
  });

  const [form, setForm] = useState<ContingentSettings | null>(null);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  const mutation = useMutation({
    mutationFn: (payload: ContingentSettingsUpdate) => updateContingentSettings(payload),
    onSuccess: (saved) => {
      queryClient.setQueryData(queryKeys.overtimeContingentSettings(activeCompanyId), saved);
      setForm(saved);
      toast({
        title: 'Enregistré',
        description: 'Paramètres du contingent heures sup mis à jour.',
      });
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

  const handleSave = () => {
    if (!form) return;
    mutation.mutate({
      legal_cor_contingent_hours: form.legal_cor_contingent_hours,
      management_contingent_hours: form.management_contingent_hours,
      hours_per_rest_day: form.hours_per_rest_day,
      include_structural_hours: form.include_structural_hours,
      pause_deduction_enabled: form.pause_deduction_enabled,
      pause_hs_deduction_per_workday: form.pause_hs_deduction_per_workday,
      workdays_per_year_for_pause: form.workdays_per_year_for_pause,
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
        <CardContent className="py-6 text-destructive text-sm">
          Impossible de charger les paramètres contingent.
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Clock className="h-4 w-4" />
          Plafond annuel heures sup (contingent)
        </CardTitle>
        <CardDescription>
          Plafond de pilotage interne et seuil COR légal (220 h par défaut, art. D3121-24).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="mgmt-contingent">Plafond de pilotage (h/an)</Label>
            <Input
              id="mgmt-contingent"
              type="number"
              min={0}
              step="0.01"
              disabled={!canEdit}
              value={form.management_contingent_hours ?? ''}
              onChange={(e) =>
                setForm({
                  ...form,
                  management_contingent_hours:
                    e.target.value === '' ? null : Number(e.target.value),
                })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="legal-cor">Seuil COR légal (h/an)</Label>
            <Input
              id="legal-cor"
              type="number"
              min={0}
              step="0.01"
              disabled={!canEdit}
              value={form.legal_cor_contingent_hours}
              onChange={(e) =>
                setForm({
                  ...form,
                  legal_cor_contingent_hours: Number(e.target.value),
                })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="hours-rest">Heures par jour de repos</Label>
            <Input
              id="hours-rest"
              type="number"
              min={0.5}
              step="0.1"
              disabled={!canEdit}
              value={form.hours_per_rest_day}
              onChange={(e) =>
                setForm({ ...form, hours_per_rest_day: Number(e.target.value) })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="workdays-pause">Jours ouvrés / an (pauses)</Label>
            <Input
              id="workdays-pause"
              type="number"
              min={1}
              max={366}
              disabled={!canEdit || !form.pause_deduction_enabled}
              value={form.workdays_per_year_for_pause}
              onChange={(e) =>
                setForm({
                  ...form,
                  workdays_per_year_for_pause: Number(e.target.value),
                })
              }
            />
          </div>
        </div>

        <div className="flex flex-wrap gap-6">
          <div className="flex items-center gap-2">
            <Switch
              id="include-structural"
              checked={form.include_structural_hours}
              disabled={!canEdit}
              onCheckedChange={(checked) =>
                setForm({ ...form, include_structural_hours: checked })
              }
            />
            <Label htmlFor="include-structural">Inclure les HS structurelles</Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              id="pause-deduction"
              checked={form.pause_deduction_enabled}
              disabled={!canEdit}
              onCheckedChange={(checked) =>
                setForm({ ...form, pause_deduction_enabled: checked })
              }
            />
            <Label htmlFor="pause-deduction">Déduction pauses</Label>
          </div>
        </div>

        {form.pause_deduction_enabled && (
          <div className="space-y-2 max-w-xs">
            <Label htmlFor="pause-ratio">Heures déduites par jour ouvré</Label>
            <Input
              id="pause-ratio"
              type="number"
              min={0}
              step="0.0001"
              disabled={!canEdit}
              value={form.pause_hs_deduction_per_workday}
              onChange={(e) =>
                setForm({
                  ...form,
                  pause_hs_deduction_per_workday: Number(e.target.value),
                })
              }
            />
          </div>
        )}

        {canEdit && (
          <Button onClick={handleSave} disabled={mutation.isPending}>
            Enregistrer
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
