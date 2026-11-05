import type { Control } from 'react-hook-form';
import { useWatch } from 'react-hook-form';

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
  MOTIFS_DISPENSE_MUTUELLE,
  motifDispense,
} from '@/features/employee-detail/components/dispenseMutuelle';
import type { EmployeeProfileEditFormValues } from '@/features/employee-detail/components/employeeProfileEditSchema';

/**
 * Le salarié refuse la mutuelle de l'entreprise : la RH pose la dispense, avec
 * son motif légal et la date de la demande signée (D911-2, R242-1-6). Ne
 * s'affiche que quand aucune formule n'est choisie.
 */
export function DispenseMutuelleFields({
  control,
}: {
  control: Control<EmployeeProfileEditFormValues>;
}) {
  const dispense = useWatch({ control, name: 'specificites_paie.mutuelle.dispense' });
  const motif = motifDispense(dispense?.motif ?? '');

  return (
    <div className="mt-3 space-y-3 rounded-md border p-4">
      <FormField
        control={control}
        name="specificites_paie.mutuelle.dispense.active"
        render={({ field }) => (
          <FormItem className="flex flex-row items-start space-x-3 space-y-0">
            <FormControl>
              <Checkbox checked={field.value ?? false} onCheckedChange={(c) => field.onChange(c === true)} />
            </FormControl>
            <div className="space-y-1 leading-none">
              <FormLabel>Le salarié ne veut pas adhérer (dispense)</FormLabel>
              <p className="text-xs text-muted-foreground">
                Seulement dans un cas prévu par la loi, et avec sa demande signée.
              </p>
            </div>
          </FormItem>
        )}
      />

      {dispense?.active ? (
        <div className="space-y-3">
          <FormField
            control={control}
            name="specificites_paie.mutuelle.dispense.motif"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Motif de la dispense</FormLabel>
                <Select onValueChange={field.onChange} value={field.value || ''}>
                  <FormControl>
                    <SelectTrigger><SelectValue placeholder="Choisir le motif" /></SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    {MOTIFS_DISPENSE_MUTUELLE.map((m) => (
                      <SelectItem key={m.code} value={m.code}>{m.libelle}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {motif ? (
                  <p className="text-xs text-muted-foreground">
                    {motif.source}.
                    {motif.selonActe
                      ? " Valable seulement si l'acte de l'entreprise (décision unilatérale ou accord) prévoit ce cas."
                      : ''}
                  </p>
                ) : null}
                <FormMessage />
              </FormItem>
            )}
          />

          <div className="grid gap-3 sm:grid-cols-2">
            <FormField
              control={control}
              name="specificites_paie.mutuelle.dispense.demande_recue_le"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Demande signée reçue le</FormLabel>
                  <FormControl><Input {...field} type="date" /></FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            {motif?.besoin === 'justificatif' ? (
              <FormField
                control={control}
                name="specificites_paie.mutuelle.dispense.justificatif_recu_le"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Dernier justificatif reçu le</FormLabel>
                    <FormControl><Input {...field} type="date" /></FormControl>
                    <p className="text-xs text-muted-foreground">
                      À redemander chaque année ; vide, c'est la date de la demande.
                    </p>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}

            {motif?.besoin === 'fin' ? (
              <FormField
                control={control}
                name="specificites_paie.mutuelle.dispense.fin_le"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Fin de la dispense le</FormLabel>
                    <FormControl><Input {...field} type="date" /></FormControl>
                    <p className="text-xs text-muted-foreground">
                      {motif.code === 'css'
                        ? "Fin de l'aide (complémentaire santé solidaire)."
                        : 'Échéance du contrat individuel.'}
                    </p>
                    <FormMessage />
                  </FormItem>
                )}
              />
            ) : null}
          </div>

          <p className="text-xs text-muted-foreground">
            Gardez la demande signée : elle doit dire que le salarié a été informé des conséquences
            de son choix (CSS R242-1-6).
          </p>
        </div>
      ) : null}
    </div>
  );
}
