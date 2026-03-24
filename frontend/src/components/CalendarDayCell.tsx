// src/components/CalendarDayCell.tsx

import { DayCellContentArg } from '@fullcalendar/core';
import { PlannedEventData, ActualHoursData } from '@/api/calendar';
import { DayData } from '@/components/ScheduleModal';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Calendar, Clock } from 'lucide-react';
import { Checkbox } from "@/components/ui/checkbox";

interface CalendarDayCellProps {
  arg: DayCellContentArg;
  plannedCalendar: PlannedEventData[];
  actualHours: ActualHoursData[];
  updateDayData: (day: Partial<DayData>) => void;
  // --- NOUVELLES PROPS POUR LA SÉLECTION ---
  selectedDays?: number[];
  onDaySelect?: (dayNumber: number, isCtrlOrMetaKey: boolean) => void;
  selectedDate: { month: number; year: number };
  // --- PROP POUR LE MODE FORFAIT JOUR ---
  isForfaitJour?: boolean;
}

const typeColors: { [key: string]: string } = {
  travail: "bg-transparent text-foreground",
  conge: "bg-blue-100 text-blue-800",
  ferie: "bg-purple-100 text-purple-800",
  arret_maladie: "bg-amber-100 text-amber-800",
  weekend: "bg-gray-100 text-gray-500",
};

