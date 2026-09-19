/**
 * Attribution d'une semaine à chaque fichier déposé dans l'import de pointages.
 *
 * Clé : `file.name` (unique dans la liste déposée) ; valeur : lundi ISO
 * (YYYY-MM-DD), ce que le backend attend en `week_anchor_date`. Absente =
 * « Non précisée », comme le sélecteur d'aujourd'hui, sans pré-remplissage.
 */
export type WeekByFile = Record<string, string>;

/** Les semaines dans l'ordre des fichiers, `null` quand non précisée. */
export function weeksAlignedWithFiles(
  files: { name: string }[],
  weekByFile: WeekByFile,
): (string | null)[] {
  return files.map((f) => weekByFile[f.name] || null);
}

/** Les fichiers sans semaine — bloquant en mode hebdomadaire, comme avant. */
export function filesMissingWeek(files: { name: string }[], weekByFile: WeekByFile): string[] {
  return files.filter((f) => !weekByFile[f.name]).map((f) => f.name);
}

/** « S28 » pour chaque semaine donnée à plusieurs fichiers : le dernier écrasera le premier. */
export function duplicateWeekLabels(
  files: { name: string }[],
  weekByFile: WeekByFile,
  options: { value: string; week: number }[],
): string[] {
  const count = new Map<string, number>();
  for (const f of files) {
    const value = weekByFile[f.name];
    if (value) count.set(value, (count.get(value) ?? 0) + 1);
  }
  return options.filter((o) => (count.get(o.value) ?? 0) > 1).map((o) => `S${o.week}`);
}
