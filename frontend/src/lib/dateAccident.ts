// Date de l'accident ou de la première constatation d'un arrêt (DSN 60.012).

/** Types d'arrêt qui portent une date d'accident. */
export function arretAvecDateAccident(type: string | null | undefined): boolean {
  return type === 'arret_at' || type === 'arret_maladie_pro';
}

/** Pourquoi la date saisie ne va pas, sinon null. Dates ISO (AAAA-MM-JJ). */
export function refusDateAccident(dateAccident: string, premierJour: string | null): string | null {
  if (premierJour && dateAccident > premierJour) {
    return "La date de l'accident ne peut pas être après le premier jour d'arrêt : corrigez l'une des deux dates.";
  }
  return null;
}
