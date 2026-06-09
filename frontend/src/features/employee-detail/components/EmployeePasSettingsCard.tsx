import { useEffect, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Percent } from 'lucide-react';

import { updateEmployee } from '@/api/employees';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import type { Employee } from '@/features/employee-detail/types';
import { useToast } from '@/hooks/use-toast';

interface EmployeePasSettingsCardProps {
  employeeId: string;
  employee: Employee;
  canEdit?: boolean;
  onEmployeeUpdated: (employee: Employee) => void;
}

function readPasSettings(employee: Employee) {
  const pas = employee.specificites_paie?.prelevement_a_la_source;
  const taux = typeof pas?.taux === 'number' ? pas.taux : 0;
  const isPersonnalise = pas?.is_personnalise ?? taux > 0;
  return { isPersonnalise, taux };
}

export function EmployeePasSettingsCard({
  employeeId,
  employee,
  canEdit = true,
  onEmployeeUpdated,
}: EmployeePasSettingsCardProps) {
  const { toast } = useToast();
  const [isPersonnalise, setIsPersonnalise] = useState(false);
  const [taux, setTaux] = useState('');

  useEffect(() => {
    const settings = readPasSettings(employee);
    setIsPersonnalise(settings.isPersonnalise);
    setTaux(settings.isPersonnalise ? String(settings.taux) : '');
  }, [employee]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const parsedTaux = isPersonnalise ? Number.parseFloat(taux.replace(',', '.')) : 0;
      if (isPersonnalise && (Number.isNaN(parsedTaux) || parsedTaux < 0 || parsedTaux > 100)) {
        throw new Error('Le taux PAS doit être un nombre entre 0 et 100.');
      }
      return updateEmployee(employeeId, {
        specificites_paie: {
          prelevement_a_la_source: {
            is_personnalise: isPersonnalise,
            taux: isPersonnalise ? parsedTaux : 0,
          },
        },
      });
    },
    onSuccess: (updated) => {
      onEmployeeUpdated(updated);
      toast({ title: 'Taux PAS enregistré' });
    },
    onError: (error: unknown) => {
      const message =
        error instanceof Error
          ? error.message
          : 'Impossible d’enregistrer le taux PAS.';
      toast({ title: 'Erreur', description: message, variant: 'destructive' });
    },
  });

  const current = readPasSettings(employee);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center text-base">
          <Percent className="mr-2 h-5 w-5 text-primary" />
          Prélèvement à la source (PAS)
        </CardTitle>
        <CardDescription>
          Taux transmis par l&apos;administration fiscale (DGFiP). Appliqué sur les prochains bulletins.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!canEdit ? (
          <div className="space-y-1 text-sm">
            <p className="font-medium tabular-nums">
              {current.isPersonnalise && current.taux > 0
                ? `${current.taux} %`
                : 'Taux neutre (0 %)'}
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-center space-x-3">
              <Checkbox
                id="pas-personnalise"
                checked={isPersonnalise}
                onCheckedChange={(checked) => {
                  const enabled = checked === true;
                  setIsPersonnalise(enabled);
                  if (!enabled) {
                    setTaux('');
                  } else if (!taux) {
                    setTaux(current.taux > 0 ? String(current.taux) : '');
                  }
                }}
              />
              <Label htmlFor="pas-personnalise" className="cursor-pointer">
                Appliquer un taux personnalisé
              </Label>
            </div>
            {isPersonnalise ? (
              <div className="space-y-2 pl-7">
                <Label htmlFor="pas-taux">Taux personnalisé (%)</Label>
                <Input
                  id="pas-taux"
                  type="number"
                  min={0}
                  max={100}
                  step={0.1}
                  inputMode="decimal"
                  value={taux}
                  onChange={(e) => setTaux(e.target.value)}
                  placeholder="Ex. 12.5"
                />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Sans taux personnalisé, le prélèvement à la source est calculé à 0 % sur le bulletin.
              </p>
            )}
            <Button
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
            >
              Enregistrer le taux PAS
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
