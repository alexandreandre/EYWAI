import { useEffect, useState } from "react";
import { ArrowRight, Copy, Loader2, Save } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
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
import { toast } from "@/components/ui/use-toast";
import { WeekTemplate } from "@/hooks/useCalendar";
import {
  loadSavedWeekTemplates,
  saveWeekTemplate,
  type SavedWeekTemplate,
} from "@/lib/weekTemplateStorage";

interface WeekTemplateFormProps {
  template: WeekTemplate;
  setTemplate: React.Dispatch<React.SetStateAction<WeekTemplate>>;
  onApply: () => void;
  onApplyAndSave: () => void;
  onCopyPreviousMonth: () => void;
  isSaving: boolean;
  isCopyingPrevMonth?: boolean;
  isForfaitJour?: boolean;
  companyId: string;
  daysInMonth: number;
}

export function WeekTemplateForm({
  template,
  setTemplate,
  onApply,
  onApplyAndSave,
  onCopyPreviousMonth,
  isSaving,
  isCopyingPrevMonth = false,
  isForfaitJour = false,
  companyId,
  daysInMonth,
}: WeekTemplateFormProps) {
  const [savedTemplates, setSavedTemplates] = useState<SavedWeekTemplate[]>(() =>
    loadSavedWeekTemplates(companyId)
  );
  const [saveTemplateName, setSaveTemplateName] = useState("");

  useEffect(() => {
    setSavedTemplates(loadSavedWeekTemplates(companyId));
  }, [companyId]);
  const days = [
    { label: 'Lundi', key: 1 }, { label: 'Mardi', key: 2 }, { label: 'Mercredi', key: 3 },
    { label: 'Jeudi', key: 4 }, { label: 'Vendredi', key: 5 },
  ];

  const handleInputChange = (dayKey: number, value: string) => {
    setTemplate(prev => ({ ...prev, [dayKey]: value }));
  };

  const handleCheckboxChange = (dayKey: number, checked: boolean) => {
    // Pour le mode forfait jour : convertir le booléen en string "1" ou "0"
    setTemplate(prev => ({ ...prev, [dayKey]: checked ? '1' : '0' }));
  };

  return (
    <Card className="mb-4 bg-muted/40">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Modèle de semaine type</CardTitle>
        <CardDescription className="text-xs">
          {isForfaitJour 
            ? "Cochez les jours prévus, puis appliquez-les à tout le mois."
            : "Définissez les heures prévues, puis appliquez-les à tout le mois."}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col md:flex-row items-center gap-4">
        <div className="grid grid-cols-5 gap-3 flex-grow">
          {days.map(day => (
            <div key={day.key} className="grid gap-1.5">
              <Label htmlFor={`template-day-${day.key}`} className="text-xs">{day.label}</Label>
              {isForfaitJour ? (
                // Mode forfait jour : Checkbox pour jour travaillé
                <div className="flex items-center gap-2 h-9 px-3 border rounded-md bg-background">
                  <Checkbox
                    id={`template-day-${day.key}`}
                    checked={template[day.key] === '1'}
                    onCheckedChange={(checked) => handleCheckboxChange(day.key, checked === true)}
                    className="h-4 w-4"
                  />
                  <label 
                    htmlFor={`template-day-${day.key}`}
                    className="text-xs cursor-pointer flex-1"
                  >
                    Jour prévu
                  </label>
                </div>
              ) : (
                // Mode normal : Input numérique pour les heures
                <Input
                  id={`template-day-${day.key}`} 
                  type="number" 
                  placeholder="h"
                  value={template[day.key] || ''}
                  onChange={(e) => handleInputChange(day.key, e.target.value)}
                  className="h-9"
                />
              )}
            </div>
          ))}
        </div>
        
        <div className="flex flex-col gap-2 w-full md:w-auto mt-4 md:mt-0">
          <Button onClick={onApply} disabled={isSaving} className="w-full">
            <ArrowRight className="mr-2 h-4 w-4" />
            Appliquer au mois
          </Button>
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="outline" disabled={isSaving} className="w-full">
                {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Save className="mr-2 h-4 w-4" />}
                Appliquer et enregistrer
              </Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Appliquer le modèle et enregistrer ?</AlertDialogTitle>
                <AlertDialogDescription>
                  Cela écrasera les valeurs prévues des jours ouvrés du mois ({daysInMonth} jours)
                  et lancera immédiatement l&apos;enregistrement et le calcul paie.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>Annuler</AlertDialogCancel>
                <AlertDialogAction onClick={onApplyAndSave}>Confirmer</AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
          <Button
            variant="secondary"
            onClick={onCopyPreviousMonth}
            disabled={isSaving || isCopyingPrevMonth}
            className="w-full"
          >
            {isCopyingPrevMonth ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Copy className="mr-2 h-4 w-4" />
            )}
            Copier le mois précédent
          </Button>
        </div>
      </CardContent>
      <CardContent className="pt-0 border-t">
        <div className="flex flex-wrap items-end gap-2">
          {savedTemplates.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {savedTemplates.map((st) => (
                <Button
                  key={st.name}
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-8 text-xs"
                  onClick={() => setTemplate(st.template)}
                >
                  {st.name}
                </Button>
              ))}
            </div>
          )}
          <Input
            className="h-8 w-36 text-xs"
            placeholder="Nom du modèle"
            value={saveTemplateName}
            onChange={(e) => setSaveTemplateName(e.target.value)}
          />
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-8 text-xs"
            disabled={!saveTemplateName.trim()}
            onClick={() => {
              setSavedTemplates(saveWeekTemplate(companyId, saveTemplateName, template));
              setSaveTemplateName("");
              toast({ title: "Modèle enregistré", description: "Jusqu'à 3 modèles par société." });
            }}
          >
            Mémoriser
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
