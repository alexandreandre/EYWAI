/**
 * CompanyGroupDetail : Page de détail et gestion d'un groupe d'entreprises
 *
 * Permet de :
 * - Voir les informations du groupe
 * - Gérer les entreprises du groupe (ajouter/retirer)
 * - Gérer les accès utilisateurs
 * - Voir le dashboard consolidé
 */

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient from '@/api/apiClient';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { LogoUploader } from '@/components/LogoUploader';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Building2,
  ArrowLeft,
  Plus,
  Trash2,
  Users,
  DollarSign,
  TrendingUp,
  Loader2,
  UserPlus,
  X,
} from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useToast } from '@/hooks/use-toast';
import { Badge } from '@/components/ui/badge';

interface CompanyInGroup {
  id: string;
  company_name: string;
  siret: string | null;
  effectif: number;
}

interface AvailableCompany {
  id: string;
  company_name: string;
  siret: string | null;
}

interface UserAccess {
  user_id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  company_id: string;
  company_name: string;
  role: string;
}

interface CompanyAccess {
  role: string;
  is_primary: boolean;
}

interface DetailedUserAccess {
  user_id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  accesses: Record<string, CompanyAccess>; // company_id -> CompanyAccess
}

interface DetailedUserAccessesResponse {
  companies: CompanyInGroup[];
  users: DetailedUserAccess[];
}

interface GroupStats {
  metadata: {
    reference_year: number;
    reference_month: number;
    generated_at: string;
    company_count: number;
  };
  totals: {
    total_employees: number;
    total_payslip_count: number;
    total_gross_salary: number;
    total_net_salary: number;
    total_employer_charges: number;
    average_gross_per_company: number;
    average_employees_per_company: number;
  };
  by_company: Array<{
    company_id: string;
    company_name: string;
    siret: string | null;
    employee_count: number;
    payslip_count: number;
    gross_salary: number;
    net_salary: number;
    employer_charges: number;
  }>;
}

