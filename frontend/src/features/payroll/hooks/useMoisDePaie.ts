import { useCallback, useEffect, useMemo, useSyncExternalStore } from 'react';
import { useSearchParams } from 'react-router-dom';
import { moisDePaieParDefaut } from '@/features/payroll/utils/payrollMonth';
import {
  EVENEMENT_MOIS_DE_PAIE,
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

function abonner(rappel: () => void): () => void {
  window.addEventListener(EVENEMENT_MOIS_DE_PAIE, rappel);
  window.addEventListener('storage', rappel);
  return () => {
    window.removeEventListener(EVENEMENT_MOIS_DE_PAIE, rappel);
    window.removeEventListener('storage', rappel);
  };
}

function lireCle(): string {
  const m = moisDePaieRetenu() ?? moisDePaieParDefaut(new Date());
  return periodeDuMois(m);
}

/**
 * Le mois de paie en préparation, hors d'un écran de paie (menu, pastilles,
 * verrou) : le dernier mois choisi pour la société, sinon le mois de paie par
 * défaut. Le menu restait sur novembre pendant qu'Elsa faisait la paie
 * d'octobre de LEWIS (26/11).
 */
export function useMoisDePaieEnCours(): MoisDePaie {
  const cle = useSyncExternalStore(abonner, lireCle, lireCle);
  return useMemo(() => {
    const [year, month] = cle.split('-').map(Number);
    return { year, month };
  }, [cle]);
}
