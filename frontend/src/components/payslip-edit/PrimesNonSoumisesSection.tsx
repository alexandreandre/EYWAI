// frontend/src/components/payslip-edit/PrimesNonSoumisesSection.tsx

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Gift, Plus, Trash2 } from 'lucide-react';

interface PrimesNonSoumisesSectionProps {
  data: any[];
  onChange: (data: any[]) => void;
}

export default function PrimesNonSoumisesSection({ data, onChange }: PrimesNonSoumisesSectionProps) {
  const formatCurrency = (amount: number | undefined | null): string => {
    if (amount == null) return 'N/A';
    return amount.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
  };

  const handlePrimeChange = (index: number, field: string, value: any) => {
    const newData = [...data];
    newData[index] = { ...newData[index], [field]: value };
    onChange(newData);
  };

  const addPrime = () => {
    const newPrime = {
      libelle: 'Nouvelle prime non soumise',
      montant: 0
    };
    onChange([...data, newPrime]);
  };

  const removePrime = (index: number) => {
    const newData = data.filter((_, i) => i !== index);
    onChange(newData);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Gift className="h-5 w-5" />
          Primes Non Soumises
        </CardTitle>
        <CardDescription>
          Primes exonérées de cotisations et d'impôt ({data?.length || 0})
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {data && data.length > 0 ? (
            data.map((prime: any, idx: number) => (
              <div key={idx} className="p-3 border rounded-lg bg-green-50/30">
                <div className="grid grid-cols-12 gap-2 items-center">
                  <div className="col-span-1 flex justify-center">
                    <Gift className="h-4 w-4 text-green-600" />
                  </div>
                  <div className="col-span-7">
                    <Input
                      placeholder="Libellé de la prime"
                      value={prime.libelle || ''}
                      onChange={(e) => handlePrimeChange(idx, 'libelle', e.target.value)}
                      className="h-8"
                    />
                  </div>
                  <div className="col-span-3">
                    <Input
                      type="number"
                      step="0.01"
                      placeholder="Montant"
                      value={prime.montant || 0}
                      onChange={(e) => handlePrimeChange(idx, 'montant', parseFloat(e.target.value) || 0)}
                      className="h-8"
                    />
                  </div>
                  <div className="col-span-1 flex justify-end">
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => removePrime(idx)}
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
              Aucune prime non soumise ce mois-ci
            </div>
          )}
        </div>

        <Button onClick={addPrime} variant="outline" className="w-full mt-3">
          <Plus className="h-4 w-4 mr-2" />
          Ajouter une prime non soumise
        </Button>

        {data && data.length > 0 && (
          <div className="mt-4 pt-4 border-t">
            <div className="flex justify-between items-center">
              <span className="font-medium">Total Primes Non Soumises:</span>
              <span className="text-xl font-bold text-green-600">
                + {formatCurrency(data.reduce((sum, p) => sum + (p.montant || 0), 0))}
              </span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
