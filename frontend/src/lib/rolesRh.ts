/**
 * Rôles qui modifient comme un RH : administrateur, RH et collaborateur RH.
 *
 * Même règle que le serveur (`User.has_rh_access_in_company`). Le rôle
 * `collaborateur_rh` sert aux postes qui cumulent un travail de salarié et
 * une mission RH : il modifie ce qu'un RH modifie.
 */
const ROLES_RH = new Set(['admin', 'rh', 'collaborateur_rh']);

export function estRoleRh(role: string | null | undefined): boolean {
  return Boolean(role) && ROLES_RH.has(role as string);
}
