/** Libellé d'un niveau de la revue, tel qu'il se lit à côté du message. */
export function libelleNiveau(niveau: string): string {
  if (niveau === 'CRITIQUE') return 'Critique';
  if (niveau === 'AVERTISSEMENT') return 'À relire';
  return 'Info';
}

/** Les règles B s'acquittent. Les alertes du moteur, non : elles décrivent le calcul. */
export function regleAcquittable(ruleId: string): boolean {
  return /^B\d{2}$/.test(ruleId);
}
