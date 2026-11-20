/**
 * « Donner accès à d'autres sociétés » à un utilisateur existant.
 *
 * Calculs purs de l'écran de modification d'un utilisateur : quelles sociétés
 * proposer, quels rôles offrir, quel message afficher après l'enregistrement.
 */
import type { AccessibleCompany } from '@/api/permissions';
import { getRoleDisplayLabel, type AppUserRole } from '@/lib/userRoleLabels';

/** Ordre d'affichage des rôles, du plus large au plus restreint. */
const ORDRE_ROLES: AppUserRole[] = ['admin', 'rh', 'collaborateur_rh', 'collaborateur'];

/**
 * Sociétés que la personne connectée peut ouvrir à l'utilisateur : celles où
 * elle peut donner au moins un rôle, et où l'utilisateur n'a pas encore accès.
 */
export function societesProposables(
  administrables: AccessibleCompany[],
  accesActuels: Array<{ company_id: string }>,
): AccessibleCompany[] {
  const dejaOuvertes = new Set(accesActuels.map((a) => a.company_id));
  return administrables
    .filter((c) => !dejaOuvertes.has(c.company_id))
    .filter((c) => rolesDonnables([c]).length > 0)
    .sort((a, b) => a.company_name.localeCompare(b.company_name, 'fr'));
}

/**
 * Rôles que l'on peut donner dans toutes les sociétés cochées à la fois.
 * Le rôle personnalisé est écarté : il demande de choisir les droits société
 * par société, ce qui se fait depuis l'écran de chaque société.
 */
export function rolesDonnables(societes: AccessibleCompany[]): AppUserRole[] {
  if (societes.length === 0) return [];
  return ORDRE_ROLES.filter((role) =>
    societes.every((c) => c.can_create_roles.includes(role)),
  );
}

/** Rôle proposé par défaut : celui que la personne a déjà, sinon le plus restreint. */
export function roleParDefaut(
  roles: AppUserRole[],
  roleActuel: string | null | undefined,
): AppUserRole | '' {
  if (roles.length === 0) return '';
  if (roleActuel && roles.includes(roleActuel as AppUserRole)) {
    return roleActuel as AppUserRole;
  }
  return roles[roles.length - 1];
}

/** « A », « A et B », « A, B et C ». */
export function listerNoms(noms: string[]): string {
  if (noms.length <= 1) return noms[0] ?? '';
  return `${noms.slice(0, -1).join(', ')} et ${noms[noms.length - 1]}`;
}

/** Message affiché après l'enregistrement, réussites et échecs nommés. */
export function messageResultatAcces(
  reussies: string[],
  echouees: Array<{ nom: string; raison: string }>,
  role: AppUserRole,
): { succes: string | null; erreur: string | null } {
  const libelleRole = getRoleDisplayLabel(role);
  const succes =
    reussies.length > 0
      ? `Accès donné à ${listerNoms(reussies)} (rôle : ${libelleRole}). La personne se connecte avec son compte habituel.`
      : null;
  const erreur =
    echouees.length > 0
      ? `Accès non donné à ${echouees.map((e) => `${e.nom} (${e.raison})`).join(' ; ')}.`
      : null;
  return { succes, erreur };
}

/**
 * Erreur de création d'un compte : quand l'e-mail existe déjà, on dit où
 * donner l'accès au lieu de laisser la gestionnaire devant un message technique.
 */
export function messageErreurCreation(detail: unknown): string {
  const texte =
    typeof detail === 'string' && detail ? detail : "Erreur lors de la création de l'utilisateur";
  if (/already (been )?registered|already exists|existe déjà|duplicate/i.test(texte)) {
    return (
      "Un compte existe déjà avec cet e-mail. Pour lui ouvrir une autre société, ouvrez-le " +
      "depuis la liste des utilisateurs (Modifier), puis « Donner accès à d'autres sociétés »."
    );
  }
  return texte;
}
