// Détail d'un ticket support (Sheet) + changement de statut Super Admin

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import { fr } from 'date-fns/locale';
import { Loader2 } from 'lucide-react';

import {
  getTicketDetail,
  updateTicketStatus,
  type Ticket,
  type TicketStatusAdminUpdate,
} from '@/api/support';
import { getCompanyUsers } from '@/api/permissions';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { useToast } from '@/components/ui/use-toast';
import { useAuth } from '@/contexts/AuthContext';
import { cn } from '@/lib/utils';

export interface SupportTicketDetailSheetProps {
  ticketId: string | null;
  onClose: () => void;
  /** Super admin : noms d&apos;entreprise pour l&apos;affichage émetteur */
  companyNameById?: Record<string, string>;
}

function formatTicketDate(iso: string): string {
  try {
    return format(new Date(iso), 'dd/MM/yyyy HH:mm', { locale: fr });
  } catch {
    return iso;
  }
}

function truncateId(id: string, len = 8): string {
  if (id.length <= len) return id;
  return `${id.slice(0, len)}…`;
}

function statusBadgeVariant(
  status: Ticket['status'],
): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'envoye':
      return 'default';
    case 'en_cours':
      return 'secondary';
    case 'resolu':
      return 'outline';
    case 'cloture':
      return 'secondary';
    default:
      return 'outline';
  }
}

function statusBadgeClass(status: Ticket['status']): string {
  switch (status) {
    case 'envoye':
      return 'bg-blue-600 hover:bg-blue-600 text-white border-transparent';
    case 'en_cours':
      return 'bg-orange-500 hover:bg-orange-500 text-white border-transparent';
    case 'resolu':
      return 'bg-green-600 hover:bg-green-600 text-white border-transparent';
    case 'cloture':
      return 'bg-slate-500 hover:bg-slate-500 text-white border-transparent';
    default:
      return '';
  }
}

function urgencyBadgeClass(urgency: Ticket['urgency']): string {
  switch (urgency) {
    case 'critique':
      return '';
    case 'elevee':
      return 'border-orange-500 text-orange-700 bg-orange-50 dark:bg-orange-950/30 dark:text-orange-300';
    case 'normale':
      return '';
    case 'faible':
      return 'text-muted-foreground';
    default:
      return '';
  }
}

const ADMIN_STATUS_OPTIONS: { value: TicketStatusAdminUpdate; label: string }[] = [
  { value: 'en_cours', label: 'En cours' },
  { value: 'resolu', label: 'Résolu' },
  { value: 'cloture', label: 'Clôturé' },
];

