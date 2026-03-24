// src/pages/UserProfile.tsx
// Fiche utilisateur complète : consultation des informations, accès entreprises et permissions.

import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  Loader2,
  ArrowLeft,
  Edit,
  Mail,
  Briefcase,
  Shield,
  Building2,
  User,
  ChevronRight,
} from 'lucide-react';
import {
  getUserDetail,
  getUserPermissions,
  getUserCompanyAccesses,
  UserPermissionsSummary,
} from '../api/permissions';
import { useCompany } from '../contexts/CompanyContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';

const roleLabels: Record<string, string> = {
  admin: 'Administrateur',
  rh: 'Ressources Humaines',
  collaborateur_rh: 'Collaborateur RH',
  collaborateur: 'Collaborateur',
  custom: 'Personnalisé',
};

const roleColors: Record<string, string> = {
  admin: 'bg-purple-100 text-purple-800 border-purple-200',
  rh: 'bg-blue-100 text-blue-800 border-blue-200',
  collaborateur_rh: 'bg-green-100 text-green-800 border-green-200',
  collaborateur: 'bg-gray-100 text-gray-800 border-gray-200',
  custom: 'bg-orange-100 text-orange-800 border-orange-200',
};

interface CompanyAccessItem {
  company_id: string;
  company_name: string;
  role: string;
  is_primary: boolean;
  siret?: string;
  group_id?: string;
}

interface UserDetailData {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  job_title?: string;
  company_id: string;
  role: 'admin' | 'rh' | 'collaborateur_rh' | 'collaborateur' | 'custom';
  role_template_id?: string;
  role_template_name?: string;
  permission_ids?: string[];
  can_edit: boolean;
}

