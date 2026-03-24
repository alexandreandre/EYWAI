// frontend/src/pages/super-admin/CompanyDetails.tsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '../../api/apiClient';
import * as collectiveAgreementsApi from '../../api/collectiveAgreements';
import { LogoUploader } from '../../components/LogoUploader';

interface CompanyDetails {
  id: string;
  company_name: string;
  siret?: string;
  siren?: string;
  email?: string;
  phone?: string;
  address?: any;
  logo_url?: string | null;
  logo_scale?: number;
  is_active: boolean;
  created_at: string;
  stats: {
    employees_count: number;
    users_count: number;
    users_by_role: Record<string, number>;
  };
}

interface User {
  id: string;
  email?: string;
  first_name: string;
  last_name: string;
  role: string;
  created_at: string;
}

export default function CompanyDetails() {
  const { companyId } = useParams<{ companyId: string }>();
  const navigate = useNavigate();
  const [company, setCompany] = useState<CompanyDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState<User[]>([]);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [selectedRole, setSelectedRole] = useState<string | null>(null);
  const [showCreateUserModal, setShowCreateUserModal] = useState(false);
  const [creatingUser, setCreatingUser] = useState(false);
  const [userFormData, setUserFormData] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    role: 'salarie'
  });
  const [conventions, setConventions] = useState<collectiveAgreementsApi.CompanyCollectiveAgreementWithDetails[]>([]);
  const [loadingConventions, setLoadingConventions] = useState(false);

  // États pour édition et suppression
  const [showEditUserModal, setShowEditUserModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [updatingUser, setUpdatingUser] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deletingUser, setDeletingUser] = useState<User | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    loadCompanyDetails();
    loadUsers();
    loadConventions();
  }, [companyId]);

  const loadCompanyDetails = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get(`/api/super-admin/companies/${companyId}`);
      setCompany(response.data);
    } catch (error) {
      console.error('Erreur:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async (role?: string) => {
    try {
      setLoadingUsers(true);
      const params = role ? { role } : {};
      const response = await apiClient.get(`/api/super-admin/companies/${companyId}/users`, { params });
      setUsers(response.data.users);
    } catch (error) {
      console.error('Erreur:', error);
    } finally {
      setLoadingUsers(false);
    }
  };

  const loadConventions = async () => {
    try {
      setLoadingConventions(true);
      const response = await collectiveAgreementsApi.getAllCompanyAssignments();
      const companyData = response.data.find((c: any) => c.id === companyId);
      setConventions(companyData?.assigned_agreements || []);
    } catch (error) {
      console.error('Erreur lors du chargement des conventions:', error);
    } finally {
      setLoadingConventions(false);
    }
  };

  const handleRoleClick = (role: string) => {
    if (selectedRole === role) {
      setSelectedRole(null);
      loadUsers();
    } else {
      setSelectedRole(role);
      loadUsers(role);
    }
  };

  const createUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setCreatingUser(true);
      await apiClient.post(`/api/super-admin/companies/${companyId}/users`, userFormData);

      setShowCreateUserModal(false);
      setUserFormData({
        email: '',
        password: '',
        first_name: '',
        last_name: '',
        role: 'salarie'
      });

      loadUsers(selectedRole || undefined);
      loadCompanyDetails(); // Refresh stats
    } catch (error: any) {
      console.error('Erreur:', error);
      alert(error.response?.data?.detail || 'Erreur lors de la création de l\'utilisateur');
    } finally {
      setCreatingUser(false);
    }
  };

  const openEditUserModal = (user: User) => {
    setEditingUser(user);
    setShowEditUserModal(true);
  };

  const updateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;

    try {
      setUpdatingUser(true);
      await apiClient.patch(`/api/super-admin/companies/${companyId}/users/${editingUser.id}`, {
        first_name: editingUser.first_name,
        last_name: editingUser.last_name,
        email: editingUser.email,
        role: editingUser.role
      });

      setShowEditUserModal(false);
      setEditingUser(null);
      loadUsers(selectedRole || undefined);
      loadCompanyDetails();
      alert('Utilisateur mis à jour avec succès');
    } catch (error: any) {
      console.error('Erreur:', error);
      alert(error.response?.data?.detail || 'Erreur lors de la mise à jour de l\'utilisateur');
    } finally {
      setUpdatingUser(false);
    }
  };

  const openDeleteConfirm = (user: User) => {
    setDeletingUser(user);
    setShowDeleteConfirm(true);
  };

  const deleteUser = async () => {
    if (!deletingUser) return;

    try {
      setIsDeleting(true);
      const response = await apiClient.delete(`/api/super-admin/companies/${companyId}/users/${deletingUser.id}`);

      setShowDeleteConfirm(false);
      setDeletingUser(null);
      loadUsers(selectedRole || undefined);
      loadCompanyDetails();
      alert(response.data.message || 'Utilisateur supprimé avec succès');
    } catch (error: any) {
      console.error('Erreur:', error);
      alert(error.response?.data?.detail || 'Erreur lors de la suppression de l\'utilisateur');
    } finally {
      setIsDeleting(false);
    }
  };

  const toggleStatus = async () => {
    if (!company) return;
    try {
      await apiClient.patch(`/api/super-admin/companies/${companyId}`, {
        is_active: !company.is_active
      });
      loadCompanyDetails();
    } catch (error) {
      console.error('Erreur:', error);
    }
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

  if (!company) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Entreprise non trouvée</p>
        <button
          onClick={() => navigate('/super-admin/companies')}
          className="mt-4 text-indigo-600 hover:text-indigo-800"
        >
          Retour à la liste
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <button
            onClick={() => navigate('/super-admin/companies')}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{company.company_name}</h1>
            <p className="text-gray-600 mt-1">Détails de l'entreprise</p>
          </div>
        </div>

        <button
          onClick={toggleStatus}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            company.is_active
              ? 'bg-red-100 text-red-700 hover:bg-red-200'
              : 'bg-green-100 text-green-700 hover:bg-green-200'
          }`}
        >
          {company.is_active ? 'Désactiver' : 'Activer'}
        </button>
      </div>

      {/* Statut */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Statut</h2>
            <p className="text-gray-600 mt-1">État actuel de l'entreprise</p>
          </div>
          <span className={`px-4 py-2 rounded-full text-sm font-semibold ${
            company.is_active
              ? 'bg-green-100 text-green-800'
              : 'bg-red-100 text-red-800'
          }`}>
            {company.is_active ? 'Active' : 'Inactive'}
          </span>
        </div>
      </div>

      {/* Logo de l'entreprise */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Logo de l'entreprise</h2>
        <LogoUploader
          currentLogoUrl={company.logo_url}
          currentLogoScale={company.logo_scale}
          entityType="company"
          entityId={company.id}
          onLogoChange={() => {
            // Recharger les données de l'entreprise après l'upload/suppression
            loadCompanyDetails();
          }}
          onScaleChange={() => {
            // Recharger les données de l'entreprise après changement de scale
            loadCompanyDetails();
          }}
          size="lg"
        />
      </div>

      {/* Informations générales */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Informations générales</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-1">Nom de l'entreprise</label>
            <p className="text-lg text-gray-900">{company.company_name}</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-1">SIRET</label>
            <p className="text-lg text-gray-900">{company.siret || 'Non renseigné'}</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-1">SIREN</label>
            <p className="text-lg text-gray-900">{company.siren || 'Non renseigné'}</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-1">Email</label>
            <p className="text-lg text-gray-900">{company.email || 'Non renseigné'}</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-1">Téléphone</label>
            <p className="text-lg text-gray-900">{company.phone || 'Non renseigné'}</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-500 mb-1">Date de création</label>
            <p className="text-lg text-gray-900">{new Date(company.created_at).toLocaleDateString('fr-FR')}</p>
          </div>
        </div>

        {company.address && (
          <div className="mt-6">
            <label className="block text-sm font-medium text-gray-500 mb-1">Adresse</label>
            <p className="text-lg text-gray-900">{JSON.stringify(company.address)}</p>
          </div>
        )}
      </div>

      {/* Statistiques */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Statistiques</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4">
            <p className="text-sm font-medium text-blue-600">Employés</p>
            <p className="text-3xl font-bold text-blue-900 mt-2">{company.stats.employees_count}</p>
          </div>

          <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4">
            <p className="text-sm font-medium text-purple-600">Utilisateurs</p>
            <p className="text-3xl font-bold text-purple-900 mt-2">{company.stats.users_count}</p>
          </div>

          <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4">
            <p className="text-sm font-medium text-green-600">Taux d'activation</p>
            <p className="text-3xl font-bold text-green-900 mt-2">
              {company.stats.employees_count > 0
                ? Math.round((company.stats.users_count / company.stats.employees_count) * 100)
                : 0}%
            </p>
          </div>
        </div>
      </div>

      {/* Répartition par rôle */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Répartition des utilisateurs par rôle</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Object.entries(company.stats.users_by_role).map(([role, count]) => (
            <div
              key={role}
              onClick={() => handleRoleClick(role)}
              className={`border rounded-lg p-4 cursor-pointer transition-all ${
                selectedRole === role
                  ? 'border-indigo-500 bg-indigo-50 shadow-md'
                  : 'border-gray-200 hover:border-indigo-300 hover:bg-gray-50'
              }`}
            >
              <p className="text-sm text-gray-600 capitalize mb-1">{role}</p>
              <p className="text-2xl font-bold text-gray-900">{count}</p>
            </div>
          ))}
        </div>

        {Object.keys(company.stats.users_by_role).length === 0 && (
          <p className="text-gray-500 text-center py-8">Aucun utilisateur pour le moment</p>
        )}
      </div>

      {/* Conventions collectives */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">Conventions Collectives</h2>

        {loadingConventions ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
          </div>
        ) : conventions.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <svg className="mx-auto h-12 w-12 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p>Aucune convention collective assignée</p>
            <p className="text-sm mt-1">Les RH de l'entreprise peuvent en assigner depuis leur interface</p>
          </div>
        ) : (
          <div className="space-y-4">
            {conventions.map((convention) => (
              <div key={convention.id} className="border border-gray-200 rounded-lg p-4 hover:border-indigo-300 transition-colors">
                <div className="flex items-start justify-between">
                  <div className="flex-1 space-y-2">
                    <div>
                      <p className="text-sm font-medium text-gray-500">Nom</p>
                      <p className="text-lg font-semibold text-gray-900">
                        {convention.agreement_details?.name || 'N/A'}
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm font-medium text-gray-500">IDCC</p>
                        <p className="text-sm font-semibold text-gray-900">
                          {convention.agreement_details?.idcc || 'N/A'}
                        </p>
                      </div>

                      {convention.agreement_details?.sector && (
                        <div>
                          <p className="text-sm font-medium text-gray-500">Secteur</p>
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                            {convention.agreement_details.sector}
                          </span>
                        </div>
                      )}
                    </div>

                    {convention.agreement_details?.description && (
                      <div>
                        <p className="text-sm font-medium text-gray-500">Description</p>
                        <p className="text-sm text-gray-600">
                          {convention.agreement_details.description}
                        </p>
                      </div>
                    )}

                    <div>
                      <p className="text-sm font-medium text-gray-500">Date d'assignation</p>
                      <p className="text-sm text-gray-900">
                        {new Date(convention.assigned_at).toLocaleDateString('fr-FR')}
                      </p>
                    </div>
                  </div>

                  {convention.agreement_details?.rules_pdf_path && (
                    <button
                      onClick={() => {
                        const pdfUrl = convention.agreement_details?.rules_pdf_url;
                        if (pdfUrl) {
                          window.open(pdfUrl, '_blank');
                        }
                      }}
                      className="ml-4 px-3 py-2 border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors flex items-center space-x-2"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <span>PDF</span>
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Liste des utilisateurs */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              Utilisateurs
              {selectedRole && <span className="text-indigo-600"> - {selectedRole}</span>}
            </h2>
            <p className="text-sm text-gray-600 mt-1">
              {selectedRole ? `Filtré par rôle "${selectedRole}"` : 'Tous les utilisateurs'}
            </p>
          </div>
          <button
            onClick={() => setShowCreateUserModal(true)}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors flex items-center space-x-2"
          >
            <span>+</span>
            <span>Créer un utilisateur</span>
          </button>
        </div>

        {loadingUsers ? (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600 mx-auto"></div>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Utilisateur
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Email
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Rôle
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Date de création
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {users.map((user) => (
                    <tr key={user.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {user.first_name} {user.last_name}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-600">{user.email || '-'}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full bg-blue-100 text-blue-800 capitalize">
                          {user.role}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(user.created_at).toLocaleDateString('fr-FR')}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                        <button
                          onClick={() => openEditUserModal(user)}
                          className="text-indigo-600 hover:text-indigo-900"
                        >
                          Modifier
                        </button>
                        <button
                          onClick={() => openDeleteConfirm(user)}
                          className="text-red-600 hover:text-red-900"
                        >
                          Supprimer
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {users.length === 0 && (
              <p className="text-gray-500 text-center py-8">
                {selectedRole
                  ? `Aucun utilisateur avec le rôle "${selectedRole}"`
                  : 'Aucun utilisateur pour le moment'}
              </p>
            )}
          </>
        )}
      </div>

      {/* Modal de création d'utilisateur */}
      {showCreateUserModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-gray-900">Créer un utilisateur</h2>
                <button
                  onClick={() => setShowCreateUserModal(false)}
                  className="text-gray-400 hover:text-gray-600 text-2xl"
                >
                  ×
                </button>
              </div>
            </div>

            <form onSubmit={createUser} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Rôle *
                </label>
                <select
                  required
                  value={userFormData.role}
                  onChange={(e) => setUserFormData({ ...userFormData, role: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                >
                  <option value="salarie">Salarié</option>
                  <option value="manager">Manager</option>
                  <option value="rh">RH</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Prénom *
                </label>
                <input
                  type="text"
                  required
                  value={userFormData.first_name}
                  onChange={(e) => setUserFormData({ ...userFormData, first_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nom *
                </label>
                <input
                  type="text"
                  required
                  value={userFormData.last_name}
                  onChange={(e) => setUserFormData({ ...userFormData, last_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email *
                </label>
                <input
                  type="email"
                  required
                  value={userFormData.email}
                  onChange={(e) => setUserFormData({ ...userFormData, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Mot de passe *
                </label>
                <input
                  type="password"
                  required
                  minLength={6}
                  value={userFormData.password}
                  onChange={(e) => setUserFormData({ ...userFormData, password: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-500 mt-1">Minimum 6 caractères</p>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => setShowCreateUserModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={creatingUser}
                  className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {creatingUser ? 'Création en cours...' : 'Créer l\'utilisateur'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal d'édition d'utilisateur */}
      {showEditUserModal && editingUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-gray-900">Modifier l'utilisateur</h2>
                <button
                  onClick={() => setShowEditUserModal(false)}
                  className="text-gray-400 hover:text-gray-600 text-2xl"
                >
                  ×
                </button>
              </div>
            </div>

            <form onSubmit={updateUser} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Prénom *
                </label>
                <input
                  type="text"
                  required
                  value={editingUser.first_name}
                  onChange={(e) => setEditingUser({ ...editingUser, first_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Nom *
                </label>
                <input
                  type="text"
                  required
                  value={editingUser.last_name}
                  onChange={(e) => setEditingUser({ ...editingUser, last_name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Email *
                </label>
                <input
                  type="email"
                  required
                  value={editingUser.email || ''}
                  onChange={(e) => setEditingUser({ ...editingUser, email: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Rôle *
                </label>
                <select
                  required
                  value={editingUser.role}
                  onChange={(e) => setEditingUser({ ...editingUser, role: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                >
                  <option value="salarie">Salarié</option>
                  <option value="manager">Manager</option>
                  <option value="rh">RH</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-4 border-t">
                <button
                  type="button"
                  onClick={() => setShowEditUserModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={updatingUser}
                  className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {updatingUser ? 'Mise à jour...' : 'Enregistrer'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal de confirmation de suppression */}
      {showDeleteConfirm && deletingUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-gray-900">Confirmer la suppression</h2>
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="text-gray-400 hover:text-gray-600 text-2xl"
                >
                  ×
                </button>
              </div>
            </div>

            <div className="p-6">
              <div className="flex items-start space-x-3">
                <div className="flex-shrink-0">
                  <svg className="h-6 w-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div className="flex-1">
                  <p className="text-sm text-gray-900 mb-2">
                    Êtes-vous sûr de vouloir supprimer l'utilisateur <strong>{deletingUser.first_name} {deletingUser.last_name}</strong> ?
                  </p>
                  <p className="text-sm text-gray-600">
                    {deletingUser.email}
                  </p>
                  <p className="text-sm text-gray-500 mt-3">
                    Cette action supprimera l'accès de cet utilisateur à cette entreprise. Si l'utilisateur n'a plus aucun accès, son compte sera complètement supprimé.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-3 p-6 border-t bg-gray-50">
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                disabled={isDeleting}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors disabled:opacity-50"
              >
                Annuler
              </button>
              <button
                onClick={deleteUser}
                disabled={isDeleting}
                className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isDeleting ? 'Suppression...' : 'Supprimer'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
