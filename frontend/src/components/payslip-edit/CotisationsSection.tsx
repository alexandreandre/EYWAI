// frontend/src/components/payslip-edit/CotisationsSection.tsx

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Building, TrendingDown, Calculator, Plus, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';

interface CotisationsSectionProps {
  data: any;
  onChange: (data: any) => void;
}

export default function CotisationsSection({ data, onChange }: CotisationsSectionProps) {
  const [totals, setTotals] = useState({ salarial: 0, patronal: 0 });

  useEffect(() => {
    // Recalculer les totaux automatiquement
    let totalSalarial = 0;
    let totalPatronal = 0;

    const blocs = [
      data?.bloc_principales || [],
      data?.bloc_allegements || [],
      data?.bloc_csg_non_deductible || []
    ];

    blocs.forEach(bloc => {
      bloc.forEach((cot: any) => {
        totalSalarial += parseFloat(cot.montant_salarial || 0);
        totalPatronal += parseFloat(cot.montant_patronal || 0);
      });
    });

    setTotals({ salarial: totalSalarial, patronal: totalPatronal });

    // Mettre à jour les totaux dans data
    const newData = { ...data, total_salarial: totalSalarial, total_patronal: totalPatronal };
    if (JSON.stringify(newData) !== JSON.stringify(data)) {
      onChange(newData);
    }
  }, [data?.bloc_principales, data?.bloc_allegements, data?.bloc_csg_non_deductible]);

  const handleCotisationChange = (bloc: string, index: number, field: string, value: any) => {
    const newData = JSON.parse(JSON.stringify(data));
    if (!newData[bloc]) newData[bloc] = [];
    newData[bloc][index] = { ...newData[bloc][index], [field]: value };
    onChange(newData);
  };

  const addCotisation = (bloc: string, type: 'principale' | 'allegement' | 'csg') => {
    const newData = JSON.parse(JSON.stringify(data));
    if (!newData[bloc]) newData[bloc] = [];

    const newCot = {
      libelle: type === 'allegement' ? 'Nouvel allègement' : type === 'csg' ? 'Nouvelle CSG/CRDS' : 'Nouvelle cotisation',
      base: 0,
      taux_salarial: 0,
      taux_patronal: 0,
      montant_salarial: 0,
      montant_patronal: 0
    };

    newData[bloc].push(newCot);
    onChange(newData);
  };

  const removeCotisation = (bloc: string, index: number) => {
    const newData = JSON.parse(JSON.stringify(data));
    if (!newData[bloc]) return;
    newData[bloc].splice(index, 1);
    onChange(newData);
  };

  const renderCotisationRow = (cot: any, idx: number, bloc: string) => (
    <div key={idx} className="p-3 border rounded-lg bg-muted/20 mb-2">
      <div className="grid grid-cols-12 gap-2 items-center">
        <div className="col-span-3">
          <Input
            placeholder="Libellé"
            value={cot.libelle || ''}
            onChange={(e) => handleCotisationChange(bloc, idx, 'libelle', e.target.value)}
            className="h-8"
          />
        </div>
        <div className="col-span-2">
          <Input
            type="number"
            step="0.01"
            placeholder="Base"
            value={cot.base || 0}
            onChange={(e) => handleCotisationChange(bloc, idx, 'base', parseFloat(e.target.value) || 0)}
            className="h-8"
          />
        </div>
        <div className="col-span-2">
          <Input
            type="number"
            step="0.01"
            placeholder="Montant Sal."
            value={cot.montant_salarial || 0}
            onChange={(e) => handleCotisationChange(bloc, idx, 'montant_salarial', parseFloat(e.target.value) || 0)}
            className="h-8"
          />
        </div>
        <div className="col-span-2">
          <Input
            type="number"
            step="0.01"
            placeholder="Taux Sal. %"
            value={cot.taux_salarial || 0}
            onChange={(e) => handleCotisationChange(bloc, idx, 'taux_salarial', parseFloat(e.target.value) || 0)}
            className="h-8"
          />
        </div>
        <div className="col-span-2">
          <Input
            type="number"
            step="0.01"
            placeholder="Montant Pat."
            value={cot.montant_patronal || 0}
            onChange={(e) => handleCotisationChange(bloc, idx, 'montant_patronal', parseFloat(e.target.value) || 0)}
            className="h-8"
          />
        </div>
        <div className="col-span-1 flex justify-end">
          <Button
            variant="destructive"
            size="sm"
            onClick={() => removeCotisation(bloc, idx)}
            className="h-8 w-8 p-0"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building className="h-5 w-5" />
          Structure des Cotisations
        </CardTitle>
        <CardDescription>
          Vue des cotisations salariales et patronales
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Accordion type="multiple" className="w-full">
          {/* Cotisations principales */}
          <AccordionItem value="principales">
            <AccordionTrigger>
              Cotisations Principales ({data?.bloc_principales?.length || 0})
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-2 mt-2">
                {data?.bloc_principales && data.bloc_principales.length > 0 ? (
                  data.bloc_principales.map((cot: any, idx: number) =>
                    renderCotisationRow(cot, idx, 'bloc_principales')
                  )
                ) : (
                  <div className="text-center py-4 text-muted-foreground text-sm">
                    Aucune cotisation principale
                  </div>
                )}
                <Button
                  onClick={() => addCotisation('bloc_principales', 'principale')}
                  variant="outline"
                  className="w-full mt-2"
                  size="sm"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Ajouter une cotisation
                </Button>
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* Allègements */}
          <AccordionItem value="allegements">
            <AccordionTrigger className="text-green-600">
              <div className="flex items-center gap-2">
                <TrendingDown className="h-4 w-4" />
                Allègements de Cotisations ({data?.bloc_allegements?.length || 0})
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-2 mt-2">
                {data?.bloc_allegements && data.bloc_allegements.length > 0 ? (
                  data.bloc_allegements.map((cot: any, idx: number) =>
                    renderCotisationRow(cot, idx, 'bloc_allegements')
                  )
                ) : (
                  <div className="text-center py-4 text-muted-foreground text-sm">
                    Aucun allègement
                  </div>
                )}
                <Button
                  onClick={() => addCotisation('bloc_allegements', 'allegement')}
                  variant="outline"
                  className="w-full mt-2"
                  size="sm"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Ajouter un allègement
                </Button>
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* CSG/CRDS non déductible */}
          <AccordionItem value="csg">
            <AccordionTrigger>
              CSG/CRDS Non Déductible ({data?.bloc_csg_non_deductible?.length || 0})
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-2 mt-2">
                {data?.bloc_csg_non_deductible && data.bloc_csg_non_deductible.length > 0 ? (
                  data.bloc_csg_non_deductible.map((cot: any, idx: number) =>
                    renderCotisationRow(cot, idx, 'bloc_csg_non_deductible')
                  )
                ) : (
                  <div className="text-center py-4 text-muted-foreground text-sm">
                    Aucune CSG/CRDS
                  </div>
                )}
                <Button
                  onClick={() => addCotisation('bloc_csg_non_deductible', 'csg')}
                  variant="outline"
                  className="w-full mt-2"
                  size="sm"
                >
                  <Plus className="h-4 w-4 mr-2" />
                  Ajouter une CSG/CRDS
                </Button>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>

        {/* Totaux */}
        <div className="mt-6 pt-4 border-t space-y-2">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Calculator className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium">Total Cotisations Salariales:</span>
            </div>
            <span className="text-lg font-bold text-destructive">
              {totals.salarial.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="font-medium">Total Cotisations Patronales:</span>
            <span className="text-lg font-bold">
              {totals.patronal.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
