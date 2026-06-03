-- Source scraping : Contribution à la Formation Professionnelle (cotisation CFP / cfp).

INSERT INTO public.scraping_sources (
    source_key,
    source_name,
    source_type,
    description,
    target_table,
    target_field,
    primary_url,
    available_scrapers,
    orchestrator_path,
    requires_company_context,
    scraping_frequency,
    is_critical,
    is_active
)
VALUES (
    'CFP',
    'Contribution à la Formation Professionnelle',
    'cotisation',
    'Taux patronal CFP selon effectif (< 11 / 11 et plus)',
    'payroll_config',
    'cotisations.CFP',
    'https://www.urssaf.fr/accueil/employeur/cotisations/liste-cotisations/formation-professionnelle.html',
    '["CFP.py", "CFP_LegiSocial.py", "CFP_AI.py"]'::jsonb,
    'scraping/CFP/orchestrator.py',
    false,
    'manual',
    false,
    true
)
ON CONFLICT (source_key) DO UPDATE SET
    source_name = EXCLUDED.source_name,
    source_type = EXCLUDED.source_type,
    description = EXCLUDED.description,
    target_table = EXCLUDED.target_table,
    target_field = EXCLUDED.target_field,
    primary_url = EXCLUDED.primary_url,
    available_scrapers = EXCLUDED.available_scrapers,
    orchestrator_path = EXCLUDED.orchestrator_path,
    is_critical = EXCLUDED.is_critical,
    is_active = EXCLUDED.is_active,
    updated_at = now();
