import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getPrimeAncienneteSettings,
  savePrimeAncienneteSettings,
  type PrimeAncienneteSettings,
  type PrimeAncienneteSettingsUpdate,
  type ProrataMode,
} from '@/api/primeAncienneteSettings';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/hooks/use-toast';
import { Award } from 'lucide-react';

const PRORATA_LABELS: Record<ProrataMode, string> = {
  heures_contrat: 'Heures contractuelles (151,67 h)',
  jours_forfait: 'Jours forfait',
  none: 'Plein mois (sans prorata)',
};

function toUpdatePayload(form: PrimeAncienneteSettingsUpdate): PrimeAncienneteSettingsUpdate {
  return {
    valeur_point_override: form.valeur_point_override ?? null,
    min_annees_override: form.min_annees_override ?? null,
    prorata_mode_override: form.prorata_mode_override ?? null,
  };
}

export default function PrimeAncienneteSettingsCard() {
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
    queryKey: ['prime-anciennete-settings', activeCompanyId],
    queryFn: getPrimeAncienneteSettings,
    enabled: Boolean(activeCompanyId),
  });

  const [overrides, setOverrides] = useState<PrimeAncienneteSettingsUpdate>({});

  useEffect(() => {
    if (data) {
      setOverrides({
        valeur_point_override: data.overrides.valeur_point_override ?? null,
        min_annees_override: data.overrides.min_annees_override ?? null,
        prorata_mode_override: data.overrides.prorata_mode_override ?? null,
      });
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: savePrimeAncienneteSettings,
    onSuccess: (saved) => {
      queryClient.setQueryData(['prime-anciennete-settings', activeCompanyId], saved);
      toast({
        title: 'Enregistré',
        description: 'Paramètres prime d\'ancienneté mis à jour.',
      });
    },
    onError: (e: unknown) => {
      const err = e as { response?: { data?: { detail?: string } } };
      toast({
        title: 'Erreur',
        description:
          err.response?.data?.detail ?? 'Impossible d\'enregistrer les paramètres.',
        variant: 'destructive',
      });
    },
  });

  if (!activeCompanyId) return null;

  if (isError) {
    const err = error as { response?: { data?: { detail?: string } } };
    return (
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle>Prime d&apos;ancienneté</CardTitle>
          <CardDescription className="text-destructive">
            {err.response?.data?.detail ?? 'Chargement impossible.'}
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
          <Skeleton className="mt-2 h-4 w-full" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </CardContent>
      </Card>
    );
  }

  const cc = data.cc_resolved;
  const readOnly = !canEdit;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Award className="h-5 w-5 text-primary" />
          Prime d&apos;ancienneté
        </CardTitle>
        <CardDescription>
          Règle CCN appliquée automatiquement sur les bulletins. Les surcharges ci-dessous
          priment sur la convention collective.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="rounded-lg border bg-muted/30 p-4 text-sm space-y-2">
          <p>
            <span className="font-medium text-muted-foreground">Convention : </span>
            {cc.idcc ? `IDCC ${cc.idcc}` : 'Non configurée'}
          </p>
          <p>
            <span className="font-medium text-muted-foreground">Formule : </span>
            {cc.formule ?? '—'}
          </p>
          <p>
            <span className="font-medium text-muted-foreground">VP zone détectée : </span>
            {cc.valeur_point_zone != null
              ? `${cc.valeur_point_zone.toLocaleString('fr-FR', { minimumFractionDigits: 2 })} €`
              : '—'}
            {cc.zone_libelle ? ` (${cc.zone_libelle})` : ''}
            {data.code_postal ? ` — CP ${data.code_postal}` : ''}
          </p>
          <p>
            <span className="font-medium text-muted-foreground">Seuil CCN : </span>
            {cc.min_annees} an{cc.min_annees > 1 ? 's' : ''}
            {cc.statuts_exclus.length > 0
              ? ` — exclus : ${cc.statuts_exclus.join(', ')}`
              : ''}
          </p>
          <p>
            <span className="font-medium text-muted-foreground">Prorata CCN : </span>
            {cc.prorata_enabled
              ? PRORATA_LABELS[cc.prorata_mode] ?? cc.prorata_mode
              : 'Désactivé (plein mois)'}
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="vp_override">Valeur du point (override €)</Label>
            <Input
              id="vp_override"
              type="number"
              step="0.01"
              min="0"
              disabled={readOnly}
              placeholder={
                cc.valeur_point_zone != null ? String(cc.valeur_point_zone) : '5,70'
              }
              value={overrides.valeur_point_override ?? ''}
              onChange={(e) =>
                setOverrides((p) => ({
                  ...p,
                  valeur_point_override: e.target.value
                    ? parseFloat(e.target.value)
                    : null,
                }))
              }
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="min_annees_override">Ancienneté minimum (override)</Label>
            <Input
              id="min_annees_override"
              type="number"
              step="1"
              min="0"
              disabled={readOnly}
              placeholder={String(cc.min_annees)}
              value={overrides.min_annees_override ?? ''}
              onChange={(e) =>
                setOverrides((p) => ({
                  ...p,
                  min_annees_override: e.target.value
                    ? parseFloat(e.target.value)
                    : null,
                }))
              }
            />
          </div>
          <div className="grid gap-2 sm:col-span-2">
            <Label>Mode prorata (override)</Label>
            <Select
              disabled={readOnly}
              value={overrides.prorata_mode_override ?? '__default__'}
              onValueChange={(v) =>
                setOverrides((p) => ({
                  ...p,
                  prorata_mode_override:
                    v === '__default__' ? null : (v as ProrataMode),
                }))
              }
            >
              <SelectTrigger>
                <SelectValue placeholder="Utiliser la règle CCN" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__default__">Utiliser la règle CCN</SelectItem>
                {(Object.keys(PRORATA_LABELS) as ProrataMode[]).map((mode) => (
                  <SelectItem key={mode} value={mode}>
                    {PRORATA_LABELS[mode]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {!readOnly ? (
          <Button
            onClick={() => mutation.mutate(toUpdatePayload(overrides))}
            disabled={mutation.isPending}
          >
            Enregistrer
          </Button>
        ) : (
          <p className="text-xs text-muted-foreground">
            Lecture seule — réservé aux administrateurs et RH.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
