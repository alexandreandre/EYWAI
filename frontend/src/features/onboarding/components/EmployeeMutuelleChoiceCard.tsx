import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { HeartHandshake, Loader2 } from 'lucide-react';
import { useState } from 'react';

import {
  getMyMutuelleChoices,
  setMyMutuelleChoice,
  type EmployeeMutuelleChoices,
} from '@/api/pscSettings';
import { MutuelleSelectionField } from '@/components/mutuelle/MutuelleSelectionField';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useToast } from '@/hooks/use-toast';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import type { MutuelleType } from '@/api/mutuelleTypes';

export interface EmployeeMutuelleChoiceCardProps {
  employeeStatut?: string | null;
}

export function EmployeeMutuelleChoiceCard({ employeeStatut }: EmployeeMutuelleChoiceCardProps) {
  const companyId = useActiveCompanyId();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const choicesQuery = useQuery({
    queryKey: ['mutuelle-choices', 'me', companyId],
    queryFn: getMyMutuelleChoices,
    enabled: Boolean(companyId),
  });

  const data = choicesQuery.data;
  const currentId = selectedId ?? data?.current_mutuelle_type_id ?? null;

  const saveMutation = useMutation({
    mutationFn: (mutuelleTypeId: string) => setMyMutuelleChoice(mutuelleTypeId),
    onSuccess: (updated: EmployeeMutuelleChoices) => {
      setSelectedId(updated.current_mutuelle_type_id ?? null);
      queryClient.setQueryData(['mutuelle-choices', 'me', companyId], updated);
      toast({
        title: 'Mutuelle enregistrée',
        description: 'Votre formule mutuelle a bien été enregistrée.',
      });
    },
    onError: (error: unknown) => {
      const detail =
        error &&
        typeof error === 'object' &&
        'response' in error &&
        (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      toast({
        title: 'Enregistrement impossible',
        description: typeof detail === 'string' ? detail : 'Réessayez plus tard.',
        variant: 'destructive',
      });
    },
  });

  if (choicesQuery.isPending || choicesQuery.isError || !data) {
    return null;
  }

  if (!data.self_service_enabled) {
    return null;
  }

  if (data.options.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <HeartHandshake className="h-4 w-4" />
            Mutuelle
          </CardTitle>
          <CardDescription>
            Aucune formule mutuelle n&apos;est encore disponible pour votre profil. Contactez les RH.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const mutuelles = data.options.map(
    (o): MutuelleType => ({
      id: o.id,
      company_id: companyId ?? '',
      libelle: o.libelle,
      montant_salarial: o.montant_salarial,
      montant_patronal: o.montant_patronal,
      part_patronale_soumise_a_csg: true,
      is_active: true,
      pack_couverture: o.pack_couverture as MutuelleType['pack_couverture'],
      statut_categoriel: o.statut_categoriel as MutuelleType['statut_categoriel'],
      organisme_label: o.organisme_label,
      note: o.note,
    }),
  );

  const hasSelection = Boolean(currentId);
  const isDirty = selectedId !== null && selectedId !== data.current_mutuelle_type_id;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <HeartHandshake className="h-4 w-4" />
          Choisir ma mutuelle
        </CardTitle>
        <CardDescription>
          Sélectionnez la formule correspondant à votre situation (isolé, duo, famille…).
          {data.organisme_label ? ` Organisme : ${data.organisme_label}.` : ''}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <MutuelleSelectionField
          mutuelles={mutuelles}
          value={currentId}
          onChange={setSelectedId}
          employeeStatut={employeeStatut}
          companyOrganismeLabel={data.organisme_label}
        />
        <div className="flex justify-end">
          <Button
            type="button"
            disabled={!currentId || saveMutation.isPending || (!isDirty && hasSelection)}
            onClick={() => currentId && saveMutation.mutate(currentId)}
          >
            {saveMutation.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Enregistrement…
              </>
            ) : hasSelection && !isDirty ? (
              'Formule enregistrée'
            ) : (
              'Enregistrer ma mutuelle'
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
