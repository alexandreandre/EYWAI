import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Building2, Check, ChevronsUpDown } from 'lucide-react';
import { listDsnImportCompanies, type DsnImportCompany } from '@/api/dsnImport';
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
import {
  companyCommandValue,
  groupDsnImportCompanies,
} from '@/features/admin-import/lib/companyComboboxUtils';

type Props = {
  value: string;
  onChange: (companyId: string) => void;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
};

export function CompanyCombobox({
  value,
  onChange,
  disabled,
  placeholder = 'Sélectionner une entreprise…',
  className,
}: Props) {
  const [open, setOpen] = useState(false);
  const { data: companies = [], isLoading } = useQuery({
    queryKey: ['dsn-import-companies'],
    queryFn: listDsnImportCompanies,
    staleTime: 60_000,
  });

  const selected = useMemo(
    () => companies.find((c) => c.id === value) ?? null,
    [companies, value],
  );
  const grouped = useMemo(() => groupDsnImportCompanies(companies), [companies]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          disabled={disabled || isLoading}
          className={cn('w-full max-w-md justify-between', className)}
        >
          <span className="flex items-center gap-2 truncate">
            <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
            {selected
              ? `${selected.company_name}${selected.siret ? ` — ${selected.siret.slice(-5)}` : ''}`
              : placeholder}
          </span>
          <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
        <Command>
          <CommandInput placeholder="Rechercher entreprise, SIRET…" />
          <CommandList>
            <CommandEmpty>Aucune entreprise.</CommandEmpty>
            {grouped.map((group) => (
              <CommandGroup key={group.groupName} heading={group.groupName}>
                {group.companies.map((c: DsnImportCompany) => (
                  <CommandItem
                    key={c.id}
                    value={companyCommandValue(c)}
                    onSelect={() => {
                      onChange(c.id);
                      setOpen(false);
                    }}
                  >
                    <Check className={cn('mr-2 h-4 w-4', value === c.id ? 'opacity-100' : 'opacity-0')} />
                    <span className="truncate">{c.company_name}</span>
                    {c.siret ? (
                      <span className="ml-2 text-xs text-muted-foreground">{c.siret}</span>
                    ) : null}
                  </CommandItem>
                ))}
              </CommandGroup>
            ))}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
