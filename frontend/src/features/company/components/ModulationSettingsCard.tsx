import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Clock } from 'lucide-react';
import {
  getModulationSettings,
  updateModulationSettings,
  type ModulationSettings,
  type ModulationSettingsUpdate,
} from '@/api/modulation';
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
import { Link } from 'react-router-dom';

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
          Annualisation avec semaines hautes et basses (ex. 37h / 32h). Paramétrable par entreprise.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2">
          <Switch
            checked={form.enabled}
            disabled={!canEdit}
            onCheckedChange={(v) => setForm({ ...form, enabled: v })}
          />
          <Label>Activer la modulation</Label>
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

        <div className="flex flex-wrap gap-2">
          {canEdit && (
            <Button
              disabled={saveMutation.isPending}
              onClick={() =>
                saveMutation.mutate({
                  enabled: form.enabled,
                  weekly_high_hours: form.weekly_high_hours,
                  weekly_low_hours: form.weekly_low_hours,
                  high_weeks_per_cycle: form.high_weeks_per_cycle,
                  low_weeks_per_cycle: form.low_weeks_per_cycle,
                  average_weekly_hours: form.average_weekly_hours,
                  weekly_cap_hours: form.weekly_cap_hours,
                  pay_smoothed: form.pay_smoothed,
                  reference_period_months: form.reference_period_months,
                })
              }
            >
              Enregistrer
            </Button>
          )}
          <Button variant="outline" size="sm" asChild>
            <Link to="/rh/suivi-modulation">Suivi modulation</Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
