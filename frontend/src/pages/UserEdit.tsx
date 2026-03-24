import React, { useState, useEffect } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { Loader2, Save, User, Shield, AlertCircle, ArrowLeft } from 'lucide-react';
import {
  getUserDetail,
  updateUserWithPermissions,
  getRoleTemplates,
  getAccessibleCompaniesForUserCreation,
  UserUpdateWithPermissions,
  RoleTemplateDetail,
  AccessibleCompany,
} from '../api/permissions';
import PermissionsMatrix from '../components/PermissionsMatrix';
import { cn } from '../lib/utils';

const UserEdit: React.FC = () => {
  console.log('[UserEdit] 🎬 Component MOUNTING');

  const navigate = useNavigate();
  const { userId } = useParams<{ userId: string }>();

  console.log('[UserEdit] 📝 userId from useParams:', userId);
  console.log('[UserEdit] 📦 localStorage keys:', Object.keys(localStorage));

  // FIX: Utiliser 'activeCompanyId' (camelCase) au lieu de 'active_company_id'
  const companyId = localStorage.getItem('activeCompanyId') || '';

  console.log('[UserEdit] ✨ companyId resolved to:', companyId);
  console.log('[UserEdit] 🎯 Will call loadUserData?', !!(userId && companyId));

  // États
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [canEdit, setCanEdit] = useState(false);

  // Données utilisateur
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    job_title: '',
    email: '',
  });

  // Rôle et permissions
  const [currentRole, setCurrentRole] = useState<'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom'>('collaborateur');
  const [selectedRole, setSelectedRole] = useState<'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom'>('collaborateur');
  const [roleTemplateId, setRoleTemplateId] = useState<string | undefined>(undefined);
  const [permissionIds, setPermissionIds] = useState<string[]>([]);
  const [templates, setTemplates] = useState<RoleTemplateDetail[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  // Rôles accessibles pour l'utilisateur courant
  const [availableRoles, setAvailableRoles] = useState<string[]>([]);

  useEffect(() => {
    if (userId && companyId) {
      loadUserData();
      loadAvailableRoles();
    }
  }, [userId, companyId]);

  useEffect(() => {
    if (selectedRole && selectedRole !== 'custom') {
      loadTemplates(selectedRole);
    }
  }, [selectedRole]);

  const loadUserData = async () => {
    if (!userId || !companyId) {
      console.log('[UserEdit] ❌ Missing userId or companyId', { userId, companyId });
      return;
    }

    console.log('[UserEdit] 🚀 START Loading user data...', { userId, companyId });
    console.log('[UserEdit] 🔍 getUserDetail function:', getUserDetail);

    try {
      setLoading(true);
      console.log('[UserEdit] ⏳ BEFORE calling getUserDetail...');
      console.log('[UserEdit] 📡 URL will be:', `/api/users/${userId}?company_id=${companyId}`);

      const data = await getUserDetail(userId, companyId);

      console.log('[UserEdit] ✅ AFTER getUserDetail - User data received:', data);

      setFormData({
        first_name: data.first_name,
        last_name: data.last_name,
        job_title: data.job_title || '',
        email: data.email,
      });

      setCurrentRole(data.role);
      setSelectedRole(data.role);
      setRoleTemplateId(data.role_template_id);
      setPermissionIds(data.permission_ids || []);
      setCanEdit(data.can_edit);

      console.log('[UserEdit] State updated:', {
        role: data.role,
        templateId: data.role_template_id,
        permissionsCount: data.permission_ids?.length || 0,
        canEdit: data.can_edit
      });

      if (!data.can_edit) {
        setError("Vous n'avez pas les droits pour modifier cet utilisateur");
      }
    } catch (err: any) {
      console.error('[UserEdit] ❌ CATCH - Error loading user data:', err);
      console.error('[UserEdit] Error name:', err.name);
      console.error('[UserEdit] Error message:', err.message);
      console.error('[UserEdit] Error response:', err.response);
      console.error('[UserEdit] Error response status:', err.response?.status);
      console.error('[UserEdit] Error response data:', err.response?.data);
      console.error('[UserEdit] Full error object:', JSON.stringify(err, null, 2));
      setError(err.response?.data?.detail || 'Erreur lors du chargement de l\'utilisateur');
    } finally {
      setLoading(false);
      console.log('[UserEdit] 🏁 FINALLY - Loading complete');
    }
  };

  const loadTemplates = async (role: string) => {
    try {
      setLoadingTemplates(true);
      const data = await getRoleTemplates(companyId, role);
      setTemplates(data);
    } catch (err) {
      console.error('Erreur lors du chargement des templates:', err);
    } finally {
      setLoadingTemplates(false);
    }
  };

  const loadAvailableRoles = async () => {
    try {
      const companies = await getAccessibleCompaniesForUserCreation();
      const currentCompany = companies.find((c: AccessibleCompany) => c.company_id === companyId);
      if (currentCompany) {
        setAvailableRoles(currentCompany.can_create_roles);
      }
    } catch (err) {
      console.error('Erreur lors du chargement des rôles disponibles:', err);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!canEdit) {
      setError("Vous n'avez pas les droits pour modifier cet utilisateur");
      return;
    }

    if (!userId || !companyId) return;

    try {
      setSaving(true);
      setError(null);

      const updateData: UserUpdateWithPermissions = {
        first_name: formData.first_name,
        last_name: formData.last_name,
        job_title: formData.job_title || undefined,
        company_id: companyId,
        base_role: selectedRole !== currentRole ? selectedRole : undefined,
        role_template_id: roleTemplateId || undefined,
        permission_ids: permissionIds,
      };

      await updateUserWithPermissions(userId, updateData);

      // Rediriger vers la liste
      navigate('/users');
    } catch (err: any) {
      console.error('Erreur lors de la sauvegarde:', err);
      setError(err.response?.data?.detail || 'Erreur lors de la modification');
    } finally {
      setSaving(false);
    }
  };

  const roleLabels: { [key: string]: string } = {
    admin: 'Administrateur',
    rh: 'Ressources Humaines',
    salarie: 'Salarié',
    custom: 'Personnalisé',
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-6">
      <Link to="/users" className="flex items-center text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="mr-2 h-4 w-4" /> Retour à la liste des utilisateurs
      </Link>

      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">
          Modifier {formData.first_name} {formData.last_name}
        </h1>
        <p className="text-gray-600">{formData.email}</p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
            <p className="text-red-800">{error}</p>
          </div>
        </div>
      )}

      {!canEdit && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-yellow-600 flex-shrink-0" />
            <p className="text-yellow-800">
              Vous pouvez consulter ce profil mais vous n'avez pas les droits pour le modifier (hiérarchie des rôles).
            </p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* Informations personnelles */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-6">
            <User className="h-6 w-6 text-blue-600" />
            <h2 className="text-xl font-semibold text-gray-900">Informations personnelles</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Prénom *</label>
              <input
                type="text"
                value={formData.first_name}
                onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                required
                disabled={!canEdit}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Nom *</label>
              <input
                type="text"
                value={formData.last_name}
                onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                required
                disabled={!canEdit}
              />
            </div>

            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-gray-700 mb-2">Titre du poste</label>
              <input
                type="text"
                value={formData.job_title}
                onChange={(e) => setFormData({ ...formData, job_title: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                disabled={!canEdit}
              />
            </div>
          </div>
        </div>

        {/* Rôle et permissions */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-6">
            <Shield className="h-6 w-6 text-blue-600" />
            <h2 className="text-xl font-semibold text-gray-900">Rôle et permissions</h2>
          </div>

          <div className="space-y-6">
            {/* Sélection du rôle */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Rôle de base</label>
              <p className="text-sm text-gray-500 mb-3">
                Seuls les rôles que vous êtes autorisé à assigner sont disponibles. Les autres sont grisés.
              </p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {(['admin', 'rh', 'collaborateur_rh', 'collaborateur', 'custom'] as const).map((role) => {
                  const isRoleAvailable = availableRoles.includes(role);
                  const isDisabled = !canEdit || !isRoleAvailable;

                  return (
                    <button
                      key={role}
                      type="button"
                      onClick={() => isRoleAvailable && setSelectedRole(role)}
                      disabled={isDisabled}
                      className={cn(
                        'p-3 border-2 rounded-lg text-left transition-all',
                        selectedRole === role
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 bg-white hover:border-blue-300',
                        isDisabled && 'opacity-50 cursor-not-allowed'
                      )}
                      title={!isRoleAvailable ? 'Vous ne pouvez pas assigner ce rôle' : ''}
                    >
                      <Shield
                        className={cn(
                          'h-5 w-5 mb-1',
                          selectedRole === role ? 'text-blue-600' : 'text-gray-400'
                        )}
                      />
                      <div className="font-medium text-sm text-gray-900">{roleLabels[role]}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Templates de rôles */}
            {selectedRole !== 'custom' && templates.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Template de rôle (optionnel)
                </label>
                <select
                  value={roleTemplateId || ''}
                  onChange={(e) => setRoleTemplateId(e.target.value || undefined)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  disabled={!canEdit}
                >
                  <option value="">Aucun template</option>
                  {templates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name} {template.job_title && `- ${template.job_title}`}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Matrice de permissions */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Permissions ({permissionIds.length} sélectionnées)
              </label>
              <p className="text-sm text-gray-500 mb-3">
                Les permissions grisées nécessitent un niveau d'accès supérieur au vôtre et ne peuvent pas être assignées.
              </p>
              <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                <PermissionsMatrix
                  companyId={companyId}
                  selectedPermissions={permissionIds}
                  onPermissionsChange={setPermissionIds}
                  disabled={!canEdit}
                  restrictToAvailable={true}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Boutons d'action */}
        {canEdit && (
          <div className="flex justify-end gap-4">
            <button
              type="button"
              onClick={() => navigate('/users')}
              className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50"
            >
              {saving ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Enregistrement...
                </>
              ) : (
                <>
                  <Save className="h-5 w-5" />
                  Enregistrer
                </>
              )}
            </button>
          </div>
        )}
      </form>
    </div>
  );
};

export default UserEdit;
