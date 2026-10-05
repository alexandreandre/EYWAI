import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, Loader2 } from 'lucide-react';

import { appliquerAugmentation } from '@/api/augmentations';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { queryKeys } from '@/lib/queryKeys';
import {
  dateEffetParDefaut,
  erreursChangementSalaire,
  lireMontant,
  messageSalaireEnregistre,
} from './salaireDate';

interface ChangerSalaireProps {
  employeeId: string;
  companyId: string;
  salaireActuel: number | null | undefined;
  /** Appelé après l'enregistrement : relire la fiche et l'historique. */
  onChanged?: () => void;
}

/**
 * « Changer le salaire » : écrit dans l'historique daté (PUT /salary), seul
 * endroit où le salaire d'un salarié avec historique se modifie. Ce bloc n'est
 * pas un formulaire : il vit dans celui du profil, sans l'imbriquer.
 */
export function ChangerSalaire({ employeeId, companyId, salaireActuel, onChanged }: ChangerSalaireProps) {
  const queryClient = useQueryClient();
  const [ouvert, setOuvert] = useState(false);
  const [montant, setMontant] = useState('');
  const [dateEffet, setDateEffet] = useState(() => dateEffetParDefaut(new Date()));
  const [erreurs, setErreurs] = useState<string[]>([]);
  const [confirmation, setConfirmation] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (nouveau: number) =>
      appliquerAugmentation(employeeId, companyId, {
        nouveau_salaire: nouveau,
        effective_date: dateEffet,
        motif: 'Changement de salaire depuis la fiche',
      }),
    onSuccess: (_data, nouveau) => {
      setConfirmation(messageSalaireEnregistre(nouveau, dateEffet, new Date()));
      setOuvert(false);
      setMontant('');
      setErreurs([]);
      queryClient.invalidateQueries({ queryKey: queryKeys.employee(companyId, employeeId) });
      queryClient.invalidateQueries({ queryKey: ['salary-history', employeeId, companyId] });
      onChanged?.();
    },
    onError: (error: unknown) => {
      const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setErreurs([
        typeof detail === 'string'
          ? `${detail} Corrigez la saisie puis réessayez : rien n'a été enregistré.`
          : 'Le salaire n’a pas été enregistré. Vérifiez votre connexion puis réessayez.',
      ]);
    },
  });

  const valider = () => {
    const trouvees = erreursChangementSalaire({ montant, dateEffet });
    setErreurs(trouvees);
    const valeur = lireMontant(montant);
    if (trouvees.length === 0 && valeur !== null) {
      setConfirmation(null);
      mutation.mutate(valeur);
    }
  };

  return (
    <div className="space-y-2 rounded-md border border-dashed p-4 sm:col-span-2">
      <p className="text-sm">
        Salaire de base actuel : <strong>{salaireActuel ?? '—'} €</strong>. Il suit l’historique des
        salaires : il se change avec une date d’effet.
      </p>
      {confirmation && (
        <p role="status" className="flex items-start gap-1.5 text-sm text-green-700">
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {confirmation}
        </p>
      )}
      {!ouvert ? (
        <Button type="button" variant="outline" size="sm" onClick={() => setOuvert(true)}>
          Changer le salaire
        </Button>
      ) : (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="nouveau-salaire">Nouveau salaire de base mensuel brut (€)</Label>
              <Input
                id="nouveau-salaire"
                inputMode="decimal"
                value={montant}
                onChange={(e) => setMontant(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="date-effet-salaire">Date d’effet</Label>
              <Input
                id="date-effet-salaire"
                type="date"
                value={dateEffet}
                onChange={(e) => setDateEffet(e.target.value)}
              />
            </div>
          </div>
          {erreurs.length > 0 && (
            <ul role="alert" className="space-y-1 text-sm text-destructive">
              {erreurs.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
          <div className="flex gap-2">
            <Button type="button" size="sm" onClick={valider} disabled={mutation.isPending}>
              {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />}
              Enregistrer le salaire
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => {
                setOuvert(false);
                setErreurs([]);
              }}
              disabled={mutation.isPending}
            >
              Annuler
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
