/**
 * Page principale du module de simulation de paie
 * Comprend : Calcul inverse (Net→Brut), Simulation de bulletin
 */

import React, { useState, useEffect, useRef } from 'react';
import { Calculator, FileText, Loader2 } from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Button } from '../components/ui/button';
import {
  ReverseCalculationForm,
  ReverseCalculationResult,
  PayslipSimulationForm,
  PayslipSimulationResult
} from '../components/simulation';
import type { ReverseCalculationFormRef } from '../components/simulation/ReverseCalculationForm';
import type { PayslipSimulationFormRef } from '../components/simulation/PayslipSimulationForm';
import {
  reverseCalculation,
  createPayslipSimulation,
  downloadSimulationPDF,
  ReverseCalculationRequest,
  ReverseCalculationResponse,
  SimulationCreateRequest,
  SimulationCreateResponse,
} from '../api/simulation';
import apiClient from '../api/apiClient';

interface Employee {
  id: string;
  first_name: string;
  last_name: string;
  statut: string;
}

const Simulation: React.FC = () => {
  const [activeTab, setActiveTab] = useState('reverse');
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loadingEmployees, setLoadingEmployees] = useState(true);

  // Ref pour le formulaire de calcul inverse
  const reverseFormRef = useRef<ReverseCalculationFormRef>(null);

  // Ref pour le formulaire de simulation de bulletin
  const payslipFormRef = useRef<PayslipSimulationFormRef>(null);

  // État pour le calcul inverse
  const [reverseResult, setReverseResult] = useState<ReverseCalculationResponse | null>(null);
  const [reverseLoading, setReverseLoading] = useState(false);
  const [reverseError, setReverseError] = useState<string | null>(null);

  // État pour la simulation de bulletin
  const [payslipResult, setPayslipResult] = useState<SimulationCreateResponse | null>(null);
  const [payslipLoading, setPayslipLoading] = useState(false);
  const [payslipError, setPayslipError] = useState<string | null>(null);

  useEffect(() => {
    loadEmployees();
  }, []);

  const loadEmployees = async () => {
    try {
      setLoadingEmployees(true);
      const response = await apiClient.get('/api/employees');
      setEmployees(response.data);
    } catch (error) {
      console.error('Erreur chargement employés:', error);
    } finally {
      setLoadingEmployees(false);
    }
  };


  const handleReverseCalculation = async (data: ReverseCalculationRequest) => {
    try {
      setReverseLoading(true);
      setReverseError(null);
      const result = await reverseCalculation(data);
      setReverseResult(result);
    } catch (error: any) {
      console.error('Erreur calcul inverse:', error);
      setReverseError(
        error.response?.data?.detail || 'Une erreur est survenue lors du calcul inverse'
      );
    } finally {
      setReverseLoading(false);
    }
  };

  const handleResetReverseCalculation = () => {
    setReverseResult(null);
    setReverseError(null);
  };

  const handlePayslipSimulation = async (data: SimulationCreateRequest) => {
    try {
      setPayslipLoading(true);
      setPayslipError(null);
      const result = await createPayslipSimulation(data);
      setPayslipResult(result);
    } catch (error: any) {
      console.error('Erreur simulation bulletin:', error);
      setPayslipError(
        error.response?.data?.detail || 'Une erreur est survenue lors de la simulation'
      );
    } finally {
      setPayslipLoading(false);
    }
  };

  const handleResetPayslipSimulation = () => {
    setPayslipResult(null);
    setPayslipError(null);
  };


  if (loadingEmployees) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* En-tête */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Simulation de Paie</h1>
        <p className="text-gray-500 mt-1">
          Calculez le brut depuis un net cible ou simulez des bulletins de paie
        </p>
      </div>

      {/* Onglets principaux */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-2 mb-6">
          <TabsTrigger value="reverse" className="flex items-center gap-2">
            <Calculator className="h-4 w-4" />
            <span className="hidden sm:inline">Calcul Inverse</span>
            <span className="sm:hidden">Inverse</span>
          </TabsTrigger>
          <TabsTrigger value="simulation" className="flex items-center gap-2">
            <FileText className="h-4 w-4" />
            <span className="hidden sm:inline">Simulation</span>
            <span className="sm:hidden">Simul.</span>
          </TabsTrigger>
        </TabsList>

        {/* Tab: Calcul Inverse (Net → Brut) */}
        <TabsContent value="reverse" className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
            <div className="mb-6 flex items-start justify-between">
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <Calculator className="h-5 w-5 text-blue-500" />
                  Calcul Inverse : Net → Brut
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  Déterminez le salaire brut nécessaire pour obtenir un montant net cible
                </p>
              </div>
              {!reverseResult ? (
                <Button
                  onClick={() => reverseFormRef.current?.submit()}
                  disabled={reverseLoading}
                  className="ml-4"
                >
                  {reverseLoading ? (
                    <>
                      <span className="animate-spin mr-2">⏳</span>
                      Calcul en cours...
                    </>
                  ) : (
                    'Calculer le brut'
                  )}
                </Button>
              ) : (
                <Button
                  onClick={handleResetReverseCalculation}
                  variant="outline"
                  className="ml-4"
                >
                  Nouveau calcul
                </Button>
              )}
            </div>

            {!reverseResult ? (
              <>
                <ReverseCalculationForm
                  ref={reverseFormRef}
                  employees={employees}
                  onSubmit={handleReverseCalculation}
                />

                {reverseError && (
                  <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-sm text-red-700">{reverseError}</p>
                  </div>
                )}
              </>
            ) : (
              <ReverseCalculationResult
                result={reverseResult}
                onReset={handleResetReverseCalculation}
                onCreateSimulation={() => {
                  // TODO: Passer aux paramètres de simulation pré-remplis
                  setActiveTab('simulation');
                }}
              />
            )}
          </div>
        </TabsContent>

        {/* Tab: Simulation de bulletin */}
        <TabsContent value="simulation" className="space-y-6">
          <div className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
            <div className="mb-6 flex items-start justify-between">
              <div className="flex-1">
                <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                  <FileText className="h-5 w-5 text-green-500" />
                  Simulation de Bulletin de Paie
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  Générez un bulletin de paie complet à partir d'un salaire brut
                </p>
              </div>
              {!payslipResult ? (
                <Button
                  onClick={() => payslipFormRef.current?.submit()}
                  disabled={payslipLoading}
                  className="ml-4"
                >
                  {payslipLoading ? (
                    <>
                      <span className="animate-spin mr-2">⏳</span>
                      Génération en cours...
                    </>
                  ) : (
                    'Générer le bulletin'
                  )}
                </Button>
              ) : (
                <Button
                  onClick={handleResetPayslipSimulation}
                  variant="outline"
                  className="ml-4"
                >
                  Nouveau bulletin
                </Button>
              )}
            </div>

            {!payslipResult ? (
              <>
                <PayslipSimulationForm
                  ref={payslipFormRef}
                  employees={employees}
                  onSubmit={handlePayslipSimulation}
                />

                {payslipError && (
                  <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                    <p className="text-sm text-red-700">{payslipError}</p>
                  </div>
                )}
              </>
            ) : (
              <PayslipSimulationResult
                result={payslipResult}
                onReset={handleResetPayslipSimulation}
                onDownloadPDF={async () => {
                  // Télécharger le PDF de la simulation
                  if (payslipResult?.simulation_id) {
                    try {
                      await downloadSimulationPDF(payslipResult.simulation_id);
                    } catch (error) {
                      console.error('Erreur téléchargement PDF:', error);
                      alert('Erreur lors du téléchargement du PDF');
                    }
                  }
                }}
              />
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Simulation;
