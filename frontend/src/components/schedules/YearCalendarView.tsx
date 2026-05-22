import { useEffect, useState } from 'react';
import { Card, CardTitle } from '@/components/ui/card';
import { Loader2 } from 'lucide-react';
import * as calendarApi from '@/api/calendar';
import { cn } from '@/lib/utils';

type PlannedEventData = { jour: number; type: string | null; heures_prevues: number | null };
type ActualHoursData = { jour: number; heures_faites: number | null };

interface YearCalendarViewProps {
  year: number;
  employeeId: string;
  isForfaitJour?: boolean;
  onMonthClick?: (month: number) => void;
}

export function YearCalendarView({
  year,
  employeeId,
  onMonthClick,
}: YearCalendarViewProps) {
  const [yearData, setYearData] = useState<{
    [month: number]: { planned: PlannedEventData[]; actual: ActualHoursData[] };
  }>({});
  const [isLoadingYear, setIsLoadingYear] = useState(true);

  const monthNames = [
    'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
  ];

  useEffect(() => {
    const loadYearData = async () => {
      setIsLoadingYear(true);
      try {
        const promises = Array.from({ length: 12 }, async (_, monthIndex) => {
          const month = monthIndex + 1;
          const [plannedRes, actualRes] = await Promise.all([
            calendarApi.getPlannedCalendar(employeeId, year, month),
            calendarApi.getActualHours(employeeId, year, month),
          ]);

          const plannedDataFromApi = plannedRes.data.calendrier_prevu || [];
          const actualDataFromApi = actualRes.data.calendrier_reel || [];
          const daysInMonth = new Date(year, month, 0).getDate();

          const baseCalendar: PlannedEventData[] = [];
          for (let i = 1; i <= daysInMonth; i++) {
            const date = new Date(year, month - 1, i);
            const isWeekend = date.getDay() === 0 || date.getDay() === 6;
            baseCalendar.push({
              jour: i,
              type: isWeekend ? 'weekend' : 'travail',
              heures_prevues: null,
            });
          }

          const finalPlannedCalendar = baseCalendar.map((defaultDay) => {
            const apiDay = plannedDataFromApi.find(
              (p: PlannedEventData) => p.jour === defaultDay.jour
            );
            return apiDay ? { ...defaultDay, ...apiDay } : defaultDay;
          });

          const finalActualHours = baseCalendar.map((defaultDay) => {
            const apiDay = actualDataFromApi.find(
              (a: ActualHoursData) => a.jour === defaultDay.jour
            );
            return apiDay
              ? { jour: defaultDay.jour, heures_faites: apiDay.heures_faites }
              : { jour: defaultDay.jour, heures_faites: null };
          });

          return { month, planned: finalPlannedCalendar, actual: finalActualHours };
        });

        const results = await Promise.all(promises);
        const dataByMonth: typeof yearData = {};
        results.forEach((result) => {
          dataByMonth[result.month] = {
            planned: result.planned,
            actual: result.actual,
          };
        });
        setYearData(dataByMonth);
      } catch (error) {
        console.error('Erreur lors du chargement des données annuelles', error);
      } finally {
        setIsLoadingYear(false);
      }
    };

    void loadYearData();
  }, [year, employeeId]);

  const getTypeColor = (type: string | null | undefined) => {
    switch (type) {
      case 'travail':
        return 'bg-sky-100 text-sky-700';
      case 'conge':
        return 'bg-amber-100 text-amber-700';
      case 'ferie':
        return 'bg-purple-100 text-purple-700';
      case 'arret_maladie':
        return 'bg-red-100 text-red-700';
      case 'weekend':
        return 'bg-slate-100 text-slate-600';
      default:
        return 'bg-gray-50 text-gray-500';
    }
  };

  const isAbsence = (type: string | null | undefined) =>
    type === 'conge' || type === 'ferie' || type === 'arret_maladie';

  const renderMonth = (monthIndex: number) => {
    const month = monthIndex + 1;
    const monthData = yearData[month];

    if (!monthData) {
      return (
        <Card key={monthIndex} className="p-3">
          <CardTitle className="text-sm font-semibold mb-2 text-center">
            {monthNames[monthIndex]}
          </CardTitle>
          <div className="flex items-center justify-center h-32">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
        </Card>
      );
    }

    const firstDay = new Date(year, monthIndex, 1);
    const lastDay = new Date(year, monthIndex + 1, 0);
    const startDay = (firstDay.getDay() + 6) % 7;
    const daysInMonth = lastDay.getDate();
    const days = [];

    for (let i = 0; i < startDay; i++) {
      days.push(<div key={`empty-${i}`} className="aspect-square" />);
    }

    for (let day = 1; day <= daysInMonth; day++) {
      const date = new Date(year, monthIndex, day);
      const isToday = date.toDateString() === new Date().toDateString();
      const dayData = monthData.planned.find((d) => d.jour === day);
      const actualData = monthData.actual.find((d) => d.jour === day);
      const typeColor = getTypeColor(dayData?.type);
      const hasAbsence = isAbsence(dayData?.type);

      days.push(
        <div
          key={day}
          className={cn(
            'aspect-square rounded-md flex items-center justify-center text-xs font-medium transition-colors',
            typeColor,
            isToday && 'ring-2 ring-primary',
            hasAbsence && 'ring-2 ring-rose-400'
          )}
          title={`${day} ${monthNames[monthIndex]}: ${dayData?.type || 'non défini'}`}
        >
          {day}
        </div>
      );
    }

    return (
      <Card
        key={monthIndex}
        className={cn('p-3', onMonthClick && 'cursor-pointer hover:shadow-md transition-shadow')}
        onClick={() => onMonthClick?.(month)}
      >
        <CardTitle className="text-sm font-semibold mb-2 text-center">
          {monthNames[monthIndex]}
        </CardTitle>
        <div className="grid grid-cols-7 gap-0.5 text-[10px] text-center text-muted-foreground mb-1">
          {['L', 'M', 'M', 'J', 'V', 'S', 'D'].map((d, i) => (
            <div key={i} className="font-medium">
              {d}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-0.5">{days}</div>
      </Card>
    );
  };

  if (isLoadingYear) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-12 w-12 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4 p-4">
      <Card className="p-4 bg-muted/40">
        <div className="flex flex-wrap gap-x-6 gap-y-2 justify-center text-sm">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-sky-100 border border-sky-200" />
            <span className="text-sky-700">Travail</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-amber-100 border border-amber-200" />
            <span className="text-amber-700">Congé</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-purple-100 border border-purple-200" />
            <span className="text-purple-700">Férié</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-red-100 border border-red-200" />
            <span className="text-red-700">Arrêt</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded bg-slate-100 border border-slate-200" />
            <span className="text-slate-600">Week-end</span>
          </div>
        </div>
      </Card>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {Array.from({ length: 12 }, (_, i) => renderMonth(i))}
      </div>
    </div>
  );
}
