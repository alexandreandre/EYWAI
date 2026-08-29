import { useCallback, useEffect, useRef, type PointerEvent } from 'react';

export function idsInIndexRange(ids: string[], from: number, to: number): string[] {
  if (ids.length === 0) return [];
  const start = Math.max(0, Math.min(from, to));
  const end = Math.min(ids.length - 1, Math.max(from, to));
  return ids.slice(start, end + 1);
}

interface UsePaintSelectArgs {
  ids: string[];
  selectedIds: Set<string>;
  onSetSelected: (ids: string[], selected: boolean) => void;
}

export function usePaintSelect({ ids, selectedIds, onSetSelected }: UsePaintSelectArgs) {
  const painting = useRef<boolean | null>(null);
  const lastIndex = useRef<number | null>(null);

  useEffect(() => {
    const endPaint = () => {
      painting.current = null;
      document.body.classList.remove('select-none');
    };
    window.addEventListener('pointerup', endPaint);
    window.addEventListener('pointercancel', endPaint);
    return () => {
      window.removeEventListener('pointerup', endPaint);
      window.removeEventListener('pointercancel', endPaint);
    };
  }, []);

  const onHandlePointerDown = useCallback(
    (event: PointerEvent<HTMLElement>, index: number) => {
      if (event.button !== 0) return;
      event.preventDefault();
      const id = ids[index];
      if (!id) return;

      if (event.shiftKey && lastIndex.current != null) {
        onSetSelected(idsInIndexRange(ids, lastIndex.current, index), true);
        lastIndex.current = index;
        return;
      }

      const select = !selectedIds.has(id);
      painting.current = select;
      document.body.classList.add('select-none');
      onSetSelected([id], select);
      lastIndex.current = index;
    },
    [ids, onSetSelected, selectedIds],
  );

  const onHandlePointerEnter = useCallback(
    (index: number) => {
      if (painting.current == null) return;
      const id = ids[index];
      if (!id) return;
      onSetSelected([id], painting.current);
    },
    [ids, onSetSelected],
  );

  return { onHandlePointerDown, onHandlePointerEnter };
}
