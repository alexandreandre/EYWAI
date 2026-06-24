import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, FileStack } from 'lucide-react';
import { listDsnImportCompanies } from '@/api/dsnImport';
import { CompanyCombobox } from '@/features/admin-import/components/CompanyCombobox';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type Props = {
  companyId: string;
  onCompanyChange: (companyId: string) => void;
  onCreateNewViaDsn: () => void;
};

export function CompanySetupIntroStep({
  companyId,
  onCompanyChange,
  onCreateNewViaDsn,
}: Props) {
  const { data: companies = [] } = useQuery({
    queryKey: ['dsn-import-companies'],
    queryFn: listDsnImportCompanies,
    staleTime: 60_000,
  });

  const selected = useMemo(
    () => companies.find((c) => c.id === companyId) ?? null,
    [companies, companyId],
  );

  return (
    <div className="space-y-5">
      <section
        className={cn(
          'rounded-lg border p-4 space-y-3',
          companyId ? 'border-primary/30 bg-primary/5' : 'border-border bg-card',
        )}
      >
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-foreground">Filiale existante</h3>
          <p className="text-sm text-muted-foreground">
            Choisissez une entreprise déjà présente dans EYWAI pour compléter ses imports et
            paramètres.
          </p>
        </div>
        <CompanyCombobox
          value={companyId}
          onChange={onCompanyChange}
          placeholder="Rechercher une filiale du groupe…"
          className="max-w-full"
        />
        {selected ? (
          <p className="flex items-center gap-1.5 text-xs text-emerald-700">
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
            <span>
              <strong>{selected.company_name}</strong>
              {selected.siret ? ` · SIRET ${selected.siret}` : ''}
            </span>
          </p>
        ) : null}
      </section>

      <p className="text-center text-xs text-muted-foreground">
        Première importation dans EYWAI ?
        <button
          type="button"
          className="ml-1 text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
          onClick={onCreateNewViaDsn}
        >
          Créer une filiale via DSN
        </button>
      </p>

      <section className="rounded-lg border bg-muted/20 px-4 py-3">
        <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-foreground">
          <FileStack className="h-4 w-4 shrink-0 text-muted-foreground" />
          Documents utiles pour le parcours
        </h3>
        <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
          <li>DSN mensuelle (.txt, .dsn, .edi)</li>
          <li>Fichier paie — enrichissement salarié (Excel, CSV)</li>
          <li>Bulletins PDF pour compteur CP (PDF)</li>
          <li>Calendrier annuel (Excel, CSV)</li>
        </ul>
      </section>
    </div>
  );
}

export function CompanySetupIntroFooter({
  companyId,
  onContinue,
  onClose,
}: {
  companyId: string;
  onContinue: () => void;
  onClose: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-t bg-background px-4 py-2">
      <Button type="button" size="sm" className="h-8 shrink-0" disabled={!companyId} onClick={onContinue}>
        Continuer
      </Button>
      <Button type="button" variant="ghost" size="sm" className="h-8 shrink-0 px-2" onClick={onClose}>
        Fermer
      </Button>
      {!companyId ? (
        <span className="ml-auto hidden truncate text-xs text-muted-foreground sm:inline">
          Sélectionnez une entreprise pour poursuivre.
        </span>
      ) : null}
    </div>
  );
}
