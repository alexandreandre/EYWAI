import Rates from '@/pages/rh/Rates';

/**
 * Suivi des taux — vue administrateur plateforme.
 *
 * Réutilise la page RH « Suivi des taux » en activant les fonctionnalités admin
 * (validation des changements en attente, alertes critiques, saisie manuelle).
 */
export default function RatesAdmin() {
  return <Rates admin />;
}
