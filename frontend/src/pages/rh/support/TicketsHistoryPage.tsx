// Liste des tickets support (filtres et tableau selon le rôle)

import { useEffect, useMemo, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { differenceInHours } from 'date-fns';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';
import { Loader2 } from 'lucide-react';

import apiClient from '@/api/apiClient';
import { isPlatformAdmin } from '@/lib/platformAdmin';
import { getTickets, type Ticket, type TicketUrgency } from '@/api/support';
import { getCompanyUsers } from '@/api/permissions';
import {
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';
import { SupportTicketDetailSheet } from '@/components/support/SupportTicketDetailSheet';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAuth } from '@/contexts/AuthContext';
import { useCompany } from '@/contexts/CompanyContext';

const ALL_VALUE = '__all__';

const MODULE_OPTIONS = [
  'Employés',
  'Paie & Bulletins',
  'Absences & Congés',
  'Notes de frais',
  'Calendriers & Plannings',
  'Badgeuse & pointage',
  'Sorties de salarié',
  'Simulation de paie',
  'Conventions collectives',
  'Saisies & Avances',
  'Titres de séjour',
  'Entretiens annuels',
  'Promotions',
  'Primes & Participation',
  'Mutuelle',
  'Recrutement',
  'CSE & dialogue social',
  'Suivi médical',
  'Mon compte / Accès',
  'Copilot IA',
  'Autre',
];

const URGENCY_OPTIONS: { value: TicketUrgency; label: string }[] = [
  { value: 'critique', label: 'Critique' },
  { value: 'elevee', label: 'Élevée' },
  { value: 'normale', label: 'Normale' },
  { value: 'faible', label: 'Faible' },
];

const STATUS_OPTIONS: { value: Ticket['status']; label: string }[] = [
  { value: 'envoye', label: 'Envoyé' },
  { value: 'en_cours', label: 'En cours' },
  { value: 'resolu', label: 'Résolu' },
  { value: 'cloture', label: 'Clôturé' },
];

type CompanyRow = { id: string; company_name: string };

type CompanyUserRow = {
  id: string;
  first_name?: string;
  last_name?: string;
  email?: string;
};

function formatRowDate(iso: string): string {
  try {
    return format(new Date(iso), 'dd/MM/yyyy HH:mm', { locale: fr });
  } catch {
    return iso;
  }
}

function ticketCompanyDisplay(t: Ticket): string {
  const c = t.companies;
  let name = '';
  if (c) {
    if (Array.isArray(c)) name = c[0]?.company_name ?? '';
    else name = c.company_name ?? '';
  }
  return name || `${t.company_id.slice(0, 8)}…`;
}

function descriptionExcerpt(text: string, max = 70): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}…`;
}

function urgencyBadge(urgency: TicketUrgency) {
  switch (urgency) {
    case 'critique':
      return <Badge variant="destructive">{urgency}</Badge>;
    case 'elevee':
      return (
        <Badge
          variant="outline"
          className="border-orange-500 text-orange-700 bg-orange-50 dark:bg-orange-950/30 dark:text-orange-300"
        >
          {urgency}
        </Badge>
      );
    case 'normale':
      return <Badge variant="default">{urgency}</Badge>;
    case 'faible':
      return <Badge variant="secondary">{urgency}</Badge>;
    default:
      return <Badge variant="outline">{urgency}</Badge>;
  }
}

function statusBadge(status: Ticket['status']) {
  switch (status) {
    case 'envoye':
      return (
        <Badge className="bg-blue-600 hover:bg-blue-600 text-white border-transparent">{status}</Badge>
      );
    case 'en_cours':
      return (
        <Badge className="bg-orange-500 hover:bg-orange-500 text-white border-transparent">{status}</Badge>
      );
    case 'resolu':
      return (
        <Badge className="bg-green-600 hover:bg-green-600 text-white border-transparent">{status}</Badge>
      );
    case 'cloture':
      return (
        <Badge className="bg-slate-500 hover:bg-slate-500 text-white border-transparent">{status}</Badge>
      );
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function isTicketSlaOverdue(createdAt: string, status: Ticket['status']): boolean {
  if (status === 'resolu' || status === 'cloture') return false;
  try {
    return differenceInHours(new Date(), new Date(createdAt)) >= 48;
  } catch {
    return false;
  }
}

export default function TicketsHistoryPage() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const isAdminSupportHub = location.pathname === '/super-admin/support';
  const companyFromUrl = searchParams.get('company') ?? '';

  const isPlatformAdminUser = isPlatformAdmin(user);
  const isRhManager =
    !isPlatformAdminUser &&
    user?.role != null &&
    ['admin', 'rh', 'collaborateur_rh'].includes(user.role);
  const isEmployee = !isPlatformAdminUser && !isRhManager;

  const [companyId, setCompanyId] = useState(companyFromUrl);

  useEffect(() => {
    if (companyFromUrl) setCompanyId(companyFromUrl);
  }, [companyFromUrl]);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [urgency, setUrgency] = useState('');
  const [status, setStatus] = useState('');
  const [module, setModule] = useState('');
  const [userId, setUserId] = useState('');
  const [selectedTicketId, setSelectedTicketId] = useState<string | null>(null);

  const { data: saCompanies = [] } = useQuery({
    queryKey: ['support-tickets', 'super-admin-companies'],
    queryFn: async () => {
      const response = await apiClient.get<{ companies: CompanyRow[] }>('/api/super-admin/companies', {
        params: { search: '' },
      });
      return response.data.companies ?? [];
    },
    enabled: isPlatformAdminUser,
  });

  const { data: companyUsers = [] } = useQuery({
    queryKey: ['support-tickets', 'company-users', activeCompany?.company_id],
    queryFn: () => getCompanyUsers(activeCompany!.company_id),
    enabled: isRhManager && Boolean(activeCompany?.company_id),
  });

  const userLabelMap = useMemo(() => {
    const m: Record<string, string> = {};
    for (const u of companyUsers as CompanyUserRow[]) {
      const name = [u.first_name, u.last_name].filter(Boolean).join(' ').trim();
      m[u.id] = name || u.email || u.id;
    }
    return m;
  }, [companyUsers]);

  const companyNameById = useMemo(() => {
    if (isPlatformAdminUser && saCompanies.length) {
      return Object.fromEntries(saCompanies.map((c) => [c.id, c.company_name]));
    }
    if (activeCompany?.company_id) {
      return { [activeCompany.company_id]: activeCompany.company_name };
    }
    return {} as Record<string, string>;
  }, [activeCompany, isPlatformAdminUser, saCompanies]);

  const apiFilters = useMemo(() => {
    const out: Record<string, string> = {};
    if (isPlatformAdminUser && companyId) out.company_id = companyId;
    if (dateFrom) out.date_from = dateFrom;
    if (dateTo) out.date_to = dateTo;
    if (urgency) out.urgency = urgency;
    if (status) out.status = status;
    if (module) out.module = module;
    if (isRhManager && userId) out.user_id = userId;
    return out;
  }, [companyId, dateFrom, dateTo, isRhManager, isPlatformAdminUser, module, status, urgency, userId]);

  const filterKey = JSON.stringify(apiFilters);

  const {
    data: tickets = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['support-tickets', filterKey],
    queryFn: () => getTickets(Object.keys(apiFilters).length ? apiFilters : undefined),
  });

  const pageTitle = isPlatformAdminUser
    ? 'Tous les tickets support'
    : isRhManager
      ? `Tickets support — ${activeCompany?.company_name ?? '…'}`
      : 'Mes tickets support';

  const showCompanyCol = isPlatformAdminUser;
  const showUserCol = isPlatformAdminUser || isRhManager;
  const showSlaCol = isAdminSupportHub && isPlatformAdminUser;

  const pageBody = (
    <>
      {!isAdminSupportHub ? <EmployeePageHeader title={pageTitle} /> : null}

      {!isEmployee ? (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Filtres</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {isPlatformAdminUser ? (
              <div className="space-y-2">
                <Label>Entreprise</Label>
                <Select
                  value={companyId || ALL_VALUE}
                  onValueChange={(v) => setCompanyId(v === ALL_VALUE ? '' : v)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Toutes les entreprises" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_VALUE}>Toutes</SelectItem>
                    {saCompanies.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.company_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}

            <div className="space-y-2">
              <Label htmlFor="f-date-from">Date début</Label>
              <Input
                id="f-date-from"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="f-date-to">Date fin</Label>
              <Input
                id="f-date-to"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Urgence</Label>
              <Select value={urgency || ALL_VALUE} onValueChange={(v) => setUrgency(v === ALL_VALUE ? '' : v)}>
                <SelectTrigger>
                  <SelectValue placeholder="Toutes" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_VALUE}>Toutes</SelectItem>
                  {URGENCY_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Statut</Label>
              <Select value={status || ALL_VALUE} onValueChange={(v) => setStatus(v === ALL_VALUE ? '' : v)}>
                <SelectTrigger>
                  <SelectValue placeholder="Tous" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_VALUE}>Tous</SelectItem>
                  {STATUS_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Module</Label>
              <Select value={module || ALL_VALUE} onValueChange={(v) => setModule(v === ALL_VALUE ? '' : v)}>
                <SelectTrigger>
                  <SelectValue placeholder="Tous" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_VALUE}>Tous</SelectItem>
                  {MODULE_OPTIONS.map((m) => (
                    <SelectItem key={m} value={m}>
                      {m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {isRhManager ? (
              <div className="space-y-2">
                <Label>Utilisateur</Label>
                <Select value={userId || ALL_VALUE} onValueChange={(v) => setUserId(v === ALL_VALUE ? '' : v)}>
                  <SelectTrigger>
                    <SelectValue placeholder="Tous" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={ALL_VALUE}>Tous</SelectItem>
                    {(companyUsers as CompanyUserRow[]).map((u) => (
                      <SelectItem key={u.id} value={u.id}>
                        {userLabelMap[u.id] ?? u.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-2 p-6">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : isError ? (
            <p className="text-destructive p-6 text-sm">
              Impossible de charger les tickets. Réessayez.
            </p>
          ) : tickets.length === 0 ? (
            <p className="text-muted-foreground p-6 text-sm">Aucun ticket pour le moment.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  {showCompanyCol ? <TableHead>Entreprise</TableHead> : null}
                  {showUserCol ? <TableHead>Utilisateur</TableHead> : null}
                  <TableHead>Module</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Urgence</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Statut</TableHead>
                  {showSlaCol ? <TableHead>Délai</TableHead> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {tickets.map((t) => {
                  const slaOverdue = showSlaCol && isTicketSlaOverdue(t.created_at, t.status);
                  return (
                  <TableRow
                    key={t.id}
                    className={`cursor-pointer ${slaOverdue ? 'bg-amber-50/80 dark:bg-amber-950/20' : ''}`}
                    onClick={() => setSelectedTicketId(t.id)}
                  >
                    <TableCell className="whitespace-nowrap text-sm">
                      {formatRowDate(t.created_at)}
                    </TableCell>
                    {showCompanyCol ? (
                      <TableCell className="max-w-[160px] truncate text-sm">
                        {ticketCompanyDisplay(t)}
                      </TableCell>
                    ) : null}
                    {showUserCol ? (
                      <TableCell className="max-w-[140px] truncate text-sm">
                        {userLabelMap[t.user_id] ?? `${t.user_id.slice(0, 8)}…`}
                      </TableCell>
                    ) : null}
                    <TableCell className="max-w-[140px] truncate text-sm">{t.module}</TableCell>
                    <TableCell className="max-w-[140px] truncate text-sm">{t.request_type}</TableCell>
                    <TableCell>{urgencyBadge(t.urgency)}</TableCell>
                    <TableCell className="max-w-[220px] text-sm text-muted-foreground">
                      {descriptionExcerpt(t.description)}
                    </TableCell>
                    <TableCell>{statusBadge(t.status)}</TableCell>
                    {showSlaCol ? (
                      <TableCell className="text-xs">
                        {slaOverdue ? (
                          <Badge variant="outline" className="border-amber-500 text-amber-700">
                            +48 h
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">OK</span>
                        )}
                      </TableCell>
                    ) : null}
                  </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <SupportTicketDetailSheet
        ticketId={selectedTicketId}
        onClose={() => setSelectedTicketId(null)}
        companyNameById={companyNameById}
      />
    </>
  );

  if (isAdminSupportHub) {
    return <div className="space-y-6">{pageBody}</div>;
  }

  return <EmployeePageShell>{pageBody}</EmployeePageShell>;
}
