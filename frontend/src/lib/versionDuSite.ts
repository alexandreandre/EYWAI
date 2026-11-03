/**
 * Version du site en ligne, figée au build par le déploiement :
 * `VITE_APP_VERSION` (étiquette `paie-AAAA-MM-JJ.N`) et `VITE_APP_BUILD_ID` (commit).
 * Sert au support : savoir quel code a calculé un bulletin.
 */
export type VersionDuSite = {
  /** Texte court affiché en bas du menu. */
  libelle: string;
  /** Texte complet (infobulle) : étiquette et commit entier. */
  detail: string;
};

type EnvDeVersion = { VITE_APP_VERSION?: string; VITE_APP_BUILD_ID?: string };

export function versionDuSite(env: EnvDeVersion = import.meta.env as EnvDeVersion): VersionDuSite {
  const etiquette = env.VITE_APP_VERSION?.trim() || '';
  const commit = env.VITE_APP_BUILD_ID?.trim() || '';
  const court = commit.slice(0, 7);
  if (etiquette) {
    return {
      libelle: court ? `Version ${etiquette} · ${court}` : `Version ${etiquette}`,
      detail: commit ? `${etiquette} (commit ${commit})` : etiquette,
    };
  }
  if (court) {
    return { libelle: `Version non étiquetée · ${court}`, detail: `commit ${commit}` };
  }
  return { libelle: 'Version locale', detail: 'Version locale, hors déploiement' };
}