export function CalendarDayCell({ arg, plannedCalendar, actualHours, updateDayData, selectedDays = [], onDaySelect, selectedDate, isForfaitJour = false }: CalendarDayCellProps) {
  const dayNumber = arg.date.getDate();

  const plannedDay = plannedCalendar.find(d => d.jour === dayNumber);
  const actualDay = actualHours.find(d => d.jour === dayNumber);

  // Vérifie si le jour de la cellule appartient au mois actuellement sélectionné.
  const isCurrentMonth = arg.date.getMonth() + 1 === selectedDate.month && arg.date.getFullYear() === selectedDate.year;

  const isSelected = isCurrentMonth && selectedDays.includes(dayNumber);

  // Pour les jours hors du mois courant, on affiche juste le numéro grisé.
  if (!isCurrentMonth) {
    return (
      <div className="flex h-full items-start justify-start p-2">
        <span className="text-muted-foreground/30">{arg.dayNumberText}</span>
      </div>);
  }

  const handleTypeChange = (newType: string) => {
    // Si le jour n'existe pas encore dans le calendrier, on le crée
    const currentPlanned = plannedCalendar.find(d => d.jour === dayNumber);
    const currentActual = actualHours.find(d => d.jour === dayNumber);
    if (!currentPlanned || !currentActual) {
      // On peut initialiser avec des valeurs par défaut si besoin
    }

    const isWorkDay = newType === 'travail';
    // Pour le mode forfait jour : 1 = jour travaillé, sinon 0
    // Pour le mode normal : valeur par défaut 8 heures ou valeur existante
    const defaultHours = isForfaitJour 
      ? (isWorkDay ? 1 : 0)
      : (isWorkDay ? (plannedDay.heures_prevues ?? 8) : null);
    
    updateDayData({
      jour: dayNumber,
      type: newType,
      heures_prevues: defaultHours,
    });
  };

  const handlePlannedHoursChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    updateDayData({
      jour: dayNumber,
      heures_prevues: value ? parseFloat(value) : null,
    });
  };

  const handleForfaitJourPrevuChange = (checked: boolean) => {
    // Pour le mode forfait jour : 1 = jour prévu, 0 = jour non prévu
    updateDayData({
      jour: dayNumber,
      heures_prevues: checked ? 1 : 0,
    });
  };

  const handleForfaitJourFaitChange = (checked: boolean) => {
    // Pour le mode forfait jour : 1 = jour travaillé, 0 = jour non travaillé
    updateDayData({
      jour: dayNumber,
      heures_faites: checked ? 1 : 0,
    });
  };

  const handleActualHoursChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    updateDayData({
      jour: dayNumber,
      heures_faites: value ? parseFloat(value) : null,
    });
  };

  const isToday = arg.isToday;

  // Si les données ne sont pas chargées pour ce jour (cas improbable mais sécuritaire)
  if (!plannedDay || !actualDay) {
    return (
      <div className="flex h-full items-start justify-start p-2">
        <span className="text-muted-foreground">{arg.dayNumberText}</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-col h-full w-full p-2 rounded-2xl border bg-gradient-to-br from-white/90 to-slate-50/70 dark:from-slate-900/60 dark:to-slate-800/60",
        "hover:shadow-md hover:scale-[1.01] transition-all duration-200"
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <div className={cn(
          "font-semibold text-xs rounded-full h-6 w-6 flex items-center justify-center",
          isToday ? "bg-primary text-white shadow-sm" : "text-muted-foreground"
        )}>

          {arg.dayNumberText}
        </div>
        <Select value={plannedDay.type} onValueChange={handleTypeChange}>
            <SelectTrigger className="h-6 text-xs focus:ring-0 focus:ring-offset-0 border-0 bg-transparent hover:bg-muted/50 rounded-md w-auto p-0">
              <SelectValue asChild>
                <Badge variant="outline" className={cn("text-xs font-normal border-0", typeColors[plannedDay.type])}>
                  {plannedDay.type === 'travail' ? 'Travail' : plannedDay.type === 'conge' ? 'Congé' : plannedDay.type === 'ferie' ? 'Férié' : plannedDay.type === 'arret_maladie' ? 'Arrêt' : 'Weekend'}
                </Badge>
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="travail">Travail</SelectItem>
              <SelectItem value="conge">Congé</SelectItem>
              <SelectItem value="ferie">Férié</SelectItem>
              <SelectItem value="arret_maladie">Arrêt Maladie</SelectItem>
              <SelectItem value="weekend">Weekend</SelectItem>
            </SelectContent>
          </Select>
      </div>

      <div className="flex-grow flex flex-col justify-end gap-1.5 mt-1">
        {/* Champ "heures prévues" ou "Jour prévu" selon le mode */}
        {isForfaitJour ? (
          // Mode forfait jour : Checkbox pour jour prévu (0/1)
          <div className="relative flex items-center gap-2 group/input">
            <Calendar className="h-3 w-3 text-muted-foreground group-hover/input:text-primary" />
            <div className="flex items-center gap-2 flex-1">
              <Checkbox
                id={`planned-${dayNumber}`}
                checked={plannedDay.heures_prevues === 1}
                onCheckedChange={handleForfaitJourPrevuChange}
                disabled={plannedDay.type !== 'travail'}
                className="h-4 w-4"
              />
              <label 
                htmlFor={`planned-${dayNumber}`}
                className={cn(
                  "text-xs cursor-pointer",
                  plannedDay.type !== 'travail' && "opacity-40 cursor-not-allowed"
                )}
              >
                Jour prévu
              </label>
            </div>
          </div>
        ) : (
          // Mode normal : Input numérique pour les heures
          <div className="relative flex items-center group/input">
            <Calendar className="absolute left-1 h-3 w-3 text-muted-foreground group-hover/input:text-primary" />
            <Input id={`planned-${dayNumber}`} type="number" placeholder="–" value={plannedDay.heures_prevues ?? ''} onChange={handlePlannedHoursChange} disabled={plannedDay.type !== 'travail'} 
              className="h-7 text-xs p-1 pl-5 bg-transparent border-0 rounded-md focus-visible:ring-1 focus-visible:ring-primary/50 focus-visible:ring-offset-0 disabled:opacity-40 disabled:cursor-not-allowed" 
            />
          </div>
        )}

        {/* Champ "heures faites" ou "Jour travaillé" selon le mode */}
        {isForfaitJour ? (
          // Mode forfait jour : Checkbox pour jour travaillé (0/1)
          <div className="relative flex items-center gap-2 group/input">
            <Clock className="h-3 w-3 text-muted-foreground group-hover/input:text-teal-500" />
            <div className="flex items-center gap-2 flex-1">
              <Checkbox
                id={`actual-${dayNumber}`}
                checked={actualDay.heures_faites === 1}
                onCheckedChange={handleForfaitJourFaitChange}
                className="h-4 w-4"
              />
              <label 
                htmlFor={`actual-${dayNumber}`}
                className="text-xs cursor-pointer"
              >
                Jour travaillé
              </label>
            </div>
          </div>
        ) : (
          // Mode normal : Input numérique pour les heures
          <div className="relative flex items-center group/input">
            <Clock className="absolute left-1 h-3 w-3 text-muted-foreground group-hover/input:text-teal-500" />
            <Input id={`actual-${dayNumber}`} type="number" placeholder="–" value={actualDay.heures_faites ?? ''} onChange={handleActualHoursChange} 
              className="h-7 text-xs p-1 pl-5 bg-teal-500/5 border-0 rounded-md focus-visible:bg-background focus-visible:ring-1 focus-visible:ring-teal-500 focus-visible:ring-offset-0" 
            />
          </div>
        )}
      </div>

      <div className="flex justify-end pt-1">
        <Checkbox
          checked={isSelected}
          onCheckedChange={() => onDaySelect?.(dayNumber, false)}
          aria-label={`Sélectionner le jour ${dayNumber}`}
          className="h-4 w-4"
        />
      </div>
    </div>
  );
}