export default function CompanyGroupDetail() {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [groupName, setGroupName] = useState('');
  const [groupDescription, setGroupDescription] = useState('');
  const [groupLogoUrl, setGroupLogoUrl] = useState<string | null>(null);
  const [companies, setCompanies] = useState<CompanyInGroup[]>([]);
  const [availableCompanies, setAvailableCompanies] = useState<AvailableCompany[]>([]);
  const [userAccesses, setUserAccesses] = useState<UserAccess[]>([]);
  const [detailedUserAccesses, setDetailedUserAccesses] = useState<DetailedUserAccess[]>([]);
  const [groupStats, setGroupStats] = useState<GroupStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Dialogs
  const [isAddCompanyDialogOpen, setIsAddCompanyDialogOpen] = useState(false);
  const [selectedCompanyToAdd, setSelectedCompanyToAdd] = useState('');
  const [selectedCompaniesToAdd, setSelectedCompaniesToAdd] = useState<string[]>([]);
  const [isAddingCompany, setIsAddingCompany] = useState(false);
  const [addMode, setAddMode] = useState<'single' | 'multiple'>('single');

  // User access management
  const [isManageUserDialogOpen, setIsManageUserDialogOpen] = useState(false);
  const [isManagingUser, setIsManagingUser] = useState(false);
  const [selectedUserEmail, setSelectedUserEmail] = useState('');
  const [selectedUserFirstName, setSelectedUserFirstName] = useState('');
  const [selectedUserLastName, setSelectedUserLastName] = useState('');
  const [userCompanyRoles, setUserCompanyRoles] = useState<Record<string, string>>({});
  const [editingUser, setEditingUser] = useState<DetailedUserAccess | null>(null);

  useEffect(() => {
    if (groupId) {
      loadGroupData();
    }
  }, [groupId]);

  const loadGroupData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Charger les infos du groupe
      const groupResponse = await apiClient.get(`/api/company-groups/${groupId}`);
      setGroupName(groupResponse.data.group_name);
      setGroupDescription(groupResponse.data.description || '');
      setGroupLogoUrl(groupResponse.data.logo_url || null);

      // Charger les entreprises du groupe
      const companiesResponse = await apiClient.get(`/api/company-groups/${groupId}/companies`);
      setCompanies(companiesResponse.data);

      // Charger les entreprises disponibles (non assignées)
      const availableResponse = await apiClient.get(`/api/company-groups/${groupId}/available-companies`);
      setAvailableCompanies(availableResponse.data);

      // Charger les accès utilisateurs (old format - for backwards compatibility)
      const accessResponse = await apiClient.get(`/api/company-groups/${groupId}/user-accesses`);
      setUserAccesses(accessResponse.data);

      // Charger les accès détaillés (new format - for granular management)
      const detailedAccessResponse = await apiClient.get(`/api/company-groups/${groupId}/detailed-user-accesses`);
      setDetailedUserAccesses(detailedAccessResponse.data.users);

      // Charger les stats consolidées
      const statsResponse = await apiClient.get(`/api/company-groups/${groupId}/consolidated-stats`);
      setGroupStats(statsResponse.data);

    } catch (err: any) {
      console.error('Erreur lors du chargement du groupe:', err);
      setError(err.response?.data?.detail || 'Erreur lors du chargement du groupe');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleCompanyForBulkAdd = (companyId: string) => {
    setSelectedCompaniesToAdd(prev =>
      prev.includes(companyId)
        ? prev.filter(id => id !== companyId)
        : [...prev, companyId]
    );
  };

  const handleAddCompany = async () => {
    if (addMode === 'single') {
      // Mode ajout simple
      if (!selectedCompanyToAdd) {
        toast({
          title: "Erreur",
          description: "Veuillez sélectionner une entreprise",
          variant: "destructive",
        });
        return;
      }

      try {
        setIsAddingCompany(true);
        await apiClient.post(`/api/company-groups/${groupId}/companies/${selectedCompanyToAdd}`);

        toast({
          title: "Entreprise ajoutée",
          description: "L'entreprise a été ajoutée au groupe avec succès",
        });

        setIsAddCompanyDialogOpen(false);
        setSelectedCompanyToAdd('');
        loadGroupData();
      } catch (err: any) {
        console.error('Erreur lors de l\'ajout de l\'entreprise:', err);
        toast({
          title: "Erreur",
          description: err.response?.data?.detail || 'Erreur lors de l\'ajout de l\'entreprise',
          variant: "destructive",
        });
      } finally {
        setIsAddingCompany(false);
      }
    } else {
      // Mode ajout multiple
      if (selectedCompaniesToAdd.length === 0) {
        toast({
          title: "Erreur",
          description: "Veuillez sélectionner au moins une entreprise",
          variant: "destructive",
        });
        return;
      }

      try {
        setIsAddingCompany(true);
        const response = await apiClient.post(`/api/company-groups/${groupId}/companies/bulk`, {
          company_ids: selectedCompaniesToAdd,
        });

        toast({
          title: "Entreprises ajoutées",
          description: `${response.data.success_count} entreprise(s) ajoutée(s) au groupe`,
        });

        setIsAddCompanyDialogOpen(false);
        setSelectedCompaniesToAdd([]);
        loadGroupData();
      } catch (err: any) {
        console.error('Erreur lors de l\'ajout des entreprises:', err);
        toast({
          title: "Erreur",
          description: err.response?.data?.detail || 'Erreur lors de l\'ajout des entreprises',
          variant: "destructive",
        });
      } finally {
        setIsAddingCompany(false);
      }
    }
  };

  const handleRemoveCompany = async (companyId: string, companyName: string) => {
    if (!confirm(`Voulez-vous vraiment retirer "${companyName}" de ce groupe ?`)) {
      return;
    }

    try {
      await apiClient.delete(`/api/company-groups/${groupId}/companies/${companyId}`);

      toast({
        title: "Entreprise retirée",
        description: `"${companyName}" a été retirée du groupe`,
      });

      loadGroupData();
    } catch (err: any) {
      console.error('Erreur lors du retrait de l\'entreprise:', err);
      toast({
        title: "Erreur",
        description: err.response?.data?.detail || 'Erreur lors du retrait de l\'entreprise',
        variant: "destructive",
      });
    }
  };

  const openManageUserDialog = (user?: DetailedUserAccess) => {
    if (user) {
      // Mode édition
      setEditingUser(user);
      setSelectedUserEmail(user.email);
      setSelectedUserFirstName(user.first_name || '');
      setSelectedUserLastName(user.last_name || '');

      // Pré-remplir les rôles par entreprise
      const roles: Record<string, string> = {};
      companies.forEach((company) => {
        const access = user.accesses[company.id];
        roles[company.id] = access ? access.role : 'none';
      });
      setUserCompanyRoles(roles);
    } else {
      // Mode création
      setEditingUser(null);
      setSelectedUserEmail('');
      setSelectedUserFirstName('');
      setSelectedUserLastName('');

      // Initialiser tous les rôles à "none"
      const roles: Record<string, string> = {};
      companies.forEach((company) => {
        roles[company.id] = 'none';
      });
      setUserCompanyRoles(roles);
    }
    setIsManageUserDialogOpen(true);
  };

  const handleManageUserAccess = async () => {
    if (!selectedUserEmail.trim()) {
      toast({
        title: "Erreur",
        description: "L'email de l'utilisateur est requis",
        variant: "destructive",
      });
      return;
    }

    // Construire la liste des accès (exclure "none")
    const accesses = Object.entries(userCompanyRoles)
      .filter(([, role]) => role !== 'none')
      .map(([companyId, role]) => ({
        company_id: companyId,
        role,
      }));

    try {
      setIsManagingUser(true);
      const response = await apiClient.post(`/api/company-groups/${groupId}/manage-user-access`, {
        user_email: selectedUserEmail,
        first_name: selectedUserFirstName || null,
        last_name: selectedUserLastName || null,
        accesses,
      });

      toast({
        title: "Accès mis à jour",
        description: `${response.data.added_count} accès ajoutés, ${response.data.updated_count} modifiés, ${response.data.removed_count} retirés`,
      });

      setIsManageUserDialogOpen(false);
      loadGroupData();
    } catch (err: any) {
      console.error('Erreur lors de la gestion des accès:', err);
      toast({
        title: "Erreur",
        description: err.response?.data?.detail || 'Erreur lors de la gestion des accès utilisateur',
        variant: "destructive",
      });
    } finally {
      setIsManagingUser(false);
    }
  };

  const handleRemoveUserFromGroup = async (userId: string, userEmail: string) => {
    if (!confirm(`Voulez-vous vraiment retirer tous les accès de "${userEmail}" aux entreprises de ce groupe ?`)) {
      return;
    }

    try {
      await apiClient.delete(`/api/company-groups/${groupId}/user-access/${userId}`);

      toast({
        title: "Utilisateur retiré",
        description: `Les accès de "${userEmail}" ont été retirés du groupe`,
      });

      loadGroupData();
    } catch (err: any) {
      console.error('Erreur lors du retrait de l\'utilisateur:', err);
      toast({
        title: "Erreur",
        description: err.response?.data?.detail || 'Erreur lors du retrait de l\'utilisateur',
        variant: "destructive",
      });
    }
  };

  const handleRoleChange = (companyId: string, role: string) => {
    setUserCompanyRoles(prev => ({
      ...prev,
      [companyId]: role,
    }));
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('fr-FR', {
      style: 'currency',
      currency: 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const getRoleBadgeVariant = (role: string) => {
    switch (role) {
      case 'admin':
        return 'default';
      case 'rh':
        return 'secondary';
      case 'salarie':
        return 'outline';
      default:
        return 'outline';
    }
  };

  const getRoleLabel = (role: string) => {
    switch (role) {
      case 'admin':
        return 'Administrateur';
      case 'rh':
        return 'RH';
      case 'salarie':
        return 'Salarié';
      case 'none':
        return 'Aucun accès';
      default:
        return role;
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" onClick={() => navigate('/super-admin/groups')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Retour
        </Button>
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Button variant="ghost" onClick={() => navigate('/super-admin/groups')} className="mb-4">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Retour aux groupes
        </Button>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{groupName}</h1>
            {groupDescription && (
              <p className="text-muted-foreground mt-1">{groupDescription}</p>
            )}
          </div>
          <Button onClick={loadGroupData} variant="outline">
            Actualiser
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Vue d'ensemble</TabsTrigger>
          <TabsTrigger value="companies">Entreprises ({companies.length})</TabsTrigger>
          <TabsTrigger value="users">Utilisateurs</TabsTrigger>
        </TabsList>

        {/* Vue d'ensemble */}
        <TabsContent value="overview" className="space-y-4">
          {/* Logo du groupe */}
          <Card>
            <CardHeader>
              <CardTitle>Logo du groupe</CardTitle>
              <CardDescription>
                Gérez le logo qui sera affiché pour ce groupe d'entreprises
              </CardDescription>
            </CardHeader>
            <CardContent>
              <LogoUploader
                currentLogoUrl={groupLogoUrl}
                entityType="group"
                entityId={groupId}
                onLogoChange={() => {
                  // Recharger les données du groupe après l'upload/suppression
                  loadGroupData();
                }}
                size="lg"
              />
            </CardContent>
          </Card>

          {groupStats && (
            <>
              {/* KPIs */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-sm font-medium">Entreprises</CardTitle>
                    <Building2 className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{groupStats.metadata.company_count}</div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {groupStats.totals.average_employees_per_company.toFixed(0)} employés moy.
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-sm font-medium">Total Employés</CardTitle>
                    <Users className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{groupStats.totals.total_employees}</div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {groupStats.totals.total_payslip_count} bulletins
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-sm font-medium">Masse Salariale Brute</CardTitle>
                    <DollarSign className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">
                      {formatCurrency(groupStats.totals.total_gross_salary)}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {formatCurrency(groupStats.totals.average_gross_per_company)} moy.
                    </p>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-sm font-medium">Charges Patronales</CardTitle>
                    <TrendingUp className="h-4 w-4 text-muted-foreground" />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">
                      {formatCurrency(groupStats.totals.total_employer_charges)}
                    </div>
                    <p className="text-xs text-muted-foreground mt-1">
                      {((groupStats.totals.total_employer_charges / groupStats.totals.total_gross_salary) * 100).toFixed(1)}% du brut
                    </p>
                  </CardContent>
                </Card>
              </div>

              {/* Détails par entreprise */}
              <Card>
                <CardHeader>
                  <CardTitle>Détails par Entreprise</CardTitle>
                  <CardDescription>
                    Statistiques pour le mois de {groupStats.metadata.reference_month}/{groupStats.metadata.reference_year}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b">
                          <th className="text-left p-3 font-medium">Entreprise</th>
                          <th className="text-right p-3 font-medium">Employés</th>
                          <th className="text-right p-3 font-medium">Bulletins</th>
                          <th className="text-right p-3 font-medium">Masse Sal. Brute</th>
                          <th className="text-right p-3 font-medium">Charges</th>
                        </tr>
                      </thead>
                      <tbody>
                        {groupStats.by_company.map((company) => (
                          <tr key={company.company_id} className="border-b hover:bg-muted/50">
                            <td className="p-3">
                              <div>
                                <div className="font-medium">{company.company_name}</div>
                                {company.siret && (
                                  <div className="text-xs text-muted-foreground font-mono">
                                    {company.siret}
                                  </div>
                                )}
                              </div>
                            </td>
                            <td className="text-right p-3">{company.employee_count}</td>
                            <td className="text-right p-3">{company.payslip_count}</td>
                            <td className="text-right p-3 font-medium">
                              {formatCurrency(company.gross_salary)}
                            </td>
                            <td className="text-right p-3 text-muted-foreground">
                              {formatCurrency(company.employer_charges)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr className="border-t-2 font-bold">
                          <td className="p-3">Total</td>
                          <td className="text-right p-3">{groupStats.totals.total_employees}</td>
                          <td className="text-right p-3">{groupStats.totals.total_payslip_count}</td>
                          <td className="text-right p-3">
                            {formatCurrency(groupStats.totals.total_gross_salary)}
                          </td>
                          <td className="text-right p-3">
                            {formatCurrency(groupStats.totals.total_employer_charges)}
                          </td>
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </TabsContent>

        {/* Entreprises */}
        <TabsContent value="companies" className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Entreprises du groupe</h3>
            <Button onClick={() => setIsAddCompanyDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Ajouter une entreprise
            </Button>
          </div>

          {companies.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Building2 className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">Aucune entreprise</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Ajoutez des entreprises à ce groupe
                </p>
                <Button onClick={() => setIsAddCompanyDialogOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Ajouter une entreprise
                </Button>
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {companies.map((company) => (
                <Card
                  key={company.id}
                  className="cursor-pointer hover:shadow-lg transition-shadow"
                  onClick={() => navigate(`/super-admin/companies/${company.id}`)}
                >
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg">{company.company_name}</CardTitle>
                        {company.siret && (
                          <CardDescription className="font-mono text-xs">
                            {company.siret}
                          </CardDescription>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRemoveCompany(company.id, company.company_name);
                        }}
                      >
                        <Trash2 className="h-4 w-4 text-destructive" />
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Users className="h-4 w-4" />
                      <span>{company.effectif} employés</span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          {/* Dialog Ajouter Entreprise */}
          <Dialog open={isAddCompanyDialogOpen} onOpenChange={setIsAddCompanyDialogOpen}>
            <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Ajouter des entreprises au groupe</DialogTitle>
                <DialogDescription>
                  Sélectionnez une ou plusieurs entreprises à ajouter à ce groupe
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                {/* Toggle entre mode simple et multiple */}
                <div className="flex items-center gap-4 pb-4 border-b">
                  <button
                    type="button"
                    onClick={() => setAddMode('single')}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      addMode === 'single'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground hover:bg-muted/80'
                    }`}
                  >
                    Ajout simple
                  </button>
                  <button
                    type="button"
                    onClick={() => setAddMode('multiple')}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      addMode === 'multiple'
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground hover:bg-muted/80'
                    }`}
                  >
                    Ajout multiple
                  </button>
                </div>

                {addMode === 'single' ? (
                  // Mode simple (select)
                  <div className="space-y-2">
                    <Label htmlFor="company-select">Entreprise</Label>
                    <Select value={selectedCompanyToAdd} onValueChange={setSelectedCompanyToAdd}>
                      <SelectTrigger id="company-select">
                        <SelectValue placeholder="Sélectionner une entreprise" />
                      </SelectTrigger>
                      <SelectContent>
                        {availableCompanies.length === 0 ? (
                          <div className="p-4 text-sm text-muted-foreground text-center">
                            Aucune entreprise disponible
                          </div>
                        ) : (
                          availableCompanies.map((company) => (
                            <SelectItem key={company.id} value={company.id}>
                              {company.company_name}
                              {company.siret && ` (${company.siret})`}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                  </div>
                ) : (
                  // Mode multiple (checkboxes)
                  <div className="space-y-2">
                    <Label>Entreprises à ajouter</Label>
                    {availableCompanies.length === 0 ? (
                      <p className="text-sm text-muted-foreground italic py-4">
                        Aucune entreprise disponible
                      </p>
                    ) : (
                      <div className="border rounded-lg max-h-96 overflow-y-auto">
                        {availableCompanies.map((company) => (
                          <label
                            key={company.id}
                            className="flex items-center gap-3 p-3 hover:bg-muted/50 cursor-pointer border-b last:border-b-0"
                          >
                            <input
                              type="checkbox"
                              checked={selectedCompaniesToAdd.includes(company.id)}
                              onChange={() => toggleCompanyForBulkAdd(company.id)}
                              className="w-4 h-4 text-primary border-gray-300 rounded focus:ring-2 focus:ring-primary"
                            />
                            <div className="flex-1">
                              <p className="font-medium">{company.company_name}</p>
                              {company.siret && (
                                <p className="text-xs text-muted-foreground font-mono">
                                  {company.siret}
                                </p>
                              )}
                            </div>
                          </label>
                        ))}
                      </div>
                    )}
                    {selectedCompaniesToAdd.length > 0 && (
                      <p className="text-sm text-primary font-medium">
                        {selectedCompaniesToAdd.length} entreprise(s) sélectionnée(s)
                      </p>
                    )}
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsAddCompanyDialogOpen(false)}>
                  Annuler
                </Button>
                <Button
                  onClick={handleAddCompany}
                  disabled={
                    isAddingCompany ||
                    (addMode === 'single' ? !selectedCompanyToAdd : selectedCompaniesToAdd.length === 0)
                  }
                >
                  {isAddingCompany ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Ajout...
                    </>
                  ) : addMode === 'multiple' ? (
                    `Ajouter ${selectedCompaniesToAdd.length} entreprise(s)`
                  ) : (
                    'Ajouter'
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>

        {/* Utilisateurs */}
        <TabsContent value="users" className="space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-lg font-semibold">Gestion des accès utilisateurs</h3>
            <Button onClick={() => openManageUserDialog()}>
              <UserPlus className="mr-2 h-4 w-4" />
              Ajouter un utilisateur
            </Button>
          </div>

          {detailedUserAccesses.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center justify-center py-12">
                <Users className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-semibold mb-2">Aucun utilisateur</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  Aucun utilisateur n'a accès aux entreprises de ce groupe pour le moment
                </p>
                <Button onClick={() => openManageUserDialog()}>
                  <UserPlus className="mr-2 h-4 w-4" />
                  Ajouter un utilisateur
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="text-left p-4 font-medium sticky left-0 bg-muted/50 z-10">
                          Utilisateur
                        </th>
                        {companies.map((company) => (
                          <th key={company.id} className="text-center p-4 font-medium min-w-[120px]">
                            <div className="text-sm">{company.company_name}</div>
                            {company.siret && (
                              <div className="text-xs text-muted-foreground font-mono font-normal">
                                {company.siret}
                              </div>
                            )}
                          </th>
                        ))}
                        <th className="text-right p-4 font-medium sticky right-0 bg-muted/50">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {detailedUserAccesses.map((user) => (
                        <tr key={user.user_id} className="border-b hover:bg-muted/30">
                          <td className="p-4 sticky left-0 bg-background">
                            <div>
                              <div className="font-medium">
                                {user.first_name && user.last_name
                                  ? `${user.first_name} ${user.last_name}`
                                  : user.email}
                              </div>
                              <div className="text-xs text-muted-foreground">{user.email}</div>
                            </div>
                          </td>
                          {companies.map((company) => {
                            const access = user.accesses[company.id];
                            return (
                              <td key={company.id} className="p-4 text-center">
                                {access ? (
                                  <div className="flex flex-col items-center gap-1">
                                    <Badge variant={getRoleBadgeVariant(access.role)}>
                                      {getRoleLabel(access.role)}
                                    </Badge>
                                    {access.is_primary && (
                                      <span className="text-xs text-primary font-medium">★ Principal</span>
                                    )}
                                  </div>
                                ) : (
                                  <span className="text-xs text-muted-foreground">-</span>
                                )}
                              </td>
                            );
                          })}
                          <td className="p-4 sticky right-0 bg-background">
                            <div className="flex items-center justify-end gap-2">
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => openManageUserDialog(user)}
                              >
                                Modifier
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleRemoveUserFromGroup(user.user_id, user.email)}
                              >
                                <Trash2 className="h-4 w-4 text-destructive" />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Dialog Gérer l'accès utilisateur */}
          <Dialog open={isManageUserDialogOpen} onOpenChange={setIsManageUserDialogOpen}>
            <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>
                  {editingUser ? 'Modifier les accès utilisateur' : 'Ajouter un utilisateur'}
                </DialogTitle>
                <DialogDescription>
                  Configurez les accès par entreprise pour cet utilisateur
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                {/* Informations utilisateur */}
                <div className="space-y-4 pb-4 border-b">
                  <div className="space-y-2">
                    <Label htmlFor="user-email">Email *</Label>
                    <Input
                      id="user-email"
                      type="email"
                      placeholder="utilisateur@exemple.com"
                      value={selectedUserEmail}
                      onChange={(e) => setSelectedUserEmail(e.target.value)}
                      disabled={!!editingUser}
                    />
                    {editingUser && (
                      <p className="text-xs text-muted-foreground">
                        L'email ne peut pas être modifié
                      </p>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="user-firstname">Prénom</Label>
                      <Input
                        id="user-firstname"
                        placeholder="Prénom"
                        value={selectedUserFirstName}
                        onChange={(e) => setSelectedUserFirstName(e.target.value)}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="user-lastname">Nom</Label>
                      <Input
                        id="user-lastname"
                        placeholder="Nom"
                        value={selectedUserLastName}
                        onChange={(e) => setSelectedUserLastName(e.target.value)}
                      />
                    </div>
                  </div>
                </div>

                {/* Configuration des accès par entreprise */}
                <div className="space-y-2">
                  <Label>Accès par entreprise</Label>
                  <p className="text-sm text-muted-foreground">
                    Définissez le rôle de l'utilisateur pour chaque entreprise du groupe
                  </p>
                  <div className="border rounded-lg divide-y max-h-96 overflow-y-auto">
                    {companies.map((company) => (
                      <div key={company.id} className="p-4 flex items-center justify-between">
                        <div className="flex-1">
                          <div className="font-medium">{company.company_name}</div>
                          {company.siret && (
                            <div className="text-xs text-muted-foreground font-mono">
                              {company.siret}
                            </div>
                          )}
                        </div>
                        <Select
                          value={userCompanyRoles[company.id] || 'none'}
                          onValueChange={(value) => handleRoleChange(company.id, value)}
                        >
                          <SelectTrigger className="w-[180px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="none">Aucun accès</SelectItem>
                            <SelectItem value="salarie">Salarié</SelectItem>
                            <SelectItem value="rh">RH</SelectItem>
                            <SelectItem value="admin">Administrateur</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {Object.values(userCompanyRoles).filter(r => r !== 'none').length} entreprise(s) avec accès
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsManageUserDialogOpen(false)}>
                  Annuler
                </Button>
                <Button onClick={handleManageUserAccess} disabled={isManagingUser}>
                  {isManagingUser ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Enregistrement...
                    </>
                  ) : (
                    'Enregistrer'
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </TabsContent>
      </Tabs>
    </div>
  );
}
