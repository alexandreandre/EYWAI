-- Plusieurs entretiens par collaborateur et par année civile (ex. annuel + mi-année).
ALTER TABLE public.annual_reviews
  DROP CONSTRAINT IF EXISTS annual_reviews_employee_id_year_key;

CREATE INDEX IF NOT EXISTS idx_annual_reviews_employee_company_year
  ON public.annual_reviews (employee_id, company_id, year);
