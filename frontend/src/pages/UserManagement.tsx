import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Info, Plus, UserCog, UserPlus } from 'lucide-react';

import {
  getAccessibleCompaniesForUserCreation,
  getCompanyUsers,
} from '@/api/permissions';
import { UserAccessList, type UserAccessListItem } from '@/components/users/UserAccessList';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { useCompany } from '@/contexts/CompanyContext';
import { getScopeBannerMessage } from '@/lib/userRoleLabels';

const UserManagement: React.FC = () => {
  const navigate = useNavigate();
  const { activeCompany } = useCompany();
  const [selectedCompanyId, setSelectedCompanyId] = useState('');

  const companiesQuery = useQuery({
    queryKey: ['users-accessible-companies'],
    queryFn: getAccessibleCompaniesForUserCreation,
  });

  const accessibleCompanies = companiesQuery.data ?? [];

  const selectedCompany = useMemo(
    () => accessibleCompanies.find((c) => c.company_id === selectedCompanyId),
    [accessibleCompanies, selectedCompanyId],
  );

  const canManageCompany = Boolean(
    selectedCompanyId && accessibleCompanies.some((c) => c.company_id === selectedCompanyId),
  );

  const companyName =
    selectedCompany?.company_name ??
    activeCompany?.company_name ??
    'Entreprise';

  const creatorRole = selectedCompany?.creator_role ?? '';

  useEffect(() => {
    if (accessibleCompanies.length === 0) return;

    const activeId = activeCompany?.company_id;
    const activeIsManageable =
      activeId && accessibleCompanies.some((c) => c.company_id === activeId);

    if (activeIsManageable) {
      setSelectedCompanyId(activeId);
      return;
    }

    if (!selectedCompanyId || !accessibleCompanies.some((c) => c.company_id === selectedCompanyId)) {
      setSelectedCompanyId(accessibleCompanies[0].company_id);
    }
  }, [accessibleCompanies, activeCompany?.company_id, selectedCompanyId]);

  const usersQuery = useQuery({
    queryKey: ['company-users', selectedCompanyId],
    queryFn: () => getCompanyUsers(selectedCompanyId),
    enabled: Boolean(selectedCompanyId) && canManageCompany,
  });

  const users: UserAccessListItem[] = (usersQuery.data ?? []).map((u) => ({
    id: u.id,
    email: u.email,
    first_name: u.first_name,
    last_name: u.last_name,
    company_id: u.company_id ?? selectedCompanyId,
    role: u.role,
    role_template_name: u.role_template_name,
    can_edit: u.can_edit,
  }));

  const isLoading = companiesQuery.isLoading || (canManageCompany && usersQuery.isLoading);
  const displayCount = canManageCompany ? users.length : 0;

  const handleCreateAppAccess = () => navigate('/users/create');
  const handleCreateCollaborator = () => navigate('/employees');

  if (companiesQuery.isLoading && accessibleCompanies.length === 0) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-72" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (companiesQuery.isError) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Erreur de chargement</AlertTitle>
        <AlertDescription>
          Impossible de charger les entreprises accessibles. Réessayez dans un instant.
        </AlertDescription>
      </Alert>
    );
  }

  if (accessibleCompanies.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-3xl font-bold tracking-tight">Accès applicatifs</h1>
        <Alert>
          <Info className="h-4 w-4" />
          <AlertTitle>Aucun périmètre de gestion</AlertTitle>
          <AlertDescription>
            Votre compte ne permet pas de gérer les accès applicatifs pour une entreprise.
            Contactez un administrateur si vous pensez qu&apos;il s&apos;agit d&apos;une erreur.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-3xl font-bold tracking-tight">Accès applicatifs</h1>
            <Badge variant="outline" className="font-normal">
              {companyName}
            </Badge>
          </div>
          <p className="text-muted-foreground">
            {isLoading
              ? 'Chargement…'
              : `${displayCount} compte${displayCount > 1 ? 's' : ''} dans votre périmètre`}
            {accessibleCompanies.length > 1 && (
              <span className="text-muted-foreground/80">
                {' '}
                — changez d&apos;entreprise via le menu en haut si besoin
              </span>
            )}
          </p>
        </div>

        <div className="flex shrink-0 flex-wrap gap-2">
          <Button onClick={handleCreateAppAccess}>
            <UserPlus className="mr-2 h-4 w-4" />
            Ajouter un accès applicatif
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                <Plus className="mr-2 h-4 w-4" />
                Autre création
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={handleCreateCollaborator}>
                Créer un collaborateur (fiche salarié)
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleCreateAppAccess}>
                Ajouter un accès applicatif
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {canManageCompany && creatorRole && (
        <Alert className="border-primary/20 bg-primary/5">
          <UserCog className="h-4 w-4" />
          <AlertTitle className="text-base">Votre périmètre sur cette liste</AlertTitle>
          <AlertDescription>
            {getScopeBannerMessage(creatorRole, companyName)}{' '}
            <span className="text-muted-foreground">
              Les fiches salariés (contrat, paie) se gèrent sur la page{' '}
              <Link to="/employees" className="font-medium text-primary underline-offset-4 hover:underline">
                Collaborateurs
              </Link>
              .
            </span>
          </AlertDescription>
        </Alert>
      )}

      {!canManageCompany && activeCompany && (
        <Alert>
          <Info className="h-4 w-4" />
          <AlertTitle>Entreprise active non gérable</AlertTitle>
          <AlertDescription>
            L&apos;entreprise <strong>{activeCompany.company_name}</strong> n&apos;est pas dans votre
            périmètre de gestion des accès. Sélectionnez une autre entreprise via le menu en haut (
            {accessibleCompanies.map((c) => c.company_name).join(', ')}).
          </AlertDescription>
        </Alert>
      )}

      {usersQuery.isError && canManageCompany && (
        <Alert variant="destructive">
          <AlertTitle>Impossible de charger les comptes</AlertTitle>
          <AlertDescription>
            Vérifiez votre connexion ou réessayez. Si le problème persiste, contactez le support.
          </AlertDescription>
        </Alert>
      )}

      <UserAccessList
        users={users}
        loading={isLoading}
        creatorRole={creatorRole}
        companyId={selectedCompanyId}
        companyName={companyName}
        canManageCompany={canManageCompany}
        onCreateAppAccess={handleCreateAppAccess}
      />
    </div>
  );
};

export default UserManagement;
