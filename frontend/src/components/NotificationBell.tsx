import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Bell, BellOff, CheckCheck, ChevronRight, Loader2 } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';
import { fr } from 'date-fns/locale';

import {
  getNotifications,
  getUnreadCount,
  markAllAsRead,
  markAsRead,
  type Notification,
} from '@/api/notifications';
import { useAuth } from '@/contexts/AuthContext';
import { useViewOptional } from '@/contexts/ViewContext';
import { Button } from '@/components/ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Skeleton } from '@/components/ui/skeleton';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import {
  getNotificationHref,
  getNotificationIcon,
  getNotificationIconClass,
  getNotificationTypeLabel,
  resolveNotificationNavContext,
  sortNotifications,
} from '@/lib/notificationUtils';

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
  /** Sidebar repliée : icône seule + tooltip. */
  collapsed?: boolean;
  /** Variante compacte pour le pied de sidebar (moins de hauteur). */
  compact?: boolean;
};

export function NotificationBell({
  companyId,
  enabled = true,
  collapsed = false,
  compact = false,
}: NotificationBellProps) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { user } = useAuth();
  const viewContext = useViewOptional();
  const [open, setOpen] = useState(false);

  const navContext = resolveNotificationNavContext(
    user?.role,
    viewContext?.viewMode,
  );

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
    // Précharge si des non-lues existent (badge visible avant ouverture du panneau)
    enabled: canFetch && (open || (unreadQuery.data?.count ?? 0) > 0),
  });

  const invalidateNotifs = () => {
    void queryClient.invalidateQueries({ queryKey: [...QK_UNREAD, companyId] });
    void queryClient.invalidateQueries({ queryKey: [...QK_LIST, companyId] });
  };

  const patchListLocally = (patch: (items: Notification[]) => Notification[]) => {
    queryClient.setQueryData<Notification[]>([...QK_LIST, companyId], (prev) =>
      prev ? patch(prev) : prev,
    );
  };

  const readMut = useMutation({
    mutationFn: ({ id }: { id: string }) => markAsRead(id, companyId),
    onMutate: async ({ id }) => {
      await queryClient.cancelQueries({ queryKey: [...QK_LIST, companyId] });
      const prev = queryClient.getQueryData<Notification[]>([...QK_LIST, companyId]);
      patchListLocally((items) =>
        items.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
      );
      queryClient.setQueryData([...QK_UNREAD, companyId], (old: { count: number } | undefined) => ({
        count: Math.max(0, (old?.count ?? 0) - 1),
      }));
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData([...QK_LIST, companyId], ctx.prev);
      }
      void queryClient.invalidateQueries({ queryKey: [...QK_UNREAD, companyId] });
    },
    onSettled: invalidateNotifs,
  });

  const readAllMut = useMutation({
    mutationFn: () => markAllAsRead(companyId),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: [...QK_LIST, companyId] });
      const prev = queryClient.getQueryData<Notification[]>([...QK_LIST, companyId]);
      patchListLocally((items) => items.map((n) => ({ ...n, is_read: true })));
      queryClient.setQueryData([...QK_UNREAD, companyId], { count: 0 });
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) {
        queryClient.setQueryData([...QK_LIST, companyId], ctx.prev);
      }
      void queryClient.invalidateQueries({ queryKey: [...QK_UNREAD, companyId] });
    },
    onSettled: invalidateNotifs,
  });

  const count = unreadQuery.data?.count ?? 0;
  const showBadge = count > 0;

  const sortedList = useMemo(
    () => sortNotifications(listQuery.data ?? []),
    [listQuery.data],
  );

  const handleNotificationAction = (n: Notification) => {
    const href = getNotificationHref(n.type, navContext);

    if (!n.is_read) {
      readMut.mutate({ id: n.id });
    }

    if (href) {
      setOpen(false);
      navigate(href);
    }
  };

  if (!companyId?.trim()) {
    return null;
  }

  const triggerButton = (
    <Button
      type="button"
      variant="ghost"
      size={collapsed ? 'icon' : 'sm'}
      className={cn(
        'relative shrink-0 text-muted-foreground hover:bg-primary/10 hover:text-primary',
        collapsed && 'h-8 w-8',
        !collapsed && compact && 'h-7 w-full justify-start gap-1.5 px-2',
        !collapsed && !compact && 'h-9 w-full justify-start gap-2 px-2',
      )}
      aria-label={
        showBadge
          ? `Notifications, ${count} non lue${count > 1 ? 's' : ''}`
          : 'Notifications'
      }
    >
      <Bell className="h-4 w-4 shrink-0" />
      {!collapsed && (
        <span
          className={cn(
            'flex-1 truncate text-left font-medium',
            compact ? 'text-xs' : 'text-sm',
          )}
        >
          Notifications
        </span>
      )}
      {showBadge ? (
        <span
          className={cn(
            'flex items-center justify-center rounded-full bg-destructive font-bold leading-none text-destructive-foreground',
            collapsed
              ? 'pointer-events-none absolute -right-0.5 -top-0.5 h-[18px] min-w-[18px] px-1 text-[10px]'
              : 'h-5 min-w-5 px-1.5 text-[11px]',
          )}
          aria-hidden
        >
          {badgeLabel(count)}
        </span>
      ) : null}
      {!collapsed && <ChevronRight className="ml-auto h-4 w-4 shrink-0 opacity-40" aria-hidden />}
    </Button>
  );

  return (
    <Popover open={open} onOpenChange={setOpen}>
      {collapsed ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <PopoverTrigger asChild>{triggerButton}</PopoverTrigger>
          </TooltipTrigger>
          <TooltipContent side="right">Notifications</TooltipContent>
        </Tooltip>
      ) : (
        <PopoverTrigger asChild>{triggerButton}</PopoverTrigger>
      )}
      <PopoverContent
        className="w-[min(100vw-2rem,400px)] p-0 shadow-lg"
        side={collapsed ? 'right' : 'top'}
        align={collapsed ? 'start' : 'center'}
        sideOffset={8}
      >
        <div className="border-b px-4 py-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-sm font-semibold leading-none">Notifications</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {showBadge
                  ? `${count} non lue${count > 1 ? 's' : ''}`
                  : 'Vous êtes à jour'}
              </p>
            </div>
            {count > 0 ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-8 shrink-0 gap-1.5 text-xs"
                disabled={readAllMut.isPending}
                onClick={() => readAllMut.mutate()}
              >
                {readAllMut.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <CheckCheck className="h-3.5 w-3.5" />
                )}
                Tout lu
              </Button>
            ) : null}
          </div>
        </div>
        <div className="max-h-[min(70vh,360px)] overflow-y-auto overscroll-contain p-2">
            {listQuery.isLoading && !listQuery.data?.length ? (
              <div className="space-y-2 px-1 py-1">
                <Skeleton className="h-16 w-full rounded-lg" />
                <Skeleton className="h-16 w-full rounded-lg" />
                <Skeleton className="h-16 w-full rounded-lg" />
              </div>
            ) : listQuery.isError ? (
              <div className="px-3 py-8 text-center">
                <p className="text-sm text-muted-foreground">
                  Impossible de charger les notifications.
                  {import.meta.env.DEV ? (
                    <span className="mt-1 block text-xs text-destructive/80">
                      Vérifiez la console réseau (API /api/notifications).
                    </span>
                  ) : null}
                </p>
                <Button
                  type="button"
                  variant="link"
                  size="sm"
                  className="mt-2 h-auto p-0 text-xs"
                  onClick={() => void listQuery.refetch()}
                >
                  Réessayer
                </Button>
              </div>
            ) : !sortedList.length ? (
              <div className="flex flex-col items-center gap-2 px-4 py-10 text-center">
                <BellOff className="h-8 w-8 text-muted-foreground/50" aria-hidden />
                <p className="text-sm font-medium text-foreground">Aucune notification</p>
                <p className="max-w-[280px] text-xs text-muted-foreground">
                  {user?.role === 'rh' || user?.role === 'admin'
                    ? 'Les notifications personnelles (absences, documents, rappels) nécessitent un profil collaborateur lié à votre compte. Les tâches RH à traiter restent visibles dans la navigation (pastilles rouges).'
                    : 'Les alertes liées à vos absences, documents signés ou rappels médicaux apparaîtront ici lorsque votre compte est associé à un profil collaborateur dans cette entreprise.'}
                </p>
              </div>
            ) : (
              <ul className="space-y-1" role="list">
                {sortedList.map((n) => {
                  const Icon = getNotificationIcon(n.type);
                  const href = getNotificationHref(n.type, navContext);
                  const isActionable = Boolean(href) || !n.is_read;

                  return (
                    <li key={n.id}>
                      <button
                        type="button"
                        className={cn(
                          'group flex w-full gap-3 rounded-lg border border-transparent px-3 py-2.5 text-left text-sm transition-colors',
                          !n.is_read && 'border-primary/15 bg-primary/5',
                          isActionable && 'hover:border-border hover:bg-muted/50',
                          !isActionable && 'cursor-default',
                        )}
                        onClick={() => {
                          if (isActionable) handleNotificationAction(n);
                        }}
                        disabled={readMut.isPending}
                      >
                        <span
                          className={cn(
                            'relative mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted',
                          )}
                        >
                          <Icon
                            className={cn('h-4 w-4', getNotificationIconClass(n.type))}
                            aria-hidden
                          />
                          {!n.is_read ? (
                            <span
                              className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-primary ring-2 ring-background"
                              aria-hidden
                            />
                          ) : null}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="mb-0.5 flex flex-wrap items-center gap-1.5">
                            <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                              {getNotificationTypeLabel(n.type)}
                            </span>
                          </span>
                          <span className="block text-foreground leading-snug">{n.message}</span>
                          <span className="mt-1 block text-xs text-muted-foreground">
                            {formatDistanceToNow(new Date(n.created_at), {
                              addSuffix: true,
                              locale: fr,
                            })}
                            {href ? (
                              <span className="ml-1 text-primary/80 group-hover:text-primary">
                                · Voir
                              </span>
                            ) : null}
                          </span>
                        </span>
                        {href ? (
                          <ChevronRight
                            className="mt-1 h-4 w-4 shrink-0 self-start text-muted-foreground/50 group-hover:text-muted-foreground"
                            aria-hidden
                          />
                        ) : null}
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
