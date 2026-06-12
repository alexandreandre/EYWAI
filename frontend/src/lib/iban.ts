/** Normalise un IBAN (sans espaces, majuscules). */
export function normalizeIban(value: string): string {
  return value.replace(/\s/g, '').replace(/-/g, '').toUpperCase().trim();
}

/** Valide le format IBAN (aligné sur le backend export banque). */
export function isValidIban(value: string): boolean {
  const iban = normalizeIban(value);
  if (iban.length < 15 || iban.length > 34) return false;
  return /^[A-Z]{2}[0-9]{2}[A-Z0-9]+$/.test(iban);
}
