import type { AccountingMapping } from '@/api/exports';

export type OdRegroupement = 'global' | 'par_analytique';

/**
 * Regroupements proposés pour une OD. « Par établissement » est retiré : une
 * société n'a qu'un établissement et l'OD en porte le nom, il ne changeait rien.
 * « Par analytique » n'agit que si le compte du salaire brut porte un code
 * analytique ; sans code, il donnait la même OD que « Global ».
 */
export function regroupementsProposes(
  mappings: AccountingMapping[] | undefined,
): { value: OdRegroupement; label: string }[] {
  const options: { value: OdRegroupement; label: string }[] = [{ value: 'global', label: 'Global' }];
  const salaireBrut = (mappings ?? []).filter(
    (m) => m.rubrique_code === 'salaire_brut' && m.is_active,
  );
  const retenu = salaireBrut.find((m) => !m.is_global_default) ?? salaireBrut[0];
  if (retenu?.analytique?.trim()) {
    options.push({ value: 'par_analytique', label: 'Par analytique' });
  }
  return options;
}
