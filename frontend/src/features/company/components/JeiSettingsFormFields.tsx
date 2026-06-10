import { FlaskConical } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';

export type JeiFormValues = {
  jei_enabled: boolean;
  date_creation_etablissement: string;
  taux_exoneration: number;
};

type JeiSettingsFormFieldsProps = {
  values: JeiFormValues;
  onChange: (patch: Partial<JeiFormValues>) => void;
  disabled?: boolean;
  compact?: boolean;
};

export function JeiSettingsFormFields({
  values,
  onChange,
  disabled = false,
  compact = false,
}: JeiSettingsFormFieldsProps) {
  return (
    <div className={compact ? 'space-y-4' : 'space-y-6 rounded-lg border p-4'}>
      {!compact ? (
        <div className="space-y-1">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <FlaskConical className="h-4 w-4" />
            Statut JEI — Jeune Entreprise Innovante
          </h3>
          <p className="text-xs text-muted-foreground">
            Exonération des cotisations patronales pour le personnel R&amp;D éligible (7 ans à
            compter de la création de l&apos;établissement).
          </p>
        </div>
      ) : null}

      <div className="flex items-center justify-between gap-4 rounded-md border p-3">
        <Label htmlFor="jei-enabled-form" className="cursor-pointer">
          Entreprise bénéficiant du statut JEI
        </Label>
        <Switch
          id="jei-enabled-form"
          checked={values.jei_enabled}
          disabled={disabled}
          onCheckedChange={(checked) => onChange({ jei_enabled: checked })}
        />
      </div>

      {values.jei_enabled ? (
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="jei-date-form">Date de création de l&apos;établissement *</Label>
            <Input
              id="jei-date-form"
              type="date"
              disabled={disabled}
              required={values.jei_enabled}
              value={values.date_creation_etablissement}
              onChange={(e) =>
                onChange({ date_creation_etablissement: e.target.value })
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="jei-taux-form">Taux d&apos;exonération</Label>
            <Input
              id="jei-taux-form"
              type="number"
              min={0}
              max={1}
              step={0.01}
              disabled={disabled}
              value={values.taux_exoneration}
              onChange={(e) =>
                onChange({ taux_exoneration: parseFloat(e.target.value) || 0 })
              }
            />
            <p className="text-xs text-muted-foreground">1,0 = 100 %</p>
          </div>
        </div>
      ) : null}
    </div>
  );
}

export const defaultJeiFormValues: JeiFormValues = {
  jei_enabled: false,
  date_creation_etablissement: '',
  taux_exoneration: 1,
};
