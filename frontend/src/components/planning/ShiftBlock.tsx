import type { Shift } from '@/api/planning';
import { Lock } from 'lucide-react';

const TRANSVERSE_COLORS: Record<string, string> = {
  CP: '#4CAF50',
  RTT: '#8BC34A',
  MAL: '#FF5722',
  ABS_INJ: '#F44336',
  FORM: '#2196F3',
  REP_HEB: '#9E9E9E',
};

function formatTimeShort(iso: string): string {
  if (!iso) return '';
  return iso.slice(0, 5);
}

function blockBackground(shift: Shift): string {
  if (shift.shift_type?.color) {
    return shift.shift_type.color;
  }
  const cat = shift.transverse_category;
  if (cat && TRANSVERSE_COLORS[cat]) {
    return TRANSVERSE_COLORS[cat];
  }
  return '#607D8B';
}

function blockLabel(shift: Shift): string {
  if (shift.shift_type?.label) {
    return shift.shift_type.label;
  }
  return shift.transverse_category ?? 'Shift';
}

export interface ShiftBlockProps {
  shift: Shift;
  onClick: (shift: Shift) => void;
  isLocked: boolean;
}

export function ShiftBlock({ shift, onClick, isLocked }: ShiftBlockProps) {
  const locked = isLocked || shift.is_locked;
  const bg = blockBackground(shift);
  const label = blockLabel(shift);
  const start = formatTimeShort(shift.start_time);
  const end = formatTimeShort(shift.end_time);

  return (
    <button
      type="button"
      className={`w-full rounded-md px-2 py-1 text-left text-xs font-medium text-white shadow-sm ring-1 ring-black/10 transition hover:opacity-95 ${
        locked ? 'cursor-default opacity-90' : 'cursor-pointer'
      }`}
      style={{ backgroundColor: bg }}
      onClick={(e) => {
        e.stopPropagation();
        onClick(shift);
      }}
      disabled={locked}
      aria-disabled={locked}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="truncate">{label}</span>
        {locked ? <Lock className="h-3 w-3 shrink-0 opacity-90" aria-hidden /> : null}
      </div>
      <div className="mt-0.5 font-normal opacity-95">
        {start} - {end}
      </div>
    </button>
  );
}
