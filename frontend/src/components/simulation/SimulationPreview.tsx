/**
 * Prévisualisation d'un bulletin simulé
 */

import React from 'react';
import { FileText, Download, Save } from 'lucide-react';
import { Button } from '../ui/button';

interface SimulationPreviewProps {
  payslipData: any;
  onDownloadPdf?: () => void;
  onSave?: () => void;
}

export const SimulationPreview: React.FC<SimulationPreviewProps> = ({
  payslipData,
  onDownloadPdf,
  onSave,
}) => {
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
    }).format(value);
  };

  if (!payslipData) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        <div className="text-center">
          <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg">Aucune simulation générée</p>
        </div>
      </div>
    );
  }

  const brut = payslipData.salaire_brut || 0;
  const netAPayer = payslipData.net_a_payer || 0;
  const coutEmployeur = payslipData.pied_de_page?.cout_total_employeur || 0;

  return (
    <div className="space-y-6">
      {/* Résumé */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-green-50 rounded-lg p-4">
          <p className="text-xs font-medium text-green-700 uppercase mb-1">Salaire brut</p>
          <p className="text-2xl font-bold text-green-900">{formatCurrency(brut)}</p>
        </div>

        <div className="bg-blue-50 rounded-lg p-4">
          <p className="text-xs font-medium text-blue-700 uppercase mb-1">Net à payer</p>
          <p className="text-2xl font-bold text-blue-900">{formatCurrency(netAPayer)}</p>
        </div>

        <div className="bg-purple-50 rounded-lg p-4">
          <p className="text-xs font-medium text-purple-700 uppercase mb-1">Coût employeur</p>
          <p className="text-2xl font-bold text-purple-900">{formatCurrency(coutEmployeur)}</p>
        </div>
      </div>

      {/* Bulletin simplifié */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Aperçu du bulletin</h3>

        <div className="space-y-2 text-sm">
          {payslipData.calcul_du_brut?.slice(0, 5).map((ligne: any, index: number) => (
            <div key={index} className="flex justify-between py-1 border-b border-gray-100">
              <span className="text-gray-700">{ligne.libelle}</span>
              <span className="font-medium">
                {ligne.gain ? formatCurrency(ligne.gain) : `-${formatCurrency(Math.abs(ligne.perte || 0))}`}
              </span>
            </div>
          ))}
          {payslipData.calcul_du_brut?.length > 5 && (
            <p className="text-xs text-gray-500 italic">
              ... et {payslipData.calcul_du_brut.length - 5} autre(s) ligne(s)
            </p>
          )}
        </div>

        <div className="mt-4 pt-4 border-t flex justify-between font-semibold">
          <span>TOTAL BRUT</span>
          <span>{formatCurrency(brut)}</span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-end gap-3">
        {onDownloadPdf && (
          <Button variant="outline" onClick={onDownloadPdf}>
            <Download className="h-4 w-4 mr-2" />
            Télécharger PDF
          </Button>
        )}
        {onSave && (
          <Button onClick={onSave}>
            <Save className="h-4 w-4 mr-2" />
            Sauvegarder
          </Button>
        )}
      </div>
    </div>
  );
};
