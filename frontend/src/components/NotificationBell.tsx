import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Bell, FileCheck, Loader2 } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { fr } from 'date-fns/locale';

import {
  getNotifications,
  getUnreadCount,
  markAllAsRead,
  markAsRead,
  type Notification,
} from '@/api/notifications';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';

const QK_UNREAD = ['notifications-unread'] as const;
const QK_LIST = ['notifications-list'] as const;

function badgeLabel(count: number): string {
  if (count <= 0) return '';
  return count > 9 ? '9+' : String(count);
}

type NotificationBellProps = {
  companyId: string;
  /** Si false, aucune requête. */
  enabled?: boolean;
};

export function NotificationBell({ companyId, enabled = true }: NotificationBellProps) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);

  const hasCompany = Boolean(companyId?.trim());
  const canFetch = hasCompany && enabled;

  const unreadQuery = useQuery({
    queryKey: [...QK_UNREAD, companyId],
    queryFn: () => getUnreadCount(companyId),
    enabled: canFetch,
    refetchInterval: 60_000,
  });

  const listQuery = useQuery({
    queryKey: [...QK_LIST, companyId],
    queryFn: () => getNotifications(companyId),
    enabled: canFetch && open,
  });

  const invalidateNotifs = () => {
    void queryClient.invalidateQueries({ queryKey: [...QK_UNREAD, companyId] });
    void queryClient.invalidateQueries({ queryKey: [...QK_LIST, companyId] });
  };

  const readMut = useMutation({
    mutationFn: ({ id }: { id: string }) => markAsRead(id, companyId),
    onSuccess: invalidateNotifs,
  });

  const readAllMut = useMutation({
    mutationFn: () => markAllAsRead(companyId),
    onSuccess: invalidateNotifs,
  });

  const count = unreadQuery.data?.count ?? 0;
  const showBadge = count > 0;

  const handleRowClick = (n: Notification) => {
    if (!companyId || n.is_read) return;
    readMut.mutate({ id: n.id });
  };

  if (!companyId?.trim()) {
    return null;
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="relative h-8 w-8 shrink-0 text-muted-foreground hover:bg-primary/10 hover:text-primary"
          aria-label="Notifications"
        >
          <Bell className="h-4 w-4" />
          {showBadge ? (
            <span
              className="pointer-events-none absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-destructive px-1 text-[10px] font-bold leading-none text-destructive-foreground"
              aria-hidden
            >
              {badgeLabel(count)}
            </span>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[min(100vw-2rem,380px)] p-0" align="end">
        <div className="flex items-center justify-between border-b px-3 py-2">
          <p className="text-sm font-semibold">Notifications</p>
          {count > 0 ? (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 text-xs"
              disabled={readAllMut.isPending}
              onClick={() => readAllMut.mutate()}
            >
              {readAllMut.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
              Tout marquer comme lu
            </Button>
          ) : null}
        </div>
        <ScrollArea className="max-h-[min(70vh,320px)]">
          <div className="p-2">
            {listQuery.isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
                <Skeleton className="h-14 w-full" />
              </div>
            ) : listQuery.isError ? (
              <p className="px-2 py-6 text-center text-sm text-muted-foreground">
                Impossible de charger les notifications.
              </p>
            ) : !listQuery.data?.length ? (
              <p className="px-2 py-8 text-center text-sm text-muted-foreground">Aucune notification.</p>
            ) : (
              <ul className="space-y-1">
                {listQuery.data.map((n) => (
                  <li key={n.id}>
                    <button
                      type="button"
                      className={cn(
                        'flex w-full gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors',
                        n.is_read ? 'bg-transparent hover:bg-muted/60' : 'bg-primary/8 hover:bg-primary/12',
                      )}
                      onClick={() => handleRowClick(n)}
                      disabled={readMut.isPending}
                    >
                      {n.type === 'avenant_signe' ? (
                        <FileCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" aria-hidden />
                      ) : (
                        <Bell className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                      )}
                      <span className="min-w-0 flex-1">
                        <span className="block text-foreground">{n.message}</span>
                        <span className="text-xs text-muted-foreground">
                          {formatDistanceToNow(new Date(n.created_at), {
                            addSuffix: true,
                            locale: fr,
                          })}
                        </span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
}
