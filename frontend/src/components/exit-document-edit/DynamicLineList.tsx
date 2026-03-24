// frontend/src/components/exit-document-edit/DynamicLineList.tsx

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent } from '@/components/ui/card';
import { Plus, Trash2 } from 'lucide-react';
import { Separator } from '@/components/ui/separator';

export interface LineField {
  key: string;
  label: string;
  type?: 'text' | 'number' | 'date' | 'textarea';
  placeholder?: string;
  required?: boolean;
}

interface DynamicLineListProps {
  title: string;
  description?: string;
  category: string; // Chemin dans les données (ex: 'indemnities.custom_lines')
  fields: LineField[]; // Champs pour chaque ligne
  data: any;
  onChange: (newData: any) => void;
  emptyMessage?: string;
}

export default function DynamicLineList({
  title,
  description,
  category,
  fields,
  data,
  onChange,
  emptyMessage = "Aucune ligne ajoutée",
}: DynamicLineListProps) {
  // Récupérer les lignes depuis le chemin de catégorie
  const getLines = (): any[] => {
    const parts = category.split('.');
    let current = data;
    for (const part of parts) {
      if (!current || typeof current !== 'object') return [];
      current = current[part];
    }
    return Array.isArray(current) ? current : [];
  };

  // Mettre à jour les lignes
  const setLines = (newLines: any[]) => {
    const newData = JSON.parse(JSON.stringify(data));
    const parts = category.split('.');
    let current = newData;
    
    // Créer le chemin si nécessaire
    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]]) {
        current[parts[i]] = {};
      }
      current = current[parts[i]];
    }
    
    current[parts[parts.length - 1]] = newLines;
    onChange(newData);
  };

  const lines = getLines();

  const addLine = () => {
    const newLine: any = {};
    fields.forEach(field => {
      newLine[field.key] = field.type === 'number' ? 0 : '';
    });
    setLines([...lines, newLine]);
  };

  const removeLine = (index: number) => {
    const newLines = lines.filter((_, i) => i !== index);
    setLines(newLines);
  };

  const updateLineField = (index: number, fieldKey: string, value: any) => {
    const newLines = [...lines];
    if (!newLines[index]) {
      newLines[index] = {};
    }
    newLines[index][fieldKey] = value;
    setLines(newLines);
  };

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="font-semibold text-lg">{title}</h3>
            {description && (
              <p className="text-sm text-muted-foreground mt-1">{description}</p>
            )}
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addLine}
            className="flex items-center gap-2"
          >
            <Plus className="h-4 w-4" />
            Ajouter une ligne
          </Button>
        </div>

        {lines.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground text-sm">
            {emptyMessage}
          </div>
        ) : (
          <div className="space-y-4">
            {lines.map((line, index) => (
              <div key={index}>
                <Card className="bg-slate-50">
                  <CardContent className="pt-4">
                    <div className="flex items-center justify-between mb-4">
                      <span className="text-sm font-medium text-slate-600">
                        Ligne {index + 1}
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeLine(index)}
                        className="text-red-600 hover:text-red-700 hover:bg-red-50"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {fields.map((field) => {
                        const fieldValue = line[field.key] || '';
                        const isTextarea = field.type === 'textarea';
                        const colSpan = isTextarea ? 'md:col-span-2 lg:col-span-3' : '';

                        return (
                          <div key={field.key} className={colSpan}>
                            <Label htmlFor={`${category}-${index}-${field.key}`}>
                              {field.label}
                              {field.required && <span className="text-red-500 ml-1">*</span>}
                            </Label>
                            {isTextarea ? (
                              <textarea
                                id={`${category}-${index}-${field.key}`}
                                value={fieldValue}
                                onChange={(e) => updateLineField(index, field.key, e.target.value)}
                                placeholder={field.placeholder}
                                className="mt-2 flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                rows={3}
                              />
                            ) : (
                              <Input
                                id={`${category}-${index}-${field.key}`}
                                type={field.type || 'text'}
                                value={fieldValue}
                                onChange={(e) => {
                                  const value = field.type === 'number'
                                    ? parseFloat(e.target.value) || 0
                                    : e.target.value;
                                  updateLineField(index, field.key, value);
                                }}
                                placeholder={field.placeholder}
                                step={field.type === 'number' ? '0.01' : undefined}
                                className="mt-2"
                              />
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
                {index < lines.length - 1 && <Separator className="my-4" />}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

