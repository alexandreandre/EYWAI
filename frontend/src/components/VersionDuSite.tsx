import { versionDuSite } from '@/lib/versionDuSite';

/** Version du site en ligne, en bas du menu (masquée quand le menu est replié). */
export function VersionDuSite({ collapsed = false }: { collapsed?: boolean }) {
  if (collapsed) return null;
  const { libelle, detail } = versionDuSite();
  return (
    <p className="mt-1.5 truncate text-[11px] leading-tight text-muted-foreground" title={detail}>
      {libelle}
    </p>
  );
}
