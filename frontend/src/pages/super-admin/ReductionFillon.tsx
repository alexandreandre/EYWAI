// frontend/src/pages/super-admin/ReductionFillon.tsx
import { useState, useEffect } from 'react';
import apiClient from '../../api/apiClient';

interface Employee {
  id: string;
  name: string;
  company_name: string;
  salaire_base: number;
  duree_hebdomadaire: number;
  statut: string;
  job_title: string;
}

interface ReductionFillonRequest {
  employee_id: string;
  month: number;
  year: number;
}

interface TauxDetails {
  maladie: number;
  allocations_familiales: number;
  vieillesse_plafonnee: number;
  vieillesse_deplafonnee: number;
  csa: number;
  chomage: number;
  retraite_comp_t1: number;
  ceg_t1: number;
  fnal: number;
  at_mp: number;
}

interface TauxDetailExplicatif {
  libelle: string;
  valeur: number;
  source?: string;
  valeur_pourcentage?: number;
  note?: string;
  condition?: string;
}

interface CalculCoefficientCDetail {
  condition?: string;
  resultat?: string;
  reduction_totale?: number;
  remboursement?: string;
  formule_complete?: string;
  etape_1?: { calcul: string; valeur: string; resultat: number };
  etape_2?: { calcul: string; valeur: string; resultat: number };
  etape_3?: { calcul: string; valeur: string; resultat: number };
  etape_4?: { calcul: string; valeur: string; resultat: number; avant_bornage?: boolean };
  bornage?: {
    necessaire: boolean;
    bornee_inferieure: boolean;
    bornee_superieure: boolean;
    avant_bornage: number;
    apres_bornage: number;
    borne_min: number;
    borne_max: number;
  };
  coefficient_C_final?: number;
}

interface CalculDetail {
  salaire_brut_mois: number;
  heures_remunerees_mois: number;
  brut_total_cumule: number;
  heures_total_cumulees: number;
  smic_horaire: number;
  smic_reference_cumule: number;
  seuil_eligibilite_1_6_smic: number;
  ratio_brut_smic: number;
  eligible: boolean;
  parametre_T: number;
  taux_details: TauxDetails;
  taux_details_explicatifs?: Record<string, TauxDetailExplicatif>;
  calcul_T_detail?: {
    somme_taux: number;
    nombre_taux: number;
    verification: number;
  };
  coefficient_C: number;
  formule_C: string;
  calcul_coefficient_C_detail?: CalculCoefficientCDetail;
  reduction_totale_due: number;
  reduction_deja_appliquee: number;
  montant_reduction_mois: number;
  calcul_cumuls?: {
    brut_precedent: number;
    brut_mois: number;
    brut_total: number;
    formule: string;
  };
  calcul_heures?: {
    heures_precedentes: number;
    heures_mois: number;
    heures_total: number;
    formule: string;
  };
  calcul_smic?: {
    smic_horaire: number;
    heures_cumulees: number;
    smic_reference: number;
    formule: string;
  };
  calcul_seuil?: {
    smic_reference: number;
    seuil_1_6: number;
    formule: string;
  };
  verification_eligibilite?: {
    brut_cumule: number;
    seuil: number;
    comparaison: string;
    eligible: boolean;
    ratio: number;
  };
  calcul_reduction_finale?: {
    reduction_totale_due: number;
    formule_totale: string;
    reduction_deja_appliquee: number;
    montant_mois: number;
    formule_mois: string;
    montant_final_arrondi: number;
  };
}

interface CompositionBrut {
  salaire_base_mensuel: number;
  primes_soumises: number;
  detail_primes_soumises: Array<{ name: string; amount: number }>;
  primes_non_soumises: number;
  detail_primes_non_soumises: Array<{ name: string; amount: number }>;
  salaire_brut_mois: number;
}

interface ScheduleData {
  heures_prevues: number;
  heures_travaillees: number;
  heures_remunerees_mois: number;
  heures_mensuelles_contrat: number;
  calendrier_reel_count: number;
  calendrier_prevu_count: number;
  source_heures_utilisees?: string;
  detail_jours_reel?: Array<{ date: string | number; type: string; heures_faites: number }>;
  detail_jours_prevu?: Array<{ date: string | number; type: string; heures_prevues: number }>;
  formule_heures_mensuelles?: string;
}

interface ReductionFillonResponse {
  result: {
    libelle: string;
    base: number;
    taux_patronal: number | null;
    montant_patronal: number;
    valeur_cumulative_a_enregistrer: number;
  } | null;
  employee_data: {
    id: string;
    name: string;
    statut: string;
    job_title: string;
    duree_hebdomadaire: number;
    salaire_base_mensuel: number;
    hire_date: string;
  };
  company_data: {
    name: string;
    effectif: number;
    taux_at_mp: number;
    taux_at_mp_pourcentage: number;
  };
  schedule_data: ScheduleData;
  composition_brut?: CompositionBrut;
  monthly_inputs_data: {
    primes: Array<{ name: string; amount: number; is_socially_taxed: boolean }>;
    total_primes_soumises: number;
    total_primes_non_soumises: number;
  };
  expenses_data: {
    count: number;
    total_amount: number;
    expenses: Array<{ date: string; type: string; amount: number; status: string }>;
  };
  absences_data: {
    count: number;
    types: string[];
  };
  cumuls_precedents: {
    brut_total: number;
    heures_remunerees: number;
    reduction_generale_patronale: number;
  };
  calcul_detail: CalculDetail;
  input_data: {
    employee_id: string;
    month: number;
    year: number;
  };
  error: string | null;
}

