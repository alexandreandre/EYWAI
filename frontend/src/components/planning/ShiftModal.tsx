import { useEffect, useMemo } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import type {
  EmployeeForPlanning,
  Shift,
  ShiftCreatePayload,
  ShiftType,
  ShiftUpdatePayload,
} from '@/api/planning';

const TRANSVERSE_OPTIONS: { code: string; label: string }[] = [
  { code: 'CP', label: 'Congé payé (CP)' },
  { code: 'RTT', label: 'RTT' },
  { code: 'MAL', label: 'Maladie' },
  { code: 'ABS_INJ', label: 'Absence injustifiée' },
  { code: 'FORM', label: 'Formation' },
  { code: 'REP_HEB', label: 'Repos hebdomadaire' },
];

const CATEGORY_PREFIX_TYPE = 'type:';
const CATEGORY_PREFIX_TRNS = 'trns:';

function timeToMinutes(hm: string): number {
  const [h, m] = hm.split(':').map((x) => Number(x));
  return (h || 0) * 60 + (m || 0);
}

function toHms(hm: string): string {
  return hm.length <= 5 ? `${hm}:00` : hm.slice(0, 8);
}

function buildCategoryKey(shift: Shift): string {
  if (shift.shift_type?.id) {
    return `${CATEGORY_PREFIX_TYPE}${shift.shift_type.id}`;
  }
  if (shift.transverse_category) {
    return `${CATEGORY_PREFIX_TRNS}${shift.transverse_category}`;
  }
  return '';
}

function parseCategoryKey(key: string): {
  shift_type_id: string | null;
  transverse_category: string | null;
} {
  if (key.startsWith(CATEGORY_PREFIX_TYPE)) {
    return {
      shift_type_id: key.slice(CATEGORY_PREFIX_TYPE.length),
      transverse_category: null,
    };
  }
  if (key.startsWith(CATEGORY_PREFIX_TRNS)) {
    return {
      shift_type_id: null,
      transverse_category: key.slice(CATEGORY_PREFIX_TRNS.length),
    };
  }
  return { shift_type_id: null, transverse_category: null };
}

function defaultTimesForCategory(
  categoryKey: string,
  shiftTypes: ShiftType[],
): { start: string; end: string } {
  const { shift_type_id } = parseCategoryKey(categoryKey);
  const st = shiftTypes.find((t) => t.id === shift_type_id);
  if (st?.default_start) {
    return {
      start: st.default_start.slice(0, 5),
      end: (st.default_end || '17:00').slice(0, 5),
    };
  }
  return { start: '09:00', end: '17:00' };
}

function createFormSchema(shiftTypes: ShiftType[]) {
  return z
    .object({
      shift_date: z.string().min(1, 'La date est requise'),
      categoryKey: z.string().min(1, 'Choisissez une catégorie'),
      start_time: z
        .string()
        .regex(/^\d{2}:\d{2}$/, 'Format HH:MM'),
      end_time: z
        .string()
        .regex(/^\d{2}:\d{2}$/, 'Format HH:MM'),
      post: z.string().optional(),
      location: z.string().optional(),
      comment_internal: z.string().optional(),
      comment_employee: z.string().optional(),
    })
    .superRefine((data, ctx) => {
      const { shift_type_id } = parseCategoryKey(data.categoryKey);
      const st = shiftTypes.find((t) => t.id === shift_type_id);
      const allowsOvernight = st?.allows_overnight ?? false;
      const a = timeToMinutes(data.start_time);
      const b = timeToMinutes(data.end_time);
      if (!allowsOvernight && b <= a) {
        ctx.addIssue({
          code: 'custom',
          path: ['end_time'],
          message: "L'heure de fin doit être après l'heure de début",
        });
      }
    });
}

type ShiftFormValues = z.infer<ReturnType<typeof createFormSchema>>;

export interface ShiftModalProps {
  mode: 'create' | 'edit';
  open: boolean;
  onClose: () => void;
  onSubmit: (data: ShiftCreatePayload | ShiftUpdatePayload) => void;
  onDelete?: () => void;
  shiftTypes: ShiftType[];
  prefillEmployeeId?: string;
  prefillDate?: string;
  initialData?: Shift;
  employees?: EmployeeForPlanning[];
  isLoading: boolean;
  conflictWarnings?: string[];
}

