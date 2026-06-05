// frontend/src/pages/super-admin/Users.tsx
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../../../api/apiClient';
import { AdminPageHeader } from '@/features/admin/components/eywai/AdminPageHeader';
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { UserPlus } from 'lucide-react';

import { log } from '@/lib/logger';
interface User {
  id: string;
  first_name: string;
  last_name: string;
  role: string;
  company_id: string;
  company_name?: string;
  created_at: string;
}

export default function Users() {
  const navigate = useNavigate();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    search: '',
    role: '',
    company_id: ''
  });

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const response = await apiClient.get('/api/super-admin/users', {
        params: filters
      });
      setUsers(response.data.users);
    } catch (error) {
      log.error('Erreur:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <SharkFinLoader variant="fullPage" label="Chargement des utilisateurs…" />;
  }

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Utilisateurs"
        description="Tous les comptes de la plateforme, par entreprise et par profil."
        actions={
          <Button variant="outline" onClick={() => navigate('/super-admin/access')}>
            <UserPlus className="mr-2 h-4 w-4" />
            Profils & droits RH
          </Button>
        }
      />

      <Card>
        <CardContent className="grid gap-4 pt-6 md:grid-cols-4">
          <Input
            placeholder="Rechercher…"
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            onKeyDown={(e) => e.key === 'Enter' && loadUsers()}
          />
          <select
            value={filters.role}
            onChange={(e) => setFilters({ ...filters, role: e.target.value })}
            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
          >
            <option value="">Tous les rôles</option>
            <option value="admin">Admin</option>
            <option value="rh">RH</option>
            <option value="manager">Manager</option>
            <option value="salarie">Salarié</option>
          </select>
          <Button onClick={loadUsers} className="md:col-span-2">
            Appliquer les filtres
          </Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {['admin', 'rh', 'manager', 'salarie'].map((role) => (
          <Card key={role}>
            <CardContent className="pt-4">
              <p className="text-sm text-muted-foreground capitalize">{role}</p>
              <p className="text-2xl font-bold tabular-nums">
                {users.filter((u) => u.role === role).length}
              </p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Utilisateur</TableHead>
                <TableHead>Entreprise</TableHead>
                <TableHead>Rôle</TableHead>
                <TableHead>Créé le</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((user) => (
                <TableRow key={user.id}>
                  <TableCell className="font-medium">
                    {user.first_name} {user.last_name}
                  </TableCell>
                  <TableCell>{user.company_name || '—'}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{user.role}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(user.created_at).toLocaleDateString('fr-FR')}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {users.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">Aucun utilisateur</p>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
