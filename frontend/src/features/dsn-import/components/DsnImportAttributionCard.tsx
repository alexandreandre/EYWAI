import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Building2, Check, ChevronsUpDown, Sparkles, Loader2 } from 'lucide-react';
import { listDsnImportCompanies, type DsnImportCompany } from '@/api/dsnImport';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
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

type Mode = 'auto' | 'existing';

function groupCompanies(companies: DsnImportCompany[]): Array<{
  groupName: string;
  groupId: string | null;
  companies: DsnImportCompany[];
}> {
  const buckets = new Map<string, { groupName: string; groupId: string | null; companies: DsnImportCompany[] }>();
  companies.forEach((c) => {
    const key = c.group_id ?? '__none__';
    if (!buckets.has(key)) {
      buckets.set(key, {
        groupName: c.group_name ?? 'Sans groupe',
        groupId: c.group_id ?? null,
        companies: [],
      });
    }
    buckets.get(key)!.companies.push(c);
  });
  return Array.from(buckets.values()).sort((a, b) => a.groupName.localeCompare(b.groupName));
}

function companyCommandValue(c: DsnImportCompany): string {
  return [c.company_name, c.siret ?? '', c.siren ?? '', c.group_name ?? ''].join(' ').trim();
}

export function DsnImportAttributionCard({
  targetCompanyId,
  onChange,
  detectedExisting,
  detectedSiret,
  isRevalidating,
  locked = false,
}: {
  targetCompanyId: string | null;
  onChange: (companyId: string | null) => void;
  detectedExisting: boolean;
  detectedSiret?: string | null;
  isRevalidating: boolean;
  locked?: boolean;
}) {
  const [mode, setMode] = useState<Mode>(locked || targetCompanyId ? 'existing' : 'auto');
  const [comboboxOpen, setComboboxOpen] = useState(false);

  const { data: companies, isLoading } = useQuery({
    queryKey: ['dsn-import-companies'],
    queryFn: listDsnImportCompanies,
    staleTime: 60_000,
  });

  const grouped = useMemo(() => groupCompanies(companies ?? []), [companies]);

  const selected = useMemo(
    () => (companies ?? []).find((c) => c.id === targetCompanyId) ?? null,
    [companies, targetCompanyId],
  );

  const selectMode = (next: Mode) => {
    if (locked) return;
    setMode(next);
    if (next === 'auto') onChange(null);
  };

  if (locked && selected) {
    return (
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <Building2 className="h-4 w-4 text-muted-foreground" />
            Entreprise
          </CardTitle>
          <CardDescription>
            Import mensuel — dossier verrouillé sur l&apos;entreprise sélectionnée.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Badge variant="secondary" className="font-normal">
            {selected.company_name}
            {selected.siret ? ` (…${selected.siret.slice(-5)})` : ''}
          </Badge>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Building2 className="h-4 w-4 text-muted-foreground" />
          Rattachement du dossier
          {isRevalidating && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
        </CardTitle>
        <CardDescription>
          Choisissez où importer cette DSN : laissez EYWAI décider via le SIRET, ou rattachez
          l&apos;import à une entreprise déjà créée.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => selectMode('auto')}
            className={cn(
              'flex flex-col gap-1 rounded-lg border p-3 text-left transition',
              mode === 'auto'
                ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                : 'hover:border-muted-foreground/40',
            )}
          >
            <span className="flex items-center gap-1.5 text-sm font-medium">
              <Sparkles className="h-3.5 w-3.5" />
              Automatique
            </span>
            <span className="text-xs text-muted-foreground">
              {detectedExisting
                ? `Dossier existant détecté${detectedSiret ? ` (SIRET …${String(detectedSiret).slice(-5)})` : ''} — mise à jour.`
                : 'Création d\u2019un nouveau dossier selon le SIRET de la DSN.'}
            </span>
          </button>
          <button
            type="button"
            onClick={() => selectMode('existing')}
            className={cn(
              'flex flex-col gap-1 rounded-lg border p-3 text-left transition',
              mode === 'existing'
                ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                : 'hover:border-muted-foreground/40',
            )}
          >
            <span className="flex items-center gap-1.5 text-sm font-medium">
              <Building2 className="h-3.5 w-3.5" />
              Entreprise existante
            </span>
            <span className="text-xs text-muted-foreground">
              Attacher les salariés et cumuls à une entreprise déjà présente dans EYWAI.
            </span>
          </button>
        </div>

        {mode === 'existing' && (
          <div className="space-y-2 rounded-lg border bg-muted/20 p-3">
            {isLoading ? (
              <p className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Chargement des entreprises…
              </p>
            ) : (companies ?? []).length === 0 ? (
              <p className="py-2 text-sm text-muted-foreground">
                Aucune entreprise existante. Utilisez le mode automatique.
              </p>
            ) : (
              <Popover open={comboboxOpen} onOpenChange={setComboboxOpen} modal={false}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={comboboxOpen}
                    className="h-10 w-full justify-between gap-2 font-normal"
                  >
                    <span className="min-w-0 truncate text-left">
                      {selected ? (
                        <>
                          {selected.company_name}
                          {selected.siret ? (
                            <span className="ml-1.5 font-mono text-xs text-muted-foreground">
                              …{selected.siret.slice(-5)}
                            </span>
                          ) : null}
                        </>
                      ) : (
                        <span className="text-muted-foreground">
                          Rechercher une entreprise, un SIRET, un groupe…
                        </span>
                      )}
                    </span>
                    <ChevronsUpDown className="h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent
                  className="w-[var(--radix-popover-trigger-width)] p-0"
                  align="start"
                >
                  <Command>
                    <CommandInput placeholder="Rechercher une entreprise, un SIRET, un groupe…" />
                    <CommandList className="max-h-[320px]">
                      <CommandEmpty>Aucune entreprise trouvée.</CommandEmpty>
                      {grouped.map((g) => (
                        <CommandGroup key={g.groupId ?? '__none__'} heading={g.groupName}>
                          {g.companies.map((c) => (
                            <CommandItem
                              key={c.id}
                              value={companyCommandValue(c)}
                              onSelect={() => {
                                onChange(c.id);
                                setComboboxOpen(false);
                              }}
                            >
                              <Check
                                className={cn(
                                  'mr-2 h-4 w-4 shrink-0',
                                  targetCompanyId === c.id ? 'opacity-100' : 'opacity-0',
                                )}
                              />
                              <div className="min-w-0 flex-1">
                                <p className="truncate font-medium">{c.company_name}</p>
                                {(c.siret || c.group_name) && (
                                  <p className="truncate text-xs text-muted-foreground">
                                    {c.siret ? `SIRET …${c.siret.slice(-5)}` : ''}
                                    {c.siret && c.group_name ? ' · ' : ''}
                                    {c.group_name ?? ''}
                                  </p>
                                )}
                              </div>
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      ))}
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
            )}
            {selected && (
              <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                Les salariés seront rattachés à
                <Badge variant="secondary" className="font-normal">
                  {selected.company_name}
                </Badge>
                {selected.group_name && <span>du groupe {selected.group_name}.</span>}
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
