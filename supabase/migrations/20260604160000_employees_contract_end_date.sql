-- Date de fin de contrat planifiée (CDD, stage, etc.).
-- Distincte de la sortie effective (table employee_exits.last_working_day) :
-- contract_end_date = fin prévue au contrat ; employee_exits = sortie réelle.
-- Consommée par le moteur de paie (précarité CDD, prorata de sortie) via
-- contrat.json -> ContextePaie.date_fin_contrat.

ALTER TABLE public.employees
    ADD COLUMN IF NOT EXISTS contract_end_date date;

COMMENT ON COLUMN public.employees.contract_end_date IS
    'Date de fin de contrat planifiée (CDD/stage). Sortie effective: employee_exits.last_working_day.';
