/**
 * Formulaire de simulation de bulletin de paie
 */

import React, { useState, forwardRef, useImperativeHandle } from 'react';
import { cn } from '../../lib/utils';

interface PayslipSimulationFormProps {
  employees: any[];
  onSubmit: (data: any) => void;
  loading?: boolean;
}

export interface PayslipSimulationFormRef {
  submit: () => void;
}

export const PayslipSimulationForm = forwardRef<PayslipSimulationFormRef, PayslipSimulationFormProps>(({
  onSubmit,
  loading = false,
}, ref) => {
  const currentDate = new Date();
  const [formData, setFormData] = useState({
    statut: 'Non-cadre' as 'Cadre' | 'Non-cadre',
    taux_prelevement_source: 0,
    duree_hebdomadaire: 35,
    salaire_brut: 0,
    month: currentDate.getMonth() + 1,
    year: currentDate.getFullYear(),
  });

  // Exposer la méthode submit au parent via ref
  useImperativeHandle(ref, () => ({
    submit: () => {
      if (formData.salaire_brut <= 0) {
        alert('Veuillez saisir un salaire brut valide');
        return;
      }

      // Construire la requête API
      const requestData = {
        employee_id: null,
        month: formData.month,
        year: formData.year,
        scenario_name: 'Simulation directe',
        scenario_data: {
          salaire_base_override: formData.salaire_brut,
          manual_params: {
            statut: formData.statut,
            taux_prelevement_source: formData.taux_prelevement_source,
            duree_hebdomadaire: formData.duree_hebdomadaire,
          },
        },
        prefill_from_real: false,
      };

      onSubmit(requestData);
    }
  }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Appeler la méthode exposée
    if (ref && 'current' in ref && ref.current) {
      ref.current.submit();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Salaire brut */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Salaire brut (€) <span className="text-red-500">*</span>
        </label>
        <input
          type="number"
          className="w-full px-3 py-2 border border-gray-300 rounded-md text-lg font-semibold"
          value={formData.salaire_brut || ''}
          onChange={(e) => setFormData({ ...formData, salaire_brut: parseFloat(e.target.value) || 0 })}
          placeholder="2500.00"
          step="0.01"
          min="0"
          required
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
              onChange={(e) => setFormData({ ...formData, statut: e.target.value as 'Cadre' | 'Non-cadre' })}
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
              onChange={(e) => setFormData({ ...formData, statut: e.target.value as 'Cadre' | 'Non-cadre' })}
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
          onChange={(e) => setFormData({ ...formData, taux_prelevement_source: parseFloat(e.target.value) || 0 })}
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
          onChange={(e) => setFormData({ ...formData, duree_hebdomadaire: parseFloat(e.target.value) || 35 })}
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
