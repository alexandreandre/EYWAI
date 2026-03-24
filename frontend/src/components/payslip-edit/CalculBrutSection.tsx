// frontend/src/components/payslip-edit/CalculBrutSection.tsx

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { PlusCircle, Trash2, DollarSign, Calculator } from 'lucide-react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

interface CalculBrutSectionProps {
  data: any[];
  salaireBrut: number;
  onChange: (data: any[], newBrut: number) => void;
}

export default function CalculBrutSection({ data, salaireBrut, onChange }: CalculBrutSectionProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);

  // Fonction pour recalculer le total brut
  const recalculateBrut = (lines: any[]) => {
    let total = 0;
    lines.forEach((ligne) => {
      if (!ligne.is_sous_total) {
        const gain = ligne.gain || 0;
        const perte = ligne.perte || 0;
        total += gain - perte;
      }
    });
    return total;
  };

  // Ajouter une nouvelle ligne
  const handleAddLine = () => {
    const newLine = {
      libelle: 'Nouvelle ligne',
      quantite: 0,
      taux: 0,
      gain: 0,
      perte: 0,
      is_sous_total: false,
    };
    const newData = [...data, newLine];
    const newBrut = recalculateBrut(newData);
    onChange(newData, newBrut);
  };

  // Supprimer une ligne
  const handleDeleteLine = (index: number) => {
    const newData = data.filter((_, i) => i !== index);
    const newBrut = recalculateBrut(newData);
    onChange(newData, newBrut);
  };

  // Modifier une ligne
  const handleLineChange = (index: number, field: string, value: any) => {
    const newData = [...data];
    newData[index] = { ...newData[index], [field]: value };

    // Recalculer le montant si quantité ou taux change
    if (field === 'quantite' || field === 'taux') {
      const quantite = parseFloat(newData[index].quantite) || 0;
      const taux = parseFloat(newData[index].taux) || 0;
      newData[index].gain = quantite * taux;
    }

    const newBrut = recalculateBrut(newData);
    onChange(newData, newBrut);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <DollarSign className="h-5 w-5" />
          Calcul du Brut
        </CardTitle>
        <CardDescription>
          Modifiez les lignes de calcul du salaire brut
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="border rounded-lg overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Libellé</TableHead>
                <TableHead className="text-right">Base/Qté</TableHead>
                <TableHead className="text-right">Taux</TableHead>
                <TableHead className="text-right">Gains (€)</TableHead>
                <TableHead className="text-right">Retenues (€)</TableHead>
                <TableHead className="w-[100px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((ligne, index) => (
                <TableRow key={index} className={ligne.is_sous_total ? 'bg-muted font-medium' : ''}>
                  <TableCell>
                    {editingIndex === index ? (
                      <Input
                        value={ligne.libelle}
                        onChange={(e) => handleLineChange(index, 'libelle', e.target.value)}
                        className="h-8"
                      />
                    ) : (
                      <span onClick={() => setEditingIndex(index)} className="cursor-pointer hover:underline">
                        {ligne.libelle}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {!ligne.is_sous_total && editingIndex === index ? (
                      <Input
                        type="number"
                        step="0.01"
                        value={ligne.quantite || ''}
                        onChange={(e) => handleLineChange(index, 'quantite', parseFloat(e.target.value) || 0)}
                        className="h-8 w-24 text-right"
                      />
                    ) : (
                      <span onClick={() => setEditingIndex(index)} className="cursor-pointer hover:underline">
                        {ligne.quantite?.toFixed(2) || ''}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {!ligne.is_sous_total && editingIndex === index ? (
                      <Input
                        type="number"
                        step="0.0001"
                        value={ligne.taux || ''}
                        onChange={(e) => handleLineChange(index, 'taux', parseFloat(e.target.value) || 0)}
                        className="h-8 w-24 text-right"
                      />
                    ) : (
                      <span onClick={() => setEditingIndex(index)} className="cursor-pointer hover:underline">
                        {ligne.taux?.toFixed(4) || ''}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {editingIndex === index && !ligne.is_sous_total ? (
                      <Input
                        type="number"
                        step="0.01"
                        value={ligne.gain || ''}
                        onChange={(e) => handleLineChange(index, 'gain', parseFloat(e.target.value) || 0)}
                        className="h-8 w-24 text-right"
                      />
                    ) : (
                      <span onClick={() => setEditingIndex(index)} className="cursor-pointer hover:underline">
                        {ligne.gain?.toFixed(2) || ''}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {editingIndex === index && !ligne.is_sous_total ? (
                      <Input
                        type="number"
                        step="0.01"
                        value={ligne.perte || ''}
                        onChange={(e) => handleLineChange(index, 'perte', parseFloat(e.target.value) || 0)}
                        className="h-8 w-24 text-right"
                      />
                    ) : (
                      <span onClick={() => setEditingIndex(index)} className="cursor-pointer hover:underline">
                        {ligne.perte?.toFixed(2) || ''}
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    {!ligne.is_sous_total && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteLine(index)}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        <div className="flex items-center justify-between pt-4 border-t">
          <Button onClick={handleAddLine} variant="outline">
            <PlusCircle className="h-4 w-4 mr-2" />
            Ajouter une ligne
          </Button>

          <div className="flex items-center gap-2">
            <Calculator className="h-5 w-5 text-muted-foreground" />
            <span className="text-lg font-bold">
              Total Brut: {salaireBrut?.toFixed(2)} €
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
