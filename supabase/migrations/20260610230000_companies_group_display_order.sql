-- Ordre d'affichage personnalisé des entreprises au sein d'un groupe (page admin).
ALTER TABLE public.companies
  ADD COLUMN IF NOT EXISTS group_display_order integer;

COMMENT ON COLUMN public.companies.group_display_order IS
  'Ordre d''affichage dans le groupe (page admin Entreprises du groupe).';

-- Backfill : ordre alphabétique par groupe existant
WITH ranked AS (
  SELECT id,
         ROW_NUMBER() OVER (
           PARTITION BY group_id ORDER BY company_name
         ) AS rn
  FROM public.companies
  WHERE group_id IS NOT NULL
)
UPDATE public.companies c
SET group_display_order = ranked.rn
FROM ranked
WHERE c.id = ranked.id;
