import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowUpDown,
  Edit,
  Search,
  UserPlus,
  Users as UsersIcon,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  AppUserRole,
  getFilterableBaseRoles,
  getRoleDisplayLabel,
  ROLE_BADGE_CLASS,
} from '@/lib/userRoleLabels';

export interface UserAccessListItem {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  company_id: string;
  role: AppUserRole;
  role_template_name?: string;
  can_edit: boolean;
}

type SortKey = 'name' | 'role' | 'email';
type SortOrder = 'asc' | 'desc';

function initials(first: string, last: string): string {
  return `${first.charAt(0) || ''}${last.charAt(0) || ''}`.toUpperCase() || '?';
}

function SortableHead({
  label,
  active,
  order,
  onClick,
}: {
  label: string;
  active: boolean;
  order: SortOrder;
  onClick: () => void;
}) {
  return (
    <TableHead>
      <button
        type="button"
        className="inline-flex items-center gap-1 font-medium hover:text-foreground"
        onClick={onClick}
      >
        {label}
        <ArrowUpDown
          className={cn('h-3.5 w-3.5', active ? 'text-foreground' : 'text-muted-foreground')}
        />
        {active ? (
          <span className="sr-only">{order === 'asc' ? 'croissant' : 'décroissant'}</span>
        ) : null}
      </button>
    </TableHead>
  );
}

export interface UserAccessListProps {
  users: UserAccessListItem[];
  loading: boolean;
  creatorRole: string;
  companyId: string;
  companyName: string;
  canManageCompany: boolean;
  onCreateAppAccess?: () => void;
}

