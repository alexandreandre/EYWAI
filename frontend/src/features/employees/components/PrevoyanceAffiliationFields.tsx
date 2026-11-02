import { useQuery } from '@tanstack/react-query';
import { PlusCircle, Trash2 } from 'lucide-react';
import { type ComponentProps, forwardRef, useEffect, useRef, useState } from 'react';
import {
  type ArrayPath,
  type Control,
  type FieldValues,
  type Path,
  useController,
  useFieldArray,
  useWatch,
} from 'react-hook-form';
import { CLE_FORMULES_PREVOYANCE, prevoyanceFormulesApi } from '@/api/prevoyanceFormules';

import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  formulesPourLeStatut,
  lignesDeLaFormule,
  lignesModifiees,
} from '@/features/employees/utils/formulesPrevoyance';
import {
  aideLignesPrevoyance,
  fractionDuTexteTaux,
  texteDuTauxPrevoyance,
} from '@/features/employees/utils/prevoyance';
import { isEmployeeCadre } from '@/lib/mutuelleUtils';

const SANS_FORMULE = '__sans_formule__';

type PrevoyanceAffiliationFieldsProps<T extends FieldValues> = {
  control: Control<T>;
  namePrefix: Path<T>;
  statut?: string | null;
};

type ChampTauxPourcentProps = Omit<ComponentProps<typeof Input>, 'value' | 'onChange'> & {
  value: unknown;
  onChange: (valeur: number | string) => void;
};

/**
 * Un taux de prévoyance : saisi et affiché en %, stocké en fraction comme le
 * moteur le lit ([D1], 13/10/2026). Tant que la saisie ne change pas, la valeur
 * du formulaire reste celle de la fiche, au chiffre près.
 */
const ChampTauxPourcent = forwardRef<HTMLInputElement, ChampTauxPourcentProps>(
  function ChampTauxPourcent({ value, onChange, ...props }, ref) {
    const [texte, setTexte] = useState(() => texteDuTauxPrevoyance(value));
    const derniere = useRef<unknown>(value);

    // Valeur posée hors de la saisie (formulaire rechargé, contrat lu) : on l'affiche.
    useEffect(() => {
      if (value !== derniere.current) {
        derniere.current = value;
        setTexte(texteDuTauxPrevoyance(value));
      }
    }, [value]);

    return (
      <Input
        {...props}
        ref={ref}
        inputMode="decimal"
        value={texte}
        onChange={(e) => {
          const saisie = e.target.value;
          // Une saisie qui n'est pas un nombre reste telle quelle : le schéma la
          // refuse sous le champ, au lieu d'enregistrer 0 sans le dire.
          const valeur = fractionDuTexteTaux(saisie) ?? saisie;
          derniere.current = valeur;
          setTexte(saisie);
          onChange(valeur);
        }}
      />
    );
  },
);

