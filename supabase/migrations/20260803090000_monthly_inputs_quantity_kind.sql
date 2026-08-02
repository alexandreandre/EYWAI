-- Saisies mensuelles : distinguer une ligne ajustée à la main d'une ligne
-- générée, et lever l'ambiguïté de payroll_quantity (nombre vs valeur unitaire).
--
-- payroll_quantity porte aujourd'hui deux conventions inverses selon le
-- libellé : 62 lignes « Paniers Jours non soumis » (Mont Blanc Composite) y
-- stockent la valeur unitaire (7,5), 52 autres lignes y stockent le nombre
-- d'unités. Le moteur divise sans distinction, d'où des valeurs unitaires
-- fausses (22 € au lieu de 7,50 €).
alter table public.monthly_inputs
  add column if not exists manual_override boolean not null default false,
  add column if not exists quantity_kind text;

comment on column public.monthly_inputs.manual_override is
  'True si la ligne a été créée ou corrigée à la main : la génération mensuelle ne doit plus l''écraser.';

comment on column public.monthly_inputs.quantity_kind is
  'Sémantique de payroll_quantity : ''count'' = nombre d''unités, ''unit_value'' = valeur unitaire en euros. NULL = indéterminé.';

alter table public.monthly_inputs
  drop constraint if exists monthly_inputs_quantity_kind_check;

alter table public.monthly_inputs
  add constraint monthly_inputs_quantity_kind_check
  check (quantity_kind is null or quantity_kind in ('count', 'unit_value'));
