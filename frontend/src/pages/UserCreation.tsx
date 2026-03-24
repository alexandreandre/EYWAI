import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Loader2, Save, X, User, Building, Shield, Key, AlertCircle, Check, Plus, ChevronDown, ChevronUp, Sparkles, ArrowLeft } from 'lucide-react';
import {
  createUserWithPermissions,
  getRoleTemplates,
  getRoleTemplate,
  getAccessibleCompaniesForUserCreation,
  quickCreateRoleTemplate,
  RoleTemplateDetail,
  AccessibleCompany,
  UserCompanyAccessData,
} from '../api/permissions';
import PermissionsMatrix from '../components/PermissionsMatrix';
import { cn } from '../lib/utils';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { CONTRACT_TYPES, EMPLOYEE_STATUSES } from '../constants/contracts';

interface CompanyAccessState extends UserCompanyAccessData {
  enabled: boolean;
  expanded: boolean;
  templates: RoleTemplateDetail[];
  loadingTemplates: boolean;
  isCreatingNewRole: boolean;
  customRoles: RoleTemplateDetail[]; // Rôles custom existants pour cette entreprise
  loadingCustomRoles: boolean;
  contract_type?: string;
  statut?: string;
  newRoleData: {
    name: string;
    job_title: string;
    description: string;
    base_role: 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom';
    hasRhAccess: boolean;
    hasCollaboratorAccess: boolean;
  };
}

