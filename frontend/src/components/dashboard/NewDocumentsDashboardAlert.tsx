import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileText, Euro } from 'lucide-react';
import { Link } from 'react-router-dom';

import { getNotifications, markAsRead, type Notification } from '@/api/notifications';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import {
  isPayslipAlertNotification,
  isUnreadDocumentAlertNotification,
} from '@/lib/notificationUtils';

const QK_LIST = ['notifications-list'] as const;
const QK_UNREAD = ['notifications-unread'] as const;

function partitionDocumentAlerts(notifications: Notification[]) {
  const unread = notifications.filter(isUnreadDocumentAlertNotification);
  const bulletins = unread.filter((n) => isPayslipAlertNotification(n));
  const documents = unread.filter(
    (n) => n.type === 'nouveau_document' && !isPayslipAlertNotification(n),
  );
  return { unread, bulletins, documents };
}

function buildAlertTitle(bulletinCount: number, documentCount: number): string {
  if (bulletinCount > 0 && documentCount === 0) {
    return bulletinCount === 1
      ? 'Nouveau bulletin de paie disponible'
      : `${bulletinCount} nouveaux bulletins de paie disponibles`;
  }
  if (documentCount > 0 && bulletinCount === 0) {
    return documentCount === 1
      ? 'Nouveau document disponible'
      : `${documentCount} nouveaux documents disponibles`;
  }
  const total = bulletinCount + documentCount;
  return total === 1
    ? 'Nouvelle information dans votre espace'
    : `${total} nouveautés dans votre espace`;
}

export function NewDocumentsDashboardAlert() {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();

  const listQuery = useQuery({
    queryKey: [...QK_LIST, companyId],
    queryFn: () => getNotifications(companyId!),
    enabled: Boolean(companyId),
    refetchInterval: 60_000,
  });

  const { unread, bulletins, documents } = partitionDocumentAlerts(listQuery.data ?? []);

  const dismissMut = useMutation({
    mutationFn: (id: string) => markAsRead(id, companyId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...QK_LIST, companyId] });
      void queryClient.invalidateQueries({ queryKey: [...QK_UNREAD, companyId] });
    },
  });

  if (!companyId || unread.length === 0) {
    return null;
  }

  const latest = unread[0];
  const title = buildAlertTitle(bulletins.length, documents.length);
  const Icon = bulletins.length > 0 && documents.length === 0 ? Euro : FileText;

  return (
    <Card className="border-blue-200 bg-blue-50/80 dark:border-blue-900/50 dark:bg-blue-950/20">
      <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div className="flex min-w-0 items-start gap-2">
          <Icon className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
          <div className="min-w-0">
            <p className="text-sm font-medium">{title}</p>
            <p className="text-sm text-muted-foreground line-clamp-2">{latest.message}</p>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {bulletins.length > 0 && (
            <Button variant="secondary" size="sm" asChild>
              <Link to="/payslips">
                {bulletins.length === 1 ? 'Voir mon bulletin' : 'Voir mes bulletins'}
              </Link>
            </Button>
          )}
          {documents.length > 0 && (
            <Button variant="secondary" size="sm" asChild>
              <Link to="/employee/documents">
                {documents.length === 1 ? 'Voir mon document' : 'Voir mes documents'}
              </Link>
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            disabled={dismissMut.isPending}
            onClick={() => {
              for (const n of unread) {
                dismissMut.mutate(n.id);
              }
            }}
          >
            Marquer comme lu
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
