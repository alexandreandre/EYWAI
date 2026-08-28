/**
 * Quelle liste `menuItems` la sidebar RH affiche pour un rôle plat.
 *
 * `menuItems` n'a que trois clés (rh, manager, employee). Les rôles
 * applicatifs `admin` et `custom` n'y figurent pas : sans ce mapping, la
 * résolution `menuItems[user.role] ?? []` laisse une sidebar vide aux
 * directeurs (rôle `custom`).
 */

export type SidebarMenuKey = 'rh' | 'manager' | 'employee';

export function resolveSidebarMenuKey(
  role: string | undefined | null,
  viewMode: 'rh' | 'collaborateur' = 'rh',
): SidebarMenuKey | null {
  if (role === 'collaborateur_rh') {
    return viewMode === 'collaborateur' ? 'employee' : 'rh';
  }
  if (role === 'admin' || role === 'rh') return 'rh';
  if (role === 'custom') return 'manager';
  if (role === 'employee') return 'employee';
  return null;
}
