import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { FileText } from 'lucide-react';
import { Link } from 'react-router-dom';

import { getNotifications, markAsRead, type Notification } from '@/api/notifications';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';

const QK_LIST = ['notifications-list'] as const;
const QK_UNREAD = ['notifications-unread'] as const;

function isUnreadNewDocument(n: Notification): boolean {
  return n.type === 'nouveau_document' && !n.is_read;
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

  const unreadNewDocs = (listQuery.data ?? []).filter(isUnreadNewDocument);

  const dismissMut = useMutation({
    mutationFn: (id: string) => markAsRead(id, companyId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: [...QK_LIST, companyId] });
      void queryClient.invalidateQueries({ queryKey: [...QK_UNREAD, companyId] });
    },
  });

  if (!companyId || unreadNewDocs.length === 0) {
    return null;
  }

  const latest = unreadNewDocs[0];

  return (
    <Card className="border-blue-200 bg-blue-50/80 dark:border-blue-900/50 dark:bg-blue-950/20">
      <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div className="flex min-w-0 items-start gap-2">
          <FileText className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
          <div className="min-w-0">
            <p className="text-sm font-medium">
              {unreadNewDocs.length === 1
                ? 'Nouveau document disponible'
                : `${unreadNewDocs.length} nouveaux documents disponibles`}
            </p>
            <p className="text-sm text-muted-foreground line-clamp-2">{latest.message}</p>
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button variant="secondary" size="sm" asChild>
            <Link to="/employee/documents">Voir mes documents</Link>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={dismissMut.isPending}
            onClick={() => {
              for (const n of unreadNewDocs) {
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
