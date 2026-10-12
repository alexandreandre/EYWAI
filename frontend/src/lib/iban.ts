/** Normalise un IBAN (sans espaces, majuscules). */
export function normalizeIban(value: string): string {
  return value.replace(/\s/g, '').replace(/-/g, '').toUpperCase().trim();
}

/** Longueur de l'IBAN par pays (registre ISO 13616) ; même table que le serveur. */
export const IBAN_LONGUEURS_PAR_PAYS: Record<string, number> = {
  AD: 24, AE: 23, AL: 28, AT: 20, AZ: 28, BA: 20, BE: 16, BG: 22, BH: 22, BR: 29,
  BY: 28, CH: 21, CR: 22, CY: 28, CZ: 24, DE: 22, DK: 18, DO: 28, EE: 20, EG: 29,
  ES: 24, FI: 18, FO: 18, FR: 27, GB: 22, GE: 22, GI: 23, GL: 18, GR: 27, GT: 28,
  HR: 21, HU: 28, IE: 22, IL: 23, IQ: 23, IS: 26, IT: 27, JO: 30, KW: 30, KZ: 20,
  LB: 28, LC: 32, LI: 21, LT: 20, LU: 20, LV: 21, LY: 25, MC: 27, MD: 24, ME: 22,
  MK: 19, MR: 27, MT: 31, MU: 30, NL: 18, NO: 15, PK: 24, PL: 28, PS: 29, PT: 25,
  QA: 29, RO: 24, RS: 22, SA: 24, SC: 31, SE: 24, SI: 19, SK: 24, SM: 27, ST: 25,
  SV: 28, TL: 23, TN: 24, TR: 26, UA: 29, VA: 22, VG: 24, XK: 20,
};

/** Reste mod 97 de l'IBAN normalisé, sans nombre géant (1 si la clé est juste). */
function mod97(iban: string): number {
  const rearranged = iban.slice(4) + iban.slice(0, 4);
  let remainder = 0;
  for (const ch of rearranged) {
    const digits = /[0-9]/.test(ch) ? ch : String(ch.charCodeAt(0) - 55);
    for (const d of digits) remainder = (remainder * 10 + Number(d)) % 97;
  }
  return remainder;
}

/** Raison du refus d'un IBAN, en français ; null s'il est bon. */
export function ibanProblem(value: string): string | null {
  const iban = normalizeIban(value);
  if (!iban) return 'IBAN vide.';
  if (!/^[A-Z]{2}[0-9]{2}[A-Z0-9]+$/.test(iban)) {
    return 'IBAN invalide : deux lettres de pays, deux chiffres de clé, puis le numéro de compte.';
  }
  const attendue = IBAN_LONGUEURS_PAR_PAYS[iban.slice(0, 2)];
  if (attendue !== undefined && iban.length !== attendue) {
    return `IBAN ${iban.slice(0, 2)} de longueur incorrecte : ${attendue} caractères attendus, ${iban.length} saisis.`;
  }
  if (attendue === undefined && (iban.length < 15 || iban.length > 34)) {
    return 'IBAN de longueur incorrecte : entre 15 et 34 caractères.';
  }
  if (mod97(iban) !== 1) return "Clé de contrôle de l'IBAN incorrecte : vérifiez la saisie.";
  return null;
}

/** Valide l'IBAN : format, longueur du pays et clé de contrôle (mod 97). */
export function isValidIban(value: string): boolean {
  return ibanProblem(value) === null;
}

/**
 * Un IBAN renseigné et bien formé : pays, clé, 15 à 34 caractères. Ni la clé
 * (mod 97) ni la longueur propre au pays : faux mais bien formé, il s'enregistre
 * sur la fiche avec un avertissement (12/10/2026) ; c'est le virement qui le
 * bloque.
 */
export function ibanBienForme(value: string): boolean {
  const iban = normalizeIban(value);
  return iban.length >= 15 && iban.length <= 34 && /^[A-Z]{2}[0-9]{2}[A-Z0-9]+$/.test(iban);
}

/**
 * Ce que la fiche dit d'un IBAN bien formé mais faux ; null s'il n'y a rien à
 * dire (IBAN juste, vide ou mal formé, ou salarié payé sans virement).
 */
export function avertissementIban(value: string, modePaiement?: string | null): string | null {
  if (modePaiement === 'cheque' || modePaiement === 'especes') return null;
  if (!ibanBienForme(value)) return null;
  const probleme = ibanProblem(value);
  if (!probleme) return null;
  return `${probleme} La fiche s'enregistre, mais le virement des salaires restera bloqué tant que cet IBAN n’est pas corrigé.`;
}
