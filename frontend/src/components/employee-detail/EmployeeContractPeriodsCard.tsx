import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  addContractPeriod,
  deleteContractPeriod,
  listContractPeriods,
  type ContractPeriod,
} from '@/api/contractPeriods';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from '@/components/ui/use-toast';
import type { Employee } from '@/features/employee-detail/types';

const TYPES = ['CDI', 'CDD', 'Alternance', 'Intérim', 'Autre'] as const;

function jour(iso: string | null | undefined): string {
  if (!iso) return '';
  return iso.slice(0, 10);
}

function libelleDate(iso: string | null | undefined, siVide: string): string {
  const brut = jour(iso);
  if (!brut) return siVide;
  const [annee, mois, jourMois] = brut.split('-');
  if (!annee || !mois || !jourMois) return brut;
  return `${jourMois}/${mois}/${annee}`;
}

export function periodesPasseesVisibles(
  periodes: ContractPeriod[],
  hireDate: string | null | undefined,
  endDate: string | null | undefined,
): ContractPeriod[] {
  const debutFiche = jour(hireDate);
  const finFiche = jour(endDate);
  return periodes.filter((periode) => {
    if (!debutFiche) return true;
    return !(jour(periode.date_debut) === debutFiche && jour(periode.date_fin) === finFiche);
  });
}

export function EmployeeContractPeriodsCard({ employee }: { employee: Employee }) {
  const queryClient = useQueryClient();
  const [contractType, setContractType] = useState<string>('CDD');
  const [dateDebut, setDateDebut] = useState('');
  const [dateFin, setDateFin] = useState('');

  const query = useQuery({
    queryKey: ['contract-periods', employee.id],
    queryFn: () => listContractPeriods(employee.id),
  });

  const ajouter = useMutation({
    mutationFn: () =>
      addContractPeriod(employee.id, {
        contract_type: contractType,
        date_debut: dateDebut,
        date_fin: dateFin,
      }),
    onSuccess: () => {
      setDateDebut('');
      setDateFin('');
      queryClient.invalidateQueries({ queryKey: ['contract-periods', employee.id] });
    },
    onError: () => {
      toast({ title: 'Le contrat n’a pas été enregistré.', variant: 'destructive' });
    },
  });

  const retirer = useMutation({
    mutationFn: (periodId: string) => deleteContractPeriod(employee.id, periodId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contract-periods', employee.id] });
    },
  });

  const passees = periodesPasseesVisibles(
    query.data ?? [],
    employee.hire_date,
    employee.contract_end_date,
  );
  const anciennete = employee.seniority_reference_date || employee.hire_date;

  function soumettre(event: FormEvent) {
    event.preventDefault();
    if (!dateDebut || !dateFin || dateFin < dateDebut) {
      toast({
        title: 'Indiquez un début et une fin, la fin après le début.',
        variant: 'destructive',
      });
      return;
    }
    ajouter.mutate();
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Contrats</CardTitle>
        <CardDescription>
          Le contrat en cours est celui de la fiche. Ajoutez ici un contrat déjà terminé,
          par exemple un CDD avant une réembauche. Le trou entre deux contrats reste visible :
          l’ancienneté ne se recolle pas toute seule.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm">
          Date d’ancienneté sur la fiche : {libelleDate(anciennete, 'non renseignée')}.
          Elle ne change pas quand vous ajoutez un contrat.
        </p>
        <ul className="space-y-2 text-sm">
          <li className="rounded-md border px-3 py-2">
            <span className="font-medium">{employee.contract_type || 'Contrat en cours'}</span>
            {' — '}
            {libelleDate(employee.hire_date, 'début non renseigné')}
            {' → '}
            {libelleDate(employee.contract_end_date, 'en cours')}
            <span className="ml-2 text-muted-foreground">fiche</span>
          </li>
          {passees.map((periode) => (
            <li key={periode.id} className="flex items-center justify-between gap-3 rounded-md border px-3 py-2">
              <span>
                <span className="font-medium">{periode.contract_type}</span>
                {' — '}
                {libelleDate(periode.date_debut, '')}
                {' → '}
                {libelleDate(periode.date_fin, '')}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => retirer.mutate(periode.id)}
              >
                Retirer
              </Button>
            </li>
          ))}
        </ul>
        {query.isError ? (
          <p className="text-sm text-muted-foreground">Les contrats passés ne sont pas disponibles.</p>
        ) : null}
        <form onSubmit={soumettre} className="grid gap-3 sm:grid-cols-4">
          <div className="space-y-1">
            <Label>Type</Label>
            <Select value={contractType} onValueChange={setContractType}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TYPES.map((type) => (
                  <SelectItem key={type} value={type}>
                    {type}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label htmlFor="contrat-debut">Début</Label>
            <Input id="contrat-debut" type="date" value={dateDebut} onChange={(e) => setDateDebut(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="contrat-fin">Fin</Label>
            <Input id="contrat-fin" type="date" value={dateFin} onChange={(e) => setDateFin(e.target.value)} />
          </div>
          <div className="flex items-end">
            <Button type="submit" disabled={ajouter.isPending}>
              Ajouter
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
