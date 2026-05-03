-- Remplacements planning : métadonnées sur les shifts
ALTER TABLE public.shifts
ADD COLUMN IF NOT EXISTS is_replacement boolean NOT NULL DEFAULT false,
ADD COLUMN IF NOT EXISTS replacing_employee_id uuid REFERENCES public.employees (id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS replacement_reason text,
ADD COLUMN IF NOT EXISTS original_employee_id uuid REFERENCES public.employees (id) ON DELETE SET NULL;

COMMENT ON COLUMN public.shifts.is_replacement IS 'true si ce shift est un remplacement';
COMMENT ON COLUMN public.shifts.replacing_employee_id IS 'Salarié qui effectue le remplacement (souvent = employee_id)';
COMMENT ON COLUMN public.shifts.original_employee_id IS 'Salarié initialement prévu, remplacé';
COMMENT ON COLUMN public.shifts.replacement_reason IS 'Motif du remplacement';
