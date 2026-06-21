-- Comptabilisation pointages paramétrable (grilles horaires, tolérance, HS jour).

CREATE TABLE IF NOT EXISTS public.company_punch_accounting_settings (
    company_id uuid PRIMARY KEY REFERENCES public.companies(id) ON DELETE CASCADE,
    enabled boolean NOT NULL DEFAULT false,
    tolerance_minutes integer NOT NULL DEFAULT 30
        CHECK (tolerance_minutes >= 0 AND tolerance_minutes <= 120),
    default_break_deduct_minutes integer NOT NULL DEFAULT 45
        CHECK (default_break_deduct_minutes >= 0 AND default_break_deduct_minutes <= 180),
    use_last_nonzero_exit boolean NOT NULL DEFAULT true,
    slot_detection text NOT NULL DEFAULT 'shift_code'
        CHECK (slot_detection IN ('shift_code', 'nearest_entry', 'planning_first')),
    within_tolerance_pay_theoretical boolean NOT NULL DEFAULT true,
    require_manager_validation_for_overtime boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.company_punch_accounting_settings IS
    'Règles de comptabilisation des pointages (arrondis, pauses, HS) par entreprise.';

CREATE TABLE IF NOT EXISTS public.company_punch_shift_slots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    code text,
    label text NOT NULL DEFAULT '',
    entry_time time NOT NULL,
    exit_time time NOT NULL,
    theoretical_gross_minutes integer NOT NULL DEFAULT 465
        CHECK (theoretical_gross_minutes > 0 AND theoretical_gross_minutes <= 960),
    break_deduct_minutes integer NOT NULL DEFAULT 45
        CHECK (break_deduct_minutes >= 0 AND break_deduct_minutes <= 180),
    paid_lunch_break boolean NOT NULL DEFAULT false,
    sort_order integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_punch_shift_slots_company
    ON public.company_punch_shift_slots (company_id, sort_order);

COMMENT ON TABLE public.company_punch_shift_slots IS
    'Créneaux horaires théoriques pour la comptabilisation des pointages.';

CREATE TABLE IF NOT EXISTS public.employee_punch_overtime_reviews (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    employee_id uuid NOT NULL REFERENCES public.employees(id) ON DELETE CASCADE,
    work_date date NOT NULL,
    overtime_hours numeric(10, 2) NOT NULL DEFAULT 0
        CHECK (overtime_hours >= 0),
    reason text NOT NULL
        CHECK (reason IN ('early_entry', 'late_exit', 'daily_excess')),
    raw_entry_time time,
    raw_exit_time time,
    applied_slot_id uuid REFERENCES public.company_punch_shift_slots(id) ON DELETE SET NULL,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewed_by uuid,
    review_note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (employee_id, work_date)
);

CREATE INDEX IF NOT EXISTS idx_punch_overtime_reviews_company_period
    ON public.employee_punch_overtime_reviews (company_id, work_date);

CREATE INDEX IF NOT EXISTS idx_punch_overtime_reviews_status
    ON public.employee_punch_overtime_reviews (company_id, status, work_date);

COMMENT ON TABLE public.employee_punch_overtime_reviews IS
    'Validation jour par jour des HS détectées à la comptabilisation pointage.';

ALTER TABLE public.company_punch_accounting_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.company_punch_shift_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.employee_punch_overtime_reviews ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS company_punch_accounting_settings_select ON public.company_punch_accounting_settings;
CREATE POLICY company_punch_accounting_settings_select ON public.company_punch_accounting_settings
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_punch_accounting_settings_write ON public.company_punch_accounting_settings;
CREATE POLICY company_punch_accounting_settings_write ON public.company_punch_accounting_settings
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    )
    WITH CHECK (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );

DROP POLICY IF EXISTS company_punch_shift_slots_select ON public.company_punch_shift_slots;
CREATE POLICY company_punch_shift_slots_select ON public.company_punch_shift_slots
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS company_punch_shift_slots_write ON public.company_punch_shift_slots;
CREATE POLICY company_punch_shift_slots_write ON public.company_punch_shift_slots
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    )
    WITH CHECK (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );

DROP POLICY IF EXISTS employee_punch_overtime_reviews_select ON public.employee_punch_overtime_reviews;
CREATE POLICY employee_punch_overtime_reviews_select ON public.employee_punch_overtime_reviews
    FOR SELECT TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
        )
    );

DROP POLICY IF EXISTS employee_punch_overtime_reviews_write ON public.employee_punch_overtime_reviews;
CREATE POLICY employee_punch_overtime_reviews_write ON public.employee_punch_overtime_reviews
    FOR ALL TO authenticated
    USING (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    )
    WITH CHECK (
        company_id IN (
            SELECT uca.company_id FROM public.user_company_accesses uca
            WHERE uca.user_id = auth.uid()
            AND uca.role IN ('admin', 'rh', 'collaborateur_rh')
        )
    );