const UserProfile: React.FC = () => {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const { activeCompany } = useCompany();

  const companyId = activeCompany?.company_id ?? localStorage.getItem('activeCompanyId') ?? '';

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userDetail, setUserDetail] = useState<UserDetailData | null>(null);
  const [permissions, setPermissions] = useState<UserPermissionsSummary | null>(null);
  const [companyAccesses, setCompanyAccesses] = useState<CompanyAccessItem[]>([]);

  useEffect(() => {
    if (!userId) return;

    const loadData = async () => {
      setLoading(true);
      setError(null);
      try {
        const accessesRes = await getUserCompanyAccesses(userId);
        setCompanyAccesses(accessesRes);

        const companyIdsToTry = [
          companyId,
          accessesRes.find((a) => a.is_primary)?.company_id,
          accessesRes[0]?.company_id,
        ].filter(Boolean) as string[];

        let detailRes: UserDetailData | null = null;
        let permCompanyId: string | null = null;

        for (const cid of companyIdsToTry) {
          try {
            detailRes = await getUserDetail(userId, cid);
            permCompanyId = cid;
            break;
          } catch {
            continue;
          }
        }

        setUserDetail(detailRes);

        if (permCompanyId && detailRes) {
          try {
            const perms = await getUserPermissions(userId, permCompanyId);
            setPermissions(perms);
          } catch {
            setPermissions(null);
          }
        } else {
          setPermissions(null);
        }

        if (!detailRes && accessesRes.length === 0) {
          setError('Utilisateur non trouvé ou accès insuffisant.');
        }
      } catch (err: unknown) {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Erreur lors du chargement';
        setError(msg);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [userId, companyId]);

  const handleEdit = () => {
    if (userId) navigate(`/users/${userId}/edit`);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
      </div>
    );
  }

  if (error || !userDetail) {
    return (
      <div className="space-y-4">
        <Link to="/users" className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="mr-2 h-4 w-4" /> Retour à la liste des utilisateurs
        </Link>
        <Card>
          <CardContent className="pt-6">
            <p className="text-destructive">
              {error ?? 'Utilisateur non trouvé.'}
            </p>
            <Button variant="outline" className="mt-4" onClick={() => navigate('/users')}>
              Retour à la liste
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const displayRole = userDetail.role === 'custom' && userDetail.role_template_name
    ? userDetail.role_template_name
    : roleLabels[userDetail.role] ?? userDetail.role;
  const roleColor = roleColors[userDetail.role] ?? roleColors.custom;
  const fullName = `${userDetail.first_name} ${userDetail.last_name}`;

  return (
    <div className="space-y-6">
      <Link
        to="/users"
        className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="mr-2 h-4 w-4" /> Gestion des utilisateurs
      </Link>

      {/* En-tête */}
      <Card>
        <CardHeader className="flex flex-row items-center gap-4">
          <Avatar className="h-16 w-16">
            <AvatarFallback className="text-xl bg-primary/10 text-primary">
              {userDetail.first_name.charAt(0)}
              {userDetail.last_name.charAt(0)}
            </AvatarFallback>
          </Avatar>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <CardTitle className="text-2xl">{fullName}</CardTitle>
              <Badge variant="secondary" className={cn('font-medium', roleColor)}>
                {displayRole}
              </Badge>
            </div>
            <CardDescription className="mt-1 flex flex-wrap items-center gap-4">
              <span className="flex items-center gap-2">
                <Mail className="h-4 w-4" />
                {userDetail.email}
              </span>
              {userDetail.job_title && (
                <span className="flex items-center gap-2">
                  <Briefcase className="h-4 w-4" />
                  {userDetail.job_title}
                </span>
              )}
            </CardDescription>
          </div>
          {userDetail.can_edit && (
            <Button onClick={handleEdit} variant="default">
              <Edit className="mr-2 h-4 w-4" />
              Modifier
            </Button>
          )}
        </CardHeader>
      </Card>

      {/* Onglets */}
      <Tabs defaultValue="identity" className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="identity" className="flex items-center gap-2">
            <User className="h-4 w-4" />
            Identité
          </TabsTrigger>
          <TabsTrigger value="accesses" className="flex items-center gap-2">
            <Building2 className="h-4 w-4" />
            Accès entreprises
          </TabsTrigger>
          <TabsTrigger value="permissions" className="flex items-center gap-2">
            <Shield className="h-4 w-4" />
            Permissions
          </TabsTrigger>
        </TabsList>

        <TabsContent value="identity" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Informations personnelles</CardTitle>
              <CardDescription>Données d'identité et de contact</CardDescription>
            </CardHeader>
            <CardContent>
              <dl className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-muted-foreground">Prénom</dt>
                  <dd className="font-medium">{userDetail.first_name}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Nom</dt>
                  <dd className="font-medium">{userDetail.last_name}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Email</dt>
                  <dd className="font-medium">{userDetail.email}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Poste</dt>
                  <dd className="font-medium">{userDetail.job_title || '—'}</dd>
                </div>
              </dl>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="accesses" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Accès multi-entreprises</CardTitle>
              <CardDescription>
                Entreprises auxquelles l'utilisateur a accès et rôle dans chacune
              </CardDescription>
            </CardHeader>
            <CardContent>
              {companyAccesses.length === 0 ? (
                <p className="text-sm text-muted-foreground">Aucun accès entreprise.</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Entreprise</TableHead>
                      <TableHead>Rôle</TableHead>
                      <TableHead>Statut</TableHead>
                      <TableHead className="text-right">SIRET</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {companyAccesses.map((acc) => (
                      <TableRow key={acc.company_id}>
                        <TableCell className="font-medium">{acc.company_name}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className={cn('text-xs', roleColors[acc.role] ?? roleColors.custom)}>
                            {roleLabels[acc.role] ?? acc.role}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {acc.is_primary && (
                            <Badge variant="secondary" className="text-xs">Primaire</Badge>
                          )}
                          {!acc.is_primary && <span className="text-muted-foreground">—</span>}
                        </TableCell>
                        <TableCell className="text-right text-muted-foreground font-mono text-xs">
                          {acc.siret || '—'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="permissions" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Permissions</CardTitle>
              <CardDescription>
                {companyId
                  ? `Permissions dans l'entreprise active${activeCompany?.company_name ? ` (${activeCompany.company_name})` : ''}`
                  : 'Sélectionnez une entreprise pour afficher les permissions.'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!companyId ? (
                <p className="text-sm text-muted-foreground">
                  Veuillez sélectionner une entreprise dans le sélecteur d'en-tête pour voir les permissions.
                </p>
              ) : !permissions ? (
                <p className="text-sm text-muted-foreground">
                  Impossible de charger les permissions pour cette entreprise.
                </p>
              ) : (
                <div className="space-y-6">
                  {permissions.role_template_name && (
                    <div className="p-3 bg-muted/50 rounded-lg text-sm">
                      <span className="font-medium">Template de rôle :</span>{' '}
                      {permissions.role_template_name}
                    </div>
                  )}
                  <div>
                    <h4 className="font-medium mb-3 flex items-center gap-2">
                      <Shield className="h-4 w-4 text-primary" />
                      Résumé ({permissions.total_permissions} permission(s))
                    </h4>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                      {Object.entries(permissions.permissions_by_category || {}).map(([category, count]) => (
                        <div
                          key={category}
                          className="p-3 border rounded-lg bg-muted/30"
                        >
                          <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                            {category.replace(/_/g, ' ')}
                          </div>
                          <div className="text-lg font-semibold">{count}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <details className="group">
                    <summary className="cursor-pointer list-none flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground">
                      <ChevronRight className="h-4 w-4 transition-transform group-open:rotate-90" />
                      Voir toutes les permissions
                    </summary>
                    <ul className="mt-3 pl-6 space-y-1.5">
                      {(permissions.all_permissions || []).map((perm) => (
                        <li key={perm.id} className="text-sm flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full bg-primary" />
                          {perm.label}
                        </li>
                      ))}
                      {(!permissions.all_permissions || permissions.all_permissions.length === 0) && (
                        <li className="text-sm text-muted-foreground">Aucune permission.</li>
                      )}
                    </ul>
                  </details>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default UserProfile;
