import { useState } from 'react';
import { Check, ChevronsUpDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { cn } from '@/lib/utils';
import type { RosterEmployee } from '@/api/calendar';

interface EmployeeAssociateComboboxProps {
  roster: RosterEmployee[];
  value: string | null;
  onSelect: (employeeId: string, label: string) => void;
  placeholder?: string;
  className?: string;
  compact?: boolean;
  excludeEmployeeIds?: string[];
  includeSelectedWhenExcluded?: boolean;
  preferredEmployeeIds?: string[];
  /** Message si la liste filtrée est vide (ex. tous les salariés déjà rapprochés). */
  emptyMessage?: string;
  othersGroupHeading?: string;
}

export function EmployeeAssociateCombobox({
  roster,
  value,
  onSelect,
  placeholder = 'Associer…',
  className,
  compact = false,
  excludeEmployeeIds = [],
  includeSelectedWhenExcluded = true,
  preferredEmployeeIds = [],
  emptyMessage = 'Aucun salarié disponible.',
  othersGroupHeading,
}: EmployeeAssociateComboboxProps) {
  const [open, setOpen] = useState(false);

  const excluded = new Set(
    excludeEmployeeIds.filter((id) => id && (!includeSelectedWhenExcluded || id !== value)),
  );
  const available = roster.filter((emp) => !excluded.has(emp.id));
  const preferred = new Set(preferredEmployeeIds.filter(Boolean));
  const suggested = available.filter((emp) => preferred.has(emp.id));
  const others = available.filter((emp) => !preferred.has(emp.id));

  const selected = roster.find((e) => e.id === value);
  const displayLabel = selected
    ? `${selected.last_name} ${selected.first_name}`
    : placeholder;

  const renderEmployee = (emp: RosterEmployee) => {
    const label = `${emp.last_name} ${emp.first_name}`;
    const searchValue = [emp.last_name, emp.first_name, emp.time_tracking_id ?? '']
      .join(' ')
      .toLowerCase();
    return (
      <CommandItem
        key={emp.id}
        value={`${searchValue} ${emp.id}`}
        keywords={[emp.last_name, emp.first_name, emp.time_tracking_id ?? ''].filter(Boolean)}
        onSelect={() => {
          onSelect(emp.id, label);
          setOpen(false);
        }}
      >
        <Check
          className={cn('mr-2 h-4 w-4', value === emp.id ? 'opacity-100' : 'opacity-0')}
        />
        <span className="flex min-w-0 flex-col">
          <span className="truncate">{label}</span>
          {emp.time_tracking_id ? (
            <span className="text-[10px] text-muted-foreground">Mat. {emp.time_tracking_id}</span>
          ) : null}
        </span>
      </CommandItem>
    );
  };

  return (
    <Popover open={open} onOpenChange={setOpen} modal={false}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn(
            'justify-between font-normal',
            compact ? 'h-7 w-[180px] px-2 text-xs' : 'h-8 w-[200px] px-2 text-xs',
            className,
          )}
        >
          <span className="truncate">{displayLabel}</span>
          <ChevronsUpDown className="ml-1 h-3.5 w-3.5 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[280px] p-0" align="end">
        <Command>
          <CommandInput placeholder="Taper nom, prénom ou matricule…" className="h-9" />
          <CommandList>
            <CommandEmpty>{emptyMessage}</CommandEmpty>
            {suggested.length > 0 ? (
              <CommandGroup heading="Suggestions">
                {suggested.map((emp) => renderEmployee(emp))}
              </CommandGroup>
            ) : null}
            {others.length > 0 ? (
              <CommandGroup
                heading={
                  othersGroupHeading ??
                  (suggested.length > 0 ? 'Autres salariés' : undefined)
                }
              >
                {others.map((emp) => renderEmployee(emp))}
              </CommandGroup>
            ) : null}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
