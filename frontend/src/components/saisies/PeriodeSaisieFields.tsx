import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { erreurPeriodeSaisie, libelleAvecPeriode } from './periodeSaisie';

interface Props {
  nom: string;
  debut: string;
  fin: string;
  onDebutChange: (value: string) => void;
  onFinChange: (value: string) => void;
}

export function PeriodeSaisieFields({ nom, debut, fin, onDebutChange, onFinChange }: Props) {
  const erreur = erreurPeriodeSaisie(debut, fin);
  return (
    <fieldset className="space-y-2 rounded-md border p-3">
      <legend className="px-1 text-sm font-medium">Période à afficher sur le bulletin (facultatif)</legend>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label htmlFor="saisie-periode-debut">Du</Label>
          <Input id="saisie-periode-debut" type="date" value={debut}
            onChange={(e) => onDebutChange(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="saisie-periode-fin">Au</Label>
          <Input id="saisie-periode-fin" type="date" value={fin} min={debut || undefined}
            onChange={(e) => onFinChange(e.target.value)} />
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Les dates complètent le libellé imprimé, par exemple pour un rappel de maintien.
        Le versement reste sur le mois sélectionné. Vérifiez le maintien déjà calculé avant d’ajouter un complément.
      </p>
      {(debut || fin) && (
        erreur
          ? <p role="alert" className="text-xs text-destructive">{erreur}</p>
          : <p className="text-xs" aria-live="polite">
              Libellé du bulletin : {libelleAvecPeriode(nom || 'Saisie', debut, fin)}
            </p>
      )}
    </fieldset>
  );
}
