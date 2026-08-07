import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CalendarCheck } from 'lucide-react';
import {
  getInterviewCampaignSettings,
  updateInterviewCampaignSettings,
  type InterviewCampaignMode,
  type InterviewCampaignSettings,
} from '@/api/annualReviews';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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

const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
];

const PERIODICITES = [
  { value: 1, label: 'Chaque année' },
  { value: 2, label: 'Tous les 2 ans' },
  { value: 3, label: 'Tous les 3 ans' },
  { value: 6, label: 'Tous les 6 ans' },
];

const DEFAUT: InterviewCampaignSettings = {
  enabled: false,
  campaign_mode: 'mois_fixe',
  campaign_month: 10,
  periodicity_years: 1,
};

export default function InterviewCampaignSettingsCard() {
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
    queryKey: queryKeys.interviewCampaignSettings(activeCompanyId),
    queryFn: async () => (await getInterviewCampaignSettings()).data,
    enabled: Boolean(activeCompanyId),
  });

  const [form, setForm] = useState<InterviewCampaignSettings>(DEFAUT);

  useEffect(() => {
    // Une société jamais réglée revient avec le mois à null : on propose octobre
    // pour que le sélecteur ait une valeur, sans rien enregistrer tant qu'on ne
    // clique pas sur Enregistrer.
    if (data) setForm({ ...data, campaign_month: data.campaign_month ?? 10 });
  }, [data]);

  const save = useMutation({
    mutationFn: (payload: InterviewCampaignSettings) =>
      updateInterviewCampaignSettings(payload).then((r) => r.data),
    onSuccess: (saved) => {
      queryClient.setQueryData(
        queryKeys.interviewCampaignSettings(activeCompanyId),
        saved,
      );
      setForm({ ...saved, campaign_month: saved.campaign_month ?? 10 });
      toast({
        title: 'Enregistré',
        description: 'Campagne d’entretiens mise à jour.',
      });
    },
    onError: () => {
      toast({
        title: 'Échec',
        description: 'La campagne d’entretiens n’a pas pu être enregistrée.',
        variant: 'destructive',
      });
    },
  });

  if (isLoading) {
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
            <CalendarCheck className="h-5 w-5" />
            Campagne d&apos;entretiens
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-destructive">
          Impossible de charger la campagne d&apos;entretiens.
        </CardContent>
      </Card>
    );
  }

  const moisFixe = form.campaign_mode === 'mois_fixe';

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <CalendarCheck className="h-5 w-5" />
          Campagne d&apos;entretiens
        </CardTitle>
        <CardDescription>
          Quand les entretiens de cette société sont attendus. Tant que la campagne est
          éteinte, seuls les cadres et les forfaits jour remontent dans les entretiens à
          planifier.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-wrap items-center gap-3">
          <Switch
            id="interview-campaign-enabled"
            checked={form.enabled}
            disabled={!canEdit}
            onCheckedChange={(checked) => setForm({ ...form, enabled: checked })}
          />
          <Label htmlFor="interview-campaign-enabled">
            Activer la campagne pour toute la société
          </Label>
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-2">
            <Label>Quand</Label>
            <Select
              value={form.campaign_mode}
              disabled={!canEdit}
              onValueChange={(v) =>
                setForm({ ...form, campaign_mode: v as InterviewCampaignMode })
              }
            >
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="mois_fixe">Un mois pour tous</SelectItem>
                <SelectItem value="anniversaire_embauche">
                  À la date d&apos;ancienneté
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Mois de campagne</Label>
            <Select
              value={String(form.campaign_month ?? 10)}
              disabled={!canEdit || !moisFixe}
              onValueChange={(v) => setForm({ ...form, campaign_month: Number(v) })}
            >
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {MOIS.map((label, idx) => (
                  <SelectItem key={label} value={String(idx + 1)}>{label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {!moisFixe && (
              <p className="text-xs text-muted-foreground">
                Sans objet : chaque salarié suit sa propre date d&apos;entrée.
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label>Périodicité</Label>
            <Select
              value={String(form.periodicity_years)}
              disabled={!canEdit}
              onValueChange={(v) =>
                setForm({ ...form, periodicity_years: Number(v) })
              }
            >
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                {PERIODICITES.map((p) => (
                  <SelectItem key={p.value} value={String(p.value)}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {canEdit && (
          <Button
            type="button"
            disabled={save.isPending}
            onClick={() =>
              save.mutate({
                enabled: form.enabled,
                campaign_mode: form.campaign_mode,
                campaign_month: moisFixe ? form.campaign_month : null,
                periodicity_years: form.periodicity_years,
              })
            }
          >
            Enregistrer
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
