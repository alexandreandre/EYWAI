import { PlusCircle, Trash2 } from 'lucide-react';
import {
  type Control,
  type FieldValues,
  type Path,
  useFieldArray,
  useWatch,
} from 'react-hook-form';

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
import { isEmployeeCadre } from '@/lib/mutuelleUtils';

type PrevoyanceAffiliationFieldsProps<T extends FieldValues> = {
  control: Control<T>;
  namePrefix: Path<T>;
  statut?: string | null;
};

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

  const { fields, append, remove } = useFieldArray({
    control,
    name: lignesPath,
  });

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

          {!cadre && (lignes?.length ?? 0) === 0 ? (
            <p className="text-xs text-muted-foreground">
              Sans ligne saisie, le barème national s&apos;applique au bulletin.
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
                        <Input type="number" step="0.0001" {...salarialField} />
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
                        <Input type="number" step="0.0001" {...patronalField} />
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
                        <Input type="number" step="0.01" {...fsField} />
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
