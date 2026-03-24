/**
 * Affichage des résultats du calcul inverse (Net → Brut)
 */

import React from 'react';
import { CheckCircle, AlertCircle, TrendingUp, DollarSign, Building } from 'lucide-react';
import { Button } from '../ui/button';
import { ReverseCalculationResponse } from '../../api/simulation';
import { cn } from '../../lib/utils';

interface ReverseCalculationResultProps {
  result: ReverseCalculationResponse;
  onReset?: () => void;
  onCreateSimulation?: () => void;
}

export const ReverseCalculationResult: React.FC<ReverseCalculationResultProps> = ({
  result,
  onReset,
  onCreateSimulation,
}) => {
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
    }).format(value);
  };

  const cotisationsSalariales =
    result.brut_calcule - (result.bulletin_complet?.synthese_net?.net_social_avant_impot || 0);
  const cotisationsPatronales = result.cout_employeur - result.brut_calcule;

  return (
    <div className="space-y-6">
      {/* Carte de résumé */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Résultat du calcul</h3>
            <p className="text-sm text-gray-500 mt-1">
              Convergence en {result.iterations} itération{result.iterations > 1 ? 's' : ''}
            </p>
          </div>
          {result.convergence ? (
            <div className="flex items-center text-green-600">
              <CheckCircle className="h-5 w-5 mr-1" />
              <span className="text-sm font-medium">Succès</span>
            </div>
          ) : (
            <div className="flex items-center text-orange-600">
              <AlertCircle className="h-5 w-5 mr-1" />
              <span className="text-sm font-medium">Approximation</span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Net obtenu */}
          <div className="bg-blue-50 rounded-lg p-4">
            <div className="flex items-center text-blue-700 mb-2">
              <DollarSign className="h-4 w-4 mr-1" />
              <span className="text-xs font-medium uppercase">Net obtenu</span>
            </div>
            <p className="text-2xl font-bold text-blue-900">{formatCurrency(result.net_obtenu)}</p>
            {Math.abs(result.ecart) > 0.01 && (
              <p className="text-xs text-blue-600 mt-1">Écart: {formatCurrency(result.ecart)}</p>
            )}
          </div>

          {/* Brut calculé */}
          <div className="bg-green-50 rounded-lg p-4">
            <div className="flex items-center text-green-700 mb-2">
              <TrendingUp className="h-4 w-4 mr-1" />
              <span className="text-xs font-medium uppercase">Brut nécessaire</span>
            </div>
            <p className="text-2xl font-bold text-green-900">{formatCurrency(result.brut_calcule)}</p>
          </div>

          {/* Coût employeur */}
          <div className="bg-purple-50 rounded-lg p-4">
            <div className="flex items-center text-purple-700 mb-2">
              <Building className="h-4 w-4 mr-1" />
              <span className="text-xs font-medium uppercase">Coût employeur</span>
            </div>
            <p className="text-2xl font-bold text-purple-900">{formatCurrency(result.cout_employeur)}</p>
          </div>
        </div>
      </div>

      {/* Graphique de répartition */}
      <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
        <h4 className="text-md font-semibold text-gray-900 mb-4">Répartition du coût</h4>

        <div className="space-y-4">
          {/* Barre de progression visuelle */}
          <div className="relative h-12 bg-gray-100 rounded-lg overflow-hidden">
            <div
              className="absolute h-full bg-green-500 flex items-center justify-center text-white text-sm font-medium"
              style={{
                width: `${(result.brut_calcule / result.cout_employeur) * 100}%`,
              }}
            >
              <span className="px-2">Brut</span>
            </div>
            <div
              className="absolute h-full bg-blue-500 flex items-center justify-center text-white text-sm font-medium"
              style={{
                left: `${(result.brut_calcule / result.cout_employeur) * 100}%`,
                width: `${(cotisationsPatronales / result.cout_employeur) * 100}%`,
              }}
            >
              <span className="px-2">Cotis. patronales</span>
            </div>
          </div>

          {/* Détails */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-600">Salaire brut:</span>
              <span className="font-medium">{formatCurrency(result.brut_calcule)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Cotisations patronales:</span>
              <span className="font-medium text-blue-600">{formatCurrency(cotisationsPatronales)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-600">Cotisations salariales:</span>
              <span className="font-medium text-red-600">-{formatCurrency(cotisationsSalariales)}</span>
            </div>
            <div className="flex justify-between font-semibold border-t pt-2">
              <span className="text-gray-900">Net à payer:</span>
              <span className="text-green-600">{formatCurrency(result.net_obtenu)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Tableau détaillé des cotisations */}
      {result.bulletin_complet?.structure_cotisations && (
        <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
          <h4 className="text-md font-semibold text-gray-900 mb-4">Détail des cotisations</h4>

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Libellé</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">Base</th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                    Taux salarial
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                    Part salariale
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                    Taux patronal
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                    Part patronale
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {result.bulletin_complet.structure_cotisations.bloc_principales?.map(
                  (ligne: any, index: number) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="px-4 py-2">{ligne.libelle}</td>
                      <td className="px-4 py-2 text-right">{formatCurrency(ligne.base || 0)}</td>
                      <td className="px-4 py-2 text-right">{(ligne.taux_salarial || 0).toFixed(2)}%</td>
                      <td className="px-4 py-2 text-right text-red-600">
                        {formatCurrency(ligne.part_salariale || 0)}
                      </td>
                      <td className="px-4 py-2 text-right">{(ligne.taux_patronal || 0).toFixed(2)}%</td>
                      <td className="px-4 py-2 text-right text-blue-600">
                        {formatCurrency(ligne.part_patronale || 0)}
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex justify-between pt-4 border-t">
        {onReset && (
          <Button variant="outline" onClick={onReset}>
            Nouveau calcul
          </Button>
        )}
        {onCreateSimulation && (
          <Button onClick={onCreateSimulation}>Créer une simulation avec ces paramètres</Button>
        )}
      </div>
    </div>
  );
};
