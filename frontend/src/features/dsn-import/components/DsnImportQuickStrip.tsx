import { useCallback, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Building2, Check, ChevronsUpDown, FileText, Loader2, Upload } from 'lucide-react';
import {
  fetchDsnCoverage,
  listDsnImportCompanies,
  type DsnImportCompany,
} from '@/api/dsnImport';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
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

const MONTHS_FR = [
  'janvier',
  'février',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'août',
  'septembre',
  'octobre',
  'novembre',
  'décembre',
];

function formatPeriodLabel(period?: string | null): string {
  if (!period) return '—';
  const [y, m] = period.split('-');
  const mi = parseInt(m, 10);
  if (!y || !mi || mi < 1 || mi > 12) return period;
  return `${MONTHS_FR[mi - 1]} ${y}`;
}

function groupCompanies(companies: DsnImportCompany[]) {
  const buckets = new Map<string, { groupName: string; companies: DsnImportCompany[] }>();
  companies.forEach((c) => {
    const key = c.group_id ?? '__none__';
    if (!buckets.has(key)) {
      buckets.set(key, { groupName: c.group_name ?? 'Sans groupe', companies: [] });
    }
    buckets.get(key)!.companies.push(c);
  });
  return Array.from(buckets.values()).sort((a, b) => a.groupName.localeCompare(b.groupName));
}

function companyCommandValue(c: DsnImportCompany): string {
  return [c.company_name, c.siret ?? '', c.siren ?? '', c.group_name ?? ''].join(' ').trim();
}

type Props = {
  selectedCompanyId: string;
  onCompanyChange: (companyId: string) => void;
  onAnalyze: (files: File[]) => void;
  isAnalyzing?: boolean;
};

export function DsnImportQuickStrip({
  selectedCompanyId,
  onCompanyChange,
  onAnalyze,
  isAnalyzing = false,
}: Props) {
  const [comboboxOpen, setComboboxOpen] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const { data: companies, isLoading: loadingCompanies } = useQuery({
    queryKey: ['dsn-import-companies'],
    queryFn: listDsnImportCompanies,
    staleTime: 60_000,
  });

  const { data: coverage } = useQuery({
    queryKey: ['dsn-coverage', selectedCompanyId],
    queryFn: () => fetchDsnCoverage(selectedCompanyId),
    enabled: Boolean(selectedCompanyId),
    staleTime: 30_000,
  });

  const grouped = useMemo(() => groupCompanies(companies ?? []), [companies]);

  const selected = useMemo(
    () => (companies ?? []).find((c) => c.id === selectedCompanyId) ?? null,
    [companies, selectedCompanyId],
  );

  const onFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const list = e.target.files ? Array.from(e.target.files) : [];
    setSelectedFiles(list.slice(0, 1));
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setSelectedFiles(Array.from(e.dataTransfer.files).slice(0, 1));
  }, []);

  const handleAnalyze = () => {
    if (selectedFiles.length === 0 || !selectedCompanyId) return;
    onAnalyze(selectedFiles);
    setSelectedFiles([]);
  };

  const periodLabel = formatPeriodLabel(coverage?.expected_last_period);

  return (
    <Card className="border-primary/20 bg-muted/20">
      <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
        <div className="flex min-w-0 flex-1 flex-col gap-2 sm:flex-row sm:items-center">
          {loadingCompanies ? (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          ) : (
            <Popover open={comboboxOpen} onOpenChange={setComboboxOpen}>
              <PopoverTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  role="combobox"
                  aria-expanded={comboboxOpen}
                  className="w-full justify-between sm:max-w-xs"
                >
                  <span className="flex min-w-0 items-center gap-2 truncate">
                    <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
                    {selected ? selected.company_name : 'Choisir l\u2019entreprise…'}
                  </span>
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[320px] p-0" align="start">
                <Command>
                  <CommandInput placeholder="Rechercher une entreprise…" />
                  <CommandList>
                    <CommandEmpty>Aucune entreprise.</CommandEmpty>
                    {grouped.map(({ groupName, companies: items }) => (
                      <CommandGroup key={groupName} heading={groupName}>
                        {items.map((c) => (
                          <CommandItem
                            key={c.id}
                            value={companyCommandValue(c)}
                            onSelect={() => {
                              onCompanyChange(c.id);
                              setComboboxOpen(false);
                            }}
                          >
                            <Check
                              className={cn(
                                'mr-2 h-4 w-4',
                                selectedCompanyId === c.id ? 'opacity-100' : 'opacity-0',
                              )}
                            />
                            <span className="truncate">
                              {c.company_name}
                              {c.siret ? ` (…${c.siret.slice(-5)})` : ''}
                            </span>
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    ))}
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
          )}

          <p className="text-sm text-muted-foreground">
            {selectedCompanyId ? (
              <>
                Import mensuel —{' '}
                <span className="font-medium text-foreground">{selected.company_name}</span>
                {coverage?.expected_last_period ? (
                  <>
                    {' '}
                    <span className="text-muted-foreground">
                      (prochain mois attendu : {periodLabel})
                    </span>
                  </>
                ) : null}
              </>
            ) : (
              'Sélectionnez une entreprise, déposez la DSN — le mois sera détecté automatiquement.'
            )}
          </p>
        </div>

        <div className="flex min-w-0 flex-1 items-center gap-2">
          <div
            className={cn(
              'flex min-h-[44px] flex-1 cursor-pointer items-center gap-2 rounded-md border border-dashed px-3 py-2 text-sm transition',
              selectedFiles.length > 0
                ? 'border-primary/40 bg-background'
                : 'border-muted-foreground/30 hover:border-primary/40',
            )}
            onDragOver={(e) => e.preventDefault()}
            onDrop={onDrop}
            onClick={() => document.getElementById('dsn-quick-strip-input')?.click()}
          >
            <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
            <span className="truncate text-muted-foreground">
              {selectedFiles[0]?.name ?? 'Déposer 1 fichier DSN (.txt, .dsn)'}
            </span>
            <input
              id="dsn-quick-strip-input"
              type="file"
              accept=".txt,.dsn,.edi"
              className="hidden"
              onChange={onFileChange}
            />
          </div>
          <Button
            type="button"
            size="sm"
            disabled={!selectedCompanyId || selectedFiles.length === 0 || isAnalyzing}
            onClick={handleAnalyze}
          >
            {isAnalyzing ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <Upload className="mr-1.5 h-4 w-4" />
            )}
            Analyser
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
