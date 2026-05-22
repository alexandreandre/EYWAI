export type AppUserRole = 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom';

export const ROLE_LABELS: Record<AppUserRole, string> = {
  admin: 'Administrateur',
  rh: 'Ressources Humaines',
  collaborateur_rh: 'Collaborateur RH',
  collaborateur: 'Collaborateur',
  custom: 'Personnalisé',
};

export const ROLE_BADGE_CLASS: Record<AppUserRole, string> = {
  admin: 'bg-purple-100 text-purple-800 border-purple-200',
  rh: 'bg-blue-100 text-blue-800 border-blue-200',
  collaborateur_rh: 'bg-green-100 text-green-800 border-green-200',
  collaborateur: 'bg-muted text-muted-foreground border-border',
  custom: 'bg-orange-100 text-orange-800 border-orange-200',
};

export function getRoleDisplayLabel(
  role: AppUserRole,
  roleTemplateName?: string | null,
): string {
  if (role === 'custom' && roleTemplateName) return roleTemplateName;
  return ROLE_LABELS[role] ?? role;
}

export function getScopeBannerMessage(creatorRole: string, companyName: string): string {
  if (creatorRole === 'admin') {
    return `Tous les comptes applicatifs de ${companyName}, y compris les administrateurs.`;
  }
  if (creatorRole === 'rh') {
    return `Comptes ayant accès à ${companyName}. Les administrateurs ne figurent pas dans cette liste. Vous pouvez modifier les rôles : collaborateur RH, collaborateur et rôles personnalisés.`;
  }
  if (creatorRole === 'collaborateur_rh') {
    return `Comptes ayant accès à ${companyName} dans votre périmètre (collaborateur RH et collaborateurs).`;
  }
  return `Comptes ayant accès à ${companyName}, selon les droits de votre rôle.`;
}

/** Rôles de base affichables dans le filtre selon le rôle du connecté. */
export function getFilterableBaseRoles(creatorRole: string): AppUserRole[] {
  if (creatorRole === 'admin') {
    return ['admin', 'rh', 'collaborateur_rh', 'collaborateur'];
  }
  if (creatorRole === 'rh') {
    return ['rh', 'collaborateur_rh', 'collaborateur'];
  }
  if (creatorRole === 'collaborateur_rh') {
    return ['collaborateur_rh', 'collaborateur'];
  }
  return [];
}
