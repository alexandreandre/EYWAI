// frontend/src/components/payslip-edit/NotesDeFraisSection.tsx

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Receipt, Plus, Trash2 } from 'lucide-react';

interface NotesDeFraisSectionProps {
  data: any[];
  onChange: (data: any[]) => void;
}

export default function NotesDeFraisSection({ data, onChange }: NotesDeFraisSectionProps) {
  const formatCurrency = (amount: number | undefined | null): string => {
    if (amount == null) return 'N/A';
    return amount.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
  };

  const handleNoteDeFraisChange = (index: number, field: string, value: any) => {
    const newData = [...data];
    newData[index] = { ...newData[index], [field]: value };
    onChange(newData);
  };

  const addNoteDeFrais = () => {
    const newNote = {
      libelle: 'Nouvelle note de frais',
      date: new Date().toISOString().split('T')[0], // Date du jour au format YYYY-MM-DD
      montant: 0,
      type: 'Déplacement'
    };
    onChange([...data, newNote]);
  };

  const removeNoteDeFrais = (index: number) => {
    const newData = data.filter((_, i) => i !== index);
    onChange(newData);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Receipt className="h-5 w-5" />
          Notes de Frais
        </CardTitle>
        <CardDescription>
          Remboursements de frais professionnels ({data?.length || 0})
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {data && data.length > 0 ? (
            data.map((note: any, idx: number) => (
              <div key={idx} className="p-3 border rounded-lg bg-blue-50/30">
                <div className="grid grid-cols-12 gap-2 items-center">
                  <div className="col-span-1 flex justify-center">
                    <Receipt className="h-4 w-4 text-blue-600" />
                  </div>
                  <div className="col-span-4">
                    <Input
                      placeholder="Libellé"
                      value={note.libelle || ''}
                      onChange={(e) => handleNoteDeFraisChange(idx, 'libelle', e.target.value)}
                      className="h-8"
                    />
                  </div>
                  <div className="col-span-2">
                    <Input
                      type="text"
                      placeholder="Type"
                      value={note.type || ''}
                      onChange={(e) => handleNoteDeFraisChange(idx, 'type', e.target.value)}
                      className="h-8"
                    />
                  </div>
                  <div className="col-span-2">
                    <Input
                      type="date"
                      value={note.date || ''}
                      onChange={(e) => handleNoteDeFraisChange(idx, 'date', e.target.value)}
                      className="h-8"
                    />
                  </div>
                  <div className="col-span-2">
                    <Input
                      type="number"
                      step="0.01"
                      placeholder="Montant"
                      value={note.montant || 0}
                      onChange={(e) => handleNoteDeFraisChange(idx, 'montant', parseFloat(e.target.value) || 0)}
                      className="h-8"
                    />
                  </div>
                  <div className="col-span-1 flex justify-end">
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => removeNoteDeFrais(idx)}
                      className="h-8 w-8 p-0"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              Aucune note de frais ce mois-ci
            </div>
          )}
        </div>

        <Button onClick={addNoteDeFrais} variant="outline" className="w-full mt-3">
          <Plus className="h-4 w-4 mr-2" />
          Ajouter une note de frais
        </Button>

        {data && data.length > 0 && (
          <div className="mt-4 pt-4 border-t">
            <div className="flex justify-between items-center">
              <span className="font-medium">Total Notes de Frais:</span>
              <span className="text-xl font-bold text-blue-600">
                + {formatCurrency(data.reduce((sum, n) => sum + (n.montant || 0), 0))}
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
