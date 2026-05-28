/** Nom du groupe plateforme unique (rattachement automatique des entreprises). */
export const DEFAULT_PLATFORM_GROUP_NAME = "MAJI";

export function findDefaultGroupId(
  groups: Array<{ id: string; group_name: string }>,
): string | null {
  const byName = groups.find(
    (g) => g.group_name.trim().toUpperCase() === DEFAULT_PLATFORM_GROUP_NAME.toUpperCase(),
  );
  if (byName) return byName.id;
  if (groups.length === 1) return groups[0].id;
  return null;
}
