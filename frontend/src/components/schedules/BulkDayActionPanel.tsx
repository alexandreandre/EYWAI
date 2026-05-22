import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Loader2, Save } from 'lucide-react';
import type { DayData } from '@/components/ScheduleModal';

interface BulkDayActionPanelProps {
  selectedCount: number;
  onBulkUpdate: (data: Partial<Omit<DayData, 'jour'>>) => void;
  updateSelection: (mode: 'all' | 'weekdays' | 'none') => void;
  onBulkUpdateAndSave: (data: Partial<Omit<DayData, 'jour'>>) => void;
  isSaving: boolean;
  isForfaitJour: boolean;
}

export function BulkDayActionPanel({
  selectedCount,
  onBulkUpdate,
  updateSelection,
  onBulkUpdateAndSave,
  isSaving,
  isForfaitJour,
}: BulkDayActionPanelProps) {
  const [type, setType] = useState('');
  const [plannedHours, setPlannedHours] = useState('');
  const [actualHours, setActualHours] = useState('');
  const [actualHoursForfaitJour, setActualHoursForfaitJour] = useState('');

  const buildUpdateDataAndCall = (
    callback: (data: Partial<Omit<DayData, 'jour'>>) => void
  ) => {
    const updateData: Partial<Omit<DayData, 'jour'>> = {};
    let hasUpdate = false;

    if (type) {
      updateData.type = type;
      if (type !== 'travail') updateData.heures_prevues = null;
      hasUpdate = true;
    }

    if (isForfaitJour) {
      const parsedPlanned =
        plannedHours.trim() !== '' ? parseFloat(plannedHours) : NaN;
      if (!isNaN(parsedPlanned)) {
        updateData.heures_prevues = parsedPlanned > 0 ? 1 : 0;
        if (type === '' && parsedPlanned > 0) updateData.type = 'travail';
        hasUpdate = true;
      }
      const parsedActual =
        actualHoursForfaitJour.trim() !== ''
          ? parseFloat(actualHoursForfaitJour)
          : NaN;
      if (!isNaN(parsedActual)) {
        updateData.heures_faites = parsedActual > 0 ? 1 : 0;
        if (type === '' && parsedActual > 0 && !updateData.type) {
          updateData.type = 'travail';
        }
        hasUpdate = true;
      }
    } else {
      const parsedPlanned = parseFloat(plannedHours);
      if (!isNaN(parsedPlanned)) {
        updateData.heures_prevues = parsedPlanned;
        if (type === '' && parsedPlanned > 0) updateData.type = 'travail';
        hasUpdate = true;
      }
      const parsedActual = parseFloat(actualHours);
      if (!isNaN(parsedActual)) {
        updateData.heures_faites = parsedActual;
        if (type === '' && parsedActual > 0 && !updateData.type) {
          updateData.type = 'travail';
        }
        hasUpdate = true;
      }
    }

    if (hasUpdate) callback(updateData);
  };

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-[60] bg-card p-3 border rounded-lg shadow-2xl flex flex-wrap items-center gap-3 max-w-[95vw]">
      <div className="flex flex-col pr-3 border-r">
        <p className="text-sm font-medium">{selectedCount} jours sélectionnés</p>
        <div className="flex items-center gap-1.5 mt-1">
          <Button
            variant="link"
            size="sm"
            className="h-auto p-0 text-xs"
            onClick={() => updateSelection('all')}
          >
            Tout
          </Button>
          <span className="text-xs text-muted-foreground">|</span>
          <Button
            variant="link"
            size="sm"
            className="h-auto p-0 text-xs"
            onClick={() => updateSelection('weekdays')}
          >
            Ouvrés
          </Button>
          <span className="text-xs text-muted-foreground">|</span>
          <Button
            variant="link"
            size="sm"
            className="h-auto p-0 text-xs text-destructive"
            onClick={() => updateSelection('none')}
          >
            Désélectionner
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Label className="text-xs">Type</Label>
        <Select value={type} onValueChange={setType} disabled={isSaving}>
          <SelectTrigger className="h-8 w-[120px] text-xs">
            <SelectValue placeholder="Type…" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="travail">Travail</SelectItem>
            <SelectItem value="conge">Congé</SelectItem>
            <SelectItem value="ferie">Férié</SelectItem>
            <SelectItem value="arret_maladie">Arrêt</SelectItem>
            <SelectItem value="weekend">Week-end</SelectItem>
          </SelectContent>
        </Select>
        {isForfaitJour ? (
          <>
            <Select value={plannedHours} onValueChange={setPlannedHours} disabled={isSaving}>
              <SelectTrigger className="h-8 w-[110px] text-xs">
                <SelectValue placeholder="Prévu" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1">Jour prévu</SelectItem>
                <SelectItem value="0">Non prévu</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={actualHoursForfaitJour}
              onValueChange={setActualHoursForfaitJour}
              disabled={isSaving}
            >
              <SelectTrigger className="h-8 w-[110px] text-xs">
                <SelectValue placeholder="Réel" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="1">Travaillé</SelectItem>
                <SelectItem value="0">Non travaillé</SelectItem>
              </SelectContent>
            </Select>
          </>
        ) : (
          <>
            <Input
              type="number"
              value={plannedHours}
              onChange={(e) => setPlannedHours(e.target.value)}
              placeholder="H. prév."
              className="h-8 w-20 text-xs"
              disabled={isSaving}
            />
            <Input
              type="number"
              value={actualHours}
              onChange={(e) => setActualHours(e.target.value)}
              placeholder="H. faites"
              className="h-8 w-20 text-xs"
              disabled={isSaving}
            />
          </>
        )}
      </div>

      <Button
        size="sm"
        onClick={() => buildUpdateDataAndCall(onBulkUpdateAndSave)}
        disabled={isSaving}
      >
        {isSaving ? (
          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
        ) : (
          <Save className="mr-2 h-4 w-4" />
        )}
        Appliquer et enregistrer
      </Button>
      <Button
        size="sm"
        variant="outline"
        onClick={() => buildUpdateDataAndCall(onBulkUpdate)}
        disabled={isSaving}
      >
        Appliquer
      </Button>
    </div>
  );
}
