import { useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';

import type { MutuelleType } from '@/api/mutuelleTypes';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  AUCUNE_FORMULE,
  basculerFormule,
  filterMutuellesForEmployee,
  formatMutuelleAmountsLine,
  formatMutuelleOptionTitle,
  listMutuellePackFilters,
  sortMutuellesForSelection,
} from '@/lib/mutuelleUtils';
import { cn } from '@/lib/utils';

export interface MutuelleSelectionFieldProps {
  mutuelles: MutuelleType[];
  value?: string | null | undefined;
  onChange?: (mutuelleTypeId: string) => void;
  /**
   * Plusieurs formules à la fois (base + options), en cases à cocher, avec
   * « Aucune formule ». Utilisé par la fiche et la création ([B17]).
   */
  values?: string[];
  onChangeValues?: (mutuelleTypeIds: string[]) => void;
  employeeStatut?: string | null;
  companyOrganismeLabel?: string | null;
  loading?: boolean;
  emptyMessage?: string;
  className?: string;
}

export function MutuelleSelectionField({
  mutuelles,
  value,
  onChange,
  values,
  onChangeValues,
  employeeStatut,
  companyOrganismeLabel,
  loading = false,
  emptyMessage = 'Aucune formule mutuelle disponible.',
  className,
}: MutuelleSelectionFieldProps) {
  const [packFilter, setPackFilter] = useState<string>('all');

  const eligible = useMemo(() => {
    const filtered = filterMutuellesForEmployee(mutuelles, employeeStatut);
    const byPack =
      packFilter === 'all'
        ? filtered
        : filtered.filter((m) => m.pack_couverture === packFilter);
    return sortMutuellesForSelection(byPack);
  }, [mutuelles, employeeStatut, packFilter]);

  const packFilters = useMemo(
    () => listMutuellePackFilters(filterMutuellesForEmployee(mutuelles, employeeStatut)),
    [mutuelles, employeeStatut],
  );

  if (loading) {
    return <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-label="Chargement" />;
  }

  const plusieurs = values !== undefined && onChangeValues !== undefined;
  const choisis = values ?? [];
  // Une formule déjà sur la fiche reste affichée et cochée, même hors du filtre
  // de statut ou de pack : la décocher doit être un geste, pas un effet de bord.
  const visibles = plusieurs
    ? [
        ...eligible,
        ...mutuelles.filter((m) => choisis.includes(m.id) && !eligible.some((e) => e.id === m.id)),
      ]
    : eligible;

  if (visibles.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>;
  }

  return (
    <div className={cn('space-y-3', className)}>
      {companyOrganismeLabel ? (
        <p className="text-sm text-muted-foreground">
          Organisme : <span className="font-medium text-foreground">{companyOrganismeLabel}</span>
        </p>
      ) : null}

      {packFilters.length > 2 ? (
        <ToggleGroup
          type="single"
          value={packFilter}
          onValueChange={(next) => setPackFilter(next || 'all')}
          className="flex flex-wrap justify-start gap-1"
        >
          {packFilters.map((f) => (
            <ToggleGroupItem key={f.id} value={f.id} size="sm" className="text-xs">
              {f.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      ) : null}

      {plusieurs ? (
        <div className="space-y-2">
          {visibles.map((m) => {
            const optionId = `mutuelle-${m.id}`;
            const coche = choisis.includes(m.id);
            return (
              <div
                key={m.id}
                className={cn(
                  'flex items-start gap-3 rounded-md border p-3 transition-colors',
                  coche ? 'border-primary bg-primary/5' : 'hover:bg-muted/40',
                )}
              >
                <Checkbox
                  id={optionId}
                  checked={coche}
                  onCheckedChange={(etat) => onChangeValues(basculerFormule(choisis, m.id, etat === true))}
                  className="mt-0.5"
                />
                <Label htmlFor={optionId} className="flex-1 cursor-pointer space-y-1 font-normal">
                  <span className="block text-sm font-medium leading-snug">
                    {formatMutuelleOptionTitle(m, companyOrganismeLabel)}
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {formatMutuelleAmountsLine(m)}
                  </span>
                  {m.note ? (
                    <span className="block text-xs text-muted-foreground italic">{m.note}</span>
                  ) : null}
                </Label>
              </div>
            );
          })}
          <div className="flex items-start gap-3 rounded-md border border-dashed p-3">
            <Checkbox
              id="mutuelle-aucune"
              checked={choisis.length === 0}
              onCheckedChange={(etat) => onChangeValues(basculerFormule(choisis, AUCUNE_FORMULE, etat === true))}
              className="mt-0.5"
            />
            <Label htmlFor="mutuelle-aucune" className="flex-1 cursor-pointer space-y-1 font-normal">
              <span className="block text-sm font-medium leading-snug">Aucune formule (salarié dispensé)</span>
              <span className="block text-xs text-muted-foreground">
                Aucune cotisation de mutuelle au bulletin.
              </span>
            </Label>
          </div>
          {choisis.length > 1 ? (
            <p className="text-xs text-muted-foreground">
              {choisis.length} formules cochées : chacune donne sa ligne au bulletin (base et options).
            </p>
          ) : null}
        </div>
      ) : (
      <RadioGroup value={value ?? ''} onValueChange={onChange} className="space-y-2">
        {eligible.map((m) => {
          const optionId = `mutuelle-${m.id}`;
          return (
            <div
              key={m.id}
              className={cn(
                'flex items-start gap-3 rounded-md border p-3 transition-colors',
                value === m.id ? 'border-primary bg-primary/5' : 'hover:bg-muted/40',
              )}
            >
              <RadioGroupItem value={m.id} id={optionId} className="mt-0.5" />
              <Label htmlFor={optionId} className="flex-1 cursor-pointer space-y-1 font-normal">
                <span className="block text-sm font-medium leading-snug">
                  {formatMutuelleOptionTitle(m, companyOrganismeLabel)}
                </span>
                <span className="block text-xs text-muted-foreground">
                  {formatMutuelleAmountsLine(m)}
                </span>
                {m.note ? (
                  <span className="block text-xs text-muted-foreground italic">{m.note}</span>
                ) : null}
              </Label>
            </div>
          );
        })}
      </RadioGroup>
      )}
    </div>
  );
}
