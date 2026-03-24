// frontend/src/components/payslip-edit/SyntheseNetSection.tsx

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Calculator, Euro } from 'lucide-react';
import { useEffect } from 'react';

interface SyntheseNetSectionProps {
  data: any;
  netAPayer: number;
  onChange: (data: any, newNetAPayer: number) => void;
}

export default function SyntheseNetSection({ data, netAPayer, onChange }: SyntheseNetSectionProps) {
  const formatCurrency = (amount: number | undefined | null): string => {
    if (amount == null) return 'N/A';
    return amount.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
  };

  // Recalculer le net à payer automatiquement
  useEffect(() => {
    const netSocial = parseFloat(data?.net_social_avant_impot || 0);
    const impot = parseFloat(data?.impot_prelevement_a_la_source?.montant || 0);
    const transport = parseFloat(data?.remboursement_transport || 0);

    const calculatedNet = netSocial - impot + transport;

    if (calculatedNet !== netAPayer) {
      onChange(data, calculatedNet);
    }
  }, [data?.net_social_avant_impot, data?.impot_prelevement_a_la_source?.montant, data?.remboursement_transport]);

  const handleFieldChange = (field: string, value: any) => {
    const newData = JSON.parse(JSON.stringify(data));

    if (field.includes('.')) {
      const parts = field.split('.');
      let current = newData;
      for (let i = 0; i < parts.length - 1; i++) {
        if (!current[parts[i]]) current[parts[i]] = {};
        current = current[parts[i]];
      }
      current[parts[parts.length - 1]] = value;
    } else {
      newData[field] = value;
    }

    // Le net à payer sera recalculé par le useEffect
    onChange(newData, netAPayer);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Calculator className="h-5 w-5" />
          Synthèse Net
        </CardTitle>
        <CardDescription>
          Récapitulatif du net à payer
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-3">
          <div className="py-2 border-b">
            <Label htmlFor="net_social" className="text-xs">Net social avant impôt</Label>
            <Input
              id="net_social"
              type="number"
              step="0.01"
              value={data?.net_social_avant_impot || 0}
              onChange={(e) => handleFieldChange('net_social_avant_impot', parseFloat(e.target.value) || 0)}
              className="h-8 mt-1"
            />
          </div>

          <div className="py-2 border-b">
            <Label htmlFor="net_imposable" className="text-xs">Net imposable</Label>
            <Input
              id="net_imposable"
              type="number"
              step="0.01"
              value={data?.net_imposable || 0}
              onChange={(e) => handleFieldChange('net_imposable', parseFloat(e.target.value) || 0)}
              className="h-8 mt-1"
            />
          </div>

          <div className="bg-red-50 p-3 rounded-lg space-y-2">
            <h4 className="font-medium text-sm">Impôt prélevé à la source</h4>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label htmlFor="impot_base" className="text-xs">Base</Label>
                <Input
                  id="impot_base"
                  type="number"
                  step="0.01"
                  value={data?.impot_prelevement_a_la_source?.base || 0}
                  onChange={(e) => handleFieldChange('impot_prelevement_a_la_source.base', parseFloat(e.target.value) || 0)}
                  className="h-8"
                />
              </div>
              <div>
                <Label htmlFor="impot_taux" className="text-xs">Taux %</Label>
                <Input
                  id="impot_taux"
                  type="number"
                  step="0.01"
                  value={data?.impot_prelevement_a_la_source?.taux || 0}
                  onChange={(e) => handleFieldChange('impot_prelevement_a_la_source.taux', parseFloat(e.target.value) || 0)}
                  className="h-8"
                />
              </div>
              <div>
                <Label htmlFor="impot_montant" className="text-xs">Montant</Label>
                <Input
                  id="impot_montant"
                  type="number"
                  step="0.01"
                  value={data?.impot_prelevement_a_la_source?.montant || 0}
                  onChange={(e) => handleFieldChange('impot_prelevement_a_la_source.montant', parseFloat(e.target.value) || 0)}
                  className="h-8"
                />
              </div>
            </div>
          </div>

          <div className="py-2 border-b">
            <Label htmlFor="transport" className="text-xs text-green-600">Remboursement transport (50%)</Label>
            <Input
              id="transport"
              type="number"
              step="0.01"
              value={data?.remboursement_transport || 0}
              onChange={(e) => handleFieldChange('remboursement_transport', parseFloat(e.target.value) || 0)}
              className="h-8 mt-1"
            />
          </div>
        </div>

        <div className="pt-4 border-t-2">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Euro className="h-6 w-6 text-green-600" />
              <span className="text-xl font-bold">NET À PAYER:</span>
            </div>
            <span className="text-2xl font-bold text-green-600">
              {formatCurrency(netAPayer)}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
