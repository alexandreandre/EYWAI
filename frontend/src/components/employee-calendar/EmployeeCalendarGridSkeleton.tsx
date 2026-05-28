import { Skeleton } from '@/components/ui/skeleton';

const DAY_HEADERS = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

export function EmployeeCalendarGridSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-busy="true" aria-label="Chargement du calendrier">
      <div className="grid grid-cols-7 gap-1 text-center">
        {DAY_HEADERS.map((d) => (
          <Skeleton key={d} className="mx-auto h-4 w-8" />
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1.5">
        {Array.from({ length: 35 }).map((_, i) => (
          <Skeleton key={i} className="min-h-[5.5rem] rounded-xl" />
        ))}
      </div>
    </div>
  );
}
