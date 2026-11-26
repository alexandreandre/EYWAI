import type { Control } from 'react-hook-form';
import { useWatch } from 'react-hook-form';

import { Checkbox } from '@/components/ui/checkbox';
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import type { EmployeeProfileEditFormValues } from '@/features/employee-detail/components/employeeProfileEditSchema';
import { joursAttendus, RETRAITE_PROGRESSIVE_VIDE } from '@/features/employee-detail/components/retraiteProgressive';

type Cle = 'vieillesse_temps_plein' | 'complementaire_temps_plein' | 'prise_en_charge_part_salariale';

function Case({
  control,
  cle,
  libelle,
  aide,
}: {
  control: Control<EmployeeProfileEditFormValues>;
  cle: Cle;
  libelle: string;
  aide: string;
}) {
  return (
    <FormField
      control={control}
      name={`specificites_paie.retraite_progressive.${cle}`}
      render={({ field }) => (
        <FormItem className="flex flex-row items-start space-x-3 space-y-0">
          <FormControl>
            <Checkbox checked={Boolean(field.value)} onCheckedChange={(c) => field.onChange(c === true)} />
          </FormControl>
          <div className="space-y-1 leading-none">
            <FormLabel>{libelle}</FormLabel>
            <p className="text-xs text-muted-foreground">{aide}</p>
            <FormMessage />
          </div>
        </FormItem>
      )}
    />
  );
}

/**
 * Retraite progressive : quotité, dates, et l'accord sur les cotisations
 * vieillesse à temps plein. Le bulletin ajoute les lignes « Surcotisation
 * retraite progressive » ; la DSN déclare les bases 22 et 24.
 */
export function RetraiteProgressiveFields({
  control,
  isForfaitJour,
  joursForfait,
}: {
  control: Control<EmployeeProfileEditFormValues>;
  isForfaitJour: boolean;
  joursForfait: string;
}) {
  const reglage = useWatch({ control, name: 'specificites_paie.retraite_progressive' }) ?? RETRAITE_PROGRESSIVE_VIDE;
  const jours = joursAttendus(reglage);
  const forfaitSaisi = Number(String(joursForfait ?? '').replace(',', '.')) || 218;
  const forfaitAReprendre = isForfaitJour && reglage.actif && jours !== null && Math.abs(forfaitSaisi - jours) > 1;

  return (
    <div className="space-y-3 rounded-md border p-4">
      <FormField
        control={control}
        name="specificites_paie.retraite_progressive.actif"
        render={({ field }) => (
          <FormItem className="flex flex-row items-start space-x-3 space-y-0">
            <FormControl>
              <Checkbox checked={Boolean(field.value)} onCheckedChange={(c) => field.onChange(c === true)} />
            </FormControl>
            <div className="space-y-1 leading-none">
              <FormLabel>Retraite progressive</FormLabel>
              <p className="text-xs text-muted-foreground">
                Le salarié touche une part de sa retraite et travaille à temps partiel (40 à 80 % du temps plein).
              </p>
            </div>
          </FormItem>
        )}
      />

      {reglage.actif ? (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-3">
            <FormField
              control={control}
              name="specificites_paie.retraite_progressive.quotite"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Temps travaillé (%)</FormLabel>
                  <FormControl>
                    <Input {...field} value={field.value ?? ''} inputMode="decimal" placeholder="50" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={control}
              name="specificites_paie.retraite_progressive.date_debut"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Depuis le</FormLabel>
                  <FormControl>
                    <Input {...field} value={field.value ?? ''} type="date" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={control}
              name="specificites_paie.retraite_progressive.date_fin"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Jusqu&apos;au (facultatif)</FormLabel>
                  <FormControl>
                    <Input {...field} value={field.value ?? ''} type="date" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>

          {forfaitAReprendre ? (
            <p className="rounded-md bg-amber-50 p-2 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-100">
              À {reglage.quotite} %, le forfait est de {jours} jours par an ; la fiche en compte {forfaitSaisi}. Le
              salaire et les jours du bulletin suivent la fiche : modifiez les jours du forfait et le salaire si le
              temps de travail a changé.
            </p>
          ) : null}

          <Case
            control={control}
            cle="vieillesse_temps_plein"
            libelle="Cotisations vieillesse sur un temps plein"
            aide={
              isForfaitJour
                ? "Accord écrit de l'employeur. Au forfait jours, ouvert seulement sous 1,7 SMIC : au-delà, le bulletin le signale et ne pose rien."
                : "Accord écrit de l'employeur. La différence avec le temps partiel s'ajoute au bulletin (« Surcotisation retraite progressive »)."
            }
          />
          <Case
            control={control}
            cle="complementaire_temps_plein"
            libelle="Retraite complémentaire (Agirc-Arrco) sur un temps plein"
            aide="Seulement si l'accord le prévoit aussi pour la complémentaire."
          />
          <Case
            control={control}
            cle="prise_en_charge_part_salariale"
            libelle="L'employeur paie aussi la part salariale du supplément"
            aide="Décoché : l'employeur paie sa part, le salarié la sienne (retenue sur son net). Coché avec la complémentaire : l'employeur paie en plus le forfait social de 20 % sur la part complémentaire prise en charge."
          />
          <FormField
            control={control}
            name="specificites_paie.retraite_progressive.salaire_temps_plein"
            render={({ field }) => (
              <FormItem className="sm:max-w-sm">
                <FormLabel>Salaire temps plein (facultatif)</FormLabel>
                <FormControl>
                  <Input {...field} value={field.value ?? ''} inputMode="decimal" placeholder="Calculé par Martine" />
                </FormControl>
                <p className="text-xs text-muted-foreground">
                  Vide : Martine le calcule chaque mois. À remplir seulement si l&apos;accord fixe un montant.
                </p>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>
      ) : null}
    </div>
  );
}
