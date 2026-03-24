/**
 * Affichage du résultat d'une simulation de bulletin
 */

import React from 'react';
import { Button } from '../ui/button';
import { FileText, RefreshCw, Download } from 'lucide-react';

interface PayslipSimulationResultProps {
  result: any;
  onReset: () => void;
  onDownloadPDF?: () => void;
}

export const PayslipSimulationResult: React.FC<PayslipSimulationResultProps> = ({
  result,
  onReset,
  onDownloadPDF,
}) => {
  const payslip = result.payslip_data;
  const simulation_id = result.simulation_id;

  if (!payslip) {
    return (
      <div className="p-8 text-center text-gray-500">
        <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>Aucune donnée de bulletin disponible</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Actions */}
      <div className="flex items-center justify-between pb-4 border-b">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Résultat de la simulation</h3>
          <p className="text-sm text-gray-500">ID: {simulation_id}</p>
        </div>
        <div className="flex gap-2">
          {onDownloadPDF && (
            <Button onClick={onDownloadPDF} variant="outline" size="sm">
              <Download className="h-4 w-4 mr-2" />
              Télécharger PDF
            </Button>
          )}
          <Button onClick={onReset} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Nouvelle simulation
          </Button>
        </div>
      </div>

      {/* En-tête du bulletin */}
      {payslip.en_tete && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Entreprise</h4>
              <p className="text-sm text-gray-600">{payslip.en_tete.entreprise?.raison_sociale}</p>
              <p className="text-xs text-gray-500">{payslip.en_tete.entreprise?.siret}</p>
            </div>
            <div>
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Collaborateur</h4>
              <p className="text-sm text-gray-600">{payslip.en_tete.salarie?.nom_complet}</p>
              <p className="text-xs text-gray-500">{payslip.en_tete.salarie?.statut}</p>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-blue-300">
            <p className="text-sm font-medium text-gray-700">Période: {payslip.en_tete.periode}</p>
          </div>
        </div>
      )}

      {/* Montants principaux */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-sm text-gray-500 mb-1">Salaire brut</p>
          <p className="text-2xl font-bold text-gray-900">
            {payslip.salaire_brut?.toFixed(2) || '0.00'} €
          </p>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <p className="text-sm text-gray-500 mb-1">Net imposable</p>
          <p className="text-2xl font-bold text-blue-600">
            {payslip.synthese_net?.net_imposable?.toFixed(2) || '0.00'} €
          </p>
        </div>

        <div className="bg-white border border-green-200 rounded-lg p-4 bg-green-50">
          <p className="text-sm text-gray-500 mb-1">Net à payer</p>
          <p className="text-2xl font-bold text-green-600">
            {payslip.net_a_payer?.toFixed(2) || '0.00'} €
          </p>
        </div>
      </div>

      {/* Détails du brut */}
      {payslip.calcul_du_brut && payslip.calcul_du_brut.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="text-md font-semibold text-gray-900 mb-3">Détail du salaire brut</h4>
          <div className="space-y-2">
            {payslip.calcul_du_brut.map((ligne: any, index: number) => (
              <div key={index} className="flex justify-between text-sm">
                <span className="text-gray-600">{ligne.libelle}</span>
                <span className="font-medium text-gray-900">
                  {ligne.gain ? `+${ligne.gain.toFixed(2)}` : ''}
                  {ligne.perte ? `-${ligne.perte.toFixed(2)}` : ''} €
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cotisations */}
      {payslip.structure_cotisations && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="text-md font-semibold text-gray-900 mb-3">Cotisations sociales</h4>

          <div className="space-y-4">
            {/* Cotisations principales */}
            {payslip.structure_cotisations.bloc_principales &&
             payslip.structure_cotisations.bloc_principales.length > 0 && (
              <div>
                <h5 className="text-sm font-medium text-gray-700 mb-2">Cotisations principales</h5>
                <div className="space-y-1">
                  {payslip.structure_cotisations.bloc_principales.map((ligne: any, index: number) => (
                    <div key={index} className="flex justify-between text-sm">
                      <span className="text-gray-600">{ligne.libelle}</span>
                      <div className="flex gap-4">
                        <span className="text-gray-500">
                          Sal: {ligne.montant_salarial?.toFixed(2) || '0.00'} €
                        </span>
                        <span className="text-gray-500">
                          Pat: {ligne.montant_patronal?.toFixed(2) || '0.00'} €
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Total */}
            <div className="pt-3 border-t">
              <div className="flex justify-between text-sm font-semibold">
                <span>Total cotisations</span>
                <div className="flex gap-4">
                  <span className="text-red-600">
                    Sal: -{payslip.structure_cotisations.total_salarial?.toFixed(2) || '0.00'} €
                  </span>
                  <span className="text-gray-600">
                    Pat: {payslip.structure_cotisations.total_patronal?.toFixed(2) || '0.00'} €
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Synthèse net */}
      {payslip.synthese_net && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="text-md font-semibold text-gray-900 mb-3">Synthèse net</h4>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Net social avant impôt</span>
              <span className="font-medium text-gray-900">
                {payslip.synthese_net.net_social_avant_impot?.toFixed(2) || '0.00'} €
              </span>
            </div>

            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Net imposable</span>
              <span className="font-medium text-gray-900">
                {payslip.synthese_net.net_imposable?.toFixed(2) || '0.00'} €
              </span>
            </div>

            {payslip.synthese_net.impot_prelevement_a_la_source && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">
                  Prélèvement à la source ({payslip.synthese_net.impot_prelevement_a_la_source.taux?.toFixed(1) || '0.0'}%)
                </span>
                <span className="font-medium text-red-600">
                  -{payslip.synthese_net.impot_prelevement_a_la_source.montant?.toFixed(2) || '0.00'} €
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Coût employeur */}
      {payslip.pied_de_page?.cout_total_employeur && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <div className="flex justify-between items-center">
            <span className="text-md font-semibold text-gray-900">Coût total employeur</span>
            <span className="text-2xl font-bold text-amber-600">
              {payslip.pied_de_page.cout_total_employeur.toFixed(2)} €
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
