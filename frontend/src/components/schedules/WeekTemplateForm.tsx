import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Loader2, Save, ArrowRight } from 'lucide-react';
import type { WeekTemplate } from '@/hooks/useCalendar';

interface WeekTemplateFormProps {
  template: WeekTemplate;
  setTemplate: React.Dispatch<React.SetStateAction<WeekTemplate>>;
  onApply: () => void;
  onApplyAndSave: () => void;
  isSaving: boolean;
  isForfaitJour?: boolean;
}

export function WeekTemplateForm({
  template,
  setTemplate,
  onApply,
  onApplyAndSave,
  isSaving,
  isForfaitJour = false,
}: WeekTemplateFormProps) {
  const days = [
    { label: 'Lundi', key: 1 },
    { label: 'Mardi', key: 2 },
    { label: 'Mercredi', key: 3 },
    { label: 'Jeudi', key: 4 },
    { label: 'Vendredi', key: 5 },
  ];

  const handleInputChange = (dayKey: number, value: string) => {
    setTemplate((prev) => ({ ...prev, [dayKey]: value }));
  };

  const handleCheckboxChange = (dayKey: number, checked: boolean) => {
    setTemplate((prev) => ({ ...prev, [dayKey]: checked ? '1' : '0' }));
  };

  return (
    <Card className="mb-4 bg-muted/40">
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Modèle de semaine type</CardTitle>
        <CardDescription className="text-xs">
          {isForfaitJour
            ? 'Cochez les jours prévus, puis appliquez-les à tout le mois.'
            : 'Définissez les heures prévues, puis appliquez-les à tout le mois.'}
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col md:flex-row items-center gap-4">
        <div className="grid grid-cols-5 gap-3 flex-grow">
          {days.map((day) => (
            <div key={day.key} className="grid gap-1.5">
              <Label htmlFor={`template-day-${day.key}`} className="text-xs">
                {day.label}
              </Label>
              {isForfaitJour ? (
                <div className="flex items-center gap-2 h-9 px-3 border rounded-md bg-background">
                  <Checkbox
                    id={`template-day-${day.key}`}
                    checked={template[day.key] === '1'}
                    onCheckedChange={(checked) =>
                      handleCheckboxChange(day.key, checked === true)
                    }
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

        <Button
          onClick={onApplyAndSave}
          disabled={isSaving}
          className="w-full md:w-auto mt-4 md:mt-0"
        >
          {isSaving ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <Save className="mr-2 h-4 w-4" />
          )}
          Appliquer et enregistrer
        </Button>
        <Button
          onClick={onApply}
          disabled={isSaving}
          variant="outline"
          className="w-full md:w-auto mt-4 md:mt-0"
        >
          <ArrowRight className="mr-2 h-4 w-4" />
          Appliquer au mois
        </Button>
      </CardContent>
    </Card>
  );
}