export function SupportTicketDetailSheet({
  ticketId,
  onClose,
  companyNameById,
}: SupportTicketDetailSheetProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [statusSelect, setStatusSelect] = useState<TicketStatusAdminUpdate | ''>('');

  useEffect(() => {
    setStatusSelect('');
  }, [ticketId]);

  const isSuperAdmin = Boolean(user?.is_super_admin || user?.role === 'super_admin');
  const isRhManager =
    !isSuperAdmin &&
    user?.role != null &&
    ['admin', 'rh', 'collaborateur_rh'].includes(user.role);

  const showEmitter = isSuperAdmin || isRhManager;

  const {
    data: ticket,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ['support-ticket', ticketId],
    queryFn: () => getTicketDetail(ticketId!),
    enabled: Boolean(ticketId),
  });

  const { data: companyUsers = [] } = useQuery({
    queryKey: ['company-users-emitter', ticket?.company_id],
    queryFn: () => getCompanyUsers(ticket!.company_id),
    enabled: Boolean(showEmitter && ticket?.company_id),
  });

  const emitter = useMemo(() => {
    if (!ticket) return null;
    return (companyUsers as Array<{ id: string; first_name?: string; last_name?: string; email?: string }>).find(
      (u) => u.id === ticket.user_id,
    );
  }, [companyUsers, ticket]);

  const emitterCompanyName = useMemo(() => {
    if (!ticket) return '';
    return companyNameById?.[ticket.company_id] ?? ticket.company_id;
  }, [companyNameById, ticket]);

  const statusMutation = useMutation({
    mutationFn: (status: TicketStatusAdminUpdate) => updateTicketStatus(ticketId!, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['support-tickets'] });
      queryClient.invalidateQueries({ queryKey: ['support-ticket', ticketId] });
      setStatusSelect('');
      toast({ title: 'Statut mis à jour', description: 'Le ticket a été mis à jour.' });
    },
    onError: () => {
      toast({
        title: 'Erreur',
        description: 'Impossible de mettre à jour le statut.',
        variant: 'destructive',
      });
    },
  });

  const historySorted = useMemo(() => {
    const h = ticket?.status_history ?? [];
    return [...h].sort(
      (a, b) => new Date(a.changed_at).getTime() - new Date(b.changed_at).getTime(),
    );
  }, [ticket?.status_history]);

  const open = ticketId !== null;

  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <SheetContent className="flex w-full flex-col gap-0 overflow-y-auto sm:max-w-xl">
        {!ticketId ? null : isLoading ? (
          <div className="flex flex-1 items-center justify-center py-16">
            <Loader2 className="h-10 w-10 animate-spin text-muted-foreground" />
          </div>
        ) : isError || !ticket ? (
          <div className="py-8 text-center text-sm text-destructive">
            Impossible de charger ce ticket.
          </div>
        ) : (
          <>
            <SheetHeader className="space-y-3 border-b pb-4 text-left">
              <div className="flex flex-wrap items-center gap-2">
                <SheetTitle className="font-mono text-base">
                  Ticket {truncateId(ticket.id)}
                </SheetTitle>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-left">
                <span className="text-muted-foreground text-sm">
                  Créé le {formatTicketDate(ticket.created_at)}
                </span>
                <Badge className={cn(statusBadgeClass(ticket.status))} variant={statusBadgeVariant(ticket.status)}>
                  {ticket.status}
                </Badge>
                <Badge
                  variant={ticket.urgency === 'critique' ? 'destructive' : 'outline'}
                  className={cn(urgencyBadgeClass(ticket.urgency))}
                >
                  {ticket.urgency}
                </Badge>
              </div>
            </SheetHeader>

            <div className="flex-1 space-y-6 py-6">
              <section>
                <h3 className="mb-2 text-sm font-semibold">Informations</h3>
                <dl className="space-y-2 text-sm">
                  <div>
                    <dt className="text-muted-foreground">Module</dt>
                    <dd>{ticket.module}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Type de demande</dt>
                    <dd>{ticket.request_type}</dd>
                  </div>
                  <div>
                    <dt className="text-muted-foreground">Description</dt>
                    <dd className="whitespace-pre-wrap">{ticket.description}</dd>
                  </div>
                  {ticket.context ? (
                    <div>
                      <dt className="text-muted-foreground">Contexte</dt>
                      <dd className="whitespace-pre-wrap">{ticket.context}</dd>
                    </div>
                  ) : null}
                </dl>
              </section>

              {showEmitter ? (
                <section>
                  <h3 className="mb-2 text-sm font-semibold">Émetteur</h3>
                  <dl className="space-y-2 text-sm">
                    <div>
                      <dt className="text-muted-foreground">Nom</dt>
                      <dd>
                        {emitter
                          ? [emitter.first_name, emitter.last_name].filter(Boolean).join(' ') || '—'
                          : '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">E-mail</dt>
                      <dd>{emitter?.email ?? '—'}</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Entreprise</dt>
                      <dd>{emitterCompanyName}</dd>
                    </div>
                  </dl>
                </section>
              ) : null}

              <section>
                <h3 className="mb-3 text-sm font-semibold">Historique</h3>
                {historySorted.length === 0 ? (
                  <p className="text-muted-foreground text-sm">Aucun historique.</p>
                ) : (
                  <ul className="relative space-y-4 border-l-2 border-muted pl-4">
                    {historySorted.map((item) => (
                      <li key={item.id} className="relative">
                        <span className="absolute -left-[calc(0.5rem+5px)] top-1.5 h-2.5 w-2.5 rounded-full bg-primary" />
                        <p className="text-muted-foreground text-xs">
                          {formatTicketDate(item.changed_at)}
                        </p>
                        <p className="text-sm">
                          <span className="font-medium">{item.new_status}</span>
                          {item.old_status != null ? (
                            <span className="text-muted-foreground">
                              {' '}
                              (depuis {item.old_status})
                            </span>
                          ) : null}
                        </p>
                        <p className="text-muted-foreground font-mono text-xs">
                          Par {truncateId(item.changed_by, 12)}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {isSuperAdmin ? (
                <div className="space-y-3 border-t pt-4">
                  <Label htmlFor="support-ticket-status">Changer le statut</Label>
                  <div className="flex flex-wrap items-center gap-3">
                    <Select
                      value={statusSelect || undefined}
                      onValueChange={(v) => setStatusSelect(v as TicketStatusAdminUpdate)}
                    >
                      <SelectTrigger id="support-ticket-status" className="w-[200px]">
                        <SelectValue placeholder="Choisir un statut" />
                      </SelectTrigger>
                      <SelectContent>
                        {ADMIN_STATUS_OPTIONS.map((o) => (
                          <SelectItem key={o.value} value={o.value}>
                            {o.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Button
                      type="button"
                      disabled={!statusSelect || statusMutation.isPending}
                      onClick={() => {
                        if (statusSelect) statusMutation.mutate(statusSelect);
                      }}
                    >
                      {statusMutation.isPending ? (
                        <>
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          Enregistrement…
                        </>
                      ) : (
                        'Appliquer'
                      )}
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
