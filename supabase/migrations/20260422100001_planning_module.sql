-- Module Planning : référentiels, shifts, statuts semaine/jour, historique, paramètres entreprise.
-- Aligné sur app.modules.planning.infrastructure.repository (upserts / contraintes d'unicité).

CREATE TABLE IF NOT EXISTS public.collective_agreements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    code text NOT NULL,
    label text NOT NULL,
    idcc text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.shift_types (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    collective_agreement_id uuid REFERENCES public.collective_agreements (id) ON DELETE SET NULL,
    code text NOT NULL,
    label text NOT NULL,
    color text,
    default_start time,
    default_end time,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now ()
);

CREATE TABLE IF NOT EXISTS public.shifts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    company_id uuid NOT NULL,
    employee_id uuid NOT NULL,
    shift_type_id uuid REFERENCES public.shift_types (id) ON DELETE SET NULL,
    transverse_category text,
    shift_date date NOT NULL,
    start_time time NOT NULL,
    end_time time NOT NULL,
    post text,
    location text,
    comment_internal text,
    comment_employee text,
    source text NOT NULL DEFAULT 'manual',
    created_by uuid,
    is_locked boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now ()
);

CREATE TABLE IF NOT EXISTS public.planning_week_status (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    company_id uuid NOT NULL,
    week_start date NOT NULL,
    status text NOT NULL DEFAULT 'draft',
    payroll_transmitted boolean NOT NULL DEFAULT false,
    payroll_transmitted_at timestamptz,
    team_view_enabled boolean NOT NULL DEFAULT false,
    locked_at timestamptz,
    locked_by uuid,
    created_at timestamptz NOT NULL DEFAULT now (),
    UNIQUE (company_id, week_start)
);

CREATE TABLE IF NOT EXISTS public.planning_day_status (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    company_id uuid NOT NULL,
    day_date date NOT NULL,
    is_locked boolean NOT NULL DEFAULT false,
    locked_at timestamptz,
    locked_by uuid,
    lock_reason text,
    created_at timestamptz NOT NULL DEFAULT now (),
    UNIQUE (company_id, day_date)
);

CREATE TABLE IF NOT EXISTS public.planning_lock_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    company_id uuid NOT NULL,
    action text NOT NULL,
    target_week_start date,
    target_date date,
    performed_by uuid,
    reason text,
    shifts_count integer,
    total_hours numeric,
    created_at timestamptz NOT NULL DEFAULT now ()
);

CREATE TABLE IF NOT EXISTS public.company_planning_settings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid (),
    company_id uuid NOT NULL,
    collective_agreement_id uuid REFERENCES public.collective_agreements (id) ON DELETE SET NULL,
    team_view_default boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now (),
    updated_at timestamptz NOT NULL DEFAULT now (),
    UNIQUE (company_id)
);