export function UserAccessList({
  users,
  loading,
  creatorRole,
  companyId,
  companyName,
  canManageCompany,
  onCreateAppAccess,
}: UserAccessListProps) {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('all');
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

  const customRoleNames = useMemo(() => {
    const names = new Set<string>();
    for (const u of users) {
      if (u.role === 'custom' && u.role_template_name) {
        names.add(u.role_template_name);
      }
    }
    return Array.from(names).sort((a, b) => a.localeCompare(b, 'fr'));
  }, [users]);

  const roleFilterOptions = useMemo(() => {
    const base = getFilterableBaseRoles(creatorRole);
    const presentBase = base.filter((r) => users.some((u) => u.role === r));
    const options: { value: string; label: string }[] = [
      { value: 'all', label: 'Tous les rôles' },
      ...presentBase.map((r) => ({
        value: r,
        label: getRoleDisplayLabel(r),
      })),
      ...customRoleNames.map((name) => ({ value: `custom:${name}`, label: name })),
    ];
    return options;
  }, [creatorRole, users, customRoleNames]);

  const roleCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const u of users) {
      const key =
        u.role === 'custom' && u.role_template_name
          ? u.role_template_name
          : getRoleDisplayLabel(u.role);
      counts[key] = (counts[key] ?? 0) + 1;
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1]);
  }, [users]);

  const filteredSortedUsers = useMemo(() => {
    let list = [...users];
    const q = searchQuery.trim().toLowerCase();
    if (q) {
      list = list.filter(
        (u) =>
          u.first_name.toLowerCase().includes(q) ||
          u.last_name.toLowerCase().includes(q) ||
          u.email.toLowerCase().includes(q),
      );
    }
    if (roleFilter !== 'all') {
      if (roleFilter.startsWith('custom:')) {
        const name = roleFilter.slice('custom:'.length);
        list = list.filter((u) => u.role === 'custom' && u.role_template_name === name);
      } else {
        list = list.filter((u) => u.role === roleFilter);
      }
    }
    const dir = sortOrder === 'asc' ? 1 : -1;
    list.sort((a, b) => {
      if (sortKey === 'name') {
        const na = `${a.last_name} ${a.first_name}`.toLowerCase();
        const nb = `${b.last_name} ${b.first_name}`.toLowerCase();
        return na.localeCompare(nb, 'fr') * dir;
      }
      if (sortKey === 'email') {
        return a.email.localeCompare(b.email, 'fr') * dir;
      }
      const ra = getRoleDisplayLabel(a.role, a.role_template_name);
      const rb = getRoleDisplayLabel(b.role, b.role_template_name);
      return ra.localeCompare(rb, 'fr') * dir;
    });
    return list;
  }, [users, searchQuery, roleFilter, sortKey, sortOrder]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortOrder('asc');
    }
  };

  const openProfile = (userId: string) => {
    const params = new URLSearchParams({ company_id: companyId });
    navigate(`/users/${userId}?${params.toString()}`);
  };

  const openEdit = (userId: string) => {
    const params = new URLSearchParams({ company_id: companyId });
    navigate(`/users/${userId}/edit?${params.toString()}`);
  };

  const emptyTitle = !canManageCompany
    ? 'Entreprise hors périmètre'
    : searchQuery || roleFilter !== 'all'
      ? 'Aucun résultat'
      : 'Aucun compte dans votre périmètre';

  const emptyDescription = !canManageCompany
    ? `Vous ne pouvez pas gérer les accès applicatifs pour ${companyName}. Changez d'entreprise via le menu en haut ou contactez un administrateur.`
    : searchQuery || roleFilter !== 'all'
      ? 'Essayez de modifier votre recherche ou le filtre de rôle.'
      : `Aucun compte applicatif visible pour ${companyName} avec votre niveau d'accès.`;

  return (
    <div className="space-y-4">
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Rechercher par nom ou e-mail…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
                disabled={!canManageCompany || loading}
              />
            </div>
            <Select
              value={roleFilter}
              onValueChange={setRoleFilter}
              disabled={!canManageCompany || loading}
            >
              <SelectTrigger className="w-full md:w-[220px]">
                <SelectValue placeholder="Rôle" />
              </SelectTrigger>
              <SelectContent>
                {roleFilterOptions.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {canManageCompany && roleCounts.length > 0 && !loading && (
            <div className="mt-4 flex flex-wrap gap-2">
              {roleCounts.map(([label, count]) => (
                <Badge key={label} variant="secondary" className="font-normal">
                  {label} · {count}
                </Badge>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-3 p-6">
              {[1, 2, 3, 4].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : filteredSortedUsers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-14 text-center">
              <UsersIcon className="mb-4 h-14 w-14 text-muted-foreground/40" />
              <p className="text-lg font-medium">{emptyTitle}</p>
              <p className="mt-2 max-w-md text-sm text-muted-foreground">{emptyDescription}</p>
              {canManageCompany && onCreateAppAccess && !searchQuery && roleFilter === 'all' && (
                <Button className="mt-6" onClick={onCreateAppAccess}>
                  <UserPlus className="mr-2 h-4 w-4" />
                  Ajouter un accès applicatif
                </Button>
              )}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <SortableHead
                    label="Nom"
                    active={sortKey === 'name'}
                    order={sortOrder}
                    onClick={() => toggleSort('name')}
                  />
                  <SortableHead
                    label="E-mail"
                    active={sortKey === 'email'}
                    order={sortOrder}
                    onClick={() => toggleSort('email')}
                  />
                  <SortableHead
                    label="Rôle"
                    active={sortKey === 'role'}
                    order={sortOrder}
                    onClick={() => toggleSort('role')}
                  />
                  <TableHead className="w-[100px] text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredSortedUsers.map((user) => (
                  <TableRow
                    key={user.id}
                    className="cursor-pointer"
                    onClick={() => openProfile(user.id)}
                  >
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Avatar className="h-9 w-9">
                          <AvatarFallback className="text-xs">
                            {initials(user.first_name, user.last_name)}
                          </AvatarFallback>
                        </Avatar>
                        <span className="font-medium">
                          {user.first_name} {user.last_name}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{user.email}</TableCell>
                    <TableCell>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge
                          variant="outline"
                          className={cn('border', ROLE_BADGE_CLASS[user.role])}
                        >
                          {getRoleDisplayLabel(user.role, user.role_template_name)}
                        </Badge>
                        {!user.can_edit && (
                          <Badge variant="secondary" className="font-normal">
                            Lecture seule
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                      {user.can_edit ? (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => openEdit(user.id)}
                        >
                          <Edit className="mr-1 h-4 w-4" />
                          Modifier
                        </Button>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
