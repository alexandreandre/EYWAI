// Règles pures du lien d'activation (invitabilité, mot de passe).
// Miroir des règles backend : adresse réelle uniquement, jamais fabriquée.

import { isDsnImportPlaceholderEmail } from '@/lib/employeeProfileUtils';

export function emailsMatch(
  left: string | null | undefined,
  right: string | null | undefined,
): boolean {
  const a = (left || '').trim().toLowerCase();
  const b = (right || '').trim().toLowerCase();
  if (!a || !b) return false;
  return a === b;
}

/** Invitable = adresse non vide et jamais fabriquée par la plateforme. */
export function isEmployeeInvitable(email: string | null | undefined): boolean {
  const value = email?.trim();
  if (!value || !value.includes('@')) {
    // Les anciens placeholders `*.dsn-import.local` n'ont pas de `@` : exclus aussi.
    return false;
  }
  return !isDsnImportPlaceholderEmail(value);
}

/** Raison affichée en info-bulle quand le bouton « Inviter » est désactivé. */
export function getInvitationDisabledReason(
  email: string | null | undefined,
): string | null {
  if (isEmployeeInvitable(email)) return null;
  return (
    "Renseignez d'abord une adresse e-mail personnelle sur la fiche : " +
    'aucune invitation ne peut partir sans adresse réelle.'
  );
}

export interface PasswordChecks {
  longueur: boolean;
  majuscule: boolean;
  minuscule: boolean;
  chiffre: boolean;
}

/** Mêmes critères que la réinitialisation de mot de passe existante. */
export function getPasswordChecks(password: string): PasswordChecks {
  return {
    longueur: password.length >= 8,
    majuscule: /[A-Z]/.test(password),
    minuscule: /[a-z]/.test(password),
    chiffre: /[0-9]/.test(password),
  };
}

export function isPasswordAcceptable(password: string): boolean {
  const checks = getPasswordChecks(password);
  return checks.longueur && checks.majuscule && checks.minuscule && checks.chiffre;
}

/** Nombre de critères remplis (0 à 4) — alimente la jauge simple. */
export function getPasswordStrength(password: string): number {
  return Object.values(getPasswordChecks(password)).filter(Boolean).length;
}
