/**
 * Historique des simulations sauvegardées
 */

import React from 'react';
import { Calendar, FileText, Trash2, Eye, GitCompare, Download } from 'lucide-react';
import { Button } from '../ui/button';
import { SimulationInfo, downloadSimulationPDF } from '../../api/simulation';

interface SimulationHistoryProps {
  simulations: SimulationInfo[];
  onView?: (simulationId: string) => void;
  onCompare?: (simulationId: string) => void;
  onDelete?: (simulationId: string) => void;
  loading?: boolean;
}

export const SimulationHistory: React.FC<SimulationHistoryProps> = ({
  simulations,
  onView,
  onCompare,
  onDelete,
  loading = false,
}) => {
  const formatCurrency = (value?: number) => {
    if (!value) return '-';
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
    }).format(value);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getSimulationTypeLabel = (type: string) => {
    switch (type) {
      case 'reverse_calculation':
        return 'Calcul inverse';
      case 'payslip_simulation':
        return 'Bulletin simulé';
      default:
        return type;
    }
  };

  const getMonthLabel = (month: number) => {
    return new Date(2000, month - 1).toLocaleString('fr-FR', { month: 'long' });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (simulations.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        <div className="text-center">
          <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
          <p className="text-lg">Aucune simulation sauvegardée</p>
          <p className="text-sm mt-2">Les simulations créées apparaîtront ici</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* En-tête */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {simulations.length} simulation{simulations.length > 1 ? 's' : ''}
        </p>
      </div>

      {/* Tableau des simulations */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Période
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Scénario
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                  Net à payer
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                  Date création
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {simulations.map((sim) => (
                <tr key={sim.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="flex items-center text-sm">
                      <Calendar className="h-4 w-4 mr-2 text-gray-400" />
                      <span className="font-medium capitalize">
                        {getMonthLabel(sim.month)} {sim.year}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                      {getSimulationTypeLabel(sim.simulation_type)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-900">
                    {sim.scenario_name || <span className="text-gray-400 italic">Sans nom</span>}
                  </td>
                  <td className="px-4 py-3 text-sm text-right font-medium text-gray-900">
                    {formatCurrency(sim.net_a_payer)}
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">{formatDate(sim.created_at)}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-center gap-2">
                      {onView && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onView(sim.id)}
                          title="Voir les détails"
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      )}
                      {/* Bouton de téléchargement PDF */}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={async () => {
                          try {
                            await downloadSimulationPDF(sim.id);
                          } catch (error) {
                            console.error('Erreur téléchargement PDF:', error);
                            alert('Erreur lors du téléchargement du PDF');
                          }
                        }}
                        title="Télécharger le bulletin (PDF)"
                        className="text-green-600 hover:text-green-700 hover:bg-green-50"
                      >
                        <Download className="h-4 w-4" />
                      </Button>
                      {onCompare && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => onCompare(sim.id)}
                          title="Comparer"
                        >
                          <GitCompare className="h-4 w-4" />
                        </Button>
                      )}
                      {onDelete && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            if (window.confirm('Voulez-vous vraiment supprimer cette simulation ?')) {
                              onDelete(sim.id);
                            }
                          }}
                          title="Supprimer"
                          className="text-red-600 hover:text-red-700 hover:bg-red-50"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
