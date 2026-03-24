import React from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useCalendar } from "@/hooks/useCalendar";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Loader2, CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";
import { EmployeeCalendarDayCell } from "@/components/EmployeeCalendarDayCell";
import { Button } from "@/components/ui/button";

export default function EmployeeCalendarPage() {
  const { user } = useAuth();
  const {
    selectedDate,
    setSelectedDate,
    plannedCalendar,
    actualHours,
    isLoading: isCalendarLoading,
  } = useCalendar(user?.id);

  const year = selectedDate.year;
  const month = selectedDate.month - 1;

  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const daysInMonth = lastDay.getDate();
  const startDayOfWeek = (firstDay.getDay() + 6) % 7; // Lundi = 0

  const handlePreviousMonth = () => {
    const newDate = new Date(year, month - 1, 1);
    setSelectedDate({ month: newDate.getMonth() + 1, year: newDate.getFullYear() });
  };

  const handleNextMonth = () => {
    const newDate = new Date(year, month + 1, 1);
    setSelectedDate({ month: newDate.getMonth() + 1, year: newDate.getFullYear() });
  };

  const monthName = new Date(year, month).toLocaleString("fr-FR", {
    month: "long",
    year: "numeric",
  });

  const dayNames = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"];

  return (
    <div className="flex flex-col gap-6 mt-0 pt-0">
      <h1 className="text-3xl font-bold flex items-center gap-2">
        <CalendarDays className="h-7 w-7 text-primary" />
        Mon Calendrier
      </h1>

      <Card className="border-0 shadow-lg bg-gradient-to-br from-white/80 to-slate-50/60 dark:from-slate-900/60 dark:to-slate-800/60 backdrop-blur-md">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg md:text-xl font-semibold capitalize">
              {monthName}
            </CardTitle>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="icon"
                onClick={handlePreviousMonth}
                className="border-none hover:bg-accent/20 transition"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="icon"
                onClick={handleNextMonth}
                className="border-none hover:bg-accent/20 transition"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <CardDescription className="text-muted-foreground">
            Vue de votre planning prévisionnel et des heures réalisées
          </CardDescription>
        </CardHeader>

        <CardContent className="p-4 md:p-6">
          {isCalendarLoading ? (
            <div className="flex h-[400px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              {/* Noms des jours */}
              <div className="grid grid-cols-7 text-center text-sm font-medium text-muted-foreground">
                {dayNames.map((name) => (
                  <div key={name}>{name}</div>
                ))}
              </div>

              {/* Jours du mois */}
              <div className="grid grid-cols-7 gap-2 sm:gap-3">
                {/* Cases vides avant le 1er jour */}
                {Array.from({ length: startDayOfWeek }).map((_, i) => (
                  <div key={`empty-${i}`} className="aspect-square" />
                ))}

                {Array.from({ length: daysInMonth }).map((_, i) => {
                  const day = i + 1;
                  const date = new Date(year, month, day);
                  const isToday =
                    date.toDateString() === new Date().toDateString();

                  const arg = {
                    dayNumberText: String(day),
                    isToday,
                    isOther: false,
                  } as any;

                  return (
                    <div
                      key={day}
                      className="aspect-square rounded-2xl bg-white dark:bg-slate-900/40 shadow-sm hover:shadow-md transition-all"
                    >
                      <EmployeeCalendarDayCell
                        arg={arg}
                        plannedCalendar={plannedCalendar}
                        actualHours={actualHours}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
