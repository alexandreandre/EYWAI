-- Modèles de semaine : équipe et description optionnelles.

ALTER TABLE public.company_week_schedule_templates
    ADD COLUMN IF NOT EXISTS team_id uuid REFERENCES public.teams(id) ON DELETE SET NULL;

ALTER TABLE public.company_week_schedule_templates
    ADD COLUMN IF NOT EXISTS description text;
