// frontend/src/pages/super-admin/Companies.tsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../api/apiClient';
import { LogoUploader } from '../../components/LogoUploader';

interface Company {
  id: string;
  company_name: string;
  siret?: string;
  email?: string;
  phone?: string;
  is_active: boolean;
  created_at: string;
  employees_count?: number;
  users_count?: number;
  group_id?: string | null;
  group_name?: string | null;
}

interface CompanyGroup {
  id: string;
  group_name: string;
  description?: string;
}

export default function Companies() {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createWithAdmin, setCreateWithAdmin] = useState(false);
  const [formData, setFormData] = useState({
    company_name: '',
    siret: '',
    email: '',
    phone: '',
    logo_url: null as string | null,
    logo_scale: 1.0,
    admin_email: '',
    admin_password: '',
    admin_first_name: '',
    admin_last_name: ''
  });
  const [logoFile, setLogoFile] = useState<File | null>(null);

  // Gestion des groupes
  const [groups, setGroups] = useState<CompanyGroup[]>([]);
  const [showGroupAssignModal, setShowGroupAssignModal] = useState(false);
  const [selectedCompanyForGroup, setSelectedCompanyForGroup] = useState<Company | null>(null);
  const [selectedGroupId, setSelectedGroupId] = useState<string>('');
  const [assigningToGroup, setAssigningToGroup] = useState(false);

  // Gestion de la suppression permanente
  const [showDeleteConfirmModal, setShowDeleteConfirmModal] = useState(false);
  const [companyToDelete, setCompanyToDelete] = useState<Company | null>(null);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    loadCompanies();
    loadGroups();
  }, []);

  const loadCompanies = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/api/super-admin/companies', {
        params: { search }
      });
      setCompanies(response.data.companies);
    } catch (error) {
      console.error('Erreur:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadGroups = async () => {
    try {
      const response = await apiClient.get('/api/company-groups/');
      setGroups(response.data);
    } catch (error) {
      console.error('Erreur lors du chargement des groupes:', error);
    }
  };

  const handleAssignToGroup = async () => {
    if (!selectedCompanyForGroup || !selectedGroupId) {
      alert('Veuillez sélectionner un groupe');
      return;
    }

    try {
      setAssigningToGroup(true);
      await apiClient.post(`/api/company-groups/${selectedGroupId}/companies/${selectedCompanyForGroup.id}`);

      alert(`L'entreprise a été ajoutée au groupe avec succès`);
      setShowGroupAssignModal(false);
      setSelectedCompanyForGroup(null);
      setSelectedGroupId('');
      loadCompanies();
    } catch (error: any) {
      console.error('Erreur:', error);
      alert(error.response?.data?.detail || 'Erreur lors de l\'assignation au groupe');
    } finally {
      setAssigningToGroup(false);
    }
  };

  const handleRemoveFromGroup = async (company: Company) => {
    if (!company.group_id) return;

    if (!confirm(`Voulez-vous vraiment retirer "${company.company_name}" du groupe "${company.group_name}" ?`)) {
      return;
    }

    try {
      await apiClient.delete(`/api/company-groups/${company.group_id}/companies/${company.id}`);
      alert(`L'entreprise a été retirée du groupe avec succès`);
      loadCompanies();
    } catch (error: any) {
      console.error('Erreur:', error);
      alert(error.response?.data?.detail || 'Erreur lors du retrait du groupe');
    }
  };

  const openGroupAssignModal = (company: Company) => {
    setSelectedCompanyForGroup(company);
    setSelectedGroupId(company.group_id || '');
    setShowGroupAssignModal(true);
  };

  const toggleCompanyStatus = async (companyId: string, currentStatus: boolean) => {
    try {
      await apiClient.patch(`/api/super-admin/companies/${companyId}`, {
        is_active: !currentStatus
      });
      loadCompanies();
    } catch (error) {
      console.error('Erreur:', error);
    }
  };

  const openDeleteConfirmModal = (company: Company) => {
    setCompanyToDelete(company);
    setShowDeleteConfirmModal(true);
  };

  const handleDeleteCompanyPermanent = async () => {
    if (!companyToDelete) return;

    try {
      setDeleting(true);
      const response = await apiClient.delete(`/api/super-admin/companies/${companyToDelete.id}/permanent`);

      alert(response.data.message || 'Entreprise supprimée définitivement avec succès');
      setShowDeleteConfirmModal(false);
      setCompanyToDelete(null);
      loadCompanies();
    } catch (error: any) {
      console.error('Erreur:', error);
      alert(error.response?.data?.detail || 'Erreur lors de la suppression de l\'entreprise');
    } finally {
      setDeleting(false);
    }
  };

  const createCompany = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setCreating(true);

      // 1. Créer l'entreprise SANS le logo (logo_url ne doit pas être envoyé si c'est une data URL)
      const dataToSend = createWithAdmin ? {
        company_name: formData.company_name,
        siret: formData.siret || undefined,
        email: formData.email || undefined,
        phone: formData.phone || undefined,
        logo_scale: formData.logo_scale,
        admin_email: formData.admin_email,
        admin_password: formData.admin_password,
        admin_first_name: formData.admin_first_name,
        admin_last_name: formData.admin_last_name
      } : {
        company_name: formData.company_name,
        siret: formData.siret || undefined,
        email: formData.email || undefined,
        phone: formData.phone || undefined,
        logo_scale: formData.logo_scale
      };

      console.log('📤 [CREATE COMPANY] Données envoyées:', dataToSend);

      const response = await apiClient.post('/api/super-admin/companies', dataToSend);
      const createdCompany = response.data.company;

      console.log('✅ [CREATE COMPANY] Entreprise créée:', createdCompany);

      // 2. Si un logo a été sélectionné, l'uploader
      if (logoFile && createdCompany?.id) {
        console.log('📤 [UPLOAD LOGO] Upload du logo pour l\'entreprise:', createdCompany.id);
        try {
          const formDataUpload = new FormData();
          formDataUpload.append('file', logoFile);
          formDataUpload.append('entity_type', 'company');
          formDataUpload.append('entity_id', createdCompany.id);

          await apiClient.post('/api/uploads/logo', formDataUpload, {
            headers: {
              'Content-Type': 'multipart/form-data'
            }
          });
          console.log('✅ [UPLOAD LOGO] Logo uploadé avec succès');
        } catch (uploadError) {
          console.error('⚠️ [UPLOAD LOGO] Erreur lors de l\'upload du logo:', uploadError);
          // On ne bloque pas la création si l'upload du logo échoue
        }
      }

      setShowCreateModal(false);
      setCreateWithAdmin(false);
      setFormData({
        company_name: '',
        siret: '',
        email: '',
        phone: '',
        logo_url: null,
        logo_scale: 1.0,
        admin_email: '',
        admin_password: '',
        admin_first_name: '',
        admin_last_name: ''
      });
      setLogoFile(null);
      loadCompanies();
    } catch (error: any) {
      console.error('❌ [CREATE COMPANY] Erreur complète:', error);
      console.error('❌ [CREATE COMPANY] Response data:', error.response?.data);
      console.error('❌ [CREATE COMPANY] Response status:', error.response?.status);
      alert(error.response?.data?.detail || JSON.stringify(error.response?.data) || 'Erreur lors de la création de l\'entreprise');
    } finally {
      setCreating(false);
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

  // Regrouper les entreprises par groupe
  const companiesByGroup: Record<string, Company[]> = {};
  const independentCompanies: Company[] = [];

  companies.forEach((company) => {
    if (company.group_id && company.group_name) {
      if (!companiesByGroup[company.group_id]) {
        companiesByGroup[company.group_id] = [];
      }
      companiesByGroup[company.group_id].push(company);
    } else {
      independentCompanies.push(company);
    }
  });

  return (
    <div>
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Gestion des Entreprises</h1>
        <p className="text-gray-600 mt-2">Gérez toutes les entreprises clientes de la plateforme</p>
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex-1 max-w-md">
          <input
            type="text"
            placeholder="Rechercher une entreprise..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadCompanies()}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
          />
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="ml-4 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors flex items-center space-x-2"
        >
          <span>+</span>
          <span>Nouvelle entreprise</span>
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total</p>
          <p className="text-3xl font-bold text-gray-900">{companies.length}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Actives</p>
          <p className="text-3xl font-bold text-green-600">
            {companies.filter(c => c.is_active).length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Inactives</p>
          <p className="text-3xl font-bold text-red-600">
            {companies.filter(c => !c.is_active).length}
          </p>
        </div>
      </div>

      {/* Groupes d'entreprises */}
      {Object.entries(companiesByGroup).map(([groupId, groupCompanies]) => (
        <div key={groupId} className="mb-8">
          <div className="bg-indigo-50 border-l-4 border-indigo-500 px-4 py-3 mb-2 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-indigo-900">
                📁 {groupCompanies[0].group_name}
              </h3>
              <p className="text-sm text-indigo-700">
                {groupCompanies.length} entreprise{groupCompanies.length > 1 ? 's' : ''}
              </p>
            </div>
            <button
              onClick={() => navigate(`/super-admin/groups/${groupId}`)}
              className="px-3 py-1 bg-indigo-600 text-white text-sm rounded hover:bg-indigo-700"
            >
              Voir le groupe
            </button>
          </div>

          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Entreprise</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">SIRET</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Employés</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Utilisateurs</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Statut</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {groupCompanies.map((company) => (
                  <tr key={company.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 cursor-pointer" onClick={() => navigate(`/super-admin/companies/${company.id}`)}>
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{company.company_name}</p>
                        <p className="text-sm text-gray-500">{company.email}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600 cursor-pointer" onClick={() => navigate(`/super-admin/companies/${company.id}`)}>
                      {company.siret || '-'}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 font-semibold cursor-pointer" onClick={() => navigate(`/super-admin/companies/${company.id}`)}>
                      {company.employees_count || 0}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 font-semibold cursor-pointer" onClick={() => navigate(`/super-admin/companies/${company.id}`)}>
                      {company.users_count || 0}
                    </td>
                    <td className="px-6 py-4 cursor-pointer" onClick={() => navigate(`/super-admin/companies/${company.id}`)}>
                      <span className={`px-3 py-1 rounded-full text-xs font-semibold ${company.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        {company.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleRemoveFromGroup(company); }}
                        className="px-3 py-1 bg-orange-100 text-orange-700 hover:bg-orange-200 rounded text-sm font-medium transition-colors"
                        title="Retirer du groupe"
                      >
                        Retirer
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleCompanyStatus(company.id, company.is_active); }}
                        className={`px-3 py-1 rounded text-sm font-medium transition-colors ${company.is_active ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200' : 'bg-green-100 text-green-700 hover:bg-green-200'}`}
                      >
                        {company.is_active ? 'Désactiver' : 'Activer'}
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); openDeleteConfirmModal(company); }}
                        className="px-3 py-1 bg-red-100 text-red-700 hover:bg-red-200 rounded text-sm font-medium transition-colors"
                        title="Supprimer définitivement"
                      >
                        🗑️ Supprimer
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}

      {/* Entreprises indépendantes */}
      {independentCompanies.length > 0 && (
        <div>
          <div className="bg-gray-50 border-l-4 border-gray-400 px-4 py-3 mb-2">
            <h3 className="text-lg font-bold text-gray-900">🏢 Entreprises Indépendantes</h3>
            <p className="text-sm text-gray-600">
              {independentCompanies.length} entreprise{independentCompanies.length > 1 ? 's' : ''} sans groupe
            </p>
          </div>

          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Entreprise</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">SIRET</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Groupe</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Employés</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Utilisateurs</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Statut</th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {independentCompanies.map((company) => (
                  <tr key={company.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4 cursor-pointer" onClick={() => navigate(`/super-admin/companies/${company.id}`)}>
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{company.company_name}</p>
                        <p className="text-sm text-gray-500">{company.email}</p>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600 cursor-pointer" onClick={() => navigate(`/super-admin/companies/${company.id}`)}>
                      {company.siret || '-'}
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={(e) => { e.stopPropagation(); openGroupAssignModal(company); }}
                        className="px-2 py-1 bg-gray-100 text-gray-600 hover:bg-gray-200 text-xs rounded"
                      >
                        + Assigner au groupe
                      </button>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 font-semibold cursor-pointer" onClick={() => navigate(`/super-admin/companies/${company.id}`)}>
                      {company.employees_count || 0}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-900 font-semibold cursor-pointer" onClick={() => navigate(`/super-admin/companies/${company.id}`)}>
                      {company.users_count || 0}
                    </td>
                    <td className="px-6 py-4 cursor-pointer" onClick={() => navigate(`/super-admin/companies/${company.id}`)}>
                      <span className={`px-3 py-1 rounded-full text-xs font-semibold ${company.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                        {company.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleCompanyStatus(company.id, company.is_active); }}
                        className={`px-3 py-1 rounded text-sm font-medium transition-colors ${company.is_active ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200' : 'bg-green-100 text-green-700 hover:bg-green-200'}`}
                      >
                        {company.is_active ? 'Désactiver' : 'Activer'}
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); openDeleteConfirmModal(company); }}
                        className="px-3 py-1 bg-red-100 text-red-700 hover:bg-red-200 rounded text-sm font-medium transition-colors"
                        title="Supprimer définitivement"
                      >
                        🗑️ Supprimer
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {companies.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500">Aucune entreprise trouvée</p>
        </div>
      )}

      {/* Modal de création */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200 sticky top-0 bg-white">
              <div className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-gray-900">Nouvelle entreprise</h2>
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="text-gray-400 hover:text-gray-600 text-2xl"
                >
                  ×
                </button>
              </div>
            </div>

            <form onSubmit={createCompany} className="p-6 space-y-6">
              {/* Logo de l'entreprise */}
              <div className="pb-6">
                <LogoUploader
                  currentLogoUrl={formData.logo_url}
                  currentLogoScale={formData.logo_scale}
                  entityType="company"
                  onLogoChange={(logoUrl) => setFormData({ ...formData, logo_url: logoUrl })}
                  onFileChange={(file) => setLogoFile(file)}
                  onScaleChange={(scale) => setFormData({ ...formData, logo_scale: scale })}
                  size="lg"
                />
              </div>

              {/* Informations entreprise */}
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Informations de l'entreprise</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Nom de l'entreprise *
                    </label>
                    <input
                      type="text"
                      required
                      value={formData.company_name}
                      onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      SIRET
                    </label>
                    <input
                      type="text"
                      value={formData.siret}
                      onChange={(e) => setFormData({ ...formData, siret: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Email entreprise
                    </label>
                    <input
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Téléphone
                    </label>
                    <input
                      type="tel"
                      value={formData.phone}
                      onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                    />
                  </div>
                </div>
              </div>

              {/* Informations administrateur */}
              <div className="border-t pt-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">Administrateur de l'entreprise</h3>
                  <label className="flex items-center space-x-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={createWithAdmin}
                      onChange={(e) => setCreateWithAdmin(e.target.checked)}
                      className="w-4 h-4 text-indigo-600 border-gray-300 rounded focus:ring-indigo-500"
                    />
                    <span className="text-sm text-gray-700">Créer maintenant</span>
                  </label>
                </div>

                {createWithAdmin ? (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Prénom *
                      </label>
                      <input
                        type="text"
                        required={createWithAdmin}
                        value={formData.admin_first_name}
                        onChange={(e) => setFormData({ ...formData, admin_first_name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Nom *
                      </label>
                      <input
                        type="text"
                        required={createWithAdmin}
                        value={formData.admin_last_name}
                        onChange={(e) => setFormData({ ...formData, admin_last_name: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Email *
                      </label>
                      <input
                        type="email"
                        required={createWithAdmin}
                        value={formData.admin_email}
                        onChange={(e) => setFormData({ ...formData, admin_email: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Mot de passe *
                      </label>
                      <input
                        type="password"
                        required={createWithAdmin}
                        minLength={6}
                        value={formData.admin_password}
                        onChange={(e) => setFormData({ ...formData, admin_password: e.target.value })}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                      />
                      <p className="text-xs text-gray-500 mt-1">Minimum 6 caractères</p>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 italic">
                    L'administrateur pourra être ajouté ultérieurement
                  </p>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end space-x-3 pt-6 border-t">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {creating ? 'Création en cours...' : 'Créer l\'entreprise'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal d'assignation au groupe */}
      {showGroupAssignModal && selectedCompanyForGroup && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-gray-900">Assigner au groupe</h2>
                <button
                  onClick={() => setShowGroupAssignModal(false)}
                  className="text-gray-400 hover:text-gray-600 text-2xl"
                >
                  ×
                </button>
              </div>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <p className="text-sm text-gray-600 mb-2">Entreprise</p>
                <p className="font-semibold text-gray-900">{selectedCompanyForGroup.company_name}</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Groupe *
                </label>
                <select
                  value={selectedGroupId}
                  onChange={(e) => setSelectedGroupId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                >
                  <option value="">-- Sélectionner un groupe --</option>
                  {groups.map((group) => (
                    <option key={group.id} value={group.id}>
                      {group.group_name}
                    </option>
                  ))}
                </select>
                {groups.length === 0 && (
                  <p className="text-xs text-gray-500 mt-1">
                    Aucun groupe disponible. Créez d'abord un groupe.
                  </p>
                )}
              </div>
            </div>

            <div className="flex items-center justify-end space-x-3 p-6 border-t">
              <button
                type="button"
                onClick={() => setShowGroupAssignModal(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Annuler
              </button>
              <button
                onClick={handleAssignToGroup}
                disabled={assigningToGroup || !selectedGroupId}
                className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {assigningToGroup ? 'Assignation en cours...' : 'Assigner'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal de confirmation de suppression permanente */}
      {showDeleteConfirmModal && companyToDelete && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full">
            <div className="p-6 border-b border-gray-200">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-bold text-red-600">⚠️ Suppression Définitive</h2>
                <button
                  onClick={() => setShowDeleteConfirmModal(false)}
                  className="text-gray-400 hover:text-gray-600 text-2xl"
                  disabled={deleting}
                >
                  ×
                </button>
              </div>
            </div>

            <div className="p-6">
              <div className="bg-red-50 border-l-4 border-red-500 p-4 mb-4">
                <div className="flex">
                  <div className="flex-shrink-0">
                    <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <div className="ml-3">
                    <h3 className="text-sm font-medium text-red-800">
                      ATTENTION : Cette action est IRRÉVERSIBLE !
                    </h3>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <p className="text-gray-900 font-semibold">
                  Vous êtes sur le point de supprimer définitivement l'entreprise :
                </p>
                <div className="bg-gray-100 p-4 rounded-lg">
                  <p className="font-bold text-lg text-gray-900">{companyToDelete.company_name}</p>
                  <p className="text-sm text-gray-600">{companyToDelete.email}</p>
                  {companyToDelete.siret && (
                    <p className="text-sm text-gray-600">SIRET: {companyToDelete.siret}</p>
                  )}
                  <div className="mt-2 flex items-center space-x-4 text-sm">
                    <span className="text-gray-700">👥 {companyToDelete.employees_count || 0} employés</span>
                    <span className="text-gray-700">🔐 {companyToDelete.users_count || 0} utilisateurs</span>
                  </div>
                </div>

                <div className="bg-yellow-50 border border-yellow-200 p-4 rounded-lg">
                  <h4 className="font-semibold text-yellow-800 mb-2">Les données suivantes seront supprimées définitivement :</h4>
                  <ul className="list-disc list-inside text-sm text-yellow-700 space-y-1">
                    <li>Tous les employés ({companyToDelete.employees_count || 0})</li>
                    <li>Toutes les fiches de paie</li>
                    <li>Tous les contrats</li>
                    <li>Toutes les demandes d'absence</li>
                    <li>Toutes les notes de frais</li>
                    <li>Tous les plannings</li>
                    <li>Toutes les saisies mensuelles</li>
                    <li>Tous les accès utilisateurs à cette entreprise</li>
                    <li>Toutes les conventions collectives assignées</li>
                    <li>Toutes les configurations de paie</li>
                    <li>L'entreprise elle-même</li>
                  </ul>
                </div>

                <p className="text-sm text-red-600 font-semibold">
                  ⚠️ Cette action ne peut pas être annulée. Toutes les données seront perdues définitivement.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end space-x-3 p-6 border-t bg-gray-50">
              <button
                type="button"
                onClick={() => setShowDeleteConfirmModal(false)}
                disabled={deleting}
                className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-100 transition-colors disabled:opacity-50"
              >
                Annuler
              </button>
              <button
                onClick={handleDeleteCompanyPermanent}
                disabled={deleting}
                className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-semibold"
              >
                {deleting ? 'Suppression en cours...' : '🗑️ Supprimer Définitivement'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
