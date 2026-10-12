import { avertissementIban } from '@/lib/iban';

/**
 * Sous le champ IBAN : une clé ou une longueur fausse n'empêche pas d'enregistrer
 * la fiche, mais le virement des salaires la bloquera (12/10/2026).
 */
export function AvertissementIban({
  iban,
  modePaiement,
}: {
  iban: string | null | undefined;
  /** `salary_payment_method` : payé sans virement, rien à dire. */
  modePaiement?: string | null;
}) {
  const message = avertissementIban(iban ?? '', modePaiement);
  if (!message) return null;
  return (
    <p className="text-sm text-amber-700 dark:text-amber-400" role="alert" data-testid="avertissement-iban">
      {message}
    </p>
  );
}
