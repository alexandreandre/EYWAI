import { useCallback, useEffect, useRef, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2 } from 'lucide-react';

import type { EmployeeForPlanning } from '@/api/planning';
import {
  TEAM_COLORS,
  checkTeamName,
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

export type TeamPanelProps = {
  open: boolean;
  onClose: () => void;
  team?: Team;
  onCreate: (payload: TeamCreatePayload) => Promise<void>;
  onUpdate: (teamId: string, payload: TeamUpdateBody) => Promise<void>;
  employees: EmployeeForPlanning[];
  companyId: string;
};

export function TeamPanel({
  open,
  onClose,
  team,
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
