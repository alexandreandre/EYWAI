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
  return {
    isPersonnalise,
    taux,
    typeTaux: pas?.type_taux ?? null,
    periode: pas?.periode ?? null,
  };
}

/**
 * D'où vient le taux appliqué.
 *
 * La nomenclature DSN distingue le taux personnalisé que la DGFiP transmet
 * (01) du barème appliqué en attendant sa réponse (13). La distinction compte :
 * un salarié au barème n'est pas mal paramétré, il attend son premier compte
 * rendu métier.
 */
function origineLibelle(typeTaux: string | null): string | null {
  if (!typeTaux) return null;
  if (typeTaux === '01') return 'Taux transmis par la DGFiP';
  if (typeTaux === '13') return 'Taux barème, en attente du taux DGFiP';
  return `Type de taux ${typeTaux}`;
}

function periodeLibelle(periode: string | null): string | null {
  if (!periode) return null;
  const [annee, mois] = periode.split('-');
  const libelles = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
  ];
  const index = Number(mois) - 1;
  return libelles[index] ? `Reçu sur la période de ${libelles[index]} ${annee}` : periode;
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
        <div className="space-y-1 rounded-md border bg-muted/30 p-3 text-sm">
          <p className="font-medium tabular-nums">
            {current.isPersonnalise || current.taux > 0
              ? `${current.taux} %`
              : 'Aucun taux connu — 0 % appliqué'}
          </p>
          {origineLibelle(current.typeTaux) ? (
            <p className="text-muted-foreground">{origineLibelle(current.typeTaux)}</p>
          ) : null}
          {periodeLibelle(current.periode) ? (
            <p className="text-xs text-muted-foreground">
              {periodeLibelle(current.periode)}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              Période d&apos;origine inconnue : déposez la dernière déclaration depuis
              l&apos;écran Prélèvement à la source pour la dater.
            </p>
          )}
        </div>
        {canEdit ? (
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
                Saisir le taux à la main
              </Label>
            </div>
            {isPersonnalise ? (
              <div className="space-y-2 pl-7">
                <Label htmlFor="pas-taux">Taux (%)</Label>
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
                Sans taux connu, le prélèvement à la source est calculé à 0 % sur le
                bulletin. La saisie manuelle sera écrasée au prochain dépôt de
                déclaration : elle sert à dépanner, pas à décider du taux.
              </p>
            )}
            <Button
              onClick={() => saveMutation.mutate()}
              disabled={saveMutation.isPending}
            >
              Enregistrer le taux PAS
            </Button>
          </>
        ) : null}
      </CardContent>
    </Card>
  );
}
