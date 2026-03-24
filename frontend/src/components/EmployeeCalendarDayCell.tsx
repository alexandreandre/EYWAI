import { DayCellContentArg } from "@fullcalendar/react";
import { cn } from "@/lib/utils";
import { DayData } from "./ScheduleModal";
import {
  Clock,
  Coffee,
  Home,
  Plane,
  BriefcaseMedical,
} from "lucide-react";

interface EmployeeCalendarDayCellProps {
  arg: DayCellContentArg;
  plannedCalendar: DayData[];
  actualHours: DayData[];
}

const typeStyles: Record<
  string,
  { icon: React.ElementType; bg: string; text: string; border: string }
> = {
  travail: {
    icon: Clock,
    bg: "bg-blue-50/80 dark:bg-blue-950/40",
    text: "text-blue-700 dark:text-blue-300",
    border: "border-blue-100 dark:border-blue-900",
  },
  conge: {
    icon: Plane,
    bg: "bg-green-50/80 dark:bg-green-950/40",
    text: "text-green-700 dark:text-green-300",
    border: "border-green-100 dark:border-green-900",
  },
  ferie: {
    icon: Home,
    bg: "bg-indigo-50/80 dark:bg-indigo-950/40",
    text: "text-indigo-700 dark:text-indigo-300",
    border: "border-indigo-100 dark:border-indigo-900",
  },
  weekend: {
    icon: Coffee,
    bg: "bg-gray-50/80 dark:bg-slate-800/50",
    text: "text-gray-500 dark:text-gray-400",
    border: "border-gray-100 dark:border-slate-700",
  },
  arret_maladie: {
    icon: BriefcaseMedical,
    bg: "bg-orange-50/80 dark:bg-orange-950/40",
    text: "text-orange-700 dark:text-orange-300",
    border: "border-orange-100 dark:border-orange-900",
  },
};

export function EmployeeCalendarDayCell({
  arg,
  plannedCalendar,
  actualHours,
}: EmployeeCalendarDayCellProps) {
  const dayNumber = arg.dayNumberText.replace("日", "");
  const dayData = plannedCalendar.find((d) => d.jour === parseInt(dayNumber));
  const actualData = actualHours.find((d) => d.jour === parseInt(dayNumber));

  const dayType = dayData?.type || "weekend";
  const style = typeStyles[dayType] || typeStyles.weekend;
  const Icon = style.icon;

  const isOutside = arg.isOther;
  const isToday = arg.isToday;

  return (
    <div
      className={cn(
        "relative flex flex-col h-full w-full rounded-lg transition-all duration-200",
        "hover:scale-[1.02] hover:shadow-md",
        style.bg,
        style.border,
        "border p-2 backdrop-blur-sm",
        isOutside && "opacity-50 grayscale",
        isToday && "ring-2 ring-primary/70 shadow-lg"
      )}
    >
      <div className={cn("flex justify-between items-center")}>
        <span className={cn("font-semibold text-sm", style.text)}>
          {dayNumber}
        </span>
        {isToday && (
          <span className="text-[10px] font-medium text-primary">Aujourd’hui</span>
        )}
      </div>

      {dayData && !isOutside && (
        <div className="mt-2 flex-grow flex flex-col justify-center items-center text-center">
          <Icon className={cn("h-5 w-5 mb-1", style.text)} />
          <p
            className={cn(
              "text-xs font-medium capitalize leading-tight",
              style.text
            )}
          >
            {dayType.replace("_", " ")}
          </p>
          {dayType === "travail" && (
            <div className="text-xs mt-2 text-muted-foreground">
              <p>
                Prévu: <strong>{dayData.heures_prevues ?? 0}h</strong>
              </p>
              <p>
                Fait: <strong>{actualData?.heures_faites ?? 0}h</strong>
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
