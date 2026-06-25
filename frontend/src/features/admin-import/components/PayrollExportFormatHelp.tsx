import { ChevronDown, CircleHelp } from 'lucide-react';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';

const EXPECTED_COLUMNS = [
  { label: 'Identité', cols: 'Matricule, Nom, Prénom, Nom marital, NIR' },
  { label: 'Contacts', cols: 'E-mail, Tél., adresse (N°, voie, CP, ville…)' },
  { label: 'État civil', cols: 'Sexe, Nationalité, Date / lieu de naissance' },
  { label: 'Contrat', cols: 'Date entrée, Date sortie, CDD, Statut cadre, Jours anc.' },
  { label: 'Paie', cols: 'Salaire base, % activité, Heures/mois, Paiement, RIB/IBAN' },
  { label: 'Organisation', cols: 'Service (équipe MOD/MOI), Handicapé (Oui → code 01 RQTH)' },
  { label: 'Titre séjour', cols: 'N° carte, dates obtention / expiration' },
];

export function PayrollExportFormatHelp({ className }: { className?: string }) {
  return (
    <Collapsible className={cn('rounded-lg border bg-muted/20', className)}>
      <CollapsibleTrigger className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm text-muted-foreground hover:text-foreground transition-colors [&[data-state=open]>svg.chevron]:rotate-180">
        <CircleHelp className="h-4 w-4 shrink-0" />
        <span>Format attendu du fichier Excel</span>
        <ChevronDown className="chevron ml-auto h-4 w-4 shrink-0 transition-transform" />
      </CollapsibleTrigger>
      <CollapsibleContent className="border-t px-3 pb-3 pt-2 text-sm text-muted-foreground space-y-2">
        <p>
          Export salariés depuis <strong className="font-medium text-foreground">Quadra Paie</strong>{' '}
          ou <strong className="font-medium text-foreground">Cegid</strong> (.xlsx, .xls ou .csv).
          Les salariés doivent déjà exister dans EYWAI (import DSN préalable).
        </p>
        <ul className="space-y-1.5">
          {EXPECTED_COLUMNS.map((row) => (
            <li key={row.label} className="flex flex-wrap gap-x-2">
              <span className="font-medium text-foreground min-w-[4.5rem]">{row.label}</span>
              <span>{row.cols}</span>
            </li>
          ))}
        </ul>
        <p className="text-xs">
          Les en-têtes sont reconnus automatiquement. Le tableau de prévisualisation affiche
          toutes les colonnes détectées avec les valeurs qui seront enregistrées. Un numéro de
          téléphone placé dans la colonne e-mail (sans adresse) est détecté et rangé au bon endroit.
        </p>
      </CollapsibleContent>
    </Collapsible>
  );
}
