// frontend/src/pages/super-admin/Monitoring.tsx
import { useState, useEffect } from 'react';
import apiClient from '../../api/apiClient';

interface SystemHealth {
  status: string;
  checks: {
    database: string;
    data_integrity: string;
  };
  integrity_issues?: any[];
}

export default function Monitoring() {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadHealth();
    // Rafraîchir toutes les 30 secondes
    const interval = setInterval(loadHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadHealth = async () => {
    try {
      const response = await apiClient.get('/api/super-admin/system/health');
      setHealth(response.data);
    } catch (error) {
      console.error('Erreur:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      healthy: 'bg-green-500',
      degraded: 'bg-yellow-500',
      error: 'bg-red-500',
      ok: 'bg-green-500',
      issues_found: 'bg-yellow-500',
    };
    return colors[status] || 'bg-gray-500';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Chargement...</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Monitoring Système</h1>
        <p className="text-gray-600 mt-2">État de santé de la plateforme en temps réel</p>
      </div>

      {/* Status général */}
      <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">État global du système</h2>
            <p className="text-gray-600 mt-1">Dernière mise à jour: {new Date().toLocaleTimeString()}</p>
          </div>
          <div className="flex items-center space-x-3">
            <div className={`w-4 h-4 rounded-full ${getStatusColor(health?.status || 'error')} animate-pulse`}></div>
            <span className="text-2xl font-bold text-gray-900 uppercase">
              {health?.status === 'healthy' ? '✅ OPÉRATIONNEL' :
               health?.status === 'degraded' ? '⚠️ DÉGRADÉ' : '❌ ERREUR'}
            </span>
          </div>
        </div>
      </div>

      {/* Checks détaillés */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-gray-900">Base de données</h3>
            <div className={`w-3 h-3 rounded-full ${getStatusColor(health?.checks.database || 'error')}`}></div>
          </div>
          <p className="text-gray-600">
            {health?.checks.database === 'ok' ?
              'La base de données est opérationnelle' :
              'Problème détecté avec la base de données'}
          </p>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-gray-900">Intégrité des données</h3>
            <div className={`w-3 h-3 rounded-full ${getStatusColor(health?.checks.data_integrity || 'error')}`}></div>
          </div>
          <p className="text-gray-600">
            {health?.checks.data_integrity === 'ok' ?
              'Toutes les données sont cohérentes' :
              `${health?.integrity_issues?.length || 0} problème(s) détecté(s)`}
          </p>
        </div>
      </div>

      {/* Problèmes d'intégrité */}
      {health?.integrity_issues && health.integrity_issues.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <h3 className="text-lg font-bold text-yellow-900 mb-4">
            ⚠️ Problèmes d'intégrité détectés
          </h3>
          <div className="space-y-3">
            {health.integrity_issues.map((issue, index) => (
              <div key={index} className="bg-white rounded p-4">
                <p className="font-semibold text-gray-900">{issue.table_name}</p>
                <p className="text-sm text-gray-600">{issue.details}</p>
                <p className="text-sm text-yellow-700 mt-1">
                  {issue.issue_count} ligne(s) affectée(s)
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="mt-6 bg-gradient-to-r from-indigo-50 to-purple-50 rounded-lg p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-4">Actions disponibles</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            onClick={loadHealth}
            className="flex items-center justify-center space-x-2 bg-white hover:bg-indigo-50 border-2 border-indigo-200 rounded-lg p-4 transition-colors"
          >
            <span className="text-2xl">🔄</span>
            <span className="font-semibold text-indigo-700">Rafraîchir</span>
          </button>
          <button
            className="flex items-center justify-center space-x-2 bg-white hover:bg-green-50 border-2 border-green-200 rounded-lg p-4 transition-colors"
          >
            <span className="text-2xl">📊</span>
            <span className="font-semibold text-green-700">Exporter logs</span>
          </button>
          <button
            className="flex items-center justify-center space-x-2 bg-white hover:bg-purple-50 border-2 border-purple-200 rounded-lg p-4 transition-colors"
          >
            <span className="text-2xl">⚙️</span>
            <span className="font-semibold text-purple-700">Configuration</span>
          </button>
        </div>
      </div>
    </div>
  );
}
