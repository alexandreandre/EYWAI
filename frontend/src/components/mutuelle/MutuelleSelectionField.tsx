import { useMemo, useState } from 'react';
import { Loader2 } from 'lucide-react';

import type { MutuelleType } from '@/api/mutuelleTypes';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  filterMutuellesForEmployee,
  formatMutuelleAmountsLine,
  formatMutuelleOptionTitle,
  listMutuellePackFilters,
  sortMutuellesForSelection,
} from '@/lib/mutuelleUtils';
import { cn } from '@/lib/utils';

export interface MutuelleSelectionFieldProps {
  mutuelles: MutuelleType[];
  value: string | null | undefined;
  onChange: (mutuelleTypeId: string) => void;
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

  if (eligible.length === 0) {
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
    </div>
  );
}
