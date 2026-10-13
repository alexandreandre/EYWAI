/**
 * Le message de fin de génération d'un document de sortie. Le reçu redit les
 * alertes du bulletin de sortie (RTT et JTC non pris, « Néant » : à vérifier
 * selon l'accord, décision du 12/10) : un succès muet les cacherait.
 */
export function toastDeGeneration(reponse: { success?: boolean; alertes?: string[] | null }): {
  title: string;
  description: string;
} {
  const alertes = (reponse.alertes ?? []).filter((a) => a.trim().length > 0);
  if (alertes.length === 0) {
    return { title: 'Succès', description: 'Document généré avec succès' };
  }
  return { title: 'Document généré, à vérifier', description: alertes.join(' ') };
}
