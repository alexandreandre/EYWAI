import { majorationHsDuBareme } from '@/lib/brutDureeHebdo';
import { useRatesQuery } from './useRatesQuery';

/** Majoration des heures au-delà de 35 h, lue dans le barème des heures sup ([B15]). */
export function useMajorationHs(): number | null {
  const { data } = useRatesQuery(true);
  return majorationHsDuBareme(data);
}
