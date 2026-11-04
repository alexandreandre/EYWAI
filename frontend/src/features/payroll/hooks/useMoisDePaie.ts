import { useCallback, useEffect, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  avecMoisDePaie,
  moisDePaieAffiche,
  moisDePaieRetenu,
  periodeDuMois,
  retenirMoisDePaie,
  type MoisDePaie,
} from '@/features/payroll/utils/moisDePaie';

/**
 * Le mois de paie de l'écran : lu dans l'adresse, sinon repris de l'écran
 * précédent, sinon le mois de paie (jusqu'au 15, le mois précédent). Il est
 * toujours écrit dans l'adresse (`?month=AAAA-MM`) et retenu pour la session.
 */
export function useMoisDePaie(): { mois: MoisDePaie; choisir: (mois: MoisDePaie) => void } {
  const [searchParams, setSearchParams] = useSearchParams();
  const mois = useMemo(
    () => moisDePaieAffiche(searchParams, moisDePaieRetenu(), new Date()),
    [searchParams],
  );

  useEffect(() => {
    retenirMoisDePaie(mois);
    const ecrit = searchParams.get('month') === periodeDuMois(mois) && !searchParams.has('year');
    if (!ecrit) setSearchParams((prev) => avecMoisDePaie(prev, mois), { replace: true });
  }, [mois, searchParams, setSearchParams]);

  const choisir = useCallback(
    (suivant: MoisDePaie) => {
      retenirMoisDePaie(suivant);
      setSearchParams((prev) => avecMoisDePaie(prev, suivant), { replace: true });
    },
    [setSearchParams],
  );

  return { mois, choisir };
}
