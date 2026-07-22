import { log } from '@/lib/logger';
import { RhPageHeader } from '@/components/layout';
import React, { useState, useEffect } from 'react';
import { useNavigate, useParams, Link, useSearchParams } from 'react-router-dom';
import { Loader2, Save, User, Shield, AlertCircle, ArrowLeft } from 'lucide-react';
import {
  getUserDetail,
  updateUserWithPermissions,
  updateUserPermissions,
  getUserPermissionGrants,
  getRoleTemplates,
  getAccessibleCompaniesForUserCreation,
  buildPermissionGrantsPayload,
  syncPermissionGrants,
  UserUpdateWithPermissions,
  RoleTemplateDetail,
  AccessibleCompany,
  type PermissionGrantInput,
} from '../../api/permissions';
import PermissionsMatrix from '../../components/PermissionsMatrix';
import { PermissionScopeEditor } from '@/features/access-control';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { cn } from '../../lib/utils';
import { useCompany } from '../../contexts/CompanyContext';
import { AppUserRole, getRoleDisplayLabel } from '../../lib/userRoleLabels';

const UserEdit: React.FC = () => {
  const navigate = useNavigate();
  const { userId } = useParams<{ userId: string }>();
  const [searchParams] = useSearchParams();
  const { activeCompany } = useCompany();

  const companyId =
    searchParams.get('company_id') ||
    activeCompany?.company_id ||
    localStorage.getItem('activeCompanyId') ||
    '';

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
  const [permissionGrants, setPermissionGrants] = useState<PermissionGrantInput[]>([]);
  const [templates, setTemplates] = useState<RoleTemplateDetail[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  // Rôles accessibles pour l'utilisateur courant
  const [availableRoles, setAvailableRoles] = useState<string[]>([]);

  useEffect(() => {
    if (!userId) return;
    if (!companyId) {
      setLoading(false);
      setError(
        "Sélectionnez une entreprise dans le menu en haut ou ouvrez cette page depuis la liste des utilisateurs.",
      );
      return;
    }
    loadUserData();
    loadAvailableRoles();
  }, [userId, companyId]);

  useEffect(() => {
    if (selectedRole && selectedRole !== 'custom') {
      loadTemplates(selectedRole);
    }
  }, [selectedRole]);

  const loadUserData = async () => {
    if (!userId || !companyId) {
      return;
    }

    try {
      setLoading(true);

      const data = await getUserDetail(userId, companyId);

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

      if (data.role === 'custom') {
        try {
          const grants = await getUserPermissionGrants(userId, companyId);
          setPermissionGrants(
            grants.map((grant) => ({
              permission_id: grant.permission_id,
              scope_mode: grant.scope_mode,
              team_ids: grant.team_ids,
              targets: grant.targets,
            }))
          );
        } catch (grantErr) {
          log.error('[UserEdit] Erreur chargement grants:', grantErr);
          setPermissionGrants(syncPermissionGrants(data.permission_ids || [], []));
        }
      } else {
        setPermissionGrants([]);
      }

      if (!data.can_edit) {
        setError("Vous n'avez pas les droits pour modifier cet utilisateur");
      }
    } catch (err: any) {
      log.error('[UserEdit] Erreur chargement utilisateur:', err);
      setError(err.response?.data?.detail || 'Erreur lors du chargement de l\'utilisateur');
    } finally {
      setLoading(false);
    }
  };

  const loadTemplates = async (role: string) => {
    try {
      setLoadingTemplates(true);
      const data = await getRoleTemplates(companyId, role);
      setTemplates(data);
    } catch (err) {
      log.error('Erreur lors du chargement des templates:', err);
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
      log.error('Erreur lors du chargement des rôles disponibles:', err);
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
      };

      if (selectedRole !== 'custom') {
        updateData.permission_ids = permissionIds;
      }

      await updateUserWithPermissions(userId, updateData);

      if (selectedRole === 'custom') {
        const grantsPayload = buildPermissionGrantsPayload(permissionIds, permissionGrants);
        await updateUserPermissions(userId, companyId, permissionIds, grantsPayload);
      }

      // Rediriger vers la liste
      navigate('/users');
    } catch (err: any) {
      log.error('Erreur lors de la sauvegarde:', err);
      setError(err.response?.data?.detail || 'Erreur lors de la modification');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return <SharkFinLoader variant="fullPage" label="Chargement de l'utilisateur…" />;
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <Link to="/users" className="flex items-center text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="mr-2 h-4 w-4" /> Retour à la liste des utilisateurs
      </Link>

      <RhPageHeader
        title={`Modifier ${formData.first_name} ${formData.last_name}`}
        description={formData.email}
      />

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
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
                {(['admin', 'rh', 'collaborateur_rh', 'collaborateur', 'custom'] as const).map((role) => {
                  const isRoleAvailable = availableRoles.includes(role);
                  const isDisabled = !canEdit || !isRoleAvailable;

                  return (
                    <button
                      key={role}
                      type="button"
                      onClick={() => {
                        if (!isRoleAvailable) return;
                        setSelectedRole(role);
                        if (role === 'custom') {
                          setPermissionIds([]);
                          setPermissionGrants([]);
                          setRoleTemplateId(undefined);
                        }
                      }}
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
                      <div className="font-medium text-sm text-gray-900">
                        {getRoleDisplayLabel(role as AppUserRole)}
                      </div>
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

            {/* Matrice de permissions (rôle personnalisé uniquement) */}
            {selectedRole === 'custom' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Permissions ({permissionIds.length} sélectionnées)
                  </label>
                  <p className="text-sm text-gray-500 mb-3">
                    Choisissez manuellement les droits accordés. Les permissions grisées nécessitent un
                    niveau d&apos;accès supérieur au vôtre.
                  </p>
                  <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                    <PermissionsMatrix
                      companyId={companyId}
                      selectedPermissions={permissionIds}
                      onPermissionsChange={(permissions) => {
                        setPermissionIds(permissions);
                        setPermissionGrants((current) =>
                          syncPermissionGrants(permissions, current)
                        );
                      }}
                      disabled={!canEdit}
                      restrictToAvailable={true}
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Périmètre par permission
                  </label>
                  <PermissionScopeEditor
                    companyId={companyId}
                    selectedPermissionIds={permissionIds}
                    grants={permissionGrants}
                    onGrantsChange={setPermissionGrants}
                    disabled={!canEdit}
                  />
                </div>
              </>
            )}
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
