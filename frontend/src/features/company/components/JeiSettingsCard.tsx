import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getJeiSettings,
  saveJeiSettings,
  type JeiSettings,
  type JeiSettingsUpdate,
} from '@/api/jeiSettings';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { isPlatformAdmin } from '@/lib/platformAdmin';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';
import { FlaskConical } from 'lucide-react';

function toUpdatePayload(form: JeiSettings): JeiSettingsUpdate {
  return {
    jei_enabled: form.jei_enabled,
    date_creation_etablissement: form.date_creation_etablissement,
    taux_exoneration: form.taux_exoneration,
  };
}

function formatDateFr(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('fr-FR');
}

export default function JeiSettingsCard() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const canEdit = useMemo(() => {
    if (isPlatformAdmin(user)) return true;
    const r = activeCompany?.role ?? user?.role;
    return r === 'admin' || r === 'rh';
  }, [user, activeCompany?.role]);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['jei-settings', activeCompanyId],
    queryFn: getJeiSettings,
    enabled: Boolean(activeCompanyId),
  });

  const [form, setForm] = useState<JeiSettings | null>(null);

  useEffect(() => {
    if (data) {
      setForm(data);
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: saveJeiSettings,
    onSuccess: (saved) => {
      queryClient.setQueryData(['jei-settings', activeCompanyId], saved);
      void queryClient.invalidateQueries({ queryKey: ['company-overview', activeCompanyId] });
      setForm(saved);
      toast({ title: 'Enregistré', description: 'Paramètres JEI mis à jour.' });
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description: err.response?.data?.detail ?? 'Impossible d’enregistrer les paramètres JEI.',
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
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5" />
            Statut JEI
          </CardTitle>
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
          <Skeleton className="h-4 w-full max-w-md" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FlaskConical className="h-5 w-5" />
          Statut JEI — Jeune Entreprise Innovante
        </CardTitle>
        <CardDescription>
          Active l’exonération des cotisations patronales d’assurances sociales et d’allocations
          familiales pour le personnel R&D éligible (plafond 4,5 SMIC par salarié, 5 PASS/an par
          établissement).
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-between rounded-md border p-4">
          <div className="space-y-1">
            <Label htmlFor="jei-enabled">Entreprise bénéficiant du statut JEI</Label>
            <p className="text-sm text-muted-foreground">
              Les salariés marqués « personnel R&D éligible JEI » sur leur fiche en bénéficient.
            </p>
          </div>
          <Switch
            id="jei-enabled"
            checked={form.jei_enabled}
            disabled={readOnly}
            onCheckedChange={(checked) =>
              setForm((prev) => (prev ? { ...prev, jei_enabled: checked } : prev))
            }
          />
        </div>

        {form.jei_enabled && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="jei-date-creation">Date de création de l’établissement</Label>
              <Input
                id="jei-date-creation"
                type="date"
                disabled={readOnly}
                value={form.date_creation_etablissement ?? ''}
                onChange={(e) =>
                  setForm((prev) =>
                    prev
                      ? {
                          ...prev,
                          date_creation_etablissement: e.target.value || null,
                        }
                      : prev
                  )
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="jei-taux">Taux d’exonération</Label>
              <Input
                id="jei-taux"
                type="number"
                min={0}
                max={1}
                step={0.01}
                disabled={readOnly}
                value={form.taux_exoneration}
                onChange={(e) =>
                  setForm((prev) =>
                    prev
                      ? {
                          ...prev,
                          taux_exoneration: parseFloat(e.target.value) || 0,
                        }
                      : prev
                  )
                }
              />
              <p className="text-xs text-muted-foreground">1,0 = 100 % (régime standard).</p>
            </div>
          </div>
        )}

        {form.jei_enabled && form.date_creation_etablissement && (
          <div className="rounded-md bg-muted/50 p-4 text-sm">
            <p>
              <span className="font-medium">Fin d’éligibilité :</span>{' '}
              {formatDateFr(form.date_fin_eligibilite)}
            </p>
            <p className="text-muted-foreground">
              {form.annees_restantes != null && form.annees_restantes > 0
                ? `${form.annees_restantes} année(s) restante(s) (7 ans à compter de la création).`
                : form.annees_restantes === 0
                  ? 'Période d’éligibilité expirée.'
                  : null}
            </p>
          </div>
        )}

        {!readOnly && (
          <Button onClick={handleSave} disabled={mutation.isPending}>
            {mutation.isPending ? 'Enregistrement…' : 'Enregistrer'}
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
