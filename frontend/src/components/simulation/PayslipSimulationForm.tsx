/**
 * Formulaire de simulation de bulletin de paie
 */

import React, { useState, useEffect, forwardRef, useImperativeHandle, useMemo } from 'react';
import { cn } from '../../lib/utils';
import * as collectiveAgreementsApi from '@/api/collectiveAgreements';
import type { SimulationCreateRequest } from '@/api/simulation';

interface SimulationEmployee {
  id: string;
  first_name: string;
  last_name: string;
  statut?: string;
  duree_hebdomadaire?: number;
  hire_date?: string;
  salaire_de_base?: { valeur?: number };
  classification_conventionnelle?: collectiveAgreementsApi.ClassificationConventionnelle;
  collective_agreement_id?: string | null;
}

interface PayslipSimulationFormProps {
  employees: SimulationEmployee[];
  onSubmit: (data: SimulationCreateRequest) => void;
  loading?: boolean;
}

export interface PayslipSimulationFormRef {
  submit: () => void;
}

function classificationKey(c: collectiveAgreementsApi.ClassificationConventionnelle): string {
  return `${c.groupe_emploi}-${c.classe_emploi}-${c.coefficient}`;
}

function parseSalaireBase(employee: SimulationEmployee): number {
  const raw = employee.salaire_de_base?.valeur;
  return typeof raw === 'number' ? raw : parseFloat(String(raw || 0)) || 0;
}

