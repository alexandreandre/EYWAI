// frontend/src/pages/super-admin/CompanyDetails.tsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../../../api/apiClient';
import { fetchDsnCoverage } from '@/api/dsnImport';
import {
  DsnCoverageTimeline,
  dsnStatusLabel,
} from '@/features/dsn-import/components/DsnCoverageTimeline';
import {
  fetchAdminCompanyDetails,
  patchAdminCompany,
  type AdminCompanyDetails,
} from '@/api/adminCompanies';
import CollectiveAgreementCard from '@/components/CollectiveAgreementCard';
import { LogoUploader } from '../../../components/LogoUploader';
import { AdminPageHeader } from '@/features/admin/components/eywai/AdminPageHeader';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { Button } from '@/components/ui/button';
import NetEntreprisesConfigCard from '@/features/net-entreprises/components/NetEntreprisesConfigCard';
import {
  JeiSettingsFormFields,
  defaultJeiFormValues,
  type JeiFormValues,
} from '@/features/company/components/JeiSettingsFormFields';
import { EditCompanyDialog } from '@/pages/admin/eywai/companies/EditCompanyDialog';

import { log } from '@/lib/logger';
import { showErrorToast } from '@/lib/errorMessages';
import { toast } from '@/hooks/use-toast';
import { Pencil, Plus } from 'lucide-react';

function formatCompanyAddress(company: AdminCompanyDetails): string | null {
  if (company.adresse_rue) {
    const line = [company.adresse_code_postal, company.adresse_ville].filter(Boolean).join(' ');
    return line ? `${company.adresse_rue}, ${line}` : company.adresse_rue;
  }
  if (company.address && typeof company.address === 'object') {
    const values = Object.values(company.address).filter(Boolean);
    return values.length > 0 ? values.join(', ') : null;
  }
  return null;
}

