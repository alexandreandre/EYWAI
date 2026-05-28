import { useState } from "react";
import { Copy, Loader2, Save } from "lucide-react";
import { DayData } from "@/components/ScheduleModal";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface BulkActionPanelProps {
  selectedCount: number;
  onBulkUpdate: (data: Partial<Omit<DayData, 'jour'>>) => void;
  updateSelection: (mode: 'all' | 'weekdays' | 'none') => void;
  onBulkUpdateAndSave: (data: Partial<Omit<DayData, 'jour'>>) => void;
  onBulkCopyPlannedToActual: () => void;
  isSaving: boolean;
  isForfaitJour?: boolean;
}

function buildBulkPreview(
  selectedCount: number,
  type: string,
  plannedHours: string,
  actualHours: string,
  actualHoursForfaitJour: string,
  isForfaitJour: boolean
): string {
  const parts: string[] = [`${selectedCount} jour${selectedCount > 1 ? 's' : ''}`];
  if (type) parts.push(`Type → ${type}`);
  if (isForfaitJour) {
    if (plannedHours) parts.push(`J. prévus → ${plannedHours === '1' ? 'oui' : 'non'}`);
    if (actualHoursForfaitJour)
      parts.push(`J. travaillés → ${actualHoursForfaitJour === '1' ? 'oui' : 'non'}`);
  } else {
    if (plannedHours) parts.push(`H. prévues → ${plannedHours}`);
    if (actualHours) parts.push(`H. faites → ${actualHours}`);
  }
  return parts.join(' • ');
}