export const PayslipSimulationForm = forwardRef<PayslipSimulationFormRef, PayslipSimulationFormProps>(({
  employees,
  onSubmit,
}, ref) => {
  const currentDate = new Date();
  const [companyAgreements, setCompanyAgreements] = useState<
    collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails[]
  >([]);
  const [classificationsCc, setClassificationsCc] = useState<
    collectiveAgreementsApi.ClassificationConventionnelle[]
  >([]);
  const [salaryMinima, setSalaryMinima] = useState<
    collectiveAgreementsApi.SalaryMinimumRow[]
  >([]);

  const [formData, setFormData] = useState({
    employee_id: '' as string,
    statut: 'Non-cadre' as 'Cadre' | 'Non-cadre',
    taux_prelevement_source: 0,
    duree_hebdomadaire: 35,
    salaire_brut: 0,
    month: currentDate.getMonth() + 1,
    year: currentDate.getFullYear(),
    collective_agreement_id: '' as string,
    classification: null as collectiveAgreementsApi.ClassificationConventionnelle | null,
    date_entree: '',
    apply_cc_minimum: false,
  });

  useEffect(() => {
    collectiveAgreementsApi.getMyCompanyAgreements()
      .then((res) => setCompanyAgreements(res.data || []))
      .catch(() => setCompanyAgreements([]));
  }, []);

  useEffect(() => {
    if (!formData.collective_agreement_id) {
      setClassificationsCc([]);
      setSalaryMinima([]);
      return;
    }
    collectiveAgreementsApi.getClassifications(formData.collective_agreement_id)
      .then((res) => setClassificationsCc(res.data || []))
      .catch(() => setClassificationsCc([]));
    collectiveAgreementsApi.getSalaryMinima(formData.collective_agreement_id)
      .then((res) => setSalaryMinima(res.data || []))
      .catch(() => setSalaryMinima([]));
  }, [formData.collective_agreement_id]);

  const selectedAgreement = useMemo(
    () => companyAgreements.find((a) => a.collective_agreement_id === formData.collective_agreement_id),
    [companyAgreements, formData.collective_agreement_id]
  );

  const minimumForGrade = useMemo(() => {
    if (!formData.classification || salaryMinima.length === 0) return null;
    const keys = [
      formData.classification.coefficient,
      formData.classification.classe_emploi,
    ];
    for (const key of keys) {
      const row = salaryMinima.find((m) => Number(m.coefficient) === Number(key));
      if (row) return row;
    }
    return null;
  }, [formData.classification, salaryMinima]);

  const hourlyFromMinimum = useMemo(() => {
    if (!minimumForGrade || formData.duree_hebdomadaire <= 0) return null;
    const heuresMensuelles = (formData.duree_hebdomadaire * 52) / 12;
    return heuresMensuelles > 0 ? minimumForGrade.valeur / heuresMensuelles : null;
  }, [minimumForGrade, formData.duree_hebdomadaire]);

  const handleEmployeeChange = (employeeId: string) => {
    if (!employeeId) {
      setFormData((prev) => ({ ...prev, employee_id: '' }));
      return;
    }
    const employee = employees.find((e) => e.id === employeeId);
    if (!employee) return;
    const statut = (employee.statut === 'Cadre' ? 'Cadre' : 'Non-cadre') as 'Cadre' | 'Non-cadre';
    setFormData((prev) => ({
      ...prev,
      employee_id: employeeId,
      statut,
      duree_hebdomadaire: employee.duree_hebdomadaire ?? prev.duree_hebdomadaire,
      salaire_brut: parseSalaireBase(employee) || prev.salaire_brut,
      date_entree: employee.hire_date || prev.date_entree,
      collective_agreement_id: employee.collective_agreement_id || prev.collective_agreement_id,
      classification: employee.classification_conventionnelle || prev.classification,
    }));
  };

  const applyMinimumToBrut = () => {
    if (minimumForGrade) {
      setFormData((prev) => ({
        ...prev,
        salaire_brut: minimumForGrade.valeur,
        apply_cc_minimum: true,
      }));
    }
  };

  useImperativeHandle(ref, () => ({
    submit: () => {
      if (formData.salaire_brut <= 0 && !formData.apply_cc_minimum) {
        alert('Veuillez saisir un salaire brut valide');
        return;
      }

      const agreement = selectedAgreement;
      const manualParams = {
        statut: formData.statut,
        taux_prelevement_source: formData.taux_prelevement_source,
        duree_hebdomadaire: formData.duree_hebdomadaire,
        collective_agreement_id: formData.collective_agreement_id || undefined,
        idcc: agreement?.agreement_details?.idcc,
        convention_libelle: agreement?.agreement_details?.name,
        classification_conventionnelle: formData.classification || undefined,
        date_entree: formData.date_entree || undefined,
      };

      const requestData: SimulationCreateRequest = {
        employee_id: formData.employee_id || null,
        month: formData.month,
        year: formData.year,
        scenario_name: formData.employee_id ? 'Simulation salarié' : 'Simulation directe',
        scenario_data: {
          salaire_base_override: formData.salaire_brut > 0 ? formData.salaire_brut : undefined,
          apply_cc_minimum: formData.apply_cc_minimum,
          manual_params: manualParams,
        },
        prefill_from_real: false,
      };

      onSubmit(requestData);
    },
  }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (ref && 'current' in ref && ref.current) {
      ref.current.submit();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Salarié existant (optionnel) */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Salarié (optionnel)
        </label>
        <select
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
          value={formData.employee_id}
          onChange={(e) => handleEmployeeChange(e.target.value)}
        >
          <option value="">Simulation manuelle</option>
          {employees.map((emp) => (
            <option key={emp.id} value={emp.id}>
              {emp.first_name} {emp.last_name}
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-gray-500">
          Sélectionnez un salarié pour reprendre sa CC, son grade et son salaire de base.
        </p>
      </div>

      {/* Convention collective */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Convention collective
        </label>
        <select
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
          value={formData.collective_agreement_id}
          onChange={(e) =>
            setFormData({
              ...formData,
              collective_agreement_id: e.target.value,
              classification: null,
              apply_cc_minimum: false,
            })
          }
        >
          <option value="">Aucune (simulation générique)</option>
          {companyAgreements.map((a) => (
            <option key={a.id} value={a.collective_agreement_id}>
              {a.agreement_details?.name || a.agreement_details?.idcc} (IDCC{' '}
              {a.agreement_details?.idcc})
            </option>
          ))}
        </select>
      </div>

      {/* Grade / classification */}
      {formData.collective_agreement_id && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Grade / classification
          </label>
          {classificationsCc.length > 0 ? (
            <select
              className="w-full px-3 py-2 border border-gray-300 rounded-md"
              value={formData.classification ? classificationKey(formData.classification) : ''}
              onChange={(e) => {
                const c = classificationsCc.find(
                  (x) => classificationKey(x) === e.target.value
                );
                setFormData({
                  ...formData,
                  classification: c || null,
                  apply_cc_minimum: false,
                });
              }}
            >
              <option value="">Choisir un grade</option>
              {classificationsCc.map((c) => (
                <option key={classificationKey(c)} value={classificationKey(c)}>
                  Groupe {c.groupe_emploi} — Classe {c.classe_emploi} — Coeff. {c.coefficient}
                </option>
              ))}
            </select>
          ) : (
            <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
              Aucune grille de classification disponible pour cette convention.
            </p>
          )}
          {minimumForGrade && (
            <div className="mt-2 text-sm text-gray-600 space-y-1">
              <p>
                Minimum conventionnel :{' '}
                <span className="font-semibold">{minimumForGrade.valeur.toFixed(2)} €/mois</span>
                {minimumForGrade.libelle ? ` (${minimumForGrade.libelle})` : ''}
              </p>
              {hourlyFromMinimum != null && (
                <p>
                  Taux horaire implicite (35h) :{' '}
                  <span className="font-medium">{hourlyFromMinimum.toFixed(2)} €/h</span>
                </p>
              )}
            </div>
          )}
          {minimumForGrade && (
            <button
              type="button"
              className="mt-2 text-sm text-blue-600 hover:text-blue-800 underline"
              onClick={applyMinimumToBrut}
            >
              Appliquer le minimum conventionnel au salaire brut
            </button>
          )}
        </div>
      )}

      {/* Date d'entrée (prime d'ancienneté CC) */}
      {formData.collective_agreement_id && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Date d&apos;entrée (ancienneté)
          </label>
          <input
            type="date"
            className="w-full px-3 py-2 border border-gray-300 rounded-md"
            value={formData.date_entree}
            onChange={(e) => setFormData({ ...formData, date_entree: e.target.value })}
          />
        </div>
      )}

      {/* Salaire brut */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Salaire brut (€) <span className="text-red-500">*</span>
        </label>
        <input
          type="number"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-lg font-semibold"
          value={formData.salaire_brut || ''}
          onChange={(e) =>
            setFormData({
              ...formData,
              salaire_brut: parseFloat(e.target.value) || 0,
              apply_cc_minimum: false,
            })
          }
          placeholder="2500.00"
          step="0.01"
          min="0"
          required={!formData.apply_cc_minimum}
        />
      </div>

      {/* Statut */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Statut <span className="text-red-500">*</span>
        </label>
        <div className="grid grid-cols-2 gap-4">
          <label
            className={cn(
              'flex items-center justify-center px-4 py-3 border-2 rounded-md cursor-pointer transition-colors',
              formData.statut === 'Non-cadre'
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-300 hover:border-gray-400'
            )}
          >
            <input
              type="radio"
              name="statut"
              value="Non-cadre"
              checked={formData.statut === 'Non-cadre'}
              onChange={(e) =>
                setFormData({ ...formData, statut: e.target.value as 'Cadre' | 'Non-cadre' })
              }
              className="mr-2"
            />
            Non-cadre
          </label>

          <label
            className={cn(
              'flex items-center justify-center px-4 py-3 border-2 rounded-md cursor-pointer transition-colors',
              formData.statut === 'Cadre'
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-300 hover:border-gray-400'
            )}
          >
            <input
              type="radio"
              name="statut"
              value="Cadre"
              checked={formData.statut === 'Cadre'}
              onChange={(e) =>
                setFormData({ ...formData, statut: e.target.value as 'Cadre' | 'Non-cadre' })
              }
              className="mr-2"
            />
            Cadre
          </label>
        </div>
      </div>

      {/* Taux PAS */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Taux de prélèvement à la source (%)
        </label>
        <input
          type="number"
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
          value={formData.taux_prelevement_source || ''}
          onChange={(e) =>
            setFormData({
              ...formData,
              taux_prelevement_source: parseFloat(e.target.value) || 0,
            })
          }
          placeholder="0.0"
          step="0.1"
          min="0"
          max="100"
        />
      </div>

      {/* Durée hebdomadaire */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Durée hebdomadaire (heures)
        </label>
        <input
          type="number"
          className="w-full px-3 py-2 border border-gray-300 rounded-md"
          value={formData.duree_hebdomadaire || ''}
          onChange={(e) =>
            setFormData({
              ...formData,
              duree_hebdomadaire: parseFloat(e.target.value) || 35,
            })
          }
          placeholder="35"
          step="0.5"
          min="0"
        />
      </div>

      {/* Période */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Mois <span className="text-red-500">*</span>
          </label>
          <select
            className="w-full px-3 py-2 border border-gray-300 rounded-md"
            value={formData.month}
            onChange={(e) => setFormData({ ...formData, month: parseInt(e.target.value) })}
            required
          >
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>
                {new Date(2000, m - 1).toLocaleString('fr-FR', { month: 'long' })}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Année <span className="text-red-500">*</span>
          </label>
          <input
            type="number"
            className="w-full px-3 py-2 border border-gray-300 rounded-md"
            value={formData.year}
            onChange={(e) => setFormData({ ...formData, year: parseInt(e.target.value) })}
            min={2020}
            max={2100}
            required
          />
        </div>
      </div>
    </form>
  );
});
