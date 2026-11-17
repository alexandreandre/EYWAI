import { useQuery } from '@tanstack/react-query';
import { AlertTriangle } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { getLignesCorrigeables, type LigneCorrigeable } from '@/api/payslips';
import { queryKeys } from '@/lib/queryKeys';
import { accord, pluriel } from '@/lib/pluriel';

/**
 * Lyon, 17/11 : une correction de l'onglet « Corriger » reste appliquée au
 * « Régénérer » même quand Martine calcule maintenant autre chose. L'onglet le
 * disait ligne par ligne ; le bulletin le dit aussi, en haut, sans rien bloquer.
 */
export function phraseCorrectionsPerimees(lignes: ReadonlyArray<Pick<LigneCorrigeable, 'libelle' | 'alerte'>>): string | null {
  const perimees = lignes.filter((l) => l.alerte);
  if (perimees.length === 0) return null;
  const noms = perimees.map((l) => `« ${l.libelle} »`).join(', ');
  return (
    `Martine calcule maintenant autre chose sur ${pluriel(perimees.length, 'ligne')} ` +
    `${accord(perimees.length, 'corrigée')} à la main (${noms}). ` +
    `${perimees.length > 1 ? 'Les corrections restent appliquées' : 'La correction reste appliquée'} : ` +
    'la garder ou la retirer ? Le détail est dans l’onglet « Corriger ».'
  );
}

export function CorrectionsPerimeesAlerte({
  payslipId,
  companyId,
  version,
}: {
  payslipId: string;
  companyId: string | undefined;
  version: string | null;
}) {
  // Même requête que l'onglet « Corriger » : un seul appel, partagé.
  const query = useQuery({
    queryKey: queryKeys.lignesCorrigeables(companyId, payslipId, version),
    queryFn: () => getLignesCorrigeables(payslipId, companyId),
    enabled: Boolean(companyId && payslipId),
    staleTime: 30_000,
  });
  const phrase = phraseCorrectionsPerimees(query.data?.lignes ?? []);
  if (!phrase) return null;
  return (
    <Alert data-testid="corrections-perimees">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle>Correction à revoir</AlertTitle>
      <AlertDescription>{phrase}</AlertDescription>
    </Alert>
  );
}
