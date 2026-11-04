import { BarreDeProgression } from '@/components/BarreDeProgression';
import { useBoot } from '@/contexts/BootContext';
import { ALT_LOGO_MARTINE, LOGO_MARTINE } from '@/lib/logoMartine';

export function AppBootScreen() {
  const { stepLabel } = useBoot();

  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-background"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="flex w-full max-w-sm flex-col items-center gap-8 px-6">
        <img src={LOGO_MARTINE} alt={ALT_LOGO_MARTINE} className="h-12 w-12" width={48} height={48} />
        <div className="w-full space-y-3">
          {/* L'avancement du démarrage saute d'une étape à l'autre : la barre dit
              seulement que ça avance, l'étape s'écrit dessous. */}
          <BarreDeProgression libelle="Démarrage de Martine" />
          <p className="text-center text-sm font-medium text-foreground">{stepLabel}</p>
          <p className="text-center text-xs text-muted-foreground">
            Préparation de vos données pour une navigation plus fluide
          </p>
        </div>
      </div>
    </div>
  );
}
