// src/components/ScheduleModal.tsx

import { useState, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

// Interface pour les données que le modal reçoit
export interface DayData {
  jour: number;
  type: string;
  heures_prevues: number | null;
  heures_faites: number | null;
}

// Interface pour les props du composant
interface ScheduleModalProps {
  isOpen: boolean;
  onClose: () => void;
  dayData: DayData | null;
  onSave: (updatedDay: DayData) => void;
  selectedDate: { month: number; year: number };
}

export function ScheduleModal({ isOpen, onClose, dayData, onSave, selectedDate }: ScheduleModalProps) {
  // État interne pour gérer les modifications dans le formulaire
  const [editableDay, setEditableDay] = useState<DayData | null>(dayData);

  // Mettre à jour l'état interne si le jour sélectionné change (quand on ouvre le modal)
  useEffect(() => {
    setEditableDay(dayData);
  }, [dayData]);

  const handleSave = () => {
    if (editableDay) {
        onClose(); // Fermer la modale avant de sauvegarder
        // AJOUTEZ CETTE LIGNE DE DÉBOGAGE
        console.log('[MODAL] Données envoyées au parent :', editableDay);
        onSave(editableDay);
    }
    };
  // Ne rien afficher si aucune donnée n'est sélectionnée
  if (!editableDay) {
    return null;
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-background/80 backdrop-blur-xl border-white/20">
        <DialogHeader>
          <DialogTitle>
            Édition du {editableDay.jour} {new Date(selectedDate.year, selectedDate.month - 1).toLocaleString('fr-FR', { month: 'long' })}
          </DialogTitle>
        </DialogHeader>
        
        <div className="space-y-6 py-4">
          {/* Section pour la Planification */}
          <fieldset className="border p-4 rounded-lg">
            <legend className="px-2 text-sm font-medium text-muted-foreground">Planification</legend>
            <div className="grid grid-cols-2 gap-4 items-center">
              <div>
                <Label>Type de journée</Label>
                <Select 
                  value={editableDay.type} 
                  onValueChange={(value) => {
                    const isWorkDay = value === 'travail';
                    setEditableDay(d => d ? { ...d, type: value, heures_prevues: isWorkDay ? d.heures_prevues || 8 : null } : null)
                  }}
                >
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="travail">Travail</SelectItem>
                    <SelectItem value="conge">Congé</SelectItem>
                    <SelectItem value="ferie">Férié</SelectItem>
                    <SelectItem value="weekend">Weekend</SelectItem>
                    <SelectItem value="arret_maladie">Arrêt Maladie</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Heures prévues</Label>
                <Input 
                  type="number" 
                  value={editableDay.heures_prevues ?? ''}
                  onChange={(e) => setEditableDay(d => d ? {...d, heures_prevues: e.target.value ? parseFloat(e.target.value) : null} : null)}
                  disabled={editableDay.type !== 'travail'}
                  placeholder={editableDay.type === 'travail' ? 'ex: 8' : 'N/A'}
                />
              </div>
            </div>
          </fieldset>

          {/* Section pour le Réel Effectué */}
          <fieldset className="border p-4 rounded-lg">
            <legend className="px-2 text-sm font-medium text-muted-foreground">Réel effectué</legend>
            <div>
              <Label>Heures faites</Label>
              <Input 
                type="number" 
                value={editableDay.heures_faites ?? ''}
                onChange={(e) => setEditableDay(d => d ? {...d, heures_faites: e.target.value ? parseFloat(e.target.value) : null} : null)}
                placeholder="ex: 7.5"
              />
            </div>
          </fieldset>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose}>Annuler</Button>
          <Button onClick={handleSave}>Appliquer</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}