function InfoField({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm text-foreground">{value?.trim() || 'Non renseigné'}</p>
    </div>
  );
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
  const [company, setCompany] = useState<AdminCompanyDetails | null>(null);
  const [showEditCompanyDialog, setShowEditCompanyDialog] = useState(false);
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
  // États pour édition et suppression
  const [showEditUserModal, setShowEditUserModal] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [updatingUser, setUpdatingUser] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data: dsnCoverage } = useQuery({
    queryKey: ['dsn-coverage', companyId],
    queryFn: () => fetchDsnCoverage(companyId as string),
    enabled: Boolean(companyId),
  });
  const [deletingUser, setDeletingUser] = useState<User | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [jeiForm, setJeiForm] = useState<JeiFormValues>(defaultJeiFormValues);
  const [savingJei, setSavingJei] = useState(false);

  useEffect(() => {
    loadCompanyDetails();
    loadUsers();
  }, [companyId]);

  const loadCompanyDetails = async () => {
    if (!companyId) return;
    try {
      setLoading(true);
      const data = await fetchAdminCompanyDetails(companyId);
      setCompany(data);
      setJeiForm({
        jei_enabled: Boolean(data.jei_enabled),
        date_creation_etablissement: data.date_creation_etablissement?.slice(0, 10) ?? '',
        taux_exoneration:
          typeof data.taux_exoneration === 'number' ? data.taux_exoneration : 1,
      });
    } catch (error) {
      log.error('Erreur:', error);
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
      log.error('Erreur:', error);
    } finally {
      setLoadingUsers(false);
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
      log.error('Erreur:', error);
      showErrorToast(error, {
        title: 'Création impossible',
        fallback: "La création de l'utilisateur a échoué. Réessayez.",
      });
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
      toast({ title: 'Utilisateur mis à jour' });
    } catch (error: any) {
      log.error('Erreur:', error);
      showErrorToast(error, {
        title: 'Mise à jour impossible',
        fallback: "La mise à jour de l'utilisateur a échoué. Réessayez.",
      });
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
      toast({ title: 'Utilisateur supprimé' });
    } catch (error: any) {
      log.error('Erreur:', error);
      showErrorToast(error, {
        title: 'Suppression impossible',
        fallback: "La suppression de l'utilisateur a échoué. Réessayez.",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const saveJeiSettings = async () => {
    if (!companyId) return;
    if (jeiForm.jei_enabled && !jeiForm.date_creation_etablissement) {
      toast({
        title: 'Date JEI requise',
        description:
          "Renseignez la date de création de l'établissement pour activer le statut JEI.",
        variant: 'destructive',
      });
      return;
    }
    try {
      setSavingJei(true);
      await patchAdminCompany(companyId, {
        jei_enabled: jeiForm.jei_enabled,
        date_creation_etablissement: jeiForm.jei_enabled
          ? jeiForm.date_creation_etablissement
          : null,
        taux_exoneration: jeiForm.taux_exoneration,
      });
      await loadCompanyDetails();
      toast({ title: 'Paramètres JEI enregistrés' });
    } catch (error: unknown) {
      showErrorToast(error, {
        title: 'Enregistrement impossible',
        fallback: 'Les paramètres JEI n’ont pas pu être enregistrés.',
      });
    } finally {
      setSavingJei(false);
    }
  };

  const toggleStatus = async () => {
    if (!company) return;
    try {
      await patchAdminCompany(companyId, {
        is_active: !company.is_active,
      });
      loadCompanyDetails();
    } catch (error) {
      log.error('Erreur:', error);
    }
  };

  if (loading) {
    return <SharkFinLoader variant="fullPage" label="Chargement de l'entreprise…" />;
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
    <div className="space-y-6">
      <AdminPageHeader
        title={company.company_name}
        description="Fiche entreprise — utilisateurs, conventions et suivi."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => navigate('/super-admin/companies')}>
              Retour
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate(`/super-admin/support?company=${companyId}`)}
            >
              Support
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate(`/super-admin/activity?company=${companyId}`)}
            >
              Activité
            </Button>
            <Button
              variant={company.is_active ? 'destructive' : 'default'}
              onClick={toggleStatus}
            >
              {company.is_active ? 'Désactiver' : 'Activer'}
            </Button>
          </div>
        }
      />

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
      <div className="mb-6 rounded-xl border bg-card p-6 shadow-sm">
        <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-xl font-bold text-foreground">Informations générales</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Identité légale, coordonnées et signataire des documents RH.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setShowEditCompanyDialog(true)}>
            <Pencil className="mr-2 h-4 w-4" />
            Modifier
          </Button>
        </div>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
          <InfoField label="Nom affiché" value={company.company_name} />
          <InfoField label="Raison sociale" value={company.raison_sociale} />
          <InfoField label="Forme juridique" value={company.legal_form} />
          <InfoField label="SIREN" value={company.siren} />
          <InfoField label="SIRET" value={company.siret} />
          <InfoField label="Code NAF/APE" value={company.code_naf ?? company.naf_ape} />
          <InfoField label="E-mail" value={company.email} />
          <InfoField label="Téléphone" value={company.phone} />
          <InfoField label="Site web" value={company.website} />
          <InfoField
            label="Date de création"
            value={new Date(company.created_at).toLocaleDateString('fr-FR')}
          />
          <InfoField label="Adresse" value={formatCompanyAddress(company)} />
          <InfoField label="Signataire RH" value={company.nom_signataire_rh} />
          <InfoField label="Qualité signataire" value={company.qualite_signataire_rh} />
        </div>
      </div>

      <EditCompanyDialog
        open={showEditCompanyDialog}
        onOpenChange={setShowEditCompanyDialog}
        company={company}
        onSaved={(updated) => {
          setCompany(updated);
          loadCompanyDetails();
        }}
        toast={toast}
      />

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-xl font-bold text-gray-900">Statut JEI</h2>
            <p className="text-sm text-gray-600 mt-1">
              Paramétrage paie de l&apos;entreprise. Les RH peuvent aussi le modifier depuis Mon
              Entreprise → Paramètres paie.
            </p>
          </div>
          <Button onClick={saveJeiSettings} disabled={savingJei}>
            {savingJei ? 'Enregistrement…' : 'Enregistrer le statut JEI'}
          </Button>
        </div>
        <JeiSettingsFormFields
          values={jeiForm}
          onChange={(patch) => setJeiForm((prev) => ({ ...prev, ...patch }))}
          disabled={savingJei}
          compact
        />
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
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
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
      {companyId && (
        <div className="mb-6">
          <CollectiveAgreementCard companyId={companyId} companyName={company.company_name} />
        </div>
      )}

      {/* Couverture DSN */}
      {companyId && dsnCoverage && (
        <div className="mb-6 rounded-lg border bg-white p-6 shadow">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-xl font-bold text-gray-900">Couverture DSN</h2>
            <div className="flex items-center gap-2">
              <span className="rounded-full border px-2 py-0.5 text-xs font-medium">
                {dsnStatusLabel(dsnCoverage.status)}
              </span>
              <button
                type="button"
                className="inline-flex items-center gap-1 rounded-lg border px-3 py-1.5 text-sm hover:bg-gray-50"
                onClick={() =>
                  navigate(`/super-admin/dsn-import?companyId=${companyId}&mode=monthly`)
                }
              >
                <Plus className="h-3.5 w-3.5" />
                Importer DSN
              </button>
            </div>
          </div>
          <DsnCoverageTimeline timeline={dsnCoverage.timeline} />
          {dsnCoverage.gaps.length > 0 && (
            <p className="mt-2 text-sm text-amber-800">
              Mois manquants : {dsnCoverage.gaps.join(', ')}
            </p>
          )}
        </div>
      )}

      {/* Connexion Net-entreprises (pilotage plateforme) */}
      {companyId && (
        <div className="mb-6">
          <NetEntreprisesConfigCard companyId={companyId} />
        </div>
      )}

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
          <SharkFinLoader label="Chargement des utilisateurs…" />
        ) : (
          <>
            <div className="w-full overflow-x-auto">
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
