import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { RatesComplexObject } from '@/components/rates/RatesComplexData';
import { cn } from '@/lib/utils';

type PrimeCatalogueEntry = {
  id?: string;
  libelle?: string;
  soumise_a_impot?: boolean;
  soumise_a_cotisations?: boolean;
  _commentaire?: string;
  commentaire?: string;
};

function parsePrimesList(configData: Record<string, unknown>): PrimeCatalogueEntry[] {
  const raw = configData.primes;
  if (!Array.isArray(raw)) return [];
  return raw.filter((item): item is PrimeCatalogueEntry => item !== null && typeof item === 'object');
}

function formatCatalogueIntro(configData: Record<string, unknown>): string | undefined {
  const raw = configData._commentaire ?? configData.commentaire;
  if (typeof raw !== 'string' || !raw.trim()) return undefined;
  return raw.trim();
}

function formatPrimeNote(entry: PrimeCatalogueEntry): string | undefined {
  const raw = entry._commentaire ?? entry.commentaire;
  if (typeof raw !== 'string' || !raw.trim()) return undefined;
  return raw
    .replace(/La logique exacte sera dans le moteur\.?\s*/gi, '')
    .replace(/IMPORTANT:\s*/gi, '')
    .replace(
      /Cette logique est gérée automatiquement dans generateur_fiche_paie\.py\.?/gi,
      "Le moteur de paie applique cette règle automatiquement selon l'effectif de l'entreprise.",
    )
    .replace(/\s+/g, ' ')
    .trim();
}

function formatSoumissionLabel(soumise: boolean | undefined, kind: 'cotisations' | 'impot'): string {
  if (soumise === undefined) return '—';
  if (soumise) {
    return kind === 'cotisations' ? 'Soumise aux cotisations' : "Soumise à l'impôt";
  }
  return kind === 'cotisations' ? 'Non soumise aux cotisations' : "Non soumise à l'impôt";
}

function SoumissionCell({
  soumise,
  kind,
}: {
  soumise: boolean | undefined;
  kind: 'cotisations' | 'impot';
}) {
  if (soumise === undefined) return <span className="text-muted-foreground">—</span>;
  return (
    <span
      className={cn(
        'text-sm',
        soumise ? 'text-foreground' : 'text-emerald-700 dark:text-emerald-500',
      )}
    >
      {formatSoumissionLabel(soumise, kind)}
    </span>
  );
}

export function RatesPrimesView({ configData }: { configData: Record<string, unknown> }) {
  const primes = parsePrimesList(configData);
  const intro = formatCatalogueIntro(configData);

  if (primes.length === 0) {
    return <RatesComplexObject obj={configData} />;
  }

  return (
    <div className="space-y-4">
      <p className="text-xs leading-relaxed text-muted-foreground">
        {intro ??
          'Catalogue des primes et indemnités : règles appliquées par le moteur de paie pour les cotisations sociales et l’impôt sur le revenu.'}
      </p>

      <Table>
        <TableHeader>
          <TableRow className="border-border/40 hover:bg-transparent">
            <TableHead className="h-9 text-xs font-medium text-muted-foreground">
              Prime ou indemnité
            </TableHead>
            <TableHead className="h-9 text-xs font-medium text-muted-foreground">
              Cotisations sociales
            </TableHead>
            <TableHead className="h-9 text-xs font-medium text-muted-foreground">
              Impôt sur le revenu
            </TableHead>
            <TableHead className="h-9 text-xs font-medium text-muted-foreground">
              Précisions
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {primes.map((prime) => {
            const note = formatPrimeNote(prime);
            return (
              <TableRow key={prime.id ?? prime.libelle} className="border-border/40 align-top">
                <TableCell className="py-2.5">
                  <div className="text-sm font-medium text-foreground">
                    {prime.libelle ?? '—'}
                  </div>
                </TableCell>
                <TableCell className="py-2.5">
                  <SoumissionCell soumise={prime.soumise_a_cotisations} kind="cotisations" />
                </TableCell>
                <TableCell className="py-2.5">
                  <SoumissionCell soumise={prime.soumise_a_impot} kind="impot" />
                </TableCell>
                <TableCell className="py-2.5 text-sm leading-snug text-muted-foreground">
                  {note ?? '—'}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