export function BulkActionPanel({
  selectedCount,
  onBulkUpdate,
  updateSelection,
  onBulkUpdateAndSave,
  onBulkCopyPlannedToActual,
  isSaving,
  isForfaitJour = false,
}: BulkActionPanelProps) {
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
      hasUpdate = true;
    }

    if (isForfaitJour) {
      // Mode forfait jour : heures_prevues = 1 (jour prévu) ou 0 (jour non prévu)
      const parsedPlanned = plannedHours.trim() !== '' ? parseFloat(plannedHours) : NaN;
      if (!isNaN(parsedPlanned)) {
        updateData.heures_prevues = parsedPlanned > 0 ? 1 : 0;
        if (type === '' && parsedPlanned > 0) {
          updateData.type = 'travail';
        }
        hasUpdate = true;
      }
    } else {
      // Mode normal : nombre d'heures
      const parsedPlanned = parseFloat(plannedHours);
      if (!isNaN(parsedPlanned)) {
        updateData.heures_prevues = parsedPlanned;
        if (type === '' && parsedPlanned > 0) {
          updateData.type = 'travail';
        }
        hasUpdate = true;
      }
    }

    if (isForfaitJour) {
      // Mode forfait jour : heures_faites = 1 (jour travaillé) ou 0 (jour non travaillé)
      const parsedActual = actualHoursForfaitJour.trim() !== '' ? parseFloat(actualHoursForfaitJour) : NaN;
      if (!isNaN(parsedActual)) {
        updateData.heures_faites = parsedActual > 0 ? 1 : 0;
        if (type === '' && parsedActual > 0 && !updateData.type) {
          updateData.type = 'travail';
        }
        hasUpdate = true;
      }
    } else {
      // Mode normal : nombre d'heures
      const parsedActual = parseFloat(actualHours);
      if (!isNaN(parsedActual)) {
        updateData.heures_faites = parsedActual;
        if (type === '' && parsedActual > 0 && !updateData.type) {
          updateData.type = 'travail';
        }
        hasUpdate = true;
      }
    }

    if (hasUpdate) {
      callback(updateData);
    }
  };

  const preview = buildBulkPreview(
    selectedCount,
    type,
    plannedHours,
    actualHours,
    actualHoursForfaitJour,
    isForfaitJour
  );

  const hasFieldChanges =
    Boolean(type) ||
    (isForfaitJour ? Boolean(plannedHours || actualHoursForfaitJour) : Boolean(plannedHours || actualHours));

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-card p-3 border rounded-lg shadow-2xl flex flex-col gap-2 max-w-[95vw] animate-in fade-in-90 slide-in-from-bottom-10">
      <p className="text-xs text-muted-foreground px-1">{preview}</p>
      <div className="flex flex-wrap items-center gap-3">
      <div className="flex flex-col pr-4 border-r">
        <p className="text-sm font-medium">{selectedCount} jours sélectionnés</p>
        <div className="flex items-center gap-1.5 mt-1">
          <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => updateSelection('all')}>
            Tout
          </Button>
          <span className="text-xs text-muted-foreground">|</span>
          <Button variant="link" size="sm" className="h-auto p-0 text-xs" onClick={() => updateSelection('weekdays')}>
            Ouvrés
          </Button>
          <span className="text-xs text-muted-foreground">|</span>
          <Button variant="link" size="sm" className="h-auto p-0 text-xs text-destructive hover:text-destructive" onClick={() => updateSelection('none')}>
            Désélectionner
          </Button>
        </div>
      </div>
      {/* --- FIN DE LA MODIFICATION DE L'UI --- */}

      <div className="flex items-center gap-3">
        <Label htmlFor="bulk-type" className="text-xs">Marquer comme:</Label>
        <Select value={type} onValueChange={setType}>
          <SelectTrigger id="bulk-type" className="h-8 w-[130px] text-xs"><SelectValue placeholder="Type..." /></SelectTrigger>
          <SelectContent>
            <SelectItem value="travail">Travail</SelectItem>
            <SelectItem value="conge">Congé</SelectItem>
            <SelectItem value="ferie">Férié</SelectItem>
            <SelectItem value="arret_maladie">Arrêt Maladie</SelectItem>
          </SelectContent>
        </Select>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 text-xs"
          onClick={() => {
            setType("conge");
            setPlannedHours(isForfaitJour ? "0" : "0");
          }}
        >
          Tout congé
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-8 text-xs"
          onClick={() => {
            setType("travail");
            setPlannedHours(isForfaitJour ? "1" : "8");
          }}
        >
          {isForfaitJour ? "Tout travail" : "Travail 8 h"}
        </Button>
        <Label htmlFor="bulk-planned-hours" className="text-xs">
          {isForfaitJour ? "J. prévus:" : "H. prévues:"}
        </Label>
        {isForfaitJour ? (
          <Select
            value={plannedHours === '1' ? '1' : plannedHours === '0' ? '0' : ''}
            onValueChange={setPlannedHours}
          >
            <SelectTrigger id="bulk-planned-hours" className="h-8 w-[100px] text-xs">
              <SelectValue placeholder="–" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">Jour prévu</SelectItem>
              <SelectItem value="0">Jour non prévu</SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <Input id="bulk-planned-hours" type="number" value={plannedHours} onChange={e => setPlannedHours(e.target.value)} placeholder="ex: 8" className="h-8 w-20 text-xs" />
        )}
        <Label htmlFor="bulk-actual-hours" className="text-xs">
          {isForfaitJour ? "J. travaillés:" : "H. faites:"}
        </Label>
        {isForfaitJour ? (
          <Select
            value={actualHoursForfaitJour === '1' ? '1' : actualHoursForfaitJour === '0' ? '0' : ''}
            onValueChange={setActualHoursForfaitJour}
          >
            <SelectTrigger id="bulk-actual-hours" className="h-8 w-[100px] text-xs">
              <SelectValue placeholder="–" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">Jour travaillé</SelectItem>
              <SelectItem value="0">Jour non travaillé</SelectItem>
            </SelectContent>
          </Select>
        ) : (
          <Input id="bulk-actual-hours" type="number" value={actualHours} onChange={e => setActualHours(e.target.value)} placeholder="ex: 7.5" className="h-8 w-20 text-xs" />
        )}
      </div>

      <Button
        type="button"
        size="sm"
        variant="secondary"
        onClick={onBulkCopyPlannedToActual}
        disabled={isSaving}
      >
        <Copy className="mr-1 h-3.5 w-3.5" />
        Prévu → réel
      </Button>
      <Button
        size="sm"
        onClick={() => buildUpdateDataAndCall(onBulkUpdate)}
        disabled={isSaving || !hasFieldChanges}
      >
        Appliquer
      </Button>
      <AlertDialog>
        <AlertDialogTrigger asChild>
          <Button size="sm" variant="outline" disabled={isSaving || !hasFieldChanges}>
            {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
            Appliquer et enregistrer
          </Button>
        </AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Modifier {selectedCount} jours et enregistrer ?</AlertDialogTitle>
            <AlertDialogDescription>{preview}. L&apos;enregistrement lancera le calcul paie.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={() => buildUpdateDataAndCall(onBulkUpdateAndSave)}>
              Confirmer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      <Button size="sm" variant="ghost" onClick={() => updateSelection('none')} disabled={isSaving}>
        Annuler
      </Button>
      </div>
    </div>
  );
}
