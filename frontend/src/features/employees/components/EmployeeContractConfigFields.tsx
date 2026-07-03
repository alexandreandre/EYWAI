import type { Control, FieldPath, FieldValues } from 'react-hook-form';
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
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  CONTRACT_TYPES,
  EMPLOYEE_STATUSES,
  isAlternanceContract,
  isApprentissageContract,
  needsContractEndDate,
  type EmployeeContractConfigValues,
} from '@/constants/contracts';

type ControlledProps = {
  values: EmployeeContractConfigValues;
  onChange: (patch: Partial<EmployeeContractConfigValues>) => void;
  showStatut?: boolean;
  idPrefix?: string;
};

type FormProps<T extends FieldValues> = {
  control: Control<T>;
  contractTypeName?: FieldPath<T>;
  statutName?: FieldPath<T>;
  isForfaitJourName?: FieldPath<T>;
  contractEndDateName?: FieldPath<T>;
  dateDebutExecutionName?: FieldPath<T>;
  dateConclusionContratName?: FieldPath<T>;
  maintienRegimeName?: FieldPath<T>;
  showStatut?: boolean;
};

function ContractTypeSelect({
  value,
  onValueChange,
  id,
}: {
  value: string;
  onValueChange: (value: string) => void;
  id?: string;
}) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger id={id}>
        <SelectValue placeholder="Choisir un type" />
      </SelectTrigger>
      <SelectContent>
        {CONTRACT_TYPES.map((type) => (
          <SelectItem key={type} value={type}>
            {type}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function StatutSelect({
  value,
  onValueChange,
  id,
}: {
  value: string;
  onValueChange: (value: string) => void;
  id?: string;
}) {
  return (
    <Select value={value} onValueChange={onValueChange}>
      <SelectTrigger id={id}>
        <SelectValue placeholder="Choisir un statut" />
      </SelectTrigger>
      <SelectContent>
        {EMPLOYEE_STATUSES.map((status) => (
          <SelectItem key={status} value={status}>
            {status}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function ForfaitJourToggle({
  checked,
  onCheckedChange,
  id,
}: {
  checked?: boolean;
  onCheckedChange: (checked: boolean) => void;
  id?: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-md border px-3 py-2">
      <Checkbox
        id={id}
        checked={Boolean(checked)}
        onCheckedChange={(value) => onCheckedChange(value === true)}
      />
      <div className="space-y-0.5 leading-none">
        <Label htmlFor={id} className="font-normal">
          Forfait jours
        </Label>
        <p className="text-xs text-muted-foreground">
          Calendrier en jours travaillés, sans modifier le statut.
        </p>
      </div>
    </div>
  );
}

function AlternanceFields({
  values,
  onChange,
  idPrefix = 'contract',
}: {
  values: EmployeeContractConfigValues;
  onChange: (patch: Partial<EmployeeContractConfigValues>) => void;
  idPrefix?: string;
}) {
  if (!isAlternanceContract(values.contract_type)) return null;

  const estApprenti = isApprentissageContract(values.contract_type);

  return (
    <div className="space-y-4 rounded-md border border-dashed p-4">
      <p className="text-sm font-medium text-muted-foreground">
        Alternance — ces dates déterminent le régime d&apos;exonération paie.
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor={`${idPrefix}-date-debut`}>1er jour d&apos;exécution</Label>
          <Input
            id={`${idPrefix}-date-debut`}
            type="date"
            value={values.date_debut_execution ?? ''}
            onChange={(e) => onChange({ date_debut_execution: e.target.value })}
          />
        </div>
        <div>
          <Label htmlFor={`${idPrefix}-date-conclusion`}>Date de conclusion (signature)</Label>
          <Input
            id={`${idPrefix}-date-conclusion`}
            type="date"
            value={values.date_conclusion_contrat ?? ''}
            onChange={(e) => onChange({ date_conclusion_contrat: e.target.value })}
          />
        </div>
      </div>
      {estApprenti ? (
        <div className="flex items-start gap-3 rounded-md border p-4">
          <Checkbox
            id={`${idPrefix}-maintien-regime`}
            checked={Boolean(values.maintien_regime_apprenti)}
            onCheckedChange={(checked) =>
              onChange({ maintien_regime_apprenti: checked === true })
            }
          />
          <div className="space-y-1 leading-none">
            <Label htmlFor={`${idPrefix}-maintien-regime`} className="font-normal">
              Maintien de l&apos;ancien régime (exonération 79&nbsp;% SMIC)
            </Label>
            <p className="text-xs text-muted-foreground">
              Contrat conclu avant le 01/03/2025 mais débutant après cette date.
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ContractEndDateField({
  contractType,
  value,
  onChange,
  id,
}: {
  contractType: string;
  value?: string;
  onChange: (value: string) => void;
  id?: string;
}) {
  if (!needsContractEndDate(contractType)) return null;

  return (
    <div>
      <Label htmlFor={id}>Date de fin de contrat (CDD / stage)</Label>
      <Input
        id={id}
        type="date"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
      />
      <p className="mt-1 text-xs text-muted-foreground">
        Déclenche la prime de précarité CDD et le prorata de sortie au dernier mois.
      </p>
    </div>
  );
}

/** Champs contrat en mode contrôlé (modales recrutement, etc.). */
export function EmployeeContractConfigFields({
  values,
  onChange,
  showStatut = true,
  idPrefix = 'contract',
}: ControlledProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <Label htmlFor={`${idPrefix}-type`}>Type de contrat</Label>
          <ContractTypeSelect
            id={`${idPrefix}-type`}
            value={values.contract_type}
            onValueChange={(contract_type) => onChange({ contract_type })}
          />
        </div>
        {showStatut ? (
          <div>
            <Label htmlFor={`${idPrefix}-statut`}>Statut</Label>
            <StatutSelect
              id={`${idPrefix}-statut`}
              value={values.statut}
              onValueChange={(statut) => onChange({ statut })}
            />
          </div>
        ) : null}
      </div>

      <ContractEndDateField
        id={`${idPrefix}-end-date`}
        contractType={values.contract_type}
        value={values.contract_end_date}
        onChange={(contract_end_date) => onChange({ contract_end_date })}
      />

      <ForfaitJourToggle
        id={`${idPrefix}-forfait-jour`}
        checked={values.is_forfait_jour}
        onCheckedChange={(is_forfait_jour) => onChange({ is_forfait_jour })}
      />

      <AlternanceFields values={values} onChange={onChange} idPrefix={idPrefix} />
    </div>
  );
}

/** Champs contrat branchés sur react-hook-form (création / édition fiche). */
export function EmployeeContractConfigFormFields<T extends FieldValues>({
  control,
  contractTypeName = 'contract_type' as FieldPath<T>,
  statutName = 'statut' as FieldPath<T>,
  isForfaitJourName = 'is_forfait_jour' as FieldPath<T>,
  contractEndDateName = 'contract_end_date' as FieldPath<T>,
  dateDebutExecutionName = 'date_debut_execution' as FieldPath<T>,
  dateConclusionContratName = 'date_conclusion_contrat' as FieldPath<T>,
  maintienRegimeName = 'specificites_paie.maintien_regime_apprenti' as FieldPath<T>,
  showStatut = true,
}: FormProps<T>) {
  const contractType = useWatch({ control, name: contractTypeName }) as string;
  const showContractEnd = needsContractEndDate(contractType);
  const showAlternance = isAlternanceContract(contractType);
  const showApprentiOption = isApprentissageContract(contractType);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <FormField
          control={control}
          name={contractTypeName}
          render={({ field }) => (
            <FormItem>
              <FormLabel>Type de contrat</FormLabel>
              <ContractTypeSelect value={field.value} onValueChange={field.onChange} />
              <FormMessage />
            </FormItem>
          )}
        />
        {showStatut ? (
          <FormField
            control={control}
            name={statutName}
            render={({ field }) => (
              <FormItem>
                <FormLabel>Statut</FormLabel>
                <StatutSelect value={field.value} onValueChange={field.onChange} />
                <FormMessage />
              </FormItem>
            )}
          />
        ) : null}
      </div>

      {showContractEnd ? (
        <FormField
          control={control}
          name={contractEndDateName}
          render={({ field }) => (
            <FormItem>
              <FormLabel>Date de fin de contrat (CDD / stage)</FormLabel>
              <FormControl>
                <Input type="date" {...field} value={field.value ?? ''} />
              </FormControl>
              <p className="text-xs text-muted-foreground">
                Déclenche la prime de précarité CDD et le prorata de sortie au dernier mois.
              </p>
              <FormMessage />
            </FormItem>
          )}
        />
      ) : null}

      <FormField
        control={control}
        name={isForfaitJourName}
        render={({ field }) => (
          <FormItem>
            <FormControl>
              <ForfaitJourToggle
                checked={Boolean(field.value)}
                onCheckedChange={field.onChange}
              />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />

      {showAlternance ? (
        <div className="space-y-4 rounded-md border border-dashed p-4">
          <p className="text-sm font-medium text-muted-foreground">
            Alternance — ces dates déterminent le régime d&apos;exonération paie.
          </p>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <FormField
              control={control}
              name={dateDebutExecutionName}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>1er jour d&apos;exécution</FormLabel>
                  <FormControl>
                    <Input type="date" {...field} value={field.value ?? ''} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={control}
              name={dateConclusionContratName}
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Date de conclusion (signature)</FormLabel>
                  <FormControl>
                    <Input type="date" {...field} value={field.value ?? ''} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
          {showApprentiOption ? (
            <FormField
              control={control}
              name={maintienRegimeName}
              render={({ field }) => (
                <FormItem className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
                  <FormControl>
                    <Checkbox checked={field.value} onCheckedChange={field.onChange} />
                  </FormControl>
                  <div className="space-y-1 leading-none">
                    <FormLabel>Maintien de l&apos;ancien régime (exonération 79&nbsp;% SMIC)</FormLabel>
                    <p className="text-xs text-muted-foreground">
                      Contrat conclu avant le 01/03/2025 mais débutant après cette date.
                    </p>
                  </div>
                </FormItem>
              )}
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
