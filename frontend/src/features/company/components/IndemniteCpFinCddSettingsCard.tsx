import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileCheck2 } from 'lucide-react';
import {
  getCompanySettings,
  patchCompanySettings,
  type IndemniteCpFinCddMethode,
} from '@/api/company';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Skeleton } from '@/components/ui/skeleton';
import { useToast } from '@/hooks/use-toast';
import { queryKeys } from '@/lib/queryKeys';
import {
  METHODES_INDEMNITE_CP_FIN_CDD,
  lireMethodeIndemniteCpFinCdd,
} from '@/features/company/utils/indemniteCpFinCddSettings';

export default function IndemniteCpFinCddSettingsCard() {
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

  const enregistree = useMemo(() => lireMethodeIndemniteCpFinCdd(data), [data]);
  const [methode, setMethode] = useState<IndemniteCpFinCddMethode>('remuneration_versee');

  useEffect(() => {
    setMethode(enregistree);
  }, [enregistree]);

  const mutation = useMutation({
    mutationFn: (valeur: IndemniteCpFinCddMethode) =>
      patchCompanySettings({ indemnite_cp_fin_cdd: valeur }),
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.companySettings(activeCompanyId), result);
      const choisie = METHODES_INDEMNITE_CP_FIN_CDD.find(
        (m) => m.valeur === lireMethodeIndemniteCpFinCdd(result)
      );
      toast({
        title: 'Enregistré',
        description: choisie
          ? `Indemnité de CP de fin de CDD : ${choisie.libelle.toLowerCase()}.`
          : 'Méthode mise à jour.',
      });
    },
    onError: (error: unknown) =>
      toast({
        title: 'Erreur',
        description:
          (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
          "Impossible d'enregistrer la méthode.",
        variant: 'destructive',
      }),
  });

  if (isLoading) {
    return <Skeleton className="h-48 w-full" />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileCheck2 className="h-5 w-5" />
          Indemnité de congés payés de fin de CDD
        </CardTitle>
        <CardDescription>
          Comment se calcule l&apos;assiette du dixième versé au dernier bulletin d&apos;un CDD.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <RadioGroup
          value={methode}
          onValueChange={(valeur) => setMethode(valeur as IndemniteCpFinCddMethode)}
          disabled={!canEdit}
          className="space-y-3"
        >
          {METHODES_INDEMNITE_CP_FIN_CDD.map((m) => (
            <div key={m.valeur} className="flex items-start gap-2 rounded-md border p-3">
              <RadioGroupItem id={`iccp-${m.valeur}`} value={m.valeur} className="mt-0.5" />
              <Label htmlFor={`iccp-${m.valeur}`} className="text-sm font-normal">
                {m.libelle}
                <span className="block text-xs text-muted-foreground">{m.description}</span>
              </Label>
            </div>
          ))}
        </RadioGroup>
        <Button
          type="button"
          disabled={!canEdit || mutation.isPending || methode === enregistree}
          onClick={() => mutation.mutate(methode)}
        >
          Enregistrer
        </Button>
      </CardContent>
    </Card>
  );
}
