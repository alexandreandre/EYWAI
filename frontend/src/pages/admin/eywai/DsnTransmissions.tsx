import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  getAdminNetEntreprisesTransmissions,
  TRANSMISSION_MODE_LABELS,
  TRANSMISSION_STATUS_LABELS,
  type TransmissionStatus,
} from '@/api/netEntreprises';
import { AdminPageHeader } from '@/features/admin/components/eywai/AdminPageHeader';
import TransmissionStatusBadge from '@/features/net-entreprises/components/TransmissionStatusBadge';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { NetEntreprisesLogo } from '@/features/net-entreprises/components/NetEntreprisesLogo';

const STATUS_FILTERS: TransmissionStatus[] = [
  'generated',
  'manual',
  'queued',
  'sent',
  'acknowledged',
  'rejected',
];

function formatDate(value: string | null): string {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString('fr-FR', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return value;
  }
}

export default function DsnTransmissions() {
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [period, setPeriod] = useState<string>('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['admin-dsn-transmissions', statusFilter, period],
    queryFn: () =>
      getAdminNetEntreprisesTransmissions({
        status: statusFilter === 'all' ? undefined : statusFilter,
        period: period || undefined,
      }),
  });

  const counts = data?.counts_by_status ?? {};
  const transmissions = data?.transmissions ?? [];

  const total = useMemo(
    () => Object.values(counts).reduce((a, b) => a + b, 0),
    [counts],
  );

  return (
    <div className="space-y-6">
      <AdminPageHeader
        title="Télétransmissions DSN"
        description="Suivi des dépôts DSN de toutes les entreprises de la plateforme."
        actions={<NetEntreprisesLogo />}
      />

      {/* Compteurs par statut */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-7">
        <Card>
          <CardContent className="p-4">
            <p className="text-sm text-muted-foreground">Total</p>
            {isLoading ? (
              <Skeleton className="mt-1 h-8 w-12" />
            ) : (
              <p className="mt-1 text-2xl font-bold">{total}</p>
            )}
          </CardContent>
        </Card>
        {STATUS_FILTERS.map((s) => (
          <Card key={s}>
            <CardContent className="p-4">
              <p className="text-xs text-muted-foreground">
                {TRANSMISSION_STATUS_LABELS[s]}
              </p>
              {isLoading ? (
                <Skeleton className="mt-1 h-8 w-10" />
              ) : (
                <p className="mt-1 text-2xl font-bold">{counts[s] ?? 0}</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle className="text-base">Détail des transmissions</CardTitle>
          <div className="flex flex-wrap items-center gap-3">
            <Input
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              placeholder="Période (AAAA-MM)"
              className="w-40"
            />
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-48">
                <SelectValue placeholder="Statut" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous les statuts</SelectItem>
                {STATUS_FILTERS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {TRANSMISSION_STATUS_LABELS[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : isError ? (
            <p className="text-sm text-destructive">Chargement impossible.</p>
          ) : transmissions.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              Aucune transmission pour ces critères.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Entreprise</TableHead>
                    <TableHead>Période</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead>Mode</TableHead>
                    <TableHead>Accusé</TableHead>
                    <TableHead>Générée le</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {transmissions.map((t) => (
                    <TableRow key={t.id}>
                      <TableCell className="font-medium">
                        {t.company_name || t.company_id}
                      </TableCell>
                      <TableCell>{t.period}</TableCell>
                      <TableCell>
                        <TransmissionStatusBadge status={t.status} />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {TRANSMISSION_MODE_LABELS[t.mode] ?? t.mode}
                      </TableCell>
                      <TableCell className="text-sm">
                        {t.net_entreprises_ref || '—'}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {formatDate(t.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
