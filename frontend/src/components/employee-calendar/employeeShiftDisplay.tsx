import type { Shift } from '@/api/planning';
import { cn } from '@/lib/utils';

const TRANSVERSE_COLORS: Record<string, string> = {
  CP: '#4CAF50',
  RTT: '#8BC34A',
  MAL: '#FF5722',
  ABS_INJ: '#F44336',
  FORM: '#2196F3',
  REP_HEB: '#9E9E9E',
};

export function shiftBlockColor(shift: Shift): string {
  if (shift.shift_type?.color) return shift.shift_type.color;
  const cat = shift.transverse_category;
  if (cat && TRANSVERSE_COLORS[cat]) return TRANSVERSE_COLORS[cat];
  return '#607D8B';
}

export function shiftBlockLabel(shift: Shift): string {
  if (shift.shift_type?.label) return shift.shift_type.label;
  return shift.transverse_category ?? 'Créneau';
}

export function formatShiftTimeRange(shift: Shift): string {
  return `${shift.start_time.slice(0, 5)} – ${shift.end_time.slice(0, 5)}`;
}

interface CompactShiftRowProps {
  shift: Shift;
  className?: string;
}

export function CompactShiftRow({ shift, className }: CompactShiftRowProps) {
  const bg = shiftBlockColor(shift);
  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-md px-2 py-1.5 text-xs text-white shadow-sm',
        className
      )}
      style={{ backgroundColor: bg }}
    >
      <span className="font-medium tabular-nums shrink-0">{formatShiftTimeRange(shift)}</span>
      <span className="truncate opacity-95">{shiftBlockLabel(shift)}</span>
    </div>
  );
}