export default function ReductionFillon() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loadingEmployees, setLoadingEmployees] = useState(true);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string>('');
  const [month, setMonth] = useState<number>(new Date().getMonth() + 1);
  const [year, setYear] = useState<number>(new Date().getFullYear());
  
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReductionFillonResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadEmployees();
  }, []);

  const loadEmployees = async () => {
    try {
      setLoadingEmployees(true);
      const response = await apiClient.get('/api/super-admin/reduction-fillon/employees');
      setEmployees(response.data.employees || []);
    } catch (err: any) {
      console.error('Erreur chargement employés:', err);
      setError(err.response?.data?.detail || 'Erreur lors du chargement des employés');
    } finally {
      setLoadingEmployees(false);
    }
  };

  const handleCalculate = async () => {
    if (!selectedEmployeeId) {
      setError('Veuillez sélectionner un employé');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setResult(null);

      const request: ReductionFillonRequest = {
        employee_id: selectedEmployeeId,
        month,
        year,
      };

      const response = await apiClient.post<ReductionFillonResponse>(
        '/api/super-admin/reduction-fillon/calculate',
        request
      );

      setResult(response.data);
    } catch (err: any) {
      console.error('Erreur calcul réduction Fillon:', err);
      setError(err.response?.data?.detail || 'Erreur lors du calcul de la réduction Fillon');
    } finally {
      setLoading(false);
    }
  };

  const selectedEmployee = employees.find((e) => e.id === selectedEmployeeId);

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR' }).format(value);
  };

  const formatPercent = (value: number) => {
    return `${(value * 100).toFixed(4)}%`;
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">🧮 Test Réduction Fillon</h1>
        <p className="text-gray-600 mt-2">
          Testez le calcul de la réduction générale (Fillon) avec les données réelles de Supabase
        </p>
      </div>

      {/* Formulaire */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <h2 className="text-xl font-bold text-gray-800 mb-4">📋 Paramètres du calcul</h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Sélection employé */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Employé *
            </label>
            {loadingEmployees ? (
              <div className="text-gray-500">Chargement des employés...</div>
            ) : (
              <select
                value={selectedEmployeeId}
                onChange={(e) => setSelectedEmployeeId(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">Sélectionnez un employé</option>
                {employees.map((emp) => (
                  <option key={emp.id} value={emp.id}>
                    {emp.name} ({emp.company_name || 'N/A'})
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Mois */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Mois *
            </label>
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>
                  {new Date(2000, m - 1).toLocaleString('fr-FR', { month: 'long' })}
                </option>
              ))}
            </select>
          </div>

          {/* Année */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Année *
            </label>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              min={2020}
              max={2100}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>

        {/* Info employé sélectionné */}
        {selectedEmployee && (
          <div className="mt-4 p-4 bg-blue-50 rounded-lg">
            <h3 className="font-semibold text-blue-800 mb-2">Employé sélectionné</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
              <div><span className="text-gray-600">Poste:</span> {selectedEmployee.job_title || 'N/A'}</div>
              <div><span className="text-gray-600">Statut:</span> {selectedEmployee.statut}</div>
              <div><span className="text-gray-600">Salaire base:</span> {formatCurrency(selectedEmployee.salaire_base)}</div>
              <div><span className="text-gray-600">Durée hebdo:</span> {selectedEmployee.duree_hebdomadaire}h</div>
            </div>
          </div>
        )}

        {/* Bouton calculer */}
        <div className="mt-6">
          <button
            onClick={handleCalculate}
            disabled={loading || !selectedEmployeeId}
            className="px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-lg hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed transition-all font-semibold shadow-lg"
          >
            {loading ? '⏳ Calcul en cours...' : '🧮 Calculer la réduction Fillon'}
          </button>
        </div>
      </div>

      {/* Message d'erreur */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-red-600 font-semibold">❌ {error}</p>
        </div>
      )}

      {/* Résultats détaillés */}
      {result && (
        <div className="space-y-6">
          {/* Résultat principal */}
          <div className={`rounded-lg shadow-md p-6 ${result.calcul_detail.eligible ? 'bg-green-50 border-2 border-green-200' : 'bg-yellow-50 border-2 border-yellow-200'}`}>
            <h2 className="text-2xl font-bold text-gray-800 mb-4">
              {result.calcul_detail.eligible ? '✅ Éligible à la réduction' : '❌ Non éligible à la réduction'}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div className="bg-white p-4 rounded-lg shadow">
                <p className="text-sm text-gray-600 mb-1">Coefficient C</p>
                <p className="text-3xl font-bold text-blue-600">
                  {result.calcul_detail.coefficient_C.toFixed(6)}
                </p>
              </div>
              <div className="bg-white p-4 rounded-lg shadow">
                <p className="text-sm text-gray-600 mb-1">Montant réduction du mois</p>
                <p className="text-3xl font-bold text-green-600">
                  {formatCurrency(result.result?.montant_patronal || 0)}
                </p>
              </div>
              <div className="bg-white p-4 rounded-lg shadow">
                <p className="text-sm text-gray-600 mb-1">Réduction totale cumulée</p>
                <p className="text-3xl font-bold text-purple-600">
                  {formatCurrency(result.result?.valeur_cumulative_a_enregistrer || 0)}
                </p>
              </div>
            </div>
            
            {/* Récapitulatif des valeurs clés */}
            <div className="mt-4 p-4 bg-white rounded-lg border border-gray-300">
              <h3 className="font-semibold text-gray-800 mb-3 text-sm">📋 Récapitulatif des valeurs clés</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div>
                  <span className="text-gray-600 block">Paramètre T:</span>
                  <span className="font-semibold">{formatPercent(result.calcul_detail.parametre_T)}</span>
                </div>
                <div>
                  <span className="text-gray-600 block">Brut cumulé:</span>
                  <span className="font-semibold">{formatCurrency(result.calcul_detail.brut_total_cumule)}</span>
                </div>
                <div>
                  <span className="text-gray-600 block">SMIC référence:</span>
                  <span className="font-semibold">{formatCurrency(result.calcul_detail.smic_reference_cumule)}</span>
                </div>
                <div>
                  <span className="text-gray-600 block">Ratio brut/SMIC:</span>
                  <span className="font-semibold">{result.calcul_detail.ratio_brut_smic.toFixed(4)}</span>
                </div>
                <div>
                  <span className="text-gray-600 block">Seuil 1.6 SMIC:</span>
                  <span className="font-semibold">{formatCurrency(result.calcul_detail.seuil_eligibilite_1_6_smic)}</span>
                </div>
                <div>
                  <span className="text-gray-600 block">Réduction déjà appliquée:</span>
                  <span className="font-semibold">{formatCurrency(result.calcul_detail.reduction_deja_appliquee)}</span>
                </div>
                <div>
                  <span className="text-gray-600 block">Réduction totale due:</span>
                  <span className="font-semibold">{formatCurrency(result.calcul_detail.reduction_totale_due)}</span>
                </div>
                <div>
                  <span className="text-gray-600 block">Heures cumulées:</span>
                  <span className="font-semibold">{result.calcul_detail.heures_total_cumulees.toFixed(2)}h</span>
                </div>
              </div>
            </div>
          </div>

          {/* Données de l'employé */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-bold text-gray-800 mb-4">👤 Données de l'employé</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div className="p-3 bg-gray-50 rounded">
                <span className="text-gray-500 block">Nom</span>
                <span className="font-semibold">{result.employee_data.name}</span>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <span className="text-gray-500 block">Statut</span>
                <span className="font-semibold">{result.employee_data.statut}</span>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <span className="text-gray-500 block">Salaire de base</span>
                <span className="font-semibold">{formatCurrency(result.employee_data.salaire_base_mensuel)}</span>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <span className="text-gray-500 block">Durée hebdomadaire</span>
                <span className="font-semibold">{result.employee_data.duree_hebdomadaire}h</span>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <span className="text-gray-500 block">Poste</span>
                <span className="font-semibold">{result.employee_data.job_title || 'N/A'}</span>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <span className="text-gray-500 block">Date d'embauche</span>
                <span className="font-semibold">{result.employee_data.hire_date || 'N/A'}</span>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <span className="text-gray-500 block">Entreprise</span>
                <span className="font-semibold">{result.company_data.name || 'N/A'}</span>
              </div>
              <div className="p-3 bg-gray-50 rounded">
                <span className="text-gray-500 block">Effectif entreprise</span>
                <span className="font-semibold">{result.company_data.effectif}</span>
              </div>
            </div>
          </div>

          {/* Données du mois */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Horaires */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">⏰ Horaires du mois</h3>
              <div className="space-y-3">
                <div className="flex justify-between p-2 bg-gray-50 rounded">
                  <span className="text-gray-600">Heures contrat (mensualisées)</span>
                  <span className="font-semibold">{result.schedule_data.heures_mensuelles_contrat.toFixed(2)}h</span>
                  {result.schedule_data.formule_heures_mensuelles && (
                    <div className="text-xs text-gray-500 ml-2 italic">
                      ({result.schedule_data.formule_heures_mensuelles})
                    </div>
                  )}
                </div>
                <div className="flex justify-between p-2 bg-gray-50 rounded">
                  <span className="text-gray-600">Heures prévues</span>
                  <span className="font-semibold">{result.schedule_data.heures_prevues.toFixed(2)}h</span>
                  <span className="text-xs text-gray-500 ml-2">({result.schedule_data.calendrier_prevu_count} jours)</span>
                </div>
                <div className="flex justify-between p-2 bg-gray-50 rounded">
                  <span className="text-gray-600">Heures travaillées (réelles)</span>
                  <span className="font-semibold">{result.schedule_data.heures_travaillees.toFixed(2)}h</span>
                  <span className="text-xs text-gray-500 ml-2">({result.schedule_data.calendrier_reel_count} jours)</span>
                </div>
                <div className="flex justify-between p-2 bg-blue-50 rounded border border-blue-200">
                  <span className="text-blue-700 font-medium">Heures rémunérées (calcul)</span>
                  <span className="font-bold text-blue-700">{result.schedule_data.heures_remunerees_mois.toFixed(2)}h</span>
                  {result.schedule_data.source_heures_utilisees && (
                    <span className="text-xs text-blue-600 ml-2 capitalize">
                      (Source: {result.schedule_data.source_heures_utilisees.replace(/_/g, ' ')})
                    </span>
                  )}
                </div>
                
                {/* Détail jour par jour si disponible */}
                {(result.schedule_data.detail_jours_reel && result.schedule_data.detail_jours_reel.length > 0) || 
                 (result.schedule_data.detail_jours_prevu && result.schedule_data.detail_jours_prevu.length > 0) ? (
                  <details className="mt-4">
                    <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-gray-800 p-2 bg-gray-100 rounded">
                      📅 Voir le détail jour par jour
                    </summary>
                    <div className="mt-3 space-y-3">
                      {result.schedule_data.detail_jours_reel && result.schedule_data.detail_jours_reel.length > 0 && (
                        <div>
                          <h4 className="font-semibold text-gray-700 mb-2 text-sm">Heures réelles ({result.schedule_data.detail_jours_reel.length} jours)</h4>
                          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 max-h-60 overflow-y-auto text-xs">
                            {result.schedule_data.detail_jours_reel.map((jour, idx) => (
                              <div key={idx} className="p-2 bg-white rounded border border-gray-200">
                                <div className="font-semibold text-gray-800">Jour {jour.date}</div>
                                <div className="text-gray-600 capitalize text-xs">{jour.type}</div>
                                <div className="text-blue-600 font-bold">{jour.heures_faites.toFixed(2)}h</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                      {result.schedule_data.detail_jours_prevu && result.schedule_data.detail_jours_prevu.length > 0 && (
                        <div>
                          <h4 className="font-semibold text-gray-700 mb-2 text-sm">Heures prévues ({result.schedule_data.detail_jours_prevu.length} jours)</h4>
                          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2 max-h-60 overflow-y-auto text-xs">
                            {result.schedule_data.detail_jours_prevu.map((jour, idx) => (
                              <div key={idx} className="p-2 bg-white rounded border border-gray-200">
                                <div className="font-semibold text-gray-800">Jour {jour.date}</div>
                                <div className="text-gray-600 capitalize text-xs">{jour.type}</div>
                                <div className="text-green-600 font-bold">{jour.heures_prevues.toFixed(2)}h</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </details>
                ) : null}
              </div>
            </div>

            {/* Primes et saisies */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">💰 Primes et saisies du mois</h3>
              {result.monthly_inputs_data.primes.length > 0 ? (
                <div className="space-y-2">
                  {result.monthly_inputs_data.primes.map((prime, idx) => (
                    <div key={idx} className="flex justify-between p-2 bg-gray-50 rounded">
                      <span className="text-gray-600">
                        {prime.name}
                        <span className={`ml-2 text-xs px-2 py-0.5 rounded ${prime.is_socially_taxed ? 'bg-orange-100 text-orange-700' : 'bg-green-100 text-green-700'}`}>
                          {prime.is_socially_taxed ? 'Soumise' : 'Non soumise'}
                        </span>
                      </span>
                      <span className="font-semibold">{formatCurrency(prime.amount)}</span>
                    </div>
                  ))}
                  <div className="border-t pt-2 mt-2">
                    <div className="flex justify-between p-2 bg-orange-50 rounded">
                      <span className="text-orange-700">Total primes soumises</span>
                      <span className="font-bold text-orange-700">{formatCurrency(result.monthly_inputs_data.total_primes_soumises)}</span>
                    </div>
                    <div className="flex justify-between p-2 bg-green-50 rounded mt-1">
                      <span className="text-green-700">Total primes non soumises</span>
                      <span className="font-bold text-green-700">{formatCurrency(result.monthly_inputs_data.total_primes_non_soumises)}</span>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-center py-4">Aucune prime saisie ce mois</p>
              )}
            </div>
          </div>

          {/* Notes de frais et absences */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Notes de frais */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">🧾 Notes de frais du mois</h3>
              {result.expenses_data.count > 0 ? (
                <div className="space-y-2">
                  {result.expenses_data.expenses.map((expense, idx) => (
                    <div key={idx} className="flex justify-between p-2 bg-gray-50 rounded">
                      <span className="text-gray-600">
                        {expense.type} ({expense.date})
                        <span className={`ml-2 text-xs px-2 py-0.5 rounded ${expense.status === 'validated' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                          {expense.status}
                        </span>
                      </span>
                      <span className="font-semibold">{formatCurrency(expense.amount)}</span>
                    </div>
                  ))}
                  <div className="flex justify-between p-2 bg-blue-50 rounded border border-blue-200 mt-2">
                    <span className="text-blue-700 font-medium">Total</span>
                    <span className="font-bold text-blue-700">{formatCurrency(result.expenses_data.total_amount)}</span>
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-center py-4">Aucune note de frais ce mois</p>
              )}
            </div>

            {/* Absences */}
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-bold text-gray-800 mb-4">📅 Absences validées</h3>
              {result.absences_data.count > 0 ? (
                <div>
                  <p className="text-gray-600 mb-2">{result.absences_data.count} absence(s) validée(s)</p>
                  <div className="flex flex-wrap gap-2">
                    {result.absences_data.types.map((type, idx) => (
                      <span key={idx} className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm">
                        {type}
                      </span>
                    ))}
                  </div>
                </div>
              ) : (
                <p className="text-gray-500 text-center py-4">Aucune absence validée</p>
              )}
            </div>
          </div>

          {/* Cumuls précédents */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-bold text-gray-800 mb-4">📊 Cumuls du mois précédent</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="p-4 bg-gray-50 rounded-lg">
                <span className="text-gray-500 block text-sm">Brut cumulé</span>
                <span className="text-2xl font-bold text-gray-800">{formatCurrency(result.cumuls_precedents.brut_total)}</span>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <span className="text-gray-500 block text-sm">Heures cumulées</span>
                <span className="text-2xl font-bold text-gray-800">{result.cumuls_precedents.heures_remunerees.toFixed(2)}h</span>
              </div>
              <div className="p-4 bg-gray-50 rounded-lg">
                <span className="text-gray-500 block text-sm">Réduction déjà appliquée</span>
                <span className="text-2xl font-bold text-green-600">{formatCurrency(Math.abs(result.cumuls_precedents.reduction_generale_patronale))}</span>
              </div>
            </div>
          </div>

          {/* Détail du calcul */}
          <div className="bg-gradient-to-br from-indigo-50 to-purple-50 rounded-lg shadow-md p-6">
            <h3 className="text-lg font-bold text-gray-800 mb-4">🔬 Détail complet du calcul</h3>
            
            {/* Étape 1: Composition du salaire brut */}
            <div className="mb-6 p-4 bg-white rounded-lg">
              <h4 className="font-semibold text-indigo-700 mb-3 text-base">Étape 1 : Composition du salaire brut du mois</h4>
              
              {result.composition_brut && (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm mb-4">
                    <div className="p-3 bg-indigo-50 rounded border border-indigo-200">
                      <span className="text-gray-600 block text-xs mb-1">Salaire de base mensuel</span>
                      <span className="font-bold text-lg">{formatCurrency(result.composition_brut.salaire_base_mensuel)}</span>
                    </div>
                    
                    {result.composition_brut.detail_primes_soumises.length > 0 && (
                      <div className="p-3 bg-orange-50 rounded border border-orange-200">
                        <span className="text-orange-700 block text-xs mb-1">Primes soumises (détail)</span>
                        <div className="space-y-1 mt-2">
                          {result.composition_brut.detail_primes_soumises.map((prime, idx) => (
                            <div key={idx} className="flex justify-between text-xs">
                              <span>{prime.name}:</span>
                              <span className="font-semibold">{formatCurrency(prime.amount)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    {result.composition_brut.detail_primes_non_soumises.length > 0 && (
                      <div className="p-3 bg-green-50 rounded border border-green-200">
                        <span className="text-green-700 block text-xs mb-1">Primes non soumises</span>
                        <div className="space-y-1 mt-2">
                          {result.composition_brut.detail_primes_non_soumises.map((prime, idx) => (
                            <div key={idx} className="flex justify-between text-xs">
                              <span>{prime.name}:</span>
                              <span className="font-semibold">{formatCurrency(prime.amount)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    <div className="p-3 bg-indigo-100 rounded border-2 border-indigo-400">
                      <span className="text-indigo-700 block text-xs mb-1 font-medium">= Salaire brut mois</span>
                      <span className="font-bold text-xl text-indigo-700">{formatCurrency(result.composition_brut.salaire_brut_mois)}</span>
                      <div className="text-xs text-indigo-600 mt-1">
                        {formatCurrency(result.composition_brut.salaire_base_mensuel)} + {formatCurrency(result.composition_brut.primes_soumises)}
                      </div>
                    </div>
                  </div>
                  
                  {/* Détail des heures */}
                  {result.schedule_data.source_heures_utilisees && (
                    <div className="mt-4 p-3 bg-blue-50 rounded border border-blue-200">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                        <div>
                          <span className="text-gray-600 block">Source utilisée:</span>
                          <span className="font-semibold capitalize">{result.schedule_data.source_heures_utilisees.replace(/_/g, ' ')}</span>
                        </div>
                        <div>
                          <span className="text-gray-600 block">Heures contrat:</span>
                          <span className="font-semibold">{result.schedule_data.heures_mensuelles_contrat.toFixed(2)}h</span>
                          {result.schedule_data.formule_heures_mensuelles && (
                            <div className="text-gray-500 italic">{result.schedule_data.formule_heures_mensuelles}</div>
                          )}
                        </div>
                        <div>
                          <span className="text-gray-600 block">Heures prévues:</span>
                          <span className="font-semibold">{result.schedule_data.heures_prevues.toFixed(2)}h</span>
                          <div className="text-gray-500">({result.schedule_data.calendrier_prevu_count} jours)</div>
                        </div>
                        <div>
                          <span className="text-gray-600 block">Heures travaillées:</span>
                          <span className="font-semibold">{result.schedule_data.heures_travaillees.toFixed(2)}h</span>
                          <div className="text-gray-500">({result.schedule_data.calendrier_reel_count} jours)</div>
                        </div>
                      </div>
                      
                      {result.schedule_data.detail_jours_reel && result.schedule_data.detail_jours_reel.length > 0 && (
                        <details className="mt-3">
                          <summary className="cursor-pointer text-sm font-medium text-blue-700 hover:text-blue-800">
                            Voir le détail jour par jour des heures réelles ({result.schedule_data.detail_jours_reel.length} jours)
                          </summary>
                          <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-2 text-xs max-h-40 overflow-y-auto">
                            {result.schedule_data.detail_jours_reel.map((jour, idx) => (
                              <div key={idx} className="p-2 bg-white rounded border">
                                <div className="font-semibold">Jour {jour.date}</div>
                                <div className="text-gray-600 capitalize">{jour.type}</div>
                                <div className="text-blue-600 font-bold">{jour.heures_faites}h</div>
                              </div>
                            ))}
                          </div>
                        </details>
                      )}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Étape 2: Cumuls */}
            <div className="mb-6 p-4 bg-white rounded-lg">
              <h4 className="font-semibold text-indigo-700 mb-3 text-base">Étape 2 : Calcul des cumuls annuels</h4>
              
              {result.calcul_detail.calcul_cumuls && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                    <h5 className="font-semibold text-gray-700 mb-3">Cumuls du Brut</h5>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between p-2 bg-white rounded">
                        <span className="text-gray-600">Brut cumulé du mois précédent:</span>
                        <span className="font-semibold">{formatCurrency(result.calcul_detail.calcul_cumuls.brut_precedent)}</span>
                      </div>
                      <div className="flex justify-between p-2 bg-white rounded">
                        <span className="text-gray-600">+ Brut du mois en cours:</span>
                        <span className="font-semibold">{formatCurrency(result.calcul_detail.calcul_cumuls.brut_mois)}</span>
                      </div>
                      <div className="flex justify-between p-3 bg-indigo-100 rounded border-2 border-indigo-300">
                        <span className="text-indigo-700 font-medium">= Brut total cumulé:</span>
                        <span className="font-bold text-indigo-700 text-lg">{formatCurrency(result.calcul_detail.calcul_cumuls.brut_total)}</span>
                      </div>
                      <div className="text-xs text-gray-500 font-mono bg-gray-100 p-2 rounded">
                        {result.calcul_detail.calcul_cumuls.formule}
                      </div>
                    </div>
                  </div>
                  
                  {result.calcul_detail.calcul_heures && (
                    <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
                      <h5 className="font-semibold text-gray-700 mb-3">Cumuls des Heures</h5>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between p-2 bg-white rounded">
                          <span className="text-gray-600">Heures cumulées du mois précédent:</span>
                          <span className="font-semibold">{result.calcul_detail.calcul_heures.heures_precedentes.toFixed(2)}h</span>
                        </div>
                        <div className="flex justify-between p-2 bg-white rounded">
                          <span className="text-gray-600">+ Heures du mois en cours:</span>
                          <span className="font-semibold">{result.calcul_detail.calcul_heures.heures_mois.toFixed(2)}h</span>
                        </div>
                        <div className="flex justify-between p-3 bg-indigo-100 rounded border-2 border-indigo-300">
                          <span className="text-indigo-700 font-medium">= Heures totales cumulées:</span>
                          <span className="font-bold text-indigo-700 text-lg">{result.calcul_detail.calcul_heures.heures_total.toFixed(2)}h</span>
                        </div>
                        <div className="text-xs text-gray-500 font-mono bg-gray-100 p-2 rounded">
                          {result.calcul_detail.calcul_heures.formule}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Étape 3: Paramètre T */}
            <div className="mb-6 p-4 bg-white rounded-lg">
              <h4 className="font-semibold text-indigo-700 mb-3 text-base">Étape 3 : Calcul du paramètre T (taux de cotisations patronales)</h4>
              
              <div className="mb-4">
                <p className="text-sm text-gray-600 mb-3">
                  Le paramètre T est la somme de tous les taux de cotisations patronales concernées par la réduction Fillon.
                </p>
                
                {result.calcul_detail.taux_details_explicatifs && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {Object.entries(result.calcul_detail.taux_details_explicatifs).map(([key, detail]) => (
                      <div key={key} className="p-3 bg-gray-50 rounded-lg border border-gray-200">
                        <div className="flex justify-between items-start mb-2">
                          <div className="flex-1">
                            <div className="font-semibold text-gray-800 text-sm">{detail.libelle}</div>
                            {detail.source && (
                              <div className="text-xs text-gray-500 mt-1">Source: {detail.source}</div>
                            )}
                            {detail.condition && (
                              <div className="text-xs text-blue-600 mt-1">Condition: {detail.condition}</div>
                            )}
                            {detail.note && (
                              <div className="text-xs text-purple-600 mt-1 italic">{detail.note}</div>
                            )}
                          </div>
                          <div className="text-right ml-2">
                            <div className="font-bold text-lg text-indigo-700">{formatPercent(detail.valeur)}</div>
                            {detail.valeur_pourcentage !== undefined && (
                              <div className="text-xs text-gray-500">({detail.valeur_pourcentage}%)</div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
              
              <div className="mt-4 p-4 bg-indigo-100 rounded-lg border-2 border-indigo-300">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-indigo-700 font-medium text-base">Paramètre T (somme de tous les taux):</span>
                  <span className="font-bold text-indigo-700 text-2xl">{formatPercent(result.calcul_detail.parametre_T)}</span>
                </div>
                {result.calcul_detail.calcul_T_detail && (
                  <div className="grid grid-cols-3 gap-4 mt-3 text-xs text-gray-600">
                    <div>
                      <span className="block">Nombre de taux:</span>
                      <span className="font-semibold">{result.calcul_detail.calcul_T_detail.nombre_taux}</span>
                    </div>
                    <div>
                      <span className="block">Somme calculée:</span>
                      <span className="font-semibold">{formatPercent(result.calcul_detail.calcul_T_detail.somme_taux)}</span>
                    </div>
                    <div>
                      <span className="block">Vérification:</span>
                      <span className="font-semibold">{formatPercent(result.calcul_detail.calcul_T_detail.verification)}</span>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Étape 4: SMIC et seuil */}
            <div className="mb-6 p-4 bg-white rounded-lg">
              <h4 className="font-semibold text-indigo-700 mb-3 text-base">Étape 4 : Calcul du SMIC de référence et seuil d'éligibilité</h4>
              
              {result.calcul_detail.calcul_smic && (
                <div className="mb-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <h5 className="font-semibold text-blue-800 mb-3">4.1 - Calcul du SMIC de référence cumulé</h5>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
                    <div className="p-3 bg-white rounded border border-blue-100">
                      <span className="text-gray-600 block text-xs mb-1">SMIC horaire (2025)</span>
                      <span className="font-bold text-lg">{formatCurrency(result.calcul_detail.calcul_smic.smic_horaire)}/h</span>
                    </div>
                    <div className="p-3 bg-white rounded border border-blue-100">
                      <span className="text-gray-600 block text-xs mb-1">× Heures cumulées</span>
                      <span className="font-bold text-lg">{result.calcul_detail.calcul_smic.heures_cumulees.toFixed(2)}h</span>
                    </div>
                    <div className="p-3 bg-blue-100 rounded border-2 border-blue-400">
                      <span className="text-blue-700 block text-xs mb-1 font-medium">= SMIC référence cumulé</span>
                      <span className="font-bold text-xl text-blue-700">{formatCurrency(result.calcul_detail.calcul_smic.smic_reference)}</span>
                    </div>
                  </div>
                  <div className="mt-3 text-xs text-gray-600 font-mono bg-white p-2 rounded">
                    {result.calcul_detail.calcul_smic.formule}
                  </div>
                </div>
              )}
              
              {result.calcul_detail.calcul_seuil && (
                <div className="mb-4 p-4 bg-purple-50 rounded-lg border border-purple-200">
                  <h5 className="font-semibold text-purple-800 mb-3">4.2 - Calcul du seuil d'éligibilité (1.6 × SMIC)</h5>
                  <div className="grid grid-cols-2 md:grid-cols-2 gap-3 text-sm">
                    <div className="p-3 bg-white rounded border border-purple-100">
                      <span className="text-gray-600 block text-xs mb-1">SMIC référence cumulé</span>
                      <span className="font-bold text-lg">{formatCurrency(result.calcul_detail.calcul_seuil.smic_reference)}</span>
                    </div>
                    <div className="p-3 bg-purple-100 rounded border-2 border-purple-400">
                      <span className="text-purple-700 block text-xs mb-1 font-medium">= Seuil 1.6 × SMIC</span>
                      <span className="font-bold text-xl text-purple-700">{formatCurrency(result.calcul_detail.calcul_seuil.seuil_1_6)}</span>
                    </div>
                  </div>
                  <div className="mt-3 text-xs text-gray-600 font-mono bg-white p-2 rounded">
                    {result.calcul_detail.calcul_seuil.formule}
                  </div>
                </div>
              )}
              
              {result.calcul_detail.verification_eligibilite && (
                <div className="p-4 bg-yellow-50 rounded-lg border-2 border-yellow-300">
                  <h5 className="font-semibold text-yellow-800 mb-3">4.3 - Vérification de l'éligibilité</h5>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm mb-3">
                    <div className="p-3 bg-white rounded border">
                      <span className="text-gray-600 block text-xs mb-1">Brut total cumulé</span>
                      <span className="font-bold text-lg">{formatCurrency(result.calcul_detail.verification_eligibilite.brut_cumule)}</span>
                    </div>
                    <div className="p-3 bg-white rounded border">
                      <span className="text-gray-600 block text-xs mb-1">Seuil 1.6 × SMIC</span>
                      <span className="font-bold text-lg">{formatCurrency(result.calcul_detail.verification_eligibilite.seuil)}</span>
                    </div>
                  </div>
                  <div className="p-3 bg-white rounded border-2 border-yellow-400">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-gray-700 font-medium">Comparaison:</span>
                      <span className="font-mono text-sm">{result.calcul_detail.verification_eligibilite.comparaison}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-gray-700 font-medium">Ratio brut/SMIC:</span>
                      <span className="font-bold text-lg">{result.calcul_detail.verification_eligibilite.ratio.toFixed(6)}</span>
                    </div>
                    <div className="mt-3 pt-3 border-t border-yellow-300">
                      <span className={`font-bold text-lg ${result.calcul_detail.verification_eligibilite.eligible ? 'text-green-600' : 'text-red-600'}`}>
                        {result.calcul_detail.verification_eligibilite.eligible 
                          ? '✅ Éligible (ratio < 1.6)' 
                          : '❌ Non éligible (ratio ≥ 1.6)'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Étape 5: Coefficient C */}
            <div className="mb-6 p-4 bg-white rounded-lg">
              <h4 className="font-semibold text-indigo-700 mb-3 text-base">Étape 5 : Calcul du coefficient C</h4>
              
              {result.calcul_detail.calcul_coefficient_C_detail && (
                <>
                  {result.calcul_detail.calcul_coefficient_C_detail.condition ? (
                    // Cas non éligible
                    <div className="p-4 bg-red-50 rounded-lg border-2 border-red-300">
                      <div className="mb-3">
                        <div className="font-semibold text-red-800 mb-2">Condition de non-éligibilité:</div>
                        <div className="text-sm text-red-700 font-mono bg-white p-2 rounded">
                          {result.calcul_detail.calcul_coefficient_C_detail.condition}
                        </div>
                      </div>
                      <div className="p-3 bg-white rounded border border-red-200">
                        <div className="font-semibold text-red-800 mb-1">{result.calcul_detail.calcul_coefficient_C_detail.resultat}</div>
                        {result.calcul_detail.calcul_coefficient_C_detail.reduction_totale !== undefined && (
                          <div className="text-sm text-gray-700">Réduction totale: {formatCurrency(result.calcul_detail.calcul_coefficient_C_detail.reduction_totale)}</div>
                        )}
                        {result.calcul_detail.calcul_coefficient_C_detail.remboursement && (
                          <div className="text-sm text-orange-700 mt-2">{result.calcul_detail.calcul_coefficient_C_detail.remboursement}</div>
                        )}
                      </div>
                    </div>
                  ) : (
                    // Cas éligible - calcul détaillé
                    <>
                      <div className="p-3 bg-gray-100 rounded-lg font-mono text-sm mb-4 border border-gray-300">
                        <div className="font-semibold text-gray-800 mb-2">Formule complète:</div>
                        <div className="text-indigo-700">{result.calcul_detail.calcul_coefficient_C_detail.formule_complete}</div>
                      </div>
                      
                      <div className="space-y-3 mb-4">
                        {result.calcul_detail.calcul_coefficient_C_detail.etape_1 && (
                          <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                            <div className="font-semibold text-blue-800 mb-2">Étape 5.1 - Calcul de (T / 0.6)</div>
                            <div className="grid grid-cols-3 gap-3 text-sm">
                              <div className="text-gray-600">Calcul:</div>
                              <div className="font-mono text-blue-700">{result.calcul_detail.calcul_coefficient_C_detail.etape_1.calcul}</div>
                              <div className="font-bold text-blue-700 text-lg">{result.calcul_detail.calcul_coefficient_C_detail.etape_1.resultat.toFixed(6)}</div>
                            </div>
                            <div className="mt-2 text-xs text-gray-600 font-mono bg-white p-2 rounded">
                              {result.calcul_detail.calcul_coefficient_C_detail.etape_1.valeur}
                            </div>
                          </div>
                        )}
                        
                        {result.calcul_detail.calcul_coefficient_C_detail.etape_2 && (
                          <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                            <div className="font-semibold text-blue-800 mb-2">Étape 5.2 - Calcul du ratio (1.6 × SMIC / Brut)</div>
                            <div className="grid grid-cols-3 gap-3 text-sm">
                              <div className="text-gray-600">Calcul:</div>
                              <div className="font-mono text-blue-700">{result.calcul_detail.calcul_coefficient_C_detail.etape_2.calcul}</div>
                              <div className="font-bold text-blue-700 text-lg">{result.calcul_detail.calcul_coefficient_C_detail.etape_2.resultat.toFixed(6)}</div>
                            </div>
                            <div className="mt-2 text-xs text-gray-600 font-mono bg-white p-2 rounded">
                              {result.calcul_detail.calcul_coefficient_C_detail.etape_2.valeur}
                            </div>
                          </div>
                        )}
                        
                        {result.calcul_detail.calcul_coefficient_C_detail.etape_3 && (
                          <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                            <div className="font-semibold text-blue-800 mb-2">Étape 5.3 - Soustraction de 1</div>
                            <div className="grid grid-cols-3 gap-3 text-sm">
                              <div className="text-gray-600">Calcul:</div>
                              <div className="font-mono text-blue-700">{result.calcul_detail.calcul_coefficient_C_detail.etape_3.calcul}</div>
                              <div className="font-bold text-blue-700 text-lg">{result.calcul_detail.calcul_coefficient_C_detail.etape_3.resultat.toFixed(6)}</div>
                            </div>
                            <div className="mt-2 text-xs text-gray-600 font-mono bg-white p-2 rounded">
                              {result.calcul_detail.calcul_coefficient_C_detail.etape_3.valeur}
                            </div>
                          </div>
                        )}
                        
                        {result.calcul_detail.calcul_coefficient_C_detail.etape_4 && (
                          <div className="p-3 bg-indigo-50 rounded-lg border border-indigo-200">
                            <div className="font-semibold text-indigo-800 mb-2">Étape 5.4 - Produit final (avant bornage)</div>
                            <div className="grid grid-cols-3 gap-3 text-sm">
                              <div className="text-gray-600">Calcul:</div>
                              <div className="font-mono text-indigo-700">{result.calcul_detail.calcul_coefficient_C_detail.etape_4.calcul}</div>
                              <div className="font-bold text-indigo-700 text-lg">{result.calcul_detail.calcul_coefficient_C_detail.etape_4.resultat.toFixed(6)}</div>
                            </div>
                            <div className="mt-2 text-xs text-gray-600 font-mono bg-white p-2 rounded">
                              {result.calcul_detail.calcul_coefficient_C_detail.etape_4.valeur}
                            </div>
                            <div className="mt-2 text-xs text-orange-600 italic">
                              ⚠️ Ce résultat doit être borné entre 0 et T
                            </div>
                          </div>
                        )}
                      </div>
                      
                      {result.calcul_detail.calcul_coefficient_C_detail.bornage && (
                        <div className="p-4 bg-yellow-50 rounded-lg border-2 border-yellow-300 mb-4">
                          <div className="font-semibold text-yellow-800 mb-3">5.5 - Bornage du coefficient C</div>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm mb-3">
                            <div className="p-2 bg-white rounded border">
                              <span className="text-gray-600 block text-xs">Avant bornage</span>
                              <span className="font-bold">{result.calcul_detail.calcul_coefficient_C_detail.bornage.avant_bornage.toFixed(6)}</span>
                            </div>
                            <div className="p-2 bg-white rounded border">
                              <span className="text-gray-600 block text-xs">Borne min</span>
                              <span className="font-bold">{result.calcul_detail.calcul_coefficient_C_detail.bornage.borne_min.toFixed(6)}</span>
                            </div>
                            <div className="p-2 bg-white rounded border">
                              <span className="text-gray-600 block text-xs">Borne max (T)</span>
                              <span className="font-bold">{result.calcul_detail.calcul_coefficient_C_detail.bornage.borne_max.toFixed(6)}</span>
                            </div>
                            <div className="p-2 bg-yellow-100 rounded border-2 border-yellow-400">
                              <span className="text-yellow-700 block text-xs font-medium">Après bornage</span>
                              <span className="font-bold text-yellow-700 text-lg">{result.calcul_detail.calcul_coefficient_C_detail.bornage.apres_bornage.toFixed(6)}</span>
                            </div>
                          </div>
                          <div className="p-3 bg-white rounded border border-yellow-300">
                            <div className="text-xs text-gray-700 mb-2">
                              <span className="font-semibold">Borne inférieure appliquée:</span> {result.calcul_detail.calcul_coefficient_C_detail.bornage.bornee_inferieure ? 'Oui' : 'Non'}
                            </div>
                            <div className="text-xs text-gray-700">
                              <span className="font-semibold">Borne supérieure appliquée:</span> {result.calcul_detail.calcul_coefficient_C_detail.bornage.bornee_superieure ? 'Oui' : 'Non'}
                            </div>
                            {result.calcul_detail.calcul_coefficient_C_detail.bornage.necessaire && (
                              <div className="mt-2 text-xs text-orange-600 italic">
                                ⚠️ Le coefficient a été borné car il était hors des limites [0, T]
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                      
                      <div className="p-4 bg-indigo-100 rounded-lg border-2 border-indigo-400">
                        <div className="flex justify-between items-center">
                          <span className="text-indigo-700 font-medium text-base">Coefficient C final = </span>
                          <span className="font-bold text-indigo-700 text-3xl">
                            {result.calcul_detail.calcul_coefficient_C_detail.coefficient_C_final?.toFixed(6) || result.calcul_detail.coefficient_C.toFixed(6)}
                          </span>
                        </div>
                        <div className="mt-2 text-sm text-indigo-600">
                          (borné entre 0 et T = {result.calcul_detail.parametre_T.toFixed(6)})
                        </div>
                      </div>
                    </>
                  )}
                </>
              )}
            </div>

            {/* Étape 6: Réduction finale */}
            <div className="p-4 bg-white rounded-lg">
              <h4 className="font-semibold text-indigo-700 mb-3 text-base">Étape 6 : Calcul de la réduction finale</h4>
              
              {result.calcul_detail.calcul_reduction_finale && (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-4">
                    {/* Calcul de la réduction totale due */}
                    <div className="p-4 bg-green-50 rounded-lg border border-green-200">
                      <h5 className="font-semibold text-green-800 mb-3">6.1 - Réduction totale cumulée due</h5>
                      <div className="space-y-2 text-sm">
                        <div className="p-2 bg-white rounded border">
                          <span className="text-gray-600 block text-xs mb-1">Formule:</span>
                          <span className="font-mono text-sm">Réduction totale = Brut_cumulé × Coefficient_C</span>
                        </div>
                        <div className="p-2 bg-white rounded border">
                          <span className="text-gray-600 block text-xs mb-1">Application:</span>
                          <span className="font-mono text-sm text-green-700">
                            {formatCurrency(result.calcul_detail.brut_total_cumule)} × {result.calcul_detail.coefficient_C.toFixed(6)}
                          </span>
                        </div>
                        <div className="p-3 bg-green-100 rounded border-2 border-green-400">
                          <span className="text-green-700 block text-xs mb-1 font-medium">= Réduction totale due</span>
                          <span className="font-bold text-green-700 text-2xl">
                            {formatCurrency(result.calcul_detail.calcul_reduction_finale.reduction_totale_due)}
                          </span>
                        </div>
                        <div className="text-xs text-gray-600 font-mono bg-white p-2 rounded">
                          {result.calcul_detail.calcul_reduction_finale.formule_totale}
                        </div>
                      </div>
                    </div>
                    
                    {/* Calcul de la réduction du mois */}
                    <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
                      <h5 className="font-semibold text-blue-800 mb-3">6.2 - Réduction du mois (régularisation progressive)</h5>
                      <div className="space-y-2 text-sm">
                        <div className="p-2 bg-white rounded border">
                          <span className="text-gray-600 block text-xs mb-1">Réduction totale due:</span>
                          <span className="font-semibold">{formatCurrency(result.calcul_detail.calcul_reduction_finale.reduction_totale_due)}</span>
                        </div>
                        <div className="p-2 bg-white rounded border">
                          <span className="text-gray-600 block text-xs mb-1">- Réduction déjà appliquée:</span>
                          <span className="font-semibold text-orange-600">-{formatCurrency(result.calcul_detail.calcul_reduction_finale.reduction_deja_appliquee)}</span>
                        </div>
                        <div className="p-3 bg-blue-100 rounded border-2 border-blue-400">
                          <span className="text-blue-700 block text-xs mb-1 font-medium">= Réduction du mois</span>
                          <span className="font-bold text-blue-700 text-2xl">
                            {formatCurrency(result.calcul_detail.calcul_reduction_finale.montant_mois)}
                          </span>
                        </div>
                        <div className="text-xs text-gray-600 font-mono bg-white p-2 rounded">
                          {result.calcul_detail.calcul_reduction_finale.formule_mois}
                        </div>
                        <div className="p-2 bg-purple-100 rounded border border-purple-300 mt-2">
                          <span className="text-purple-700 block text-xs mb-1 font-medium">Montant final arrondi (négatif)</span>
                          <span className="font-bold text-purple-700 text-lg">
                            {formatCurrency(result.calcul_detail.calcul_reduction_finale.montant_final_arrondi)}
                          </span>
                          <div className="text-xs text-gray-600 mt-1 italic">
                            Note: Le montant est négatif car c'est une réduction (gain pour l'employeur)
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  
                  {/* Explication de la régularisation progressive */}
                  <div className="p-4 bg-indigo-50 rounded-lg border border-indigo-300">
                    <h5 className="font-semibold text-indigo-800 mb-2">ℹ️ Explication de la régularisation progressive</h5>
                    <div className="text-sm text-indigo-700 space-y-2">
                      <p>
                        La réduction Fillon est calculée avec la <strong>méthode de régularisation progressive</strong> :
                      </p>
                      <ul className="list-disc list-inside space-y-1 ml-4">
                        <li>Le calcul se fait sur les <strong>cumuls depuis le début de l'année</strong></li>
                        <li>Chaque mois, on calcule la <strong>réduction totale due</strong> sur l'année entière</li>
                        <li>On soustrait la <strong>réduction déjà appliquée</strong> les mois précédents</li>
                        <li>La différence donne la <strong>réduction du mois</strong></li>
                      </ul>
                      <p className="mt-2 font-semibold">
                        Cela permet une régularisation automatique si le salaire varie en cours d'année.
                      </p>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
