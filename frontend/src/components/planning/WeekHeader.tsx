import { Lock, Unlock } from 'lucide-react';

export interface WeekHeaderProps {
  date: string;
  label: string;
  isLocked: boolean;
  totalHours: number;
  staffCount: number;
  onLockDay: () => void;
  isRH: boolean;
}

export function WeekHeader({
  label,
  isLocked,
  totalHours,
  staffCount,
  onLockDay,
  isRH,
}: WeekHeaderProps) {
  return (
    <div className="flex flex-col gap-1 py-1">
      <div className="flex items-center justify-between gap-1">
        <span className="font-medium leading-tight">{label}</span>
        {isRH ? (
          <button
            type="button"
            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
            onClick={(e) => {
              e.stopPropagation();
              onLockDay();
            }}
            title={isLocked ? 'Jour verrouillé' : 'Verrouiller le jour'}
            aria-label={isLocked ? 'Jour verrouillé' : 'Verrouiller le jour'}
          >
            {isLocked ? (
              <Lock className="h-4 w-4" aria-hidden />
            ) : (
              <Unlock className="h-4 w-4" aria-hidden />
            )}
          </button>
        ) : null}
      </div>
      <div className="text-[11px] leading-snug text-muted-foreground">
        {totalHours.toFixed(1)} h · {staffCount} pers.
      </div>
    </div>
  );
}