export function PrevoyanceAffiliationFields<T extends FieldValues>({
  control,
  namePrefix,
  statut,
}: PrevoyanceAffiliationFieldsProps<T>) {
  const adhesionPath = `${namePrefix}.adhesion` as Path<T>;
  const lignesPath = `${namePrefix}.lignes_specifiques` as Path<T>;
  const adhesion = useWatch({ control, name: adhesionPath }) as boolean | undefined;
  const lignes = useWatch({ control, name: lignesPath }) as unknown[] | undefined;
  const cadre = isEmployeeCadre(statut);

  const { fields, append, remove, replace } = useFieldArray({
    control,
    name: lignesPath as ArrayPath<T>,
  });
  const { field: formuleField } = useController({
    control,
    name: `${namePrefix}.formule_id` as Path<T>,
  });
  // Les formules de la société (02/11/2026) : en choisir une copie ses lignes.
  const { data: formules = [] } = useQuery({
    queryKey: CLE_FORMULES_PREVOYANCE,
    queryFn: prevoyanceFormulesApi.lister,
    staleTime: 60_000,
  });
  const proposees = formulesPourLeStatut(formules, cadre);
  const formuleId = (formuleField.value as string | null | undefined) ?? null;
  const choisie = formules.find((f) => f.id === formuleId);
  const horsListe = choisie && !proposees.includes(choisie);
  const choisirFormule = (valeur: string) => {
    if (valeur === SANS_FORMULE) {
      formuleField.onChange(null);
      return;
    }
    const formule = formules.find((f) => f.id === valeur);
    if (!formule) return;
    replace(lignesDeLaFormule(formule) as never);
    formuleField.onChange(formule.id);
  };

  const categoryLabel = cadre ? 'cadre' : 'non-cadre';

  return (
    <div className="space-y-4 rounded-md border p-4">
      <FormField
        control={control}
        name={adhesionPath}
        render={({ field }) => (
          <FormItem className="flex flex-row items-center space-x-3 space-y-0">
            <FormControl>
              <Checkbox checked={field.value} onCheckedChange={field.onChange} />
            </FormControl>
            <FormLabel className="font-normal">
              Adhésion prévoyance ({categoryLabel})
            </FormLabel>
            <FormMessage />
          </FormItem>
        )}
      />

      {adhesion ? (
        <div className="ml-2 space-y-4 border-l-2 pl-6">
          {proposees.length > 0 || choisie ? (
            <div className="space-y-1">
              <p className="text-sm font-medium">Formule de la société</p>
              <Select value={choisie ? choisie.id : SANS_FORMULE} onValueChange={choisirFormule}>
                <SelectTrigger className="max-w-md">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={SANS_FORMULE}>Aucune (lignes saisies à la main)</SelectItem>
                  {proposees.map((f) => (
                    <SelectItem key={f.id} value={f.id}>
                      {f.libelle}
                    </SelectItem>
                  ))}
                  {choisie && horsListe ? (
                    <SelectItem value={choisie.id}>
                      {choisie.libelle} ({choisie.is_active ? 'autre catégorie' : 'formule retirée'})
                    </SelectItem>
                  ) : null}
                </SelectContent>
              </Select>
              {choisie && !choisie.is_active ? (
                <p className="text-xs text-muted-foreground">
                  Formule retirée : la fiche garde ses lignes.
                </p>
              ) : null}
              {choisie && choisie.is_active && lignesModifiees(lignes as never, choisie) ? (
                <p className="text-xs text-amber-700">
                  Lignes modifiées depuis la formule « {choisie.libelle} ».
                </p>
              ) : null}
            </div>
          ) : null}
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium">
              Lignes de prévoyance ({categoryLabel})
            </h4>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                append({
                  id: `prevoyance_${fields.length + 1}`,
                  libelle: '',
                  salarial: 0,
                  patronal: 0,
                  forfait_social: 0,
                } as never)
              }
            >
              <PlusCircle className="mr-2 h-4 w-4" />
              Ajouter une ligne
            </Button>
          </div>

          {aideLignesPrevoyance(cadre, lignes?.length ?? 0) ? (
            <p className={cadre ? 'text-xs text-amber-700' : 'text-xs text-muted-foreground'}>
              {aideLignesPrevoyance(cadre, lignes?.length ?? 0)}
            </p>
          ) : null}

          {fields.map((field, index) => (
            <div key={field.id} className="space-y-2 border-b pb-4 last:border-b-0">
              <div className="flex items-end justify-between gap-2">
                <FormField
                  control={control}
                  name={`${namePrefix}.lignes_specifiques.${index}.libelle` as Path<T>}
                  render={({ field: libelleField }) => (
                    <FormItem className="flex-grow">
                      <FormLabel>Libellé</FormLabel>
                      <FormControl>
                        <Input {...libelleField} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="shrink-0 text-destructive hover:text-destructive"
                  onClick={() => remove(index)}
                  title="Supprimer la ligne"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <FormField
                  control={control}
                  name={`${namePrefix}.lignes_specifiques.${index}.salarial` as Path<T>}
                  render={({ field: salarialField }) => (
                    <FormItem>
                      <FormLabel>Taux salarial (%)</FormLabel>
                      <FormControl>
                        <ChampTauxPourcent {...salarialField} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={control}
                  name={`${namePrefix}.lignes_specifiques.${index}.patronal` as Path<T>}
                  render={({ field: patronalField }) => (
                    <FormItem>
                      <FormLabel>Taux patronal (%)</FormLabel>
                      <FormControl>
                        <ChampTauxPourcent {...patronalField} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
                <FormField
                  control={control}
                  name={`${namePrefix}.lignes_specifiques.${index}.forfait_social` as Path<T>}
                  render={({ field: fsField }) => (
                    <FormItem>
                      <FormLabel>Forfait social (%)</FormLabel>
                      <FormControl>
                        <ChampTauxPourcent {...fsField} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
