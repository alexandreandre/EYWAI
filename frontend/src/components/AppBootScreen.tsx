import { Progress } from '@/components/ui/progress';
import { useBoot } from '@/contexts/BootContext';

export function AppBootScreen() {
  const { stepLabel, progress } = useBoot();

  return (
    <div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center bg-background"
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-label={stepLabel}
    >
      <div className="flex w-full max-w-sm flex-col items-center gap-8 px-6">
        <img
          src="/Colorplast.png"
          alt="EYWAI"
          className="h-12 w-auto object-contain"
          width={160}
          height={48}
        />
        <div className="w-full space-y-3">
          <Progress value={progress} className="h-1.5" />
          <p className="text-center text-sm text-muted-foreground">{stepLabel}</p>
        </div>
      </div>
    </div>
  );
}