const UserCreation: React.FC = () => {
  const navigate = useNavigate();

  // États du formulaire de base
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: '',
    phone: '',
  });

  // Accès entreprises
  const [accessibleCompanies, setAccessibleCompanies] = useState<AccessibleCompany[]>([]);
  const [companyAccesses, setCompanyAccesses] = useState<{ [companyId: string]: CompanyAccessState }>({});

  // États généraux
  const [loading, setLoading] = useState(false);
  const [loadingCompanies, setLoadingCompanies] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [creatingTemplate, setCreatingTemplate] = useState(false);

  // Charger les entreprises accessibles
  useEffect(() => {
    loadAccessibleCompanies();
  }, []);

  const loadAccessibleCompanies = async () => {
    try {
      setLoadingCompanies(true);
      const companies = await getAccessibleCompaniesForUserCreation();
      setAccessibleCompanies(companies);

      // Initialiser les états d'accès pour chaque entreprise
      const initialAccesses: { [companyId: string]: CompanyAccessState } = {};
      companies.forEach((company) => {
        initialAccesses[company.company_id] = {
          company_id: company.company_id,
          base_role: '' as any,
          is_primary: false,
          role_template_id: undefined,
          permission_ids: [],
          enabled: false,
          expanded: false,
          templates: [],
          loadingTemplates: false,
          isCreatingNewRole: false,
          customRoles: [],
          loadingCustomRoles: false,
          contract_type: 'CDI',
          statut: 'Non-Cadre',
          newRoleData: {
            name: '',
            job_title: '',
            description: '',
            base_role: 'custom',
            hasRhAccess: false,
            hasCollaboratorAccess: false,
          },
        };
      });
      setCompanyAccesses(initialAccesses);

      // Si une seule entreprise, l'activer par défaut
      if (companies.length === 1) {
        handleToggleCompany(companies[0].company_id, true);
        setCompanyAccesses(prev => ({
          ...prev,
          [companies[0].company_id]: {
            ...prev[companies[0].company_id],
            is_primary: true
          }
        }));
      }
    } catch (err) {
      setError('Impossible de charger les entreprises');
      console.error(err);
    } finally {
      setLoadingCompanies(false);
    }
  };

  const loadRoleTemplatesForCompany = async (companyId: string, baseRole: string) => {
    try {
      setCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: { ...prev[companyId], loadingTemplates: true },
      }));

      const templates = await getRoleTemplates(companyId, baseRole, true);

      setCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: {
          ...prev[companyId],
          templates,
          loadingTemplates: false,
        },
      }));
    } catch (err) {
      console.error('Erreur lors du chargement des templates:', err);
      setCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: { ...prev[companyId], loadingTemplates: false },
      }));
    }
  };

  const loadTemplatePermissions = async (companyId: string, templateId: string) => {
    try {
      const template = await getRoleTemplate(templateId);
      const permissionIds = template.permissions.map((p) => p.id);
      setCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: {
          ...prev[companyId],
          permission_ids: permissionIds,
        },
      }));
    } catch (err) {
      console.error('Erreur lors du chargement des permissions du template:', err);
    }
  };

  const loadCustomRolesForCompany = async (companyId: string) => {
    try {
      setCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: { ...prev[companyId], loadingCustomRoles: true },
      }));

      // Charger tous les rôles personnalisés de l'entreprise (tous base_role : custom, collaborateur_rh, rh, etc.)
      // pour pouvoir réutiliser un template (ex. "Directeur de site") lors de la création d'un autre collaborateur
      const customRoles = await getRoleTemplates(companyId, undefined, false);

      setCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: {
          ...prev[companyId],
          customRoles,
          loadingCustomRoles: false,
        },
      }));
    } catch (err) {
      console.error('Erreur lors du chargement des rôles custom:', err);
      setCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: { ...prev[companyId], loadingCustomRoles: false },
      }));
    }
  };

  const handleToggleCompany = (companyId: string, enabled: boolean) => {
    setCompanyAccesses((prev) => ({
      ...prev,
      [companyId]: {
        ...prev[companyId],
        enabled,
        expanded: enabled,
      },
    }));

    // Charger les rôles custom quand on active l'entreprise
    if (enabled) {
      loadCustomRolesForCompany(companyId);
    }
  };

  const handleToggleExpand = (companyId: string) => {
    setCompanyAccesses((prev) => ({
      ...prev,
      [companyId]: {
        ...prev[companyId],
        expanded: !prev[companyId].expanded,
      },
    }));
  };

  const handleSetPrimary = (companyId: string) => {
    setCompanyAccesses((prev) => {
      const updated = { ...prev };
      // Retirer is_primary de toutes les entreprises
      Object.keys(updated).forEach((id) => {
        updated[id] = { ...updated[id], is_primary: false };
      });
      // Définir comme primaire
      updated[companyId] = { ...updated[companyId], is_primary: true };
      return updated;
    });
  };

  const handleSelectNewRole = (companyId: string) => {
    setCompanyAccesses((prev) => ({
      ...prev,
      [companyId]: {
        ...prev[companyId],
        base_role: '' as any,
        isCreatingNewRole: true,
        role_template_id: undefined,
        permission_ids: [],
        newRoleData: {
          name: '',
          job_title: '',
          description: '',
          base_role: 'custom',
          hasRhAccess: false,
          hasCollaboratorAccess: false,
        },
      },
    }));
  };

  const handleRoleChange = (companyId: string, role: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur') => {
    setCompanyAccesses((prev) => ({
      ...prev,
      [companyId]: {
        ...prev[companyId],
        base_role: role,
        isCreatingNewRole: false,
        role_template_id: undefined,
        permission_ids: [],
      },
    }));

    // Charger les templates pour ce rôle
    loadRoleTemplatesForCompany(companyId, role);
  };

  const handleSelectExistingCustomRole = async (companyId: string, roleTemplateId: string) => {
    try {
      // Charger les permissions et le base_role du template (ex. Directeur de site → collaborateur_rh)
      const template = await getRoleTemplate(roleTemplateId);
      const permissionIds = template.permissions.map((p) => p.id);
      const templateBaseRole = (template.base_role || 'custom') as 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom';

      setCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: {
          ...prev[companyId],
          base_role: templateBaseRole,
          isCreatingNewRole: false,
          role_template_id: roleTemplateId,
          permission_ids: permissionIds,
        },
      }));
    } catch (err) {
      console.error('Erreur lors du chargement du rôle custom:', err);
      setError('Erreur lors du chargement du rôle');
    }
  };

  const handleTemplateChange = (companyId: string, templateId: string) => {
    setCompanyAccesses((prev) => ({
      ...prev,
      [companyId]: {
        ...prev[companyId],
        role_template_id: templateId || undefined,
      },
    }));

    if (templateId) {
      loadTemplatePermissions(companyId, templateId);
    } else {
      setCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: {
          ...prev[companyId],
          permission_ids: [],
        },
      }));
    }
  };

  const handlePermissionsChange = (companyId: string, permissions: string[]) => {
    setCompanyAccesses((prev) => ({
      ...prev,
      [companyId]: {
        ...prev[companyId],
        permission_ids: permissions,
      },
    }));
  };

  const handleCreateNewRoleTemplate = async (companyId: string) => {
    const access = companyAccesses[companyId];

    if (!access.newRoleData.name || !access.newRoleData.job_title) {
      setError('Veuillez remplir tous les champs requis pour le nouveau rôle');
      return;
    }

    if (access.permission_ids.length === 0) {
      setError('Veuillez sélectionner au moins une permission pour ce nouveau rôle');
      return;
    }

    if (!access.newRoleData.hasRhAccess && !access.newRoleData.hasCollaboratorAccess) {
      setError('Veuillez sélectionner au moins un type d\'accès (RH ou Collaborateur)');
      return;
    }

    try {
      setCreatingTemplate(true);
      setError(null);

      // Déterminer le base_role selon les accès sélectionnés
      let baseRole: 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom' = access.newRoleData.base_role;
      
      // Si les accès sont définis, utiliser ceux-ci pour déterminer le base_role
      if (access.newRoleData.hasRhAccess && access.newRoleData.hasCollaboratorAccess) {
        baseRole = 'collaborateur_rh';
      } else if (access.newRoleData.hasRhAccess) {
        baseRole = 'rh';
      } else if (access.newRoleData.hasCollaboratorAccess) {
        baseRole = 'collaborateur';
      }
      // Sinon utiliser le base_role sélectionné (par défaut 'custom')

      const result = await quickCreateRoleTemplate({
        company_id: companyId,
        name: access.newRoleData.name,
        job_title: access.newRoleData.job_title,
        base_role: baseRole,
        description: access.newRoleData.description,
        permission_ids: access.permission_ids,
      });

      // Mettre à jour l'état avec le template créé
      setCompanyAccesses((prev) => ({
        ...prev,
        [companyId]: {
          ...prev[companyId],
          base_role: baseRole,
          role_template_id: result.template_id,
          isCreatingNewRole: false,
        },
      }));

      // Recharger les rôles custom pour afficher le nouveau dans la grille
      await loadCustomRolesForCompany(companyId);

    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erreur lors de la création du template');
      console.error(err);
    } finally {
      setCreatingTemplate(false);
    }
  };

  const validateForm = (): boolean => {
    setError(null);

    if (!formData.email || !formData.email.includes('@')) {
      setError('Email invalide');
      return false;
    }

    if (!formData.password || formData.password.length < 8) {
      setError('Le mot de passe doit contenir au moins 8 caractères');
      return false;
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Les mots de passe ne correspondent pas');
      return false;
    }

    if (!formData.first_name || !formData.last_name) {
      setError('Prénom et nom requis');
      return false;
    }

    // Vérifier qu'au moins une entreprise est activée
    const enabledCompanies = Object.values(companyAccesses).filter((c) => c.enabled);
    if (enabledCompanies.length === 0) {
      setError('Veuillez sélectionner au moins une entreprise');
      return false;
    }

    // Si plusieurs entreprises : exiger qu'une soit marquée comme primaire
    if (enabledCompanies.length > 1) {
      const primaryCompany = enabledCompanies.find((c) => c.is_primary);
      if (!primaryCompany) {
        setError('Veuillez marquer une entreprise comme primaire');
        return false;
      }
    }

    // Vérifier que toutes les entreprises activées ont un rôle
    for (const access of enabledCompanies) {
      if (access.isCreatingNewRole) {
        setError('Veuillez terminer la création du nouveau rôle ou sélectionner un rôle existant');
        return false;
      }
      if (!access.base_role) {
        setError('Veuillez sélectionner un rôle pour toutes les entreprises activées');
        return false;
      }
    }

    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) return;

    try {
      setLoading(true);
      setError(null);

      // Construire la liste des accès entreprises
      // Si une seule entreprise, elle est automatiquement primaire
      const enabledList = Object.values(companyAccesses).filter((c) => c.enabled);
      const isSingleCompany = enabledList.length === 1;
      const enabledAccesses = enabledList.map((c) => {
        const access: any = {
          company_id: c.company_id,
          base_role: c.base_role,
          is_primary: isSingleCompany ? true : c.is_primary,
          role_template_id: c.role_template_id,
          permission_ids: c.permission_ids,
        };
        
        // Ajouter contract_type et statut si présents (pour les accès collaborateur)
        if (c.contract_type) {
          access.contract_type = c.contract_type;
        }
        if (c.statut) {
          access.statut = c.statut;
        }
        
        return access;
      });

      await createUserWithPermissions({
        email: formData.email,
        password: formData.password,
        first_name: formData.first_name,
        last_name: formData.last_name,
        phone: formData.phone || undefined,
        company_accesses: enabledAccesses,
      });

      setSuccess(true);
      setTimeout(() => {
        navigate('/users');
      }, 2000);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Erreur lors de la création de l'utilisateur");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    navigate(-1);
  };

  if (loadingCompanies) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (accessibleCompanies.length === 0) {
    return (
      <div className="max-w-2xl mx-auto py-12">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <AlertCircle className="h-12 w-12 text-yellow-600 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-center mb-2">Aucune entreprise accessible</h2>
          <p className="text-gray-600 text-center">
            Vous n'avez pas les droits nécessaires pour créer des utilisateurs dans une entreprise.
          </p>
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="max-w-2xl mx-auto py-12">
        <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-center">
          <Check className="h-16 w-16 text-green-600 mx-auto mb-4" />
          <h2 className="text-2xl font-semibold text-green-900 mb-2">Utilisateur créé avec succès!</h2>
          <p className="text-green-700">Redirection en cours...</p>
        </div>
      </div>
    );
  }

  const roleLabels: { [key: string]: string } = {
    admin: 'Administrateur',
    rh: 'Ressources Humaines',
    collaborateur_rh: 'Collaborateur RH',
    collaborateur: 'Collaborateur',
  };

  const enabledCount = Object.values(companyAccesses).filter((c) => c.enabled).length;

  return (
    <div className="max-w-6xl mx-auto py-8 px-4 space-y-2">
      <Link to="/users" className="flex items-center text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="mr-2 h-4 w-4" /> Retour à la liste des utilisateurs
      </Link>

      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Créer un nouvel utilisateur</h1>
        <p className="text-gray-600">Créez un utilisateur avec des accès multi-entreprises</p>
      </div>

      {error && (
        <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
            <p className="text-red-800">{error}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-8">
        {/* SECTION: Informations personnelles */}
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
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Email *</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Téléphone</label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>
        </div>

        {/* SECTION: Authentification */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-6">
            <Key className="h-6 w-6 text-blue-600" />
            <h2 className="text-xl font-semibold text-gray-900">Authentification</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Mot de passe *</label>
              <input
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                placeholder="Min. 8 caractères"
                required
                minLength={8}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Confirmer le mot de passe *
              </label>
              <input
                type="password"
                value={formData.confirmPassword}
                onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                required
              />
            </div>
          </div>
        </div>

        {/* SECTION: Accès entreprises */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <Building className="h-6 w-6 text-blue-600" />
              <h2 className="text-xl font-semibold text-gray-900">
                Accès entreprises ({enabledCount} sélectionnée{enabledCount > 1 ? 's' : ''})
              </h2>
            </div>
          </div>

          <div className="space-y-4">
            {accessibleCompanies.map((company) => {
              const access = companyAccesses[company.company_id];
              if (!access) return null;

              return (
                <div
                  key={company.company_id}
                  className={cn(
                    'border-2 rounded-lg p-4 transition-all',
                    access.enabled ? 'border-blue-500 bg-blue-50' : 'border-gray-200 bg-white'
                  )}
                >
                  {/* En-tête entreprise */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-3 flex-1">
                      <input
                        type="checkbox"
                        checked={access.enabled}
                        onChange={(e) => handleToggleCompany(company.company_id, e.target.checked)}
                        className="w-5 h-5 text-blue-600 rounded focus:ring-blue-500"
                      />
                      <div>
                        <div className="font-semibold text-gray-900">{company.company_name}</div>
                        <div className="text-sm text-gray-600">
                          Peut créer : {company.can_create_roles
                            .filter((r) => r !== 'custom')
                            .map((r) => roleLabels[r])
                            .join(', ')}{company.can_create_roles.includes('custom') ? ' + Rôles personnalisés' : ''}
                        </div>
                      </div>
                    </div>

                    {access.enabled && (
                      <div className="flex items-center gap-2">
                        {Object.values(companyAccesses).filter((c) => c.enabled).length > 1 && (
                          <label className="flex items-center gap-2 text-sm">
                            <input
                              type="radio"
                              name="primary_company"
                              checked={access.is_primary}
                              onChange={() => handleSetPrimary(company.company_id)}
                              className="w-4 h-4 text-blue-600 focus:ring-blue-500"
                            />
                            <span className="text-gray-700">Primaire</span>
                          </label>
                        )}
                        <button
                          type="button"
                          onClick={() => handleToggleExpand(company.company_id)}
                          className="p-1 hover:bg-blue-100 rounded"
                        >
                          {access.expanded ? (
                            <ChevronUp className="h-5 w-5 text-blue-600" />
                          ) : (
                            <ChevronDown className="h-5 w-5 text-blue-600" />
                          )}
                        </button>
                      </div>
                    )}
                  </div>

                  {/* Configuration détaillée */}
                  {access.enabled && access.expanded && (
                    <div className="mt-4 space-y-4 pl-8">
                      {/* Sélection du rôle */}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Rôle de base *
                        </label>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                          {/* Rôles de base (admin, rh, salarie) */}
                          {company.can_create_roles
                            .filter((role) => role !== 'custom')
                            .map((role) => (
                            <button
                              key={role}
                              type="button"
                              onClick={() =>
                                handleRoleChange(company.company_id, role as 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur')
                              }
                              className={cn(
                                'p-3 border-2 rounded-lg text-left transition-all',
                                access.base_role === role && !access.isCreatingNewRole
                                  ? 'border-blue-500 bg-blue-100'
                                  : 'border-gray-200 bg-white hover:border-blue-300'
                              )}
                            >
                              <Shield
                                className={cn(
                                  'h-5 w-5 mb-1',
                                  access.base_role === role && !access.isCreatingNewRole ? 'text-blue-600' : 'text-gray-400'
                                )}
                              />
                              <div className="font-medium text-sm text-gray-900">{roleLabels[role]}</div>
                            </button>
                          ))}

                          {/* Rôles custom existants */}
                          {access.loadingCustomRoles ? (
                            <div className="p-3 border-2 border-gray-200 rounded-lg flex items-center justify-center bg-gray-50">
                              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
                            </div>
                          ) : (
                            access.customRoles.map((customRole) => (
                              <button
                                key={customRole.id}
                                type="button"
                                onClick={() => handleSelectExistingCustomRole(company.company_id, customRole.id)}
                                className={cn(
                                  'p-3 border-2 rounded-lg text-left transition-all',
                                  access.role_template_id === customRole.id && !access.isCreatingNewRole
                                    ? 'border-green-500 bg-green-100'
                                    : 'border-gray-200 bg-white hover:border-green-300'
                                )}
                              >
                                <Shield
                                  className={cn(
                                    'h-5 w-5 mb-1',
                                    access.role_template_id === customRole.id && !access.isCreatingNewRole ? 'text-green-600' : 'text-gray-400'
                                  )}
                                />
                                <div className="font-medium text-sm text-gray-900">{customRole.name}</div>
                                {customRole.job_title && (
                                  <div className="text-xs text-gray-500 mt-1">{customRole.job_title}</div>
                                )}
                              </button>
                            ))
                          )}

                          {/* Bouton Nouveau Rôle */}
                          <button
                            type="button"
                            onClick={() => handleSelectNewRole(company.company_id)}
                            className={cn(
                              'p-3 border-2 rounded-lg text-left transition-all',
                              access.isCreatingNewRole
                                ? 'border-purple-500 bg-purple-100'
                                : 'border-gray-200 bg-white hover:border-purple-300'
                            )}
                          >
                            <Sparkles
                              className={cn(
                                'h-5 w-5 mb-1',
                                access.isCreatingNewRole ? 'text-purple-600' : 'text-gray-400'
                              )}
                            />
                            <div className="font-medium text-sm text-gray-900">Nouveau Rôle</div>
                          </button>
                        </div>
                      </div>

                      {/* Type de contrat et Statut (affichés uniquement pour accès Collaborateur) */}
                      {access.enabled &&
                        access.expanded &&
                        (access.base_role === 'collaborateur' || access.base_role === 'collaborateur_rh') && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <Label className="block text-sm font-medium text-gray-700 mb-2">
                              Type de contrat
                            </Label>
                            <Select
                              value={access.contract_type ?? 'CDI'}
                              onValueChange={(value) =>
                                setCompanyAccesses((prev) => ({
                                  ...prev,
                                  [company.company_id]: {
                                    ...prev[company.company_id],
                                    contract_type: value,
                                  },
                                }))
                              }
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="Choisir..." />
                              </SelectTrigger>
                              <SelectContent>
                                {CONTRACT_TYPES.map((type) => (
                                  <SelectItem key={type} value={type}>
                                    {type}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                          <div>
                            <Label className="block text-sm font-medium text-gray-700 mb-2">
                              Statut
                            </Label>
                            <Select
                              value={access.statut ?? 'Non-Cadre'}
                              onValueChange={(value) =>
                                setCompanyAccesses((prev) => ({
                                  ...prev,
                                  [company.company_id]: {
                                    ...prev[company.company_id],
                                    statut: value,
                                  },
                                }))
                              }
                            >
                              <SelectTrigger>
                                <SelectValue placeholder="Choisir..." />
                              </SelectTrigger>
                              <SelectContent>
                                {EMPLOYEE_STATUSES.map((status) => (
                                  <SelectItem key={status} value={status}>
                                    {status}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>
                      )}

                      {/* Formulaire Nouveau Rôle */}
                      {access.isCreatingNewRole && (
                        <div className="bg-purple-50 border-2 border-purple-200 rounded-lg p-4 space-y-4">
                          <div className="flex items-center gap-2 mb-2">
                            <Sparkles className="h-5 w-5 text-purple-600" />
                            <h3 className="font-semibold text-purple-900">Créer un nouveau rôle personnalisé</h3>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                              <Label htmlFor={`new_role_name_${company.company_id}`}>Nom du rôle *</Label>
                              <Input
                                id={`new_role_name_${company.company_id}`}
                                value={access.newRoleData.name}
                                onChange={(e) =>
                                  setCompanyAccesses((prev) => ({
                                    ...prev,
                                    [company.company_id]: {
                                      ...prev[company.company_id],
                                      newRoleData: {
                                        ...prev[company.company_id].newRoleData,
                                        name: e.target.value,
                                      },
                                    },
                                  }))
                                }
                                placeholder="Ex: Responsable Paie"
                              />
                            </div>

                            <div>
                              <Label htmlFor={`new_role_job_${company.company_id}`}>Titre du poste *</Label>
                              <Input
                                id={`new_role_job_${company.company_id}`}
                                value={access.newRoleData.job_title}
                                onChange={(e) =>
                                  setCompanyAccesses((prev) => ({
                                    ...prev,
                                    [company.company_id]: {
                                      ...prev[company.company_id],
                                      newRoleData: {
                                        ...prev[company.company_id].newRoleData,
                                        job_title: e.target.value,
                                      },
                                    },
                                  }))
                                }
                                placeholder="Ex: Responsable de la paie"
                              />
                            </div>
                          </div>

                          <div>
                            <Label htmlFor={`new_role_desc_${company.company_id}`}>Description</Label>
                            <Textarea
                              id={`new_role_desc_${company.company_id}`}
                              value={access.newRoleData.description}
                              onChange={(e) =>
                                setCompanyAccesses((prev) => ({
                                  ...prev,
                                  [company.company_id]: {
                                    ...prev[company.company_id],
                                    newRoleData: {
                                      ...prev[company.company_id].newRoleData,
                                      description: e.target.value,
                                    },
                                  },
                                }))
                              }
                              placeholder="Description du rôle..."
                              rows={2}
                            />
                          </div>

                          {/* Sélecteur de type d'accès */}
                          <div>
                            <Label>Type d'accès *</Label>
                            <div className="mt-2 space-y-2">
                              <label className="flex items-center space-x-2 cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={access.newRoleData.hasRhAccess}
                                  onChange={(e) => {
                                    const hasRh = e.target.checked;
                                    const hasCollab = access.newRoleData.hasCollaboratorAccess;
                                    setCompanyAccesses((prev) => ({
                                      ...prev,
                                      [company.company_id]: {
                                        ...prev[company.company_id],
                                        newRoleData: {
                                          ...prev[company.company_id].newRoleData,
                                          hasRhAccess: hasRh,
                                          // Déterminer le base_role selon les accès
                                          base_role: hasRh && hasCollab ? 'collaborateur_rh' : 
                                                     hasRh ? 'rh' : 
                                                     hasCollab ? 'collaborateur' : 'custom',
                                        },
                                      },
                                    }));
                                  }}
                                  className="rounded border-gray-300"
                                />
                                <span className="text-sm text-gray-700">Accès RH</span>
                              </label>
                              <label className="flex items-center space-x-2 cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={access.newRoleData.hasCollaboratorAccess}
                                  onChange={(e) => {
                                    const hasCollab = e.target.checked;
                                    const hasRh = access.newRoleData.hasRhAccess;
                                    setCompanyAccesses((prev) => ({
                                      ...prev,
                                      [company.company_id]: {
                                        ...prev[company.company_id],
                                        newRoleData: {
                                          ...prev[company.company_id].newRoleData,
                                          hasCollaboratorAccess: hasCollab,
                                          // Déterminer le base_role selon les accès
                                          base_role: hasRh && hasCollab ? 'collaborateur_rh' : 
                                                     hasRh ? 'rh' : 
                                                     hasCollab ? 'collaborateur' : 'custom',
                                        },
                                      },
                                    }));
                                  }}
                                  className="rounded border-gray-300"
                                />
                                <span className="text-sm text-gray-700">Accès Collaborateur</span>
                              </label>
                              {!access.newRoleData.hasRhAccess && !access.newRoleData.hasCollaboratorAccess && (
                                <p className="text-xs text-red-600 mt-1">
                                  Veuillez sélectionner au moins un type d'accès
                                </p>
                              )}
                            </div>
                          </div>

                          <p className="text-sm text-purple-700">
                            Sélectionnez les permissions ci-dessous, puis le template sera créé automatiquement.
                          </p>
                        </div>
                      )}

                      {/* Matrice de permissions - seulement pour Nouveau Rôle */}
                      {access.isCreatingNewRole && (
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <label className="block text-sm font-medium text-gray-700">
                              Permissions * ({access.permission_ids.length} sélectionnées)
                            </label>
                            {access.isCreatingNewRole && (
                              <button
                                type="button"
                                onClick={() => handleCreateNewRoleTemplate(company.company_id)}
                                disabled={creatingTemplate}
                                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors flex items-center gap-2 disabled:opacity-50 text-sm"
                              >
                                {creatingTemplate ? (
                                  <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Création...
                                  </>
                                ) : (
                                  <>
                                    <Sparkles className="h-4 w-4" />
                                    Créer le rôle
                                  </>
                                )}
                              </button>
                            )}
                          </div>
                          <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                            <PermissionsMatrix
                              companyId={company.company_id}
                              selectedPermissions={access.permission_ids}
                              onPermissionsChange={(perms) =>
                                handlePermissionsChange(company.company_id, perms)
                              }
                              restrictToAvailable={true}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ACTIONS */}
        <div className="flex items-center justify-end gap-4">
          <button
            type="button"
            onClick={handleCancel}
            className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors flex items-center gap-2"
            disabled={loading}
          >
            <X className="h-5 w-5" />
            Annuler
          </button>
          <button
            type="submit"
            disabled={loading || enabledCount === 0}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                Création en cours...
              </>
            ) : (
              <>
                <Save className="h-5 w-5" />
                Créer l'utilisateur
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default UserCreation;
