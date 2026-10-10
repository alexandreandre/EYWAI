/**
 * « de » devant un nom ou un mois : « d'Élodie Vasseur », « d'octobre »,
 * mais « de Camille Roussel », « de mars ». Voyelle (accentuée ou non) ou h
 * muet : on élide.
 */
const DEBUT_ELIDE = /^[aeiouyhàâäéèêëîïôöùûüœæ]/i;

export function deDevant(mot: string | null | undefined): string {
  const propre = (mot ?? '').trim();
  if (!propre) return '';
  return DEBUT_ELIDE.test(propre) ? `d'${propre}` : `de ${propre}`;
}
