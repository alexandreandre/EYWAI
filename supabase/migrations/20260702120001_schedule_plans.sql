-- Plans/affectations de calendriers horaires prévisionnels par entreprise.
-- Couche générique qui relie un cycle de modèles (semaine A/B/…), une portée
-- (société / équipe / service / sélection de salariés) et une période, puis
-- alimente employee_schedules.planned_calendar.calendrier_prevu via le moteur
-- de génération. Idempotente.

CREATE TABLE IF NOT EXISTS public.company_schedule_plans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    name text NOT NULL,
    scope_type text NOT NULL DEFAULT 'company',      -- 'company' | 'team' | 'service' | 'employees'
    scope_ref jsonb NOT NULL DEFAULT '{}'::jsonb,     -- {team_id} | {service_id} | {employee_ids:[]}
    template_cycle jsonb NOT NULL DEFAULT '[]'::jsonb, -- liste ordonnée d'ids modèles (alternance)
    cycle_anchor date,                                -- lundi d'ancrage de l'alternance
    start_date date NOT NULL,
    end_date date,                                    -- null = ouvert / année complète
    overwrite_mode text NOT NULL DEFAULT 'preserve_manual',
    status text NOT NULL DEFAULT 'draft',             -- 'draft' | 'applied'
    needs_confirmation boolean NOT NULL DEFAULT false, -- alerte RH (donnée métier à confirmer)
    notes text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_schedule_plans_company_dates
    ON public.company_schedule_plans (company_id, start_date, end_date);

ALTER TABLE public.company_schedule_plans ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS schedule_plans_select ON public.company_schedule_plans;
CREATE POLICY schedule_plans_select ON public.company_schedule_plans
    FOR SELECT USING (true);

DROP POLICY IF EXISTS schedule_plans_write ON public.company_schedule_plans;
CREATE POLICY schedule_plans_write ON public.company_schedule_plans
    FOR ALL USING (true) WITH CHECK (true);
