// Liste des tickets support (filtres et tableau selon le rôle)

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';
import { Loader2 } from 'lucide-react';

import apiClient from '@/api/apiClient';
import { getTickets, type Ticket, type TicketUrgency } from '@/api/support';
import { getCompanyUsers } from '@/api/permissions';
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
  'Sorties de salarié',
  'Simulation de paie',
  'Conventions collectives',
  'Saisies & Avances',
  'Titres de séjour',
  'Entretiens annuels',
  'Primes & Participation',
  'Mutuelle',
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

export default function TicketsHistoryPage() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();

  const isSuperAdmin = Boolean(user?.is_super_admin || user?.role === 'super_admin');
  const isRhManager =
    !isSuperAdmin &&
    user?.role != null &&
    ['admin', 'rh', 'collaborateur_rh'].includes(user.role);
  const isEmployee = !isSuperAdmin && !isRhManager;

  const [companyId, setCompanyId] = useState('');
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
    enabled: isSuperAdmin,
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
    if (isSuperAdmin && saCompanies.length) {
      return Object.fromEntries(saCompanies.map((c) => [c.id, c.company_name]));
    }
    if (activeCompany?.company_id) {
      return { [activeCompany.company_id]: activeCompany.company_name };
    }
    return {} as Record<string, string>;
  }, [activeCompany, isSuperAdmin, saCompanies]);

  const apiFilters = useMemo(() => {
    const out: Record<string, string> = {};
    if (isSuperAdmin && companyId) out.company_id = companyId;
    if (dateFrom) out.date_from = dateFrom;
    if (dateTo) out.date_to = dateTo;
    if (urgency) out.urgency = urgency;
    if (status) out.status = status;
    if (module) out.module = module;
    if (isRhManager && userId) out.user_id = userId;
    return out;
  }, [companyId, dateFrom, dateTo, isRhManager, isSuperAdmin, module, status, urgency, userId]);

  const filterKey = JSON.stringify(apiFilters);

  const {
    data: tickets = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['support-tickets', filterKey],
    queryFn: () => getTickets(Object.keys(apiFilters).length ? apiFilters : undefined),
  });

  const pageTitle = isSuperAdmin
    ? 'Tous les tickets support'
    : isRhManager
      ? `Tickets support — ${activeCompany?.company_name ?? '…'}`
      : 'Mes tickets support';

  const showCompanyCol = isSuperAdmin;
  const showUserCol = isSuperAdmin || isRhManager;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{pageTitle}</h1>
      </div>

      {!isEmployee ? (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-base">Filtres</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {isSuperAdmin ? (
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
                </TableRow>
              </TableHeader>
              <TableBody>
                {tickets.map((t) => (
                  <TableRow
                    key={t.id}
                    className="cursor-pointer"
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
                  </TableRow>
                ))}
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
    </div>
  );
}
