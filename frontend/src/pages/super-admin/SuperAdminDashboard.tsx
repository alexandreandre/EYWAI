// frontend/src/pages/super-admin/SuperAdminDashboard.tsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../api/apiClient';

interface GlobalStats {
  companies: {
    total: number;
    active: number;
    inactive: number;
  };
  users: {
    total: number;
    by_role: Record<string, number>;
  };
  employees: {
    total: number;
  };
  super_admins: {
    total: number;
  };
  top_companies: Array<{
    id: string;
    name: string;
    employees_count: number;
  }>;
}

export default function SuperAdminDashboard() {
  const [stats, setStats] = useState<GlobalStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/api/super-admin/dashboard/stats');
      setStats(response.data);
      setError(null);
    } catch (err: any) {
      console.error('Erreur chargement stats:', err);
      setError(err.response?.data?.detail || 'Erreur lors du chargement des statistiques');
      if (err.response?.status === 403) {
        navigate('/');
      }
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Chargement des statistiques...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
          <p className="text-red-600 font-semibold">❌ {error}</p>
          <button
            onClick={loadStats}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Réessayer
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard Super Admin</h1>
        <p className="text-gray-600 mt-2">Vue d'ensemble de toute la plateforme</p>
      </div>

      {/* Statistiques principales */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Entreprises"
          value={stats?.companies.total || 0}
          subtitle={`${stats?.companies.active || 0} actives`}
          icon="🏢"
          color="blue"
        />
        <StatCard
          title="Utilisateurs"
          value={stats?.users.total || 0}
          subtitle={Object.keys(stats?.users.by_role || {}).length + ' rôles'}
          icon="👥"
          color="green"
        />
        <StatCard
          title="Employés"
          value={stats?.employees.total || 0}
          subtitle="Total dans la plateforme"
          icon="👨‍💼"
          color="purple"
        />
        <StatCard
          title="Super Admins"
          value={stats?.super_admins.total || 0}
          subtitle="Administrateurs système"
          icon="👑"
          color="yellow"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Répartition par rôle */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-bold text-gray-800 mb-4">Utilisateurs par rôle</h2>
          <div className="space-y-3">
            {Object.entries(stats?.users.by_role || {}).map(([role, count]) => (
              <div key={role} className="flex items-center justify-between">
                <span className="text-gray-700 capitalize">{role}</span>
                <span className="font-semibold text-blue-600">{count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Top entreprises */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-bold text-gray-800 mb-4">Top 5 Entreprises</h2>
          <div className="space-y-3">
            {stats?.top_companies && stats.top_companies.length > 0 ? (
              stats.top_companies.map((company, index) => (
                <div key={company.id} className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <span className="text-2xl font-bold text-gray-400">#{index + 1}</span>
                    <span className="text-gray-700">{company.name}</span>
                  </div>
                  <span className="font-semibold text-green-600">
                    {company.employees_count} employés
                  </span>
                </div>
              ))
            ) : (
              <p className="text-gray-500 text-center py-4">Aucune entreprise</p>
            )}
          </div>
        </div>
      </div>

      {/* Actions rapides */}
      <div className="mt-8 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg shadow-md p-6">
        <h2 className="text-xl font-bold text-gray-800 mb-4">Actions rapides</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button
            onClick={() => navigate('/super-admin/companies')}
            className="flex items-center justify-center space-x-2 bg-white hover:bg-blue-50 border-2 border-blue-200 rounded-lg p-4 transition-colors"
          >
            <span className="text-2xl">🏢</span>
            <span className="font-semibold text-blue-700">Gérer les entreprises</span>
          </button>
          <button
            onClick={() => navigate('/super-admin/users')}
            className="flex items-center justify-center space-x-2 bg-white hover:bg-green-50 border-2 border-green-200 rounded-lg p-4 transition-colors"
          >
            <span className="text-2xl">👥</span>
            <span className="font-semibold text-green-700">Gérer les utilisateurs</span>
          </button>
          <button
            onClick={() => navigate('/super-admin/monitoring')}
            className="flex items-center justify-center space-x-2 bg-white hover:bg-purple-50 border-2 border-purple-200 rounded-lg p-4 transition-colors"
          >
            <span className="text-2xl">📊</span>
            <span className="font-semibold text-purple-700">Monitoring système</span>
          </button>
        </div>
      </div>
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: number;
  subtitle: string;
  icon: string;
  color: 'blue' | 'green' | 'purple' | 'yellow';
}

function StatCard({ title, value, subtitle, icon, color }: StatCardProps) {
  const colorClasses = {
    blue: 'from-blue-500 to-blue-600',
    green: 'from-green-500 to-green-600',
    purple: 'from-purple-500 to-purple-600',
    yellow: 'from-yellow-500 to-yellow-600',
  };

  return (
    <div className={`bg-gradient-to-br ${colorClasses[color]} rounded-lg shadow-lg p-6 text-white`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold uppercase opacity-90">{title}</h3>
        <span className="text-3xl">{icon}</span>
      </div>
      <div className="text-4xl font-bold mb-2">{value.toLocaleString()}</div>
      <p className="text-sm opacity-80">{subtitle}</p>
    </div>
  );
}
