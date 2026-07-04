-- Pauses multi-types : payées (incluses) vs non payées (déduites au pointage).

ALTER TABLE public.company_punch_shift_slots
    ADD COLUMN IF NOT EXISTS paid_break_minutes integer NOT NULL DEFAULT 0
        CHECK (paid_break_minutes >= 0 AND paid_break_minutes <= 180);

COMMENT ON COLUMN public.company_punch_shift_slots.paid_break_minutes IS
    'Minutes de pauses rémunérées incluses dans le net théorique (non déduites du brut pointé).';

ALTER TABLE public.shift_types
    ADD COLUMN IF NOT EXISTS unpaid_break_minutes integer NOT NULL DEFAULT 0
        CHECK (unpaid_break_minutes >= 0 AND unpaid_break_minutes <= 180);

COMMENT ON COLUMN public.shift_types.unpaid_break_minutes IS
    'Pause repas non rémunérée (informatif planning ; déduction au pointage via créneaux).';

ALTER TABLE public.company_planning_settings
    ADD COLUMN IF NOT EXISTS paid_breaks_included_in_base boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.company_planning_settings.paid_breaks_included_in_base IS
    'Si true, les pauses payées du planning ne génèrent pas de ligne bulletin séparée.';
