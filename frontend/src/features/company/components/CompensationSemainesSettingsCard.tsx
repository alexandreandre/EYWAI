import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeftRight } from 'lucide-react';
import { getCompanySettings, patchCompanySettings } from '@/api/company';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';
import { lireCompensationSemaines } from '@/features/company/utils/compensationSemainesSettings';

export default function CompensationSemainesSettingsCard() {
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
    queryKey: queryKeys.companySettings(activeCompanyId),
    queryFn: getCompanySettings,
    enabled: Boolean(activeCompanyId),
  });

  const enregistre = useMemo(() => lireCompensationSemaines(data), [data]);
  const [active, setActive] = useState(false);

  useEffect(() => {
    setActive(enregistre);
  }, [enregistre]);

  const mutation = useMutation({
    mutationFn: (valeur: boolean) =>
      patchCompanySettings({ compensation_heures_entre_semaines: valeur }),
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.companySettings(activeCompanyId), result);
      toast({
        title: 'Enregistré',
        description: lireCompensationSemaines(result)
          ? 'Les heures se compensent entre semaines sur la fenêtre de paie.'
          : 'Retour à la règle hebdomadaire : chaque semaine se règle seule.',
      });
    },
    onError: (error: unknown) =>
      toast({
        title: 'Erreur',
        description:
          (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          "Impossible d'enregistrer l'option.",
        variant: 'destructive',
      }),
  });

  if (isLoading) {
    return <Skeleton className="h-40 w-full" />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ArrowLeftRight className="h-5 w-5" />
          Compensation des heures entre semaines
        </CardTitle>
        <CardDescription>
          Comment les heures manquantes d&apos;une semaine se règlent face aux heures
          supplémentaires des autres semaines de la même paie.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-start gap-2 rounded-md border p-3">
          <Checkbox
            id="compensation-semaines"
            checked={active}
            disabled={!canEdit}
            onCheckedChange={(checked) => setActive(checked === true)}
          />
          <Label htmlFor="compensation-semaines" className="text-sm font-normal">
            Compenser les heures entre les semaines de la fenêtre de paie
            <span className="block text-xs text-muted-foreground">
              Chaque semaine est soldée (écart entre heures faites et horaire prévu, majorations
              à 25 % puis 50 %), puis les semaines s&apos;additionnent sur la fenêtre des
              variables, semaines en manque comprises. Une semaine courte réduit les heures
              supplémentaires payées ; elle ne donne jamais lieu à une retenue. Le bulletin le
              mentionne.
            </span>
          </Label>
        </div>
        <p className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
          Choix de l&apos;entreprise, à assumer en connaissance de cause : la règle légale décompte
          les heures supplémentaires et les absences semaine par semaine, sans compensation
          entre semaines. Décochée, l&apos;option laisse la règle hebdomadaire s&apos;appliquer.
        </p>
        <Button
          type="button"
          disabled={!canEdit || mutation.isPending || active === enregistre}
          onClick={() => mutation.mutate(active)}
        >
          Enregistrer
        </Button>
      </CardContent>
    </Card>
  );
}
