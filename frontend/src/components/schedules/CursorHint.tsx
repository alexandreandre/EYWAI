import { useCallback, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';

const OFFSET_X = 14;
const OFFSET_Y = 18;

interface CursorHintProps {
  label: string;
  children: ReactNode;
  className?: string;
}

export function CursorHint({ label, children, className }: CursorHintProps) {
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  const onMove = useCallback((e: React.MouseEvent) => {
    const x = e.clientX + OFFSET_X;
    const y = e.clientY + OFFSET_Y;
    const maxX = window.innerWidth - 220;
    const maxY = window.innerHeight - 36;
    setPos({
      x: Math.max(8, Math.min(x, maxX)),
      y: Math.max(8, Math.min(y, maxY)),
    });
  }, []);

  return (
    <div
      className={cn(className)}
      onMouseEnter={onMove}
      onMouseMove={onMove}
      onMouseLeave={() => setPos(null)}
    >
      {children}
      {pos &&
        createPortal(
          <div
            role="tooltip"
            className="pointer-events-none fixed z-[80] rounded-md border bg-background px-2 py-1 text-[11px] font-medium text-foreground shadow-md"
            style={{ left: pos.x, top: pos.y }}
          >
            {label}
          </div>,
          document.body,
        )}
    </div>
  );
}
