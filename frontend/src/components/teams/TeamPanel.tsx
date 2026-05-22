import { useCallback, useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { BarChart2, ChevronRight, Loader2 } from 'lucide-react';

import type { EmployeeForPlanning } from '@/api/planning';
import {
  TEAM_COLORS,
  checkTeamName,
  getTeamDetail,
  type Team,
  type TeamCreatePayload,
  type TeamUpdateBody,
} from '@/api/teams';
import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Sheet,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

const formSchema = z.object({
  name: z
    .string()
    .min(1, 'Le nom est obligatoire.')
    .max(80, '80 caractères maximum.'),
  description: z.string().optional(),
  color: z.string().refine((c) => TEAM_COLORS.includes(c), {
    message: 'Couleur non autorisée.',
  }),
  manager_employee_id: z.string().optional(),
});

type FormValues = z.infer<typeof formSchema>;

function formatTeamDate(iso: string | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleDateString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

function memberLabel(
  first?: string | null,
  last?: string | null,
): string {
  const fn = first?.trim() ?? '';
  const ln = last?.trim() ?? '';
  if (!fn && !ln) return 'Collaborateur';
  const lastUpper = ln ? ln.toUpperCase() : '';
  return [fn, lastUpper].filter(Boolean).join(' ');
}

export type TeamPanelProps = {
  open: boolean;
  onClose: () => void;
  team?: Team;
  focusMembers?: boolean;
  onCreate: (payload: TeamCreatePayload) => Promise<void>;
  onUpdate: (teamId: string, payload: TeamUpdateBody) => Promise<void>;
  employees: EmployeeForPlanning[];
  companyId: string;
};

export function TeamPanel({
  open,
  onClose,
  team,
  focusMembers = false,
  onCreate,
  onUpdate,
  employees,
  companyId,
}: TeamPanelProps) {
  const { toast } = useToast();
  const isEdit = Boolean(team);
  const [submitting, setSubmitting] = useState(false);
  const [nameCheckLoading, setNameCheckLoading] = useState(false);
  const [nameAvailable, setNameAvailable] = useState<boolean | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const membersSectionRef = useRef<HTMLDivElement>(null);

  const detailQuery = useQuery({
    queryKey: ['team-detail', team?.id],
    queryFn: () => getTeamDetail(team!.id),
    enabled: open && Boolean(team?.id),
  });

  const form = useForm<FormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      description: '',
      color: '#6366f1',
      manager_employee_id: '',
    },
  });

  const watchedName = form.watch('name');
  const watchedColor = form.watch('color');

  useEffect(() => {
    if (!open) return;
    form.reset({
      name: team?.name ?? '',
      description: team?.description ?? '',
      color: team?.color && TEAM_COLORS.includes(team.color) ? team.color : '#6366f1',
      manager_employee_id: team?.manager_employee_id ?? '',
    });
    setNameAvailable(null);
  }, [open, team, form]);

  useEffect(() => {
    if (!open || !focusMembers || !isEdit) return;
    const t = setTimeout(() => {
      membersSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 300);
    return () => clearTimeout(t);
  }, [open, focusMembers, isEdit, detailQuery.isSuccess]);

  const runNameCheck = useCallback(
    async (name: string) => {
      const trimmed = name.trim();
      if (!trimmed) {
        setNameAvailable(null);
        setNameCheckLoading(false);
        return;
      }
      setNameCheckLoading(true);
      try {
        const res = await checkTeamName(
          trimmed,
          isEdit ? team?.id : undefined,
        );
        setNameAvailable(res.available);
      } catch {
        setNameAvailable(null);
      } finally {
        setNameCheckLoading(false);
      }
    },
    [isEdit, team?.id],
  );

  useEffect(() => {
    if (!open) return;
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void runNameCheck(watchedName);
    }, 500);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [watchedName, open, runNameCheck]);

  const submitDisabled =
    submitting ||
    !watchedName.trim() ||
    nameAvailable === false ||
    (Boolean(watchedName.trim()) && nameCheckLoading);

  async function onSubmit(values: FormValues) {
    if (!companyId) {
      toast({
        variant: 'destructive',
        title: 'Entreprise requise',
        description: 'Sélectionnez une entreprise active.',
      });
      return;
    }
    setSubmitting(true);
    try {
      const managerId = values.manager_employee_id?.trim();
      if (isEdit && team) {
        await onUpdate(team.id, {
          name: values.name.trim(),
          description: values.description?.trim() || null,
          color: values.color,
          manager_employee_id:
            managerId && managerId.length > 0 ? managerId : null,
        });
      } else {
        await onCreate({
          name: values.name.trim(),
          description: values.description?.trim() || undefined,
          color: values.color,
          manager_employee_id:
            managerId && managerId.length > 0 ? managerId : undefined,
        });
      }
      onClose();
    } catch {
      /* Toast d’erreur géré par le parent (mutateAsync). */
    } finally {
      setSubmitting(false);
    }
  }

  const nameHint = () => {
    const t = watchedName.trim();
    if (!t) return null;
    if (nameCheckLoading) {
      return (
        <p className="text-xs text-muted-foreground flex items-center gap-1">
          <Loader2 className="h-3 w-3 animate-spin" />
          Vérification du nom…
        </p>
      );
    }
    if (nameAvailable === true) {
      return <p className="text-xs text-emerald-600">✓ Disponible</p>;
    }
    if (nameAvailable === false) {
      return <p className="text-xs text-destructive">✗ Ce nom est déjà utilisé</p>;
    }
    return null;
  };

  const members = detailQuery.data?.members ?? [];
  const memberCount = team?.employee_count ?? members.length;

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent className="flex w-full flex-col sm:max-w-md">
        <SheetHeader>
          <SheetTitle>
            {isEdit ? 'Modifier l’équipe' : 'Nouvelle équipe'}
          </SheetTitle>
        </SheetHeader>

        <Form {...form}>
          <form
            onSubmit={form.handleSubmit(onSubmit)}
            className="flex flex-1 flex-col gap-6 overflow-y-auto py-2"
          >
            {isEdit && (
              <div
                ref={membersSectionRef}
                className="rounded-lg border bg-muted/30 p-3 space-y-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-medium">
                    Membres ({memberCount})
                  </h3>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 gap-1 text-xs"
                    asChild
                  >
                    <Link to="/analytics">
                      <BarChart2 className="h-3.5 w-3.5" />
                      Indicateurs
                    </Link>
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Pour affecter un salarié, ouvrez sa fiche Collaborateur.
                </p>
                {detailQuery.isLoading ? (
                  <div className="space-y-2">
                    <Skeleton className="h-8 w-full" />
                    <Skeleton className="h-8 w-full" />
                  </div>
                ) : detailQuery.isError ? (
                  <p className="text-xs text-destructive">
                    Impossible de charger les membres.
                  </p>
                ) : members.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Aucun salarié dans cette équipe.
                  </p>
                ) : (
                  <ul className="max-h-40 space-y-1 overflow-y-auto">
                    {members.map((m) => (
                      <li key={m.id}>
                        <Link
                          to={`/employees/${m.id}`}
                          className="flex items-center justify-between gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-muted"
                          onClick={onClose}
                        >
                          <span>
                            {memberLabel(m.first_name, m.last_name)}
                            {m.job_title ? (
                              <span className="text-muted-foreground">
                                {' '}
                                — {m.job_title}
                              </span>
                            ) : null}
                          </span>
                          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            <FormField
              control={form.control}
              name="name"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Nom</FormLabel>
                  <FormControl>
                    <div
                      className="rounded-md border border-transparent pl-2 transition-colors"
                      style={{
                        borderLeftWidth: 4,
                        borderLeftColor: watchedColor || '#6366f1',
                      }}
                    >
                      <Input
                        placeholder="Nom de l’équipe"
                        maxLength={80}
                        autoComplete="off"
                        {...field}
                      />
                    </div>
                  </FormControl>
                  {nameHint()}
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="description"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Textarea
                      placeholder="Optionnel"
                      rows={3}
                      className="resize-none"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="color"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Couleur</FormLabel>
                  <div className="grid grid-cols-4 gap-2 sm:grid-cols-4">
                    {TEAM_COLORS.map((hex) => (
                      <button
                        key={hex}
                        type="button"
                        title={hex}
                        className={cn(
                          'h-9 w-full rounded-full ring-2 ring-offset-2 ring-offset-background transition',
                          field.value === hex
                            ? 'ring-primary'
                            : 'ring-transparent hover:ring-muted-foreground/30',
                        )}
                        style={{ backgroundColor: hex }}
                        onClick={() => field.onChange(hex)}
                      />
                    ))}
                  </div>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="manager_employee_id"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Responsable</FormLabel>
                  <Select
                    value={field.value && field.value.length > 0 ? field.value : '__none__'}
                    onValueChange={(v) =>
                      field.onChange(v === '__none__' ? '' : v)
                    }
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Aucun responsable" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      <SelectItem value="__none__">Aucun responsable</SelectItem>
                      {employees.map((e) => (
                        <SelectItem key={e.id} value={e.id}>
                          {e.first_name} {e.last_name}
                          {e.job_title ? ` — ${e.job_title}` : ''}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            {isEdit && team?.updated_at ? (
              <p className="text-xs text-muted-foreground">
                Dernière mise à jour : {formatTeamDate(team.updated_at)}
              </p>
            ) : null}

            <SheetFooter className="mt-auto flex-col gap-2 sm:flex-col">
              <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                <Button type="button" variant="outline" onClick={onClose}>
                  Annuler
                </Button>
                <Button type="submit" disabled={submitDisabled}>
                  {submitting && (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                  )}
                  {isEdit ? 'Enregistrer' : 'Créer l’équipe'}
                </Button>
              </div>
            </SheetFooter>
          </form>
        </Form>
      </SheetContent>
    </Sheet>
  );
}
