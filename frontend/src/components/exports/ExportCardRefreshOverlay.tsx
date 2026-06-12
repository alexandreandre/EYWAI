import { SharkFinLoader } from '@/components/SharkFinLoader';

type ExportCardRefreshOverlayProps = {
  visible: boolean;
  label: string;
};

/** Overlay léger sur une Card pendant un refetch React Query (sans masquer le contenu au premier chargement). */
export function ExportCardRefreshOverlay({ visible, label }: ExportCardRefreshOverlayProps) {
  if (!visible) return null;

  return (
    <div
      className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-background/80 backdrop-blur-[1px]"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <SharkFinLoader variant="compact" label={label} />
    </div>
  );
}