function defaultFormValues(
  mode: ShiftModalProps['mode'],
  props: Pick<
    ShiftModalProps,
    'prefillEmployeeId' | 'prefillDate' | 'initialData' | 'shiftTypes'
  >
): ShiftFormValues {
  const firstType = props.shiftTypes[0];
  const defaultCategory =
    firstType != null ? `${CATEGORY_PREFIX_TYPE}${firstType.id}` : '';
  const { start, end } = defaultTimesForCategory(defaultCategory, props.shiftTypes);

  if (mode === 'edit' && props.initialData) {
    const s = props.initialData;
    const key = buildCategoryKey(s);
    return {
      shift_date: s.shift_date.slice(0, 10),
      categoryKey: key || defaultCategory,
      start_time: s.start_time.slice(0, 5),
      end_time: s.end_time.slice(0, 5),
      post: s.post ?? '',
      location: s.location ?? '',
      comment_internal: s.comment_internal ?? '',
      comment_employee: s.comment_employee ?? '',
    };
  }

  return {
    shift_date: props.prefillDate?.slice(0, 10) ?? '',
    categoryKey: defaultCategory,
    start_time: start,
    end_time: end,
    post: '',
    location: '',
    comment_internal: '',
    comment_employee: '',
  };
}

export function ShiftModal({
  mode,
  open,
  onClose,
  onSubmit,
  onDelete,
  shiftTypes,
  prefillEmployeeId,
  prefillDate,
  initialData,
  employees,
  isLoading,
  conflictWarnings = [],
}: ShiftModalProps) {
  const shiftTypesKey = useMemo(
    () => shiftTypes.map((t) => t.id).join(','),
    [shiftTypes]
  );

  const formSchema = useMemo(() => createFormSchema(shiftTypes), [shiftTypesKey, shiftTypes]);

  const form = useForm<ShiftFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: defaultFormValues(mode, {
      prefillEmployeeId,
      prefillDate,
      initialData,
      shiftTypes,
    }),
  });

  useEffect(() => {
    if (!open) return;
    form.reset(
      defaultFormValues(mode, {
        prefillEmployeeId,
        prefillDate,
        initialData,
        shiftTypes,
      })
    );
  }, [open, mode, prefillEmployeeId, prefillDate, initialData, shiftTypesKey, form, shiftTypes]);

  const categoryKey = form.watch('categoryKey');
  useEffect(() => {
    if (!open || mode !== 'create') return;
    const { start: s, end: e } = defaultTimesForCategory(categoryKey, shiftTypes);
    form.setValue('start_time', s);
    form.setValue('end_time', e);
  }, [categoryKey, open, mode, shiftTypes, form]);

  const employeeReadonly = Boolean(prefillEmployeeId) || mode === 'edit';

  const employeeLabel = useMemo(() => {
    const id = prefillEmployeeId ?? initialData?.employee_id;
    if (!id) return '';
    const found = employees?.find((e) => e.id === id);
    if (found) return `${found.first_name} ${found.last_name}`;
    if (initialData?.employee_first_name || initialData?.employee_last_name) {
      return `${initialData.employee_first_name ?? ''} ${initialData.employee_last_name ?? ''}`.trim();
    }
    return id;
  }, [prefillEmployeeId, initialData, employees]);

  const handleSubmit = (values: ShiftFormValues) => {
    const { shift_type_id, transverse_category } = parseCategoryKey(values.categoryKey);

    if (mode === 'create') {
      if (!prefillEmployeeId) {
        form.setError('root', {
          message: 'Identifiant salarié manquant (sélectionnez une cellule).',
        });
        return;
      }
      const payload: ShiftCreatePayload = {
        employee_id: prefillEmployeeId,
        shift_date: values.shift_date.slice(0, 10),
        shift_type_id,
        transverse_category,
        start_time: toHms(values.start_time),
        end_time: toHms(values.end_time),
        post: values.post?.trim() || undefined,
        location: values.location?.trim() || undefined,
        comment_internal: values.comment_internal?.trim() || undefined,
        comment_employee: values.comment_employee?.trim() || undefined,
      };
      onSubmit(payload);
      return;
    }

    const payload: ShiftUpdatePayload = {
      start_time: toHms(values.start_time),
      end_time: toHms(values.end_time),
      post: values.post?.trim() ? values.post.trim() : null,
      location: values.location?.trim() ? values.location.trim() : null,
      comment_internal: values.comment_internal?.trim()
        ? values.comment_internal.trim()
        : null,
      comment_employee: values.comment_employee?.trim()
        ? values.comment_employee.trim()
        : null,
      shift_type_id: shift_type_id ?? null,
      transverse_category: transverse_category ?? null,
    };
    onSubmit(payload);
  };

  const title = mode === 'create' ? 'Nouveau shift' : 'Modifier le shift';

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !isLoading) onClose();
      }}
    >
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
            {conflictWarnings.length > 0 ? (
              <div
                className="rounded-md border border-orange-300 bg-orange-50 p-3 text-sm text-orange-950 dark:border-orange-800 dark:bg-orange-950/40 dark:text-orange-100"
                role="status"
              >
                <p className="font-medium">Avertissements</p>
                <ul className="mt-2 list-inside list-disc space-y-1">
                  {conflictWarnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {form.formState.errors.root?.message ? (
              <p className="text-sm text-destructive">{form.formState.errors.root.message}</p>
            ) : null}

            <div className="space-y-2">
              <Label>Salarié</Label>
              <Input
                value={employeeLabel}
                readOnly={employeeReadonly}
                className={employeeReadonly ? 'bg-muted' : undefined}
                placeholder={mode === 'create' && !prefillEmployeeId ? 'Sélectionnez une cellule' : undefined}
              />
            </div>

            <FormField
              control={form.control}
              name="shift_date"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Date</FormLabel>
                  <FormControl>
                    <Input
                      type="date"
                      {...field}
                      disabled={mode === 'edit' || isLoading}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="categoryKey"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Catégorie</FormLabel>
                  <Select
                    value={field.value}
                    onValueChange={field.onChange}
                    disabled={isLoading}
                  >
                    <FormControl>
                      <SelectTrigger>
                        <SelectValue placeholder="Choisir…" />
                      </SelectTrigger>
                    </FormControl>
                    <SelectContent>
                      {shiftTypes.map((t) => (
                        <SelectItem key={t.id} value={`${CATEGORY_PREFIX_TYPE}${t.id}`}>
                          <span className="flex items-center gap-2">
                            <span
                              className="inline-block h-2.5 w-2.5 shrink-0 rounded-full ring-1 ring-black/10"
                              style={{ backgroundColor: t.color || '#607D8B' }}
                              aria-hidden
                            />
                            {t.label}
                          </span>
                        </SelectItem>
                      ))}
                      <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
                        Autre (transverse)
                      </div>
                      {TRANSVERSE_OPTIONS.map((o) => (
                        <SelectItem key={o.code} value={`${CATEGORY_PREFIX_TRNS}${o.code}`}>
                          <span className="flex items-center gap-2">
                            <span
                              className="inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-slate-400 ring-1 ring-black/10"
                              aria-hidden
                            />
                            {o.label}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <FormMessage />
                </FormItem>
              )}
            />

            <div className="grid grid-cols-2 gap-3">
              <FormField
                control={form.control}
                name="start_time"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Heure début</FormLabel>
                    <FormControl>
                      <Input type="time" step={60} {...field} disabled={isLoading} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="end_time"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Heure fin</FormLabel>
                    <FormControl>
                      <Input type="time" step={60} {...field} disabled={isLoading} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="post"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Poste</FormLabel>
                  <FormControl>
                    <Input {...field} disabled={isLoading} placeholder="Optionnel" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="location"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Lieu</FormLabel>
                  <FormControl>
                    <Input {...field} disabled={isLoading} placeholder="Optionnel" />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="comment_internal"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Commentaire RH</FormLabel>
                  <FormControl>
                    <Textarea
                      {...field}
                      disabled={isLoading}
                      rows={3}
                      placeholder="Non visible par le salarié"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="comment_employee"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Commentaire salarié</FormLabel>
                  <FormControl>
                    <Textarea
                      {...field}
                      disabled={isLoading}
                      rows={3}
                      placeholder="Visible par le salarié"
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />

            <DialogFooter className="flex-col gap-2 sm:flex-row sm:justify-end">
              {mode === 'edit' ? (
                <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-between">
                  <Button
                    type="button"
                    variant="destructive"
                    disabled={isLoading || !onDelete}
                    onClick={() => onDelete?.()}
                  >
                    Supprimer
                  </Button>
                  <div className="flex flex-col-reverse gap-2 sm:flex-row">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={isLoading}
                      onClick={() => !isLoading && onClose()}
                    >
                      Annuler
                    </Button>
                    <Button type="submit" disabled={isLoading}>
                      {isLoading ? (
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                      ) : null}
                      Enregistrer
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex w-full justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={isLoading}
                    onClick={() => !isLoading && onClose()}
                  >
                    Annuler
                  </Button>
                  <Button type="submit" disabled={isLoading}>
                    {isLoading ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                    ) : null}
                    Créer
                  </Button>
                </div>
              )}
